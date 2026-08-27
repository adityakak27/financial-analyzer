# Conversational Fundamental Analyst (ip-sem7)

A retrieval-grounded, tool-calling chatbot that has ingested and analyzed a set of
companies' SEC 10-K filings — and that you can interrogate conversationally about
ratios, DuPont decomposition, Altman Z / Piotroski F / Beneish M scores, trends,
peer comparisons, and disclosed risks. Every numeric claim is served by an exact
lookup against a structured database; every qualitative claim is traceable to a
filing passage.

**Research question:** *Can a hybrid (structured-lookup + retrieval) design answer
fundamental-analysis questions as accurately as reading the underlying analysis,
while remaining numerically reliable across multi-turn conversations?*

---

## Architecture

```
Layer 1 - Financial Analysis Engine ("knowledge base")
  SEC EDGAR XBRL company facts ──> normalized statements (SQLite)
      ──> ratios, DuPont(3-step), valuation multiples
      ──> Altman Z (1968), Piotroski F (2000), Beneish M (1999)
      ──> sector peer percentiles
  10-K HTML ──> Item 7 (MD&A) / Item 1A (Risk Factors) extraction
      ──> chunking + TF-IDF index   (text ONLY - never used for numbers)
      ──> Loughran-McDonald-style sentiment + red-flag tagging

Layer 2 - Conversational Interface
  question ──> entity/year resolution (conversation state)
           ──> intent routing: factual | comparative | qualitative | analytical | advice-probe
           ──> LLM tool-calling loop (OpenAI-compatible)  OR  deterministic offline engine
           ──> answer + citations + full tool-call provenance
```

The design thesis (H1): **numbers must be served from structured data via exact
lookup (`get_ratio(company, metric, year)`), never retrieved via vector similarity
over filing text.** The evaluation suite measures exactly that.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # optional: add OPENAI_API_KEY for LLM mode

# 1) collect + analyze + index (smoke-test with 5 tickers; omit names for all 19)
python -m finchat collect AAPL MSFT NVDA ADBE INTC
python -m finchat analyze                     # add --market-data if yfinance installed
python -m finchat index-text AAPL MSFT NVDA ADBE INTC

# 2) talk to it
python -m finchat chat                        # terminal REPL (--offline forces deterministic mode)
streamlit run app/streamlit_app.py            # web UI

# 3) evaluate
python -m finchat build-eval                  # builds data/eval/*.json with verified ground truth
python -m finchat eval-grounding              # H1/H2: hybrid system accuracy
python -m finchat eval-grounding --system naive_rag   # H1 baseline: same questions, no tools
python -m finchat eval-multiturn              # H4: context retention across turns
python -m finchat eval-consistency            # H3: stance-vs-scores + advice guardrail + retrieval grounding
python -m finchat report                      # aggregates eval_results/ -> summary_report.md
python -m finchat demo --offline              # sample transcripts -> eval_results/demo_transcript.md
```

Without an API key everything still runs: the agent uses its deterministic offline
engine (tool lookups + extractive retrieval answers). With `OPENAI_API_KEY` set the
same tools are exposed to an LLM via function-calling under a strict no-hallucination,
no-advice system prompt.

## Repository layout

```
finchat/
  config.py               universe (19 IT firms, FY2018-2024), settings, system prompt
  db.py                   SQLite schema (statements/ratios/scores/peer_ranks/filings/chunks/textstats)
  collect/                EDGAR client, XBRL tag mapping -> normalized statements, 10-K text pipeline
  engine/                 ratio math, DuPont, Altman/Piotroski/Beneish, peer percentiles, valuation
  nlp/                    section extraction (multi-strategy), LM-style sentiment, red-flag regexes, TF-IDF retriever
  chatbot/                tools (+JSON schemas), intent router, conversation state, LLM client, agent
  evaluation/             eval-set builder, grounding runner, naive-RAG baseline, multiturn & consistency runners, report
app/streamlit_app.py      chat UI with citations and tool-call inspectors
tests/                    27 unit/integration tests incl. hand-computed Altman/Piotroski/Beneish fixtures
data/eval/                generated question sets with ground truth
eval_results/             run artifacts + summary_report.md + demo_transcript.md
```

## Evaluation design (maps to hypotheses)

| Suite | Hypothesis | Method |
|---|---|---|
| `grounding_qa.json` (40 Q) | H2 | Factual questions whose ground truth is read directly from the computed database; answer checked numerically within tolerance |
| naive-RAG arm | H1 | Identical questions answered from retrieved filing text with **no tool access**; accuracy gap isolates the value of structured lookup |
| `analytical_rubric.json` | H3 | Expected stance derived independently from stored scores; checks whether the model's stated conclusion contradicts its own data, and whether required numbers are cited |
| `guardrail_qa.json` | scope | "Should I invest...?" probes must be declined |
| `multiturn_scripts.json` | H4 | Scripted 4-turn conversations with pronoun/relative-year follow-ups; checker inspects tool-trace ticker/year against expectations |

Latest smoke-run results on real EDGAR data (5 companies, FY2018-2024):
hybrid grounding **100%**, naive-RAG baseline **7.5%**, multi-turn retention **12/12**,
stance consistency **100%**, guardrail **100%**. See `eval_results/summary_report.md`.

## Methodology notes / honest limitations

- Fiscal-year labels use the period-end calendar year (matches universe convention);
  peer percentiles therefore compare across slightly different FY end months.
- Altman X4 falls back to book equity when no market cap is available (flagged in
  `scores.components_json`); this drags asset-light giants like MSFT toward the grey zone.
- Beneish DEPI uses a depreciation-rate proxy; missing inputs are reported per score,
  not silently skipped.
- Sentiment uses the in-repo compact lexicon by default; point `LM_LEXICON_PATH` at
  the official Loughran-McDonald CSV for the full dictionary.
- The offline naive-RAG baseline is extractive; with an LLM key both arms generate,
  which is the cleanest H1 comparison.
- The evaluation set is hand-built/small-N by design (course project scope); results
  are indicative, not statistically definitive.
- Not investment advice; out of scope by construction and tested via guardrail probes.

## Tests

```bash
python -m pytest tests/ -q     # 27 tests: ratio math, score models vs hand-computed values,
                               # section extraction, tools, state resolution, offline agent behavior
```
