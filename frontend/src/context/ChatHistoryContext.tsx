import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { ChatMessage, Conversation } from "../types";

const STORAGE_KEY = "finchat_conversations_v1";

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function makeId(): string {
  return `c_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

interface ChatHistoryState {
  conversations: Conversation[];
  activeId: string | null;
  activeConversation: Conversation | null;
  selectConversation: (id: string) => void;
  startNewChat: () => void;
  deleteConversation: (id: string) => void;
  /** Returns the id of the conversation to write into: the active one, or a brand-new one
   *  seeded from the first message text (only created once that first message is actually sent,
   *  so browsing to Chat and typing nothing never litters the Recents list). */
  ensureActiveConversation: (firstMessageText: string) => string;
  setConversationMessages: (id: string, messages: ChatMessage[]) => void;
  setConversationSessionId: (id: string, sessionId: string) => void;
}

const ChatHistoryContext = createContext<ChatHistoryState | null>(null);

export function ChatHistoryProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>(() => loadConversations());
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    } catch {
      /* storage unavailable/full - chat still works, just won't persist across reloads */
    }
  }, [conversations]);

  function selectConversation(id: string) {
    setActiveId(id);
  }

  function startNewChat() {
    setActiveId(null);
  }

  function deleteConversation(id: string) {
    setConversations((prev) => {
      const target = prev.find((c) => c.id === id);
      if (target?.sessionId) {
        api.chatReset(target.sessionId).catch(() => {});
      }
      return prev.filter((c) => c.id !== id);
    });
    setActiveId((cur) => (cur === id ? null : cur));
  }

  function ensureActiveConversation(firstMessageText: string): string {
    if (activeId) return activeId;
    const id = makeId();
    const title = firstMessageText.trim().slice(0, 60) || "New chat";
    const conv: Conversation = {
      id,
      sessionId: null,
      title,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    setConversations((prev) => [conv, ...prev]);
    setActiveId(id);
    return id;
  }

  function setConversationMessages(id: string, messages: ChatMessage[]) {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, messages, updatedAt: Date.now() } : c)));
  }

  function setConversationSessionId(id: string, sessionId: string) {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, sessionId } : c)));
  }

  const activeConversation = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? null,
    [conversations, activeId],
  );

  const value = useMemo(
    () => ({
      conversations,
      activeId,
      activeConversation,
      selectConversation,
      startNewChat,
      deleteConversation,
      ensureActiveConversation,
      setConversationMessages,
      setConversationSessionId,
    }),
    [conversations, activeId, activeConversation],
  );

  return <ChatHistoryContext.Provider value={value}>{children}</ChatHistoryContext.Provider>;
}

export function useChatHistory(): ChatHistoryState {
  const ctx = useContext(ChatHistoryContext);
  if (!ctx) throw new Error("useChatHistory must be used within ChatHistoryProvider");
  return ctx;
}
