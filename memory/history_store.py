from typing import List, Dict

from memory.base import BaseMemory


class ChatHistoryMemory(BaseMemory):
    def __init__(self,max_len=20):
        self.max_len = max_len
        self._buffer: List[int] = []

    def add(self, role: int, content: str):
        self._buffer.append({"role":role, "content":content})
        if len(self._buffer) > self.max_len:
            self._buffer = self._buffer[-self.max_len]

    def get_history(self) -> List[Dict]:
        return self._buffer.copy()
    def clear(self):
        self._buffer.clear()
