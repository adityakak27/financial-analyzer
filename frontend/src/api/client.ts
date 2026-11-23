const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch {
      /* no-op */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export const api = {
  health: () => request<any>("/api/health"),

  companies: () => request<{ companies: { ticker: string; name: string; years_covered: number }[] }>(
    "/api/companies",
  ),

  years: (ticker: string) =>
    request<any>(`/api/companies/${ticker}/years`),

  ratio: (ticker: string, metric: string, year?: number) =>
    request<any>(`/api/ratio${qs({ ticker, metric, year })}`),

  metricHistory: (
    ticker: string,
    metric: string,
    startYear?: number,
    endYear?: number,
    periodType?: string,
  ) =>
    request<any>(
      `/api/metric-history${qs({
        ticker,
        metric,
        start_year: startYear,
        end_year: endYear,
        period_type: periodType,
      })}`,
    ),

  scores: (ticker: string, year?: number) =>
    request<any>(`/api/scores${qs({ ticker, year })}`),

  lineItems: (ticker: string, year?: number) =>
    request<any>(`/api/line-items${qs({ ticker, year })}`),

  peerRanking: (ticker: string, metric: string, year?: number) =>
    request<any>(`/api/peer-ranking${qs({ ticker, metric, year })}`),

  compare: (tickerA: string, tickerB: string, year?: number) =>
    request<any>(`/api/compare${qs({ ticker_a: tickerA, ticker_b: tickerB, year })}`),

  searchFilings: (query: string, ticker?: string, section?: string, year?: number) =>
    request<any>(`/api/search-filings${qs({ query, ticker, section, year })}`),

  textSentiment: (ticker: string, year?: number, section?: string) =>
    request<any>(`/api/text-sentiment${qs({ ticker, year, section })}`),

  dcf: (body: {
    ticker: string;
    wacc?: number;
    terminal_growth?: number;
    forecast_years?: number;
    custom_growth_rate?: number | null;
  }) => request<any>("/api/dcf", { method: "POST", body: JSON.stringify(body) }),

  research: (body: { ticker: string; year?: number | null }) =>
    request<any>("/api/research", { method: "POST", body: JSON.stringify(body) }),

  chat: (body: { question: string; session_id?: string | null }) =>
    request<any>("/api/chat", { method: "POST", body: JSON.stringify(body) }),

  chatReset: (sessionId: string) =>
    request<any>("/api/chat/reset", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    }),

  mispricingOverview: (year?: number, subIndustry?: string) =>
    request<any>(`/api/mispricing/overview${qs({ year, sub_industry: subIndustry })}`),

  mispricingLeaderboard: (direction: "under" | "over", year?: number, subIndustry?: string, limit?: number) =>
    request<any>(`/api/mispricing/leaderboard${qs({ direction, year, sub_industry: subIndustry, limit })}`),

  mispricingCompany: (ticker: string, year?: number) =>
    request<any>(`/api/mispricing/company${qs({ ticker, year })}`),

  mispricingScoreEffectiveness: (score: "piotroski" | "altman" | "beneish") =>
    request<any>(`/api/mispricing/score-effectiveness${qs({ score })}`),
};
