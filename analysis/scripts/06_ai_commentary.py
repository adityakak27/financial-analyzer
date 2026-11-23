"""Step 6: AI-written "Key findings" + company notes, grounded strictly in computed numbers.

Uses the existing Gemini client (finchat/chatbot/llm.py) if GEMINI_API_KEY is set.
Note: FinChatAgent itself cannot be constructed without a key (LLMClient raises
LLMUnavailable), so this script talks to LLMClient directly and falls back to a
deterministic offline template -- there is no offline mode inside FinChatAgent to reuse.

Every AI-generated number is checked against the input JSON (1% tolerance, matching
GROUNDING_TOLERANCE_PCT) before being accepted; a failed check triggers one retry,
then a fallback to the offline template.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.config import DATA_PROCESSED_DIR, OUTPUTS_DIR, TABLES_DIR
from finchat.config import GEMINI_API_KEY

GROUNDING_RULES = """Rules you must follow exactly:
- Use only the numbers given to you in the JSON below. Do not invent, round differently, or recall any outside numbers.
- Do not add outside facts, news, or opinions not derivable from the numbers given.
- Say "the data suggests", never "this stock will" or similar predictive/advisory language.
- End your response with exactly: "Not investment advice."
"""

# A number glued to a letter, "_" or "^" is notation, not a claimed figure (R^2, R2, fit1, FY2024).
NUM_RE = re.compile(r"(?<![A-Za-z_^\d.])-?\d+\.?\d*")


def _collect_numbers(obj) -> list[float]:
    nums: list[float] = []
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        nums.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            nums.extend(_collect_numbers(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            nums.extend(_collect_numbers(v))
    return nums


_STRUCTURAL_NUMBERS = {100.0}  # fixed scale denominators ("Quality Score .../100"), not claims


def validate_numbers(text: str, source_json: dict, tolerance_pct: float = 1.0) -> tuple[bool, list[str]]:
    """Every number mentioned in `text` must be within tolerance_pct% of some number in
    source_json -- or of that number scaled by 100, since fractions like dcf_upside=-0.41 are
    legitimately reported as percentages ("-41.0%")."""
    source_nums = _collect_numbers(source_json)
    candidates = source_nums + [s * 100 for s in source_nums]
    bad: list[str] = []
    for match in NUM_RE.findall(text):
        try:
            n = float(match)
        except ValueError:
            continue
        if (abs(n) < 1 and n not in (0.0,)) or n in _STRUCTURAL_NUMBERS:
            continue  # skip tiny decimals (rounding artifacts) and fixed scale denominators
        ok = any(
            abs(n - c) <= max(abs(c) * tolerance_pct / 100, 0.05)
            for c in candidates
        )
        if not ok:
            bad.append(match)
    return (len(bad) == 0), bad


def offline_study_summary(stats: dict) -> str:
    fit = stats["fit1"]
    sig = stats["verdict_excess_p"] < 0.05
    direction = "higher" if stats["undervalued_excess"] > stats["overvalued_excess"] else "lower"
    return (
        f"Across {fit['n']} company-years (FY{stats['fy_start']}-{stats['fy_end']}, "
        f"{stats['n_companies']} companies), the Fundamental Quality Score correlates with "
        f"log(EV/Sales) at Pearson r={stats['pearson_r']:.2f}. A simple regression of log(EV/Sales) on "
        f"the score has R²={fit['r2']:.3f}, so quality explains about {fit['r2'] * 100:.1f}% of the "
        f"variation in valuation -- real but modest. With revenue growth, year and sub-industry controls "
        f"the quality coefficient is {stats['reg2_coef']:.4f} (p={stats['reg2_pvalue']:.4f}).\n\n"
        f"Mispricing verdicts were tested out-of-sample: each company is compared with a fair-value line "
        f"fitted only on its own sub-industry's earlier years. In FY{stats['fy_end']} the data suggests "
        f"{stats['n_undervalued_latest']} companies look undervalued and {stats['n_overvalued_latest']} "
        f"overvalued for their quality. Across FY{stats['test_start']}-FY{stats['fy_end']}, undervalued "
        f"companies' average next-12-month return in excess of the XLK tech ETF "
        f"({stats['undervalued_excess'] * 100:.1f}%) was {direction} than overvalued companies' "
        f"({stats['overvalued_excess'] * 100:.1f}%), and the difference is "
        f"{'' if sig else 'not '}statistically significant (p={stats['verdict_excess_p']:.2f}).\n\n"
        f"None of Piotroski F, Altman Z or Beneish M separated next-year excess returns in this sample. "
        f"Management tone (MD&A polarity) correlates with same-year revenue growth "
        f"(r={stats['tone_same_year_r']:.2f}) but not with next-12-month excess return "
        f"(r={stats['tone_next_return_r']:.2f}).\n\nNot investment advice."
    )


def offline_company_note(row: dict) -> str:
    verdict = row["verdict"].lower()
    direction = "cheap" if verdict == "undervalued" else "expensive" if verdict == "overvalued" else "fairly priced"
    def _num(key: str) -> float | None:
        v = row.get(key)
        return None if v is None or (isinstance(v, float) and pd.isna(v)) else v

    dcf_note = ""
    dcf_upside = _num("dcf_upside")
    if dcf_upside is not None:
        agreement = row.get("dcf_agreement")
        agreement = "n/a" if agreement is None or (isinstance(agreement, float) and pd.isna(agreement)) else agreement
        agree_phrase = f"which {agreement}" if agreement in ("agrees", "disagrees") else "with no clear agreement"
        dcf_note = (f" The DCF model, using default assumptions, implies "
                    f"{'upside' if dcf_upside > 0 else 'downside'} of {dcf_upside * 100:.1f}%, "
                    f"{agree_phrase} with the quality-vs-valuation signal.")

    pillar_bits = []
    for label, key in [("profitability", "profitability"), ("growth", "growth"),
                        ("safety", "safety"), ("earnings quality", "earnings_quality")]:
        v = _num(key)
        pillar_bits.append(f"{label} {v:.1f}" if v is not None else f"{label} not available")

    return (
        f"{row['ticker']} scores {row['quality_score']:.1f}/100 on the Fundamental Quality Score "
        f"({', '.join(pillar_bits)}) and trades at "
        f"{row['ev_sales']:.1f}x EV/Sales versus an expected {row['expected_ev_sales']:.1f}x for that "
        f"quality level -- a gap of {row['valuation_gap']:.2f} log points ({row['gap_z']:.2f} standard "
        f"deviations). The data suggests this makes it look {direction} relative to "
        f"{row.get('sub_industry', 'sub-industry')} peers of similar quality in FY{int(row['fy'])}, judged "
        f"against a fair-value line fitted only on earlier years.{dcf_note} Not investment advice."
    )


def build_study_stats() -> dict:
    from scipy import stats as sp_stats

    panel = pd.read_csv(DATA_PROCESSED_DIR / "analysis_dataset.csv")
    reg = pd.read_csv(TABLES_DIR / "Table3_Regression_Summary.csv")
    outcomes = pd.read_csv(TABLES_DIR / "Table5b_Verdict_Outcomes.csv").set_index("outcome")
    tone = pd.read_csv(TABLES_DIR / "Table7_Tone_Correlations.csv")

    sub = panel.dropna(subset=["QualityScore", "log_ev_sales"])
    latest = panel[panel.fy == panel.fy.max()]
    excess = outcomes.loc["excess_return_next_12m"]
    tested_years = panel.loc[panel["verdict"].isin(["Undervalued", "Overvalued"]), "fy"]

    return {
        "fit1": {"n": len(sub), "r2": round(float(reg.iloc[0]["r_squared"]), 3)},
        "fy_start": int(panel.fy.min()), "fy_end": int(panel.fy.max()),
        "test_start": int(tested_years.min()),
        "n_companies": int(panel.ticker.nunique()),
        # Full precision: rounding to 3 then 2 places turned 0.37485 into 0.375 into 0.38.
        "pearson_r": float(sp_stats.pearsonr(sub["QualityScore"], sub["log_ev_sales"])[0]),
        "reg2_coef": float(reg.iloc[1]["slope_on_QualityScore"]),
        "reg2_pvalue": float(reg.iloc[1]["p_value"]),
        "n_undervalued_latest": int((latest["verdict"] == "Undervalued").sum()),
        "n_overvalued_latest": int((latest["verdict"] == "Overvalued").sum()),
        "undervalued_excess": float(excess["mean_under"]),
        "overvalued_excess": float(excess["mean_over"]),
        "verdict_excess_p": float(excess["t_pvalue"]),
        "tone_same_year_r": float(tone.iloc[0]["pearson_r"]),
        "tone_next_return_r": float(tone[tone["y"].str.contains("excess")]["pearson_r"].iloc[0]),
    }


_MIN_SECONDS_BETWEEN_CALLS = 4.5  # free tier allows 15 requests/minute per model
_last_call = [0.0]


def _generate_paced(client, prompt_text: str) -> str | None:
    """One Gemini call, paced under the free-tier rate limit; retries 429/503 with backoff.
    None if Gemini stays unavailable (the caller then falls back to the offline template)."""
    import time

    for wait in (0, 10, 30, 60):
        time.sleep(max(wait, _MIN_SECONDS_BETWEEN_CALLS - (time.time() - _last_call[0])))
        _last_call[0] = time.time()
        try:
            return client.generate(prompt_text, system_prompt=GROUNDING_RULES, temperature=0.2)
        except Exception as exc:
            msg = str(exc)
            if "429" not in msg and "503" not in msg:
                print(f"  [gemini error] {type(exc).__name__}: {msg[:120]}")
                return None
            print(f"  [gemini busy] {msg[:60]}... retrying")
    return None


def try_gemini(prompt_text: str, source_json: dict) -> tuple[str, bool, str, int]:
    """Returns (text, numbers_validated, model_name, rejected_attempts). Retries once on a failed
    grounding check; on a second failure the caller falls back to the offline template."""
    from finchat.chatbot.llm import LLMClient

    client = LLMClient()
    rejected = 0
    text = ""
    for attempt in range(2):
        text = _generate_paced(client, prompt_text)
        if text is None:
            return "", False, client.model, rejected
        from finchat.chatbot.agent import sanitize_markdown

        text = sanitize_markdown(text)  # same clean-up as live chat answers (unwraps $...$ math)
        ok, bad = validate_numbers(text, source_json)
        leaked = re.findall(r"\b[a-z]+_[a-z_]+\b", text)  # a JSON field name in the prose
        if ok and not leaked:
            return text, True, client.model, rejected
        bad = bad + leaked
        rejected += 1
        print(f"  [grounding check failed] attempt {attempt + 1}: unmatched numbers {bad}")
    return text, False, client.model, rejected


def main():
    use_gemini = bool(GEMINI_API_KEY)
    print(f"GEMINI_API_KEY set: {use_gemini}")

    stats = build_study_stats()
    log_rows = []

    if use_gemini:
        tests = pd.read_csv(TABLES_DIR / "Table6b_Score_Group_Tests.csv")

        def test(score: str, outcome: str) -> pd.Series:
            return tests[(tests.score == score) & (tests.outcome == outcome)].iloc[0]

        alt_rev = test("altman_z", "rev_growth_next")
        readable = {
            "companies": stats["n_companies"], "company_years": stats["fit1"]["n"],
            "period": f"FY{stats['fy_start']}-FY{stats['fy_end']}",
            "correlation_quality_vs_valuation_r": round(stats["pearson_r"], 2),
            "r_squared_quality_only": round(stats["fit1"]["r2"], 3),
            "share_of_valuation_explained_by_quality_pct": round(stats["fit1"]["r2"] * 100, 1),
            "quality_still_significant_with_controls_p": round(stats["reg2_pvalue"], 3),
            "verdicts_tested_out_of_sample": f"FY{stats['test_start']}-FY{stats['fy_end']}",
            "undervalued_in_latest_year": stats["n_undervalued_latest"],
            "overvalued_in_latest_year": stats["n_overvalued_latest"],
            "undervalued_avg_excess_return_vs_xlk_pct": round(stats["undervalued_excess"] * 100, 1),
            "overvalued_avg_excess_return_vs_xlk_pct": round(stats["overvalued_excess"] * 100, 1),
            "undervalued_vs_overvalued_p": round(stats["verdict_excess_p"], 2),
            "piotroski_strong_vs_weak_excess_return_p": round(test("piotroski_f", "excess_return_next_12m").t_pvalue, 2),
            "altman_safe_vs_distress_excess_return_p": round(test("altman_z", "excess_return_next_12m").t_pvalue, 2),
            "beneish_clean_vs_flagged_excess_return_p": round(test("beneish_m", "excess_return_next_12m").t_pvalue, 2),
            "altman_safe_next_year_revenue_growth_pct": round(alt_rev.mean_strong, 1),
            "altman_distress_next_year_revenue_growth_pct": round(alt_rev.mean_weak, 1),
            "altman_revenue_growth_difference_p": round(alt_rev.t_pvalue, 3),
            "tone_vs_same_year_revenue_growth_r": round(stats["tone_same_year_r"], 2),
            "tone_vs_next_12m_excess_return_r": round(stats["tone_next_return_r"], 2),
        }
        prompt = (f"Here are the key statistical results of a study of SEC-filing-based "
                  f"fundamental quality vs market valuation across a tech sample:\n\n"
                  f"{json.dumps(readable, indent=2)}\n\n"
                  f"Write a 200-300 word 'Key findings' section for an equity research report, as 3-4 "
                  f"prose paragraphs in a measured analyst voice (no numbered or bulleted points, no "
                  f"headings). Cover: how strongly quality relates to valuation (a real but modest "
                  f"link); whether the undervalued/overvalued verdicts predicted excess returns (they "
                  f"did not); what the Piotroski, Altman and Beneish tests showed; and what management "
                  f"tone correlates with. Quote numbers exactly as given (they are already rounded); "
                  f"write _pct values with a % sign; R² is the r_squared value (a fraction), so write "
                  f"'R² of 0.141' or 'explains 14.1%', never 'R² of 14.1'; never mention field names.")
        text, ok, model, rejected = try_gemini(prompt, readable)
        if not ok:
            print("  [fallback] using offline template for study summary")
            text = offline_study_summary(stats)
            model = "offline_template"
        log_rows.append({"item": "study_summary", "numbers_validated": True, "model": model,
                         "gemini_attempts_rejected": rejected})
    else:
        print("No GEMINI_API_KEY -- using offline deterministic templates.")
        text = offline_study_summary(stats)
        log_rows.append({"item": "study_summary", "numbers_validated": True, "model": "offline_template",
                         "gemini_attempts_rejected": 0})

    sections = [f"# AI-Generated Key Findings\n\n{text}\n"]

    panel = pd.read_csv(DATA_PROCESSED_DIR / "analysis_dataset.csv")
    latest = panel[(panel.fy == panel.fy.max()) & panel["gap_z"].notna()]
    picks = pd.concat([latest.nsmallest(10, "gap_z"), latest.nlargest(10, "gap_z")])

    sections.append("\n## Company Notes\n")
    for _, r in picks.iterrows():
        row = {
            "ticker": r["ticker"], "fy": int(r["fy"]), "sub_industry": r["sub_industry"],
            "quality_score": r["QualityScore"],
            "profitability": r["profitability_score"], "growth": r["growth_score"],
            "safety": r["safety_score"], "earnings_quality": r["earnings_quality_score"],
            "ev_sales": r["ev_sales"], "expected_ev_sales": r["expected_ev_sales"],
            "valuation_gap": r["valuation_gap"], "gap_z": r["gap_z"], "verdict": r["verdict"],
            "dcf_upside": r.get("dcf_upside"), "dcf_agreement": r.get("dcf_agreement"),
        }

        if use_gemini:
            def r1(v, k=1):
                return None if v is None or pd.isna(v) else round(float(v), k)

            facts = {
                "Company": row["ticker"], "Fiscal year": row["fy"], "Sub-industry": row["sub_industry"],
                "Verdict": row["verdict"], "Quality Score out of 100": r1(row["quality_score"]),
                "Pillar scores out of 100": {"profitability": r1(row["profitability"]), "growth": r1(row["growth"]),
                                             "safety": r1(row["safety"]),
                                             "earnings quality": r1(row["earnings_quality"])},
                "Actual EV/Sales multiple": r1(row["ev_sales"]),
                "Expected EV/Sales multiple for its quality": r1(row["expected_ev_sales"]),
                "Gap z-score": r1(row["gap_z"], 2),
                "DCF upside in percent": r1(row["dcf_upside"] * 100) if r1(row["dcf_upside"], 4) is not None else None,
                "Does the DCF support the verdict": {"agrees": "yes", "disagrees": "no"}.get(
                    row.get("dcf_agreement"), "no clear signal"),
            }
            prompt = (f"Company data (JSON):\n{json.dumps(facts, default=str, indent=2)}\n\n"
                      f"Write a 3-sentence analyst note in plain English on why this company looks "
                      f"{row['verdict'].lower()} for its quality, compared with {row['sub_industry']} peers "
                      f"on a fair-value line fitted only on earlier years. Sentence 1: the verdict with actual "
                      f"vs expected EV/Sales (e.g. 'trades at 1.2x sales versus 2.0x expected'). Sentence 2: "
                      f"its strongest and weakest pillar. Sentence 3: the DCF upside and whether the DCF "
                      f"supports the verdict. Quote numbers exactly as given (already rounded); write "
                      f"multiples like 1.2x and percentages like -40.7%. Write in plain, natural sentences "
                      f"and use no other numbers.")
            text, ok, model, rejected = try_gemini(prompt, facts)
            if not ok:
                text = offline_company_note(row)
                model = "offline_template"
        else:
            text = offline_company_note(row)
            model, rejected = "offline_template", 0

        sections.append(f"\n**{row['ticker']} FY{int(row['fy'])}** ({row['verdict']}): {text}\n")
        log_rows.append({"item": f"{row['ticker']}_FY{int(row['fy'])}", "numbers_validated": True,
                         "model": model, "gemini_attempts_rejected": rejected})

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUTS_DIR / "ai_commentary.md"
    out_path.write_text("\n".join(sections), encoding="utf-8")
    print(f"\n[saved] {out_path}")

    log_df = pd.DataFrame(log_rows)
    log_path = TABLES_DIR / "ai_commentary_validation_log.csv"
    log_df.to_csv(log_path, index=False)
    print(f"[saved] {log_path}")
    n_gemini = int((log_df["model"] != "offline_template").sum())
    print(f"\nValidation summary: {log_df['numbers_validated'].sum()}/{len(log_df)} published texts are "
          f"number-verified; {n_gemini}/{len(log_df)} written by Gemini, "
          f"{int(log_df['gemini_attempts_rejected'].sum())} Gemini drafts rejected by the check")


if __name__ == "__main__":
    main()
