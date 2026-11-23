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
python -m finchat index-text AAPL MSFT NVDA ADBE INTC   # also records each 10-K's filing date
python -m finchat prices                      # caches point-in-time prices + the XLK benchmark (needs yfinance)
python -m finchat analyze --market-data       # ratios/scores using the price ON each filing date
python -m finchat mispricing                  # builds the Mispricing Radar tables (page, tools, badge)

# Order matters: `analyze --market-data` reads cached prices for each fiscal year's filing date.
# Run before `prices`, it falls back to book equity for Altman Z (never to today's market cap).
# The Mispricing Radar study itself lives in analysis/: run analysis/scripts/00..08 in order.

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
app/streamlit_app.py      original Streamlit chat UI (still works standalone)
backend/                  FastAPI web API wrapping the same finchat engine (see below)
frontend/                 React + TypeScript web client that talks to backend/ (see below)
tests/                    27 unit/integration tests incl. hand-computed Altman/Piotroski/Beneish fixtures
data/eval/                generated question sets with ground truth
eval_results/             run artifacts + summary_report.md + demo_transcript.md
```

## Web app (React frontend + FastAPI backend)

A standalone, non-Streamlit web client. The backend is a thin FastAPI layer over the
exact same `finchat` tool functions used by the chatbot (no duplicated logic); the
frontend is a Vite + React + TypeScript SPA with a chat view, company dashboard,
head-to-head comparison, DCF valuation, the 4-agent research report, and filings search.

```bash
# Terminal 1 - backend (http://localhost:8000)
pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --port 8000

# Terminal 2 - frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

The frontend reads `VITE_API_BASE_URL` (defaults to `http://localhost:8000`, see
`frontend/.env.example`). The backend reuses `finchat/config.py` for the Gemini key,
so the same root-level `.env` powers both the Streamlit app and this web app.

```
backend/
  requirements.txt        fastapi + uvicorn, plus the root requirements.txt
  app/
    main.py                routes: /api/health, /api/companies, /api/ratio,
                            /api/metric-history, /api/scores, /api/line-items,
                            /api/peer-ranking, /api/compare, /api/search-filings,
                            /api/text-sentiment, /api/dcf, /api/research, /api/chat(+/reset)
    sessions.py            in-memory per-session FinChatAgent store (chat follow-up context)
    schemas.py             pydantic request bodies
frontend/
  src/
    api/client.ts           typed fetch wrapper for every backend route
    context/SelectionContext.tsx   shared ticker/year/company-list state
    components/             Sidebar, MetricTile, MetricHistoryChart, Markdown
    pages/                   ChatPage, DashboardPage, ComparePage, ValuationPage,
                             ResearchPage, FilingsPage
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
