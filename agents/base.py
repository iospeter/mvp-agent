import json
import yaml
import os

from dotenv import load_dotenv
from openai import OpenAI

from agents._dead_loop import DeadLoopDetector
from memory.history_store import ChatHistoryMemory
from tools.registry import build_tools

load_dotenv()

class BaseAgent:
    """所有 Agent 的抽象基类（模板方法模式）。

        公共能力（配置加载/校验、记忆、工具构建、system prompt 渲染、持久化）
        在这里实现；主循环的差异（run / run_stream）交给子类。
        子类声明自己的 agent_type 字段即可自动注册，被工厂发现。
        """
    agent_type: str = ""
    _registry: dict = {}
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 只有"自己声明了 agent_type"的具体子类才注册
        # （中间抽象层、未命名的子类跳过，防止意外覆盖 simple）
        if "agent_type" not in cls.__dict__ or not cls.agent_type:
            return
        if getattr(cls, "__abstractmethods__", frozenset()):
            return

        if cls.agent_type in BaseAgent._registry:
            existing = BaseAgent._registry[cls.agent_type]
            raise ValueError(
                f"agent_type 冲突：' {cls.agent_type} ' 已被 " 
                f" {existing.__module__} . {existing.__name__} 注册，" 
                f"冲突方： {cls.__module__} . {cls.__name__} "
            )
        BaseAgent._registry[cls.agent_type] = cls


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
        # 模型优先级：CLI --model（main.py 覆盖）> agent.yaml model > .env LLM_MODEL
        self.model = self.agent_meta.get("model") or os.getenv("LLM_MODEL")

        self.memory = ChatHistoryMemory(max_len=self.settings["memory_max_history"])

        # 工具表从 YAML 配置来，不再硬编码
        self.tools_map = build_tools(self.agent_meta.get("tools", []))

        # 人设 = 模板 + 配置渲染
        self.system_prompt = self._render_system_prompt(
            template_path = "prompts/system.md",
            tools_map = self.tools_map
        )
        # 从配置加载持久化记忆（agent.yaml 没配 memory_file 则跳过）
        memory_file = self.agent_meta.get("memory_file")
        if memory_file:
            self.memory.load_from(memory_file)

    def _validate_agent_meta(self, agent_yaml_path:str):
        """校验 agent.yaml 必填字段，缺了早失败，符合 BaseTool 的早失败哲学。"""
        required = ["agent_name", "role", "goal"]
        missing = [k for k in required if not self.agent_meta.get(k)]
        if missing:
            raise ValueError(f"{agent_yaml_path} 缺少必填字段：{', '.join(missing)}")

        tools = self.agent_meta.get("tools",[])
        if not isinstance(tools, list):
            raise ValueError(f"{agent_yaml_path} 的 tools 字段必须是列表，当前类型：{type(tools).__name__}")

        memory_file = self.agent_meta.get("memory_file")
        if memory_file is not None and not isinstance(memory_file, str):
            raise ValueError(f"{agent_yaml_path} 的 memory_file 字段必须是字符串，当前类型：{type(memory_file).__name__}")

    def _save_memory(self):
        """把当前记忆持久化到 agent.yaml 配置的文件。没配 memory_file 则跳过。

                包 try-except：保存失败不阻塞 Agent 主流程（如磁盘满），只打警告。
                """
        memory_file = self.agent_meta.get("memory_file")
        if memory_file:
            try:
                self.memory.save_to(memory_file)
            except Exception as e:
                print(f"[MEMORY] 保存失败: {e}")



    def _list_tool_desc(self):
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

    # ========== 扩展点（子类可覆盖，控制"存什么"与"发什么"） ==========
    def to_memory_query(self, user_query:str) -> str:
        """写入持久化记忆的用户文本。默认原样存储。"""
        return user_query
    def to_context_query(self, user_query:str) -> str:
        """发给 LLM 的用户文本。默认与记忆一致；子类可注入增强内容（如执行计划）。"""
        return user_query

    def run(self, user_query:str, tool_choice=None, max_iterations:int=5) -> str:
        """非流式执行一轮问答，返回最终回答文本。"""
        pass

    def run_stream(self, user_query:str, tool_choice=None, max_iterations:int=5):
        """流式执行一轮问答，yield (kind, payload) 事件序列。"""
        pass










