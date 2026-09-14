import json
from email import message

import yaml
import os

from attr.validators import max_len
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.beta.chatkit import ChatSessionHistory


class SimpleAgent:
    def __init__(self, settings_path:str="settings.json", agent_yaml_path="agents/agent.yaml"):
        with open(settings_path,"r", encoding="utf-8") as f:
            self.settings = json.load(f)
        with open(agent_yaml_path,"r", encoding="utf-8") as f:
            self.agent_meta = yaml.self_load(f)

        self.client = OpenAI(
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LLM_API_KEY"),
        )
        self.model = os.getenv("LLM_MODEL")

        self.memory = ChatSessionHistory(max_len=self.settings["memory_max_history"])

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

    def run(self, user_query:str):
        self.memory.add("user", user_query)
        messages = [{"role":"system","content":self.system_promt}]
        messages.extend(self.memory.get_history())

        # -------- 极简Agent循环（没有复杂Framework，原生实现）--------
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2
        )

        answer = resp.choices[0].message.content
        self.memory.add("assistant", answer)
        return answer

