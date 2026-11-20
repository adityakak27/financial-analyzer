import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { Company } from "../types";

interface SelectionState {
  companies: Company[];
  loadingCompanies: boolean;
  ticker: string;
  setTicker: (t: string) => void;
  tickerB: string;
  setTickerB: (t: string) => void;
  years: number[];
  year: number | undefined;
  setYear: (y: number | undefined) => void;
  llmAvailable: boolean | null;
  recentQuestions: string[];
  addRecentQuestion: (q: string) => void;
  chatSignal: { type: "ask" | "reset"; question?: string; nonce: number } | null;
  askInChat: (q: string) => void;
  requestNewChat: () => void;
}

const SelectionContext = createContext<SelectionState | null>(null);

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loadingCompanies, setLoadingCompanies] = useState(true);
  const [ticker, setTicker] = useState<string>("AAPL");
  const [tickerB, setTickerB] = useState<string>("MSFT");
  const [years, setYears] = useState<number[]>([]);
  const [year, setYear] = useState<number | undefined>(undefined);
  const [llmAvailable, setLlmAvailable] = useState<boolean | null>(null);
  const [recentQuestions, setRecentQuestions] = useState<string[]>([]);
  const [chatSignal, setChatSignal] = useState<SelectionState["chatSignal"]>(null);

  function addRecentQuestion(q: string) {
    setRecentQuestions((prev) => [q, ...prev.filter((p) => p !== q)].slice(0, 12));
  }

  function askInChat(q: string) {
    setChatSignal({ type: "ask", question: q, nonce: Date.now() });
  }

  function requestNewChat() {
    setChatSignal({ type: "reset", nonce: Date.now() });
  }

  useEffect(() => {
    api
      .companies()
      .then((res) => setCompanies(res.companies || []))
      .catch(() => setCompanies([]))
      .finally(() => setLoadingCompanies(false));
    api
      .health()
      .then((res) => setLlmAvailable(!!res.llm_available))
      .catch(() => setLlmAvailable(false));
  }, []);

  useEffect(() => {
    if (!ticker) return;
    api
      .years(ticker)
      .then((res) => {
        const ys: number[] = res.years || [];
        setYears(ys);
        setYear(ys.length ? ys[ys.length - 1] : undefined);
      })
      .catch(() => {
        setYears([]);
        setYear(undefined);
      });
  }, [ticker]);

  const value = useMemo(
    () => ({
      companies,
      loadingCompanies,
      ticker,
      setTicker,
      tickerB,
      setTickerB,
      years,
      year,
      setYear,
      llmAvailable,
      recentQuestions,
      addRecentQuestion,
      chatSignal,
      askInChat,
      requestNewChat,
    }),
    [companies, loadingCompanies, ticker, tickerB, years, year, llmAvailable, recentQuestions, chatSignal],
  );

  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>;
}

export function useSelection(): SelectionState {
  const ctx = useContext(SelectionContext);
  if (!ctx) throw new Error("useSelection must be used within SelectionProvider");
  return ctx;
}
