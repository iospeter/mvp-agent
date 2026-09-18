class DeadLoopDetector:
    """检测 Agent 是否陷入死循环（重复调用同一工具+参数）。

        通过工具名 + 排序后的参数构造签名，记录每个签名的调用次数。
        同一签名被重复调用达到 max_repeat 次时，认为陷入死循环。
        """
    def __init__(self, max_repeat: int = 3):
        self.max_repeat = max_repeat
        self._signatures:dict[str, int] = {}
    def record(self, tool_name:str, args:dict) ->bool:
        """记录一次工具调用，返回 True 表示已陷入死循环。"""

        sig = f"{tool_name}:{sorted(args.items())}"
        self._signatures[sig] = self._signatures.get(sig, 0) + 1
        return self._signatures[sig] >= self.max_repeat

    def reset(self):
        """每次新 query 开始时清空记录。"""
        self._signatures.clear()