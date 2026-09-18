import json
import os.path
from typing import List, Dict

from memory.base import BaseMemory


class ChatHistoryMemory(BaseMemory):
    def __init__(self,max_len=20):
        self.max_len = max_len
        self._buffer: List[Dict] = []

    def add(self, role: str, content: str):
        self._buffer.append({"role":role, "content":content})
        if len(self._buffer) > self.max_len:
            self._buffer = self._buffer[-self.max_len:]

    def get_history(self) -> List[Dict]:
        return self._buffer.copy()

    def clear(self):
        self._buffer.clear()

    def load_from(self, path:str) ->None:
        """从 JSON 文件加载历史记录。

                容错策略：
                  - 文件不存在 → 静默跳过（首次启动正常）
                  - 文件损坏 → 静默重置为空（避免损坏文件卡死 Agent）
                """
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._buffer = data[-self.max_len:]
        except (json.JSONDecodeError, OSError):
            self._buffer = []

    def save_to(self, path:str):
        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._buffer, f, ensure_ascii=False, indent=2)

