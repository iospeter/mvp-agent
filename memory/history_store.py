import json
import os.path
from typing import List, Dict

from memory.base import BaseMemory


class ChatHistoryMemory(BaseMemory):
    def __init__(self,max_len=20, sumary_max_char = 600):
        self.max_len = max_len
        self.summery_max_char = sumary_max_char
        self._buffer: List[Dict] = []
        self._summary = ""   # 被滑出窗口的早期对话的滚动摘要

    def add(self, role: str, content: str):
        self._buffer.append({"role":role, "content":content})


        # 溢出时不再直接丢弃，而是把最老的一条折入摘要（抽取式，无 LLM 依赖）
        while len(self._buffer) > self.max_len:
            evicted = self._buffer.pop(0)
            line = f"{evicted['role']}: {evicted['content'][:100]}"
            self._summary = (self._summary + "\n" + line).strip()
            # 摘要本身也限量，防止无限增长（保留最近的摘要内容）
            if len(self._summary) > self.summery_max_char:
                self._summary = self._summary[-self.summery_max_char]

    def get_history(self) -> List[Dict]:
        history = self._buffer.copy()
        if self._summary:
            history.insert(0, {
                "role": "system",
                "content": f"[早期对话摘要，可能不完整]\n{self._summary}",
            })
        return history

    def clear(self):
        self._buffer.clear()
        self._summary = ""

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
            if isinstance(data, list): # 旧格式：纯历史列表
                self._buffer = data[-self.max_len:]
            elif isinstance(data, dict): # 新格式：摘要 + 历史
                self._summary = data.get("summary", "") or ""
                self._buffer = data.get("history",[])[-self.max_len:]
        except (json.JSONDecodeError, OSError):
            self._buffer = []
            self._summary = ""

    def save_to(self, path:str):
        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"summary": self._summary,
                 "history": self._buffer,},
                f, ensure_ascii=False, indent=2

            )

