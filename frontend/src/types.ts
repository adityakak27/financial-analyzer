export interface Company {
  ticker: string;
  name: string;
  years_covered: number;
}

export interface Citation {
  type: string;
  table?: string;
  ticker?: string;
  fy?: number | string;
  metric?: string;
  section?: string;
  chunk_id?: string | number;
  url?: string;
}

export interface ToolTraceEntry {
  name: string;
  args: Record<string, any>;
  result?: Record<string, any>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  toolTrace?: ToolTraceEntry[];
  pending?: boolean;
  ts?: number;
  liked?: boolean;
  disliked?: boolean;
}

export interface Conversation {
  id: string;
  sessionId: string | null;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}
