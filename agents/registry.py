import importlib
import pkgutil

import yaml

from agents.base import BaseAgent

_discovered = False
def auto_discover() ->None:
    """扫描 agents/ 包下所有模块并导入，触发 BaseAgent.__init_subclass__ 自动注册。

        _ 开头的模块（如 _dead_loop.py）视为私有实现，跳过。
        """
    global _discovered
    if _discovered:
        return
    pkg = importlib.import_module("agents")
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"agents.{info.name}")
    _discovered = True

def create_agent(agent_yaml_path:str, settings_path:str="settings.json") -> BaseAgent:
    """Agent 工厂：读 YAML 的 agent_type 字段，从注册表实例化对应 Agent 类。

        agent_type 缺省为 "simple"（向后兼容旧 YAML）。
        """
    with open(agent_yaml_path, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}
    agent_type = meta.get("agent_type", "simple")

    auto_discover()
    cls = BaseAgent._registry.get(agent_type)
    if cls is None:
        raise ValueError(
            f"未知 agent_type ' {agent_type} '（来自 {agent_yaml_path} ），" 
            f"可选： {', '.join(sorted(BaseAgent._registry))} "
        )
    return cls(settings_path=settings_path, agent_yaml_path=agent_yaml_path)