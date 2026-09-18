import json


from agents._dead_loop import DeadLoopDetector
from agents.base import BaseAgent


class SimpleAgent(BaseAgent):
    agent_type = "simple"

    def run(self, user_query:str, tool_choice=None, max_iterations:int=5):
        """Agent 主循环：多轮工具调用，直到模型不再调工具或达到上限。

                流程：
                  1. 第一轮：带 tools 问模型
                  2. 若模型返回 tool_calls：执行工具 → 加入上下文 → 下一轮继续问
                  3. 若模型不再调工具：返回最终答复
                  4. 达到 max_iterations：强制不再传 tools，让模型总结
                """
        if tool_choice is None:
            tool_choice = self.agent_meta.get("tool_choice", "auto")
        self.memory.add("user", user_query)
        messages = [{"role": "system","content": self.system_prompt}]
        messages.extend(self.memory.get_history())
        tools_schema = self._build_tools_schema()

        detector = DeadLoopDetector(max_repeat=3)
        for iteration in range(1, max_iterations+1):
            is_last = iteration == max_iterations
            api_tools = [] if is_last else tools_schema
            api_tool_choice = "none" if is_last else tool_choice
            # ===== 第一轮：让模型决定 =====
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                tools=api_tools,  # 关键：把工具传进去
                tool_choice=api_tool_choice,  # auto=模型自己决定；none=禁用；可强制 {"type":"function","function":{"name":"calculator"}}
            )
            msg = resp.choices[0].message
            # 不再调工具，返回最终答复
            if not msg.tool_calls:
                if iteration == 1:
                    print("[NO TOOL] 模型直接回答")
                self.memory.add("assistant", msg.content)
                self._save_memory()
                return msg.content

            # 把 assistant 带 tool_calls 的消息加入上下文
            messages.append(msg.model_dump(exclude_none=True))

            # 执行所有工具调用
            for call in msg.tool_calls:
                tool_name = call.function.name
                args = json.loads(call.function.arguments or "{}")
                print(f" [TOOL CALL] iter={iteration} {tool_name} {args}")  # 可观测性日志

                # 死循环检测
                if detector.record(tool_name, args):
                    result = f"检测到重复调用同一工具+参数，已中断。请基于已有信息回答用户。"
                    print(f"[DEAD LOOP] {tool_name} {args}")
                else:
                    tool = self.tools_map.get(tool_name)
                    if tool is None:
                        result = f" 工具{tool_name}不存在"
                    else:
                        try:
                            result = tool.run(**args)
                        except Exception as e:
                            result = f"工具执行异常: {e} "
                    print(f"[TOOL RESULT] {result} ")

                messages.append({
                    "role":"tool",
                    "tool_call_id":call.id,
                    "content":result,
                })

        # 理论上不会走到这里，最后一轮 is_last=True 时模型一定不带 tool_calls
        answer = msg.content or "达到最大调用次数，无法继续。"
        self.memory.add("assistant", answer)
        self._save_memory()
        return answer

    def run_stream(self, user_query:str, tool_choice=None, max_iterations:int=5):
        """流式版本：yield (kind, payload) 事件序列。

                事件类型：
                  ("text", str)        —— 最终回答的增量文本片段
                  ("tool_call", dict)   —— 工具调用前，payload={name, args}
                  ("tool_result", dict)—— 工具执行后，payload={name, result}
                  ("done", str)        —— 最终完整文本，收尾用
                """
        if tool_choice is None:
            tool_choice = self.agent_meta.get("tool_choice", "auto")
        self.memory.add("user", user_query)
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.memory.get_history())
        tools_schema = self._build_tools_schema()
        detector = DeadLoopDetector(max_repeat=3)
        final_answer = ""

        for iteration in range(1, max_iterations+1):
            is_last = iteration == max_iterations
            api_tools = [] if is_last else tools_schema
            api_tool_choice = "none" if is_last else tool_choice
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                tools=api_tools,
                tool_choice=api_tool_choice,
                stream=True,
            )
            # 累积器：流式 chunk 是增量，必须拼装
            content_buf = ""
            tool_calls_buf = {}

            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # 增量文本：实时推给上层
                if delta.content:
                    content_buf += delta.content
                    yield ("text", delta.content)

                # 增量 tool_calls：按 index 累积 name 和 arguments
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_buf:
                            tool_calls_buf[idx] = {"id":"", "name":"", "arguments":""}
                        if tc.id:
                            tool_calls_buf[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_buf[idx]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_buf[idx]["arguments"] += tc.function.arguments

            # 收完一轮，判断走向
            if not tool_calls_buf:
                # 最终回答轮
                final_answer = content_buf
                self.memory.add("assistant", final_answer)
                self._save_memory()
                yield ("done", final_answer)
                return

            # 工具调用轮：把 assistant 消息（带 tool_calls）加入上下文
            messages.append({
                "role":"assistant",
                "content": content_buf or None,
                "tool_calls":[
                    {
                        # 注意：必须用 t["id"]（累积器里的真实 id），
                        # 不能用循环残留变量 tc.id —— 多数厂商只在首个 chunk 带 id，后续为 None
                        "id": t["id"],
                        "type":"function",
                        "function": {
                            "name": t["name"],
                            "arguments": t["arguments"]
                        },
                    }
                    for t in tool_calls_buf.values()
                ],
            })


            for t in tool_calls_buf.values():
                tool_name = t["name"]
                args = json.loads(t["arguments"] or "{}")
                yield ("tool_call", {"name": tool_name, "args": args})

                if detector.record(tool_name, args):
                    result = "检测到重复调用同一工具+参数，已中断。请基于已有信息回答用户。"
                else:
                    tool = self.tools_map.get(tool_name)
                    if tool is None:
                        result = f"工具 {tool_name} 不存在"
                    else:
                        try:
                            result = tool.run(**args)
                        except Exception as e:
                            result = f"工具执行异常: {e}"
                yield ("tool_result", {"name": tool_name, "result": result})

                messages.append({
                    "role":"tool",
                    "tool_call_id": t["id"],
                    "content":result,
                })

        # 兑底：达到 max_iterations 时模型仍只输出 tool_calls 的情形
        final_answer = final_answer or "达到最大调用次数，无法继续。"
        self.memory.add("assistant", final_answer)
        self._save_memory()
        yield ("done", final_answer)









