import json
import yaml
import os

from dotenv import load_dotenv
from openai import OpenAI

from memory.history_store import ChatHistoryMemory
from tools import CalculatorTool, SearchDemoTool

load_dotenv()

class SimpleAgent:
    def __init__(self, settings_path:str="settings.json", agent_yaml_path="agents/agent.yaml"):
        with open(settings_path,"r", encoding="utf-8") as f:
            self.settings = json.load(f)
        with open(agent_yaml_path,"r", encoding="utf-8") as f:
            self.agent_meta = yaml.safe_load(f)

        self.client = OpenAI(
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LLM_API_KEY"),
        )
        self.model = os.getenv("LLM_MODEL")

        self.memory = ChatHistoryMemory(max_len=self.settings["memory_max_history"])

        self.tools_map = {
            "calculator":CalculatorTool(),
            "search_demo":SearchDemoTool()
        }

        with open("prompts/system.md","r", encoding="utf-8") as f:
            self.system_promt = f.read()


    def list_tool_desc(self):
        out = []
        for name, tool in self.tools_map.items():
            out.append(f"{name}: {tool.description}")
        return "\n".join(out)

    def _build_tools_schema(self):
        """从 tools_map 自动生成 OpenAI function calling 的 tools 参数"""
        schema = []
        for name, tool in self.tools_map.items():
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

    def run(self, user_query:str, tool_choice="auto"):
        self.memory.add("user", user_query)
        messages = [{"role":"system","content":self.system_promt}]
        messages.extend(self.memory.get_history())
        tools_schema = self._build_tools_schema()
        # ===== 第一轮：让模型决定 =====
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            tools=tools_schema,     # 关键：把工具传进去
            tool_choice= tool_choice,     #auto=模型自己决定；none=禁用；可强制 {"type":"function","function":{"name":"calculator"}}
        )

        msg = resp.choices[0].message
        # ===== 分支：模型想调工具 =====
        if msg.tool_calls:
            # 把 assistant 这条带 tool_calls 的消息加进上下文（不进长期 memory）
            messages.append(msg.model_dump(exclude_none=True))

            for call in msg.tool_calls:
                tool_name = call.function.name
                args = json.loads(call.function.arguments or "{}")
                print(f" [TOOL CALL] {tool_name} {args}")  # 可观测性日志

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

            # ===== 第二轮：让模型基于工具结果总结 =====
            resp2 = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                # 注意：第二轮通常不再传 tools，避免模型再次试图调工具陷入循环 # 如果你的场景需要链式调用，再传 tools 并加个最大轮数限制
            )
            answer = resp2.choices[0].message.content
        else:
            # ===== 分支：模型直接回答（没用工具） =====
            print("[NO TOOL] 模型直接回答")
            answer = msg.content

        self.memory.add("assistant", answer)
        return answer

