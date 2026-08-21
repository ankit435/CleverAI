from typing import Dict, List, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

class SessionMemoryManager:
    """
    Stateful Session & User Memory Manager for multi-turn thread context.
    """
    def __init__(self, max_history_turns: int = 10):
        self._thread_history: Dict[str, List[BaseMessage]] = {}
        self._user_facts: Dict[str, Dict[str, Any]] = {}
        self.max_history_turns = max_history_turns

    def get_history(self, thread_id: str) -> List[BaseMessage]:
        """Retrieve recent message history for a given thread_id."""
        if not thread_id:
            return []
        return self._thread_history.get(thread_id, [])

    def add_user_message(self, thread_id: str, content: str):
        """Append user message to thread memory."""
        if not thread_id:
            return
        if thread_id not in self._thread_history:
            self._thread_history[thread_id] = []
        self._thread_history[thread_id].append(HumanMessage(content=content))
        self._trim_memory(thread_id)

    def add_ai_message(self, thread_id: str, content: str):
        """Append AI message response to thread memory."""
        if not thread_id:
            return
        if thread_id not in self._thread_history:
            self._thread_history[thread_id] = []
        self._thread_history[thread_id].append(AIMessage(content=content))
        self._trim_memory(thread_id)

    def get_formatted_context(self, thread_id: str) -> str:
        """Format history into a clean prompt context block."""
        history = self.get_history(thread_id)
        if not history:
            return "No previous conversation context."

        formatted_lines = []
        for msg in history[-self.max_history_turns * 2:]:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            formatted_lines.append(f"{role}: {msg.content}")

        return "\n".join(formatted_lines)

    def _trim_memory(self, thread_id: str):
        """Keep memory window constrained to max_history_turns."""
        limit = self.max_history_turns * 2
        if len(self._thread_history[thread_id]) > limit:
            self._thread_history[thread_id] = self._thread_history[thread_id][-limit:]

# Global memory manager singleton
memory_manager = SessionMemoryManager()
