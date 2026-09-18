import json
import yaml
import os

from dotenv import load_dotenv
from marshmallow import missing
from openai import OpenAI

from agents._dead_loop import DeadLoopDetector
from memory.history_store import ChatHistoryMemory
from tools.registry import build_tools

load_dotenv()

class SimpleAgent:
    def __init__(self, settings_path:str="settings.json", agent_yaml_path="agents/agent.yaml"):
        with open(settings_path,"r", encoding="utf-8") as f:
            self.settings = json.load(f)
        with open(agent_yaml_path,"r", encoding="utf-8") as f:
            self.agent_meta = yaml.safe_load(f)

        self._validate_agent_meta(agent_yaml_path)

        self.client = OpenAI(
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LLM_API_KEY"),
        )
        self.model = os.getenv("LLM_MODEL")

        self.memory = ChatHistoryMemory(max_len=self.settings["memory_max_history"])

        # 工具表从 YAML 配置来，不再硬编码
        self.tools_map = build_tools(self.agent_meta.get("tools", []))

        # 人设 = 模板 + 配置渲染
        self.system_prompt = self._render_system_prompt(
            template_path = "prompts/system.md",
            tools_map = self.tools_map
        )

    def _validate_agent_meta(self, agent_yaml_path:str):
        """校验 agent.yaml 必填字段，缺了早失败，符合 BaseTool 的早失败哲学。"""
        required = ["agent_name", "role", "goal"]
        missing = [k for k in required if not self.agent_meta.get(k)]
        if missing:
            raise ValueError(f"{agent_yaml_path} 缺少必填字段：{', '.join(missing)}")

        tools = self.agent_meta.get("tools",[])
        if not isinstance(tools, list):
            raise ValueError(f"{agent_yaml_path} 的 tools 字段必须是列表，当前类型：{type(tools).__name__}")
    def list_tool_desc(self):
        out = []
        for name, tool in self.tools_map.items():
            out.append(f"{name}: {tool.description}")
        return "\n".join(out)

    def _build_tools_schema(self):
        """从 tools_map 自动生成 OpenAI function calling 的 tools 参数"""
        schema = []
        for name, tool in self.tools_map.items():
            # 早失败：缺 Input 模型的工具直接抛错，避免运行时 AttributeError
            if not hasattr(tool, "Input"):
                raise ValueError(f"工具 {name} 缺少Input模型")
            # 用 Pydantic 模型的 schema 自动生成参数定义
            params = tool.Input.model_json_schema()
            # 删掉 Pydantic 自带的 title 字段，OpenAI 不需要
            for k in params.get("properties", {}).values():
                k.pop("title", None)

            schema.append({
                "type":"function",
                "function":{
                    "name":name,
                    "description": tool.description,
                    "parameters":params,
                }
            })
        return schema

    def _render_system_prompt(self, template_path:str, tools_map:dict) -> str:
        """把 agent.yaml 的配置和工具清单填进 system.md 模板。"""
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
        # 拼出工具说明文本："- calculator: 执行数学计算，输入表达式字符串"
        lines = []

        for name, tool in tools_map.items():
            lines.append(f"- {name}: {tool.description}")
        tools_text = "\n".join(lines) if lines else "本 Agent 当前没有可用工具"

        return template.format(
            role= self.agent_meta.get("role", "你是一个实用的AI助手。"),
            goal=self.agent_meta.get("goal", "准确回答用户的问题。"),
            tools=tools_text,
            language=self.agent_meta.get("language","中文"),
        )

    def run(self, user_query:str, tool_choice=None, max_iterations:int=5):
        if tool_choice is None:
            tool_choice = self.agent_meta.get("tool_choice", "auto")
        """Agent 主循环：多轮工具调用，直到模型不再调工具或达到上限。

                流程：
                  1. 第一轮：带 tools 问模型
                  2. 若模型返回 tool_calls：执行工具 → 加入上下文 → 下一轮继续问
                  3. 若模型不再调工具：返回最终答复
                  4. 达到 max_iterations：强制不再传 tools，让模型总结
                """
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
        return answer

    def run_stream(self, user_query:str, tool_choice=None, max_iterations:int=5):
        if tool_choice is None:
            tool_choice = self.agent_meta.get("tool_choice", "auto")
        """流式版本：yield (kind, payload) 事件序列。

                事件类型：
                  ("text", str)        —— 最终回答的增量文本片段
                  ("tool_call", dict)   —— 工具调用前，payload={name, args}
                  ("tool_result", dict)—— 工具执行后，payload={name, result}
                  ("done", str)        —— 最终完整文本，收尾用
                """
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

        # 兜底：达到 max_iterations 时模型仍只输出 tool_calls 的情形
        final_answer = final_answer or "达到最大调用次数，无法继续。"
        self.memory.add("assistant", final_answer)
        yield ("done", final_answer)









