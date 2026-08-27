# Evaluation Report - Conversational Fundamental Analyst

_Generated: 2026-08-24 15:04:20_

## Grounding accuracy (H1, H2)

| System | N | Accuracy | Ratio acc. | Score acc. |
|---|---|---|---|---|
| naive_rag | 40 | 7.5% | 0.0% | 15.0% |
| hybrid_offline | 40 | 100.0% | 100.0% | 100.0% |

### Failure cases (most recent hybrid run)

- none in this run

## Multi-turn context retention (H4)

- Steps passed: 12/12 (100.0%)

## Analytical consistency & guardrails (H3)

- Stance consistent with underlying scores: 100.0% of 5 questions
- Required numbers explicitly cited: 100.0%
- Advice guardrail respected: 100.0% of 3 probes
- Qualitative answers grounded in correct filing text: 100.0% of 5 questions

## Limitations

- Hand-built evaluation set (small N); results are indicative, not statistically definitive.
- Offline (no-LLM) baseline uses extractive heuristics; the cleanest H1 comparison requires an LLM API key so both arms use generation.
- Peer percentiles compare fiscal-year labels across companies with different FY end months.
- Beneish DEPI uses a depreciation-rate proxy from available XBRL tags.