import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useSelection } from "../context/SelectionContext";

export default function FilingsPage() {
  const { ticker, year } = useSelection();
  const [query, setQuery] = useState("");
  const [section, setSection] = useState("");
  const [filterTicker, setFilterTicker] = useState("");
  const [searchResult, setSearchResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [sentiment, setSentiment] = useState<any>(null);

  useEffect(() => {
    if (!ticker) return;
    api
      .textSentiment(ticker, year)
      .then(setSentiment)
      .catch(() => setSentiment(null));
  }, [ticker, year]);

  async function search() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await api.searchFilings(query, filterTicker || undefined, section || undefined);
      setSearchResult(res);
    } catch (e: any) {
      setSearchResult({ error: e.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">10-K Filings Search</h1>
        <p className="page-subtitle">
          Semantic (TF-IDF) search over MD&amp;A and Risk Factors text, plus finance-specific sentiment scoring.
        </p>
      </div>

      <div className="grid grid-3" style={{ marginBottom: 20, alignItems: "start" }}>
        <div className="card" style={{ gridColumn: "span 2" }}>
          <div className="card-title">Search disclosures</div>
          <div className="row" style={{ marginBottom: 10 }}>
            <input
              className="input"
              placeholder="e.g. supply chain constraints"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
              style={{ flex: 1, minWidth: 220 }}
            />
            <select className="select" value={section} onChange={(e) => setSection(e.target.value)}>
              <option value="">Any section</option>
              <option value="mda">MD&amp;A</option>
              <option value="risk">Risk Factors</option>
            </select>
            <input
              className="input"
              placeholder="ticker filter (optional)"
              value={filterTicker}
              onChange={(e) => setFilterTicker(e.target.value.toUpperCase())}
              style={{ width: 140 }}
            />
            <button className="btn" onClick={search} disabled={loading}>
              {loading ? "Searching…" : "Search"}
            </button>
          </div>

          {searchResult?.error && <div className="error-banner">{searchResult.error}</div>}

          {searchResult?.results?.length ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {searchResult.results.map((r: any, i: number) => (
                <div key={i} className="card" style={{ background: "var(--bg)" }}>
                  <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
                    <span className="badge neutral">
                      {r.ticker} FY{r.year} · {r.section}
                    </span>
                    <span className="muted" style={{ fontSize: 11.5 }}>score {r.score}</span>
                  </div>
                  <p style={{ margin: 0, fontSize: 13 }}>{r.excerpt}</p>
                  {r.citation_url && (
                    <a href={r.citation_url} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>
                      View filing →
                    </a>
                  )}
                </div>
              ))}
            </div>
          ) : (
            searchResult && !searchResult.error && <div className="empty-state">No matching passages.</div>
          )}
        </div>

        <div className="card">
          <div className="card-title">
            Sentiment · {ticker} FY{year ?? "—"}
          </div>
          {sentiment?.sections?.length ? (
            sentiment.sections.map((s: any) => (
              <div key={s.section} style={{ marginBottom: 14 }}>
                <div style={{ fontWeight: 650, fontSize: 12.5, marginBottom: 6, textTransform: "uppercase" }}>
                  {s.section}
                </div>
                <div className="row" style={{ marginBottom: 4 }}>
                  <span className="badge negative">{s.negative_word_share_pct}% negative</span>
                  <span className="badge positive">{s.positive_word_share_pct}% positive</span>
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {s.n_words} words analyzed · polarity {s.polarity?.toFixed ? s.polarity.toFixed(3) : s.polarity}
                </div>
              </div>
            ))
          ) : (
            <div className="empty-state">No sentiment data.</div>
          )}
        </div>
      </div>
    </div>
  );
}
