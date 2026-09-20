from agents.agent import SimpleAgent
class PlanExecuteAgent(SimpleAgent):
    """先规划、后执行的 Agent（演示第二种主循环形态）。

        与 SimpleAgent 的差异：执行工具循环之前，先用一次"禁用工具"的请求
        逼模型输出分步计划，再把计划并入问题交给标准循环执行。
        """
    agent_type = "plan_execute"
    _pending_plan:str = None # 当前查询待注入的计划，经 to_context_query 用完即清
    def run(self, user_query:str, tool_choice=None, max_iterations:int=5) -> str:
        _pending_plan = self._make_plan(user_query)
        print(f"=== PLAN ===\n {_pending_plan} \n=== /PLAN ===")
        return super().run(
            user_query,
            tool_choice=tool_choice,
            max_iterations=max_iterations
        )

    def run_stream(self, user_query:str, tool_choice=None, max_iterations:int=5):
        self._pending_plan = self._make_plan(user_query)
        yield ( "text" , f"【执行计划】\n {self._pending_plan} \n【/执行计划】\n" )
        yield from super().run_stream(
            user_query,
            tool_choice=tool_choice,
            max_iterations=max_iterations
        )

    def to_memory_query(self, user_query:str) -> str:
        return user_query

    def to_context_query(self, user_query:str) -> str:
        plan = self._pending_plan
        self._pending_plan = None # 用完即清，防止污染下一轮查询
        if plan:
            return f" {user_query} \n\n（请按以下计划执行：\n {plan} \n）"
        return user_query

    def _make_plan(self, user_query:str) -> str:
        """规划阶段：不给工具、tool_choice=none，只让模型输出编号步骤。"""
        resp = self.client.chat.completions.create(
            model=self.model,
            messages= [
                {"role": "system", "content":self.system_prompt},
                {"role": "user", "content":f"请为下面的问题制定简洁的编号步骤计划，只输出计划本身，不要执行任何步骤：\n {user_query}"},
            ],
            temperature=0.2,
            tools=[],
            tool_choice="none",
        )
        return resp.choices[0].message.content or "（模型未返回计划）"