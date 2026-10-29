"""In-memory conversation history.

The `messages` list is exactly what the Groq API expects:
    [{"role": "system" | "user" | "assistant", "content": "..."}, ...]
The first item is always the system message. History lives only in memory,
so it is lost when the program exits.
"""

from __future__ import annotations

Message = dict[str, str]


class ChatHistory:
    """Keeps the list of messages for one chat session."""

    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self.messages: list[Message] = []
        self.clear()

    def clear(self) -> None:
        """Reset the conversation but keep the system message."""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def add_user(self, content: str) -> None:
        self._add("user", content)

    def add_assistant(self, content: str) -> None:
        self._add("assistant", content)

    def _add(self, role: str, content: str) -> None:
        content = content.strip()
        if not content:
            raise ValueError(f"Cannot add an empty {role} message to the history.")
        self.messages.append({"role": role, "content": content})

    def remove_last_user_message(self) -> bool:
        """Undo the most recent user message (used when a request fails).

        Returns True if a message was removed. This keeps user/assistant
        messages alternating, so a failed request never corrupts the history.
        """
        if self.messages and self.messages[-1]["role"] == "user":
            self.messages.pop()
            return True
        return False

    def messages_for_api(self, max_messages: int) -> list[Message]:
        """Return a copy to send to the model: system message + last `max_messages`."""
        conversation = self.messages[1:]
        if max_messages > 0 and len(conversation) > max_messages:
            conversation = conversation[-max_messages:]
            # Never start the window with an assistant reply.
            while conversation and conversation[0]["role"] != "user":
                conversation = conversation[1:]
        return [dict(m) for m in [self.messages[0], *conversation]]

    def recent(self, count: int) -> list[Message]:
        """Return the last `count` non-system messages (oldest first)."""
        conversation = self.messages[1:]
        return conversation[-count:] if count > 0 else []

    def __len__(self) -> int:
        """Number of user + assistant messages (the system message is not counted)."""
        return len(self.messages) - 1
