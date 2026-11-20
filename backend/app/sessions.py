from __future__ import annotations

import threading
import time
import uuid

from finchat.chatbot.agent import FinChatAgent

_SESSION_TTL_SECONDS = 2 * 60 * 60


class SessionStore:
    """In-memory store of chat agents keyed by session id.

    Each FinChatAgent carries its own ConversationState + message history, so a
    session id is how the frontend keeps one chat thread's follow-up context
    (ticker/year focus, prior turns) separate from another open tab.
    """

    def __init__(self) -> None:
        self._agents: dict[str, FinChatAgent] = {}
        self._touched: dict[str, float] = {}
        self._lock = threading.Lock()

    def _evict_stale(self) -> None:
        now = time.time()
        stale = [sid for sid, t in self._touched.items() if now - t > _SESSION_TTL_SECONDS]
        for sid in stale:
            self._agents.pop(sid, None)
            self._touched.pop(sid, None)

    def get_or_create(self, session_id: str | None) -> tuple[str, FinChatAgent]:
        with self._lock:
            self._evict_stale()
            if session_id and session_id in self._agents:
                self._touched[session_id] = time.time()
                return session_id, self._agents[session_id]
            new_id = session_id or str(uuid.uuid4())
            agent = FinChatAgent()
            self._agents[new_id] = agent
            self._touched[new_id] = time.time()
            return new_id, agent

    def reset(self, session_id: str) -> None:
        with self._lock:
            agent = self._agents.get(session_id)
            if agent is not None:
                agent.reset()
            self._touched[session_id] = time.time()


store = SessionStore()
