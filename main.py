import argparse
import datetime
import os.path
import sys

from agents import agent

def _c(text:str, color)->str:
    """给文本加 ANSI 颜色码。Windows Terminal / 现代终端支持，老 CMD 可能显示乱码。"""
    palette = {
        "red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
        "blue": "\033[94m", "magenta": "\033[95m", "cyan": "\033[96m",
        "gray": "\033[90m", "bold": "\033[1m",
    }
    return f"{palette.get(color, '')}{text}\033[0m"


def _resolve_agent_path(name_or_path: str) -> str:
    """把 --agent 的值解析成实际 YAML 路径。

        支持两种形式：
          --agent coder             → agents/coder.yaml
          --agent agents/coder.yaml → 原样使用
        """
    if os.path.exists(name_or_path):
        return name_or_path
    candidate = os.path.join("agents", f"{name_or_path}.yaml")
    if os.path.exists(candidate):
        return candidate
    print(f"错误：找不到 Agent 配置 '{name_or_path}'（也试过 {candidate}）", file=sys.stderr)
    sys.exit(1)

def _handle_commond(cmd: str, agent_instance) -> bool:
    """处理 / 开头的命令。返回 True 继续循环，False 退出。"""
    parts = cmd.split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if name == "/help":
        print(_c("可用命令：", "bold"))
        print("  /help     显示此帮助")
        print("  /clear    清空当前会话记忆")
        print("  /memory   查看当前记忆条数")
        print("  /tools    列出当前 Agent 可用工具")
        print("  /reset    删除记忆文件（重置持久化记忆）")
        print("  /save     导出当前对话为 Markdown")
        print("  exit/quit 退出程序")
    elif name == "/clear":
        agent_instance.clear()
    elif name == "/memory":
        count = len(agent_instance.memory.get_history())
        print(f"当前记忆条数: {_c(str(count), 'cyan')}")
    elif name == "/tools":
        tools = agent_instance.tools_map
        if not tools:
            print("当前 Agent 没有可用工具")
        else:
            print(_c("可用工具：", "bold"))
            for n, t in tools.items():
                print(f"  {_c(n, 'green')}: {t.description}")
    elif name == "/reset":
        mf = agent_instance.agent_meta.get("memory_file")
        if mf and os.path.exists(mf):
            os.remove(mf)
            agent_instance.memory.clear()
            print(_c(f"已重置记忆文件 {mf}", "yellow"))
        else:
            print("没有记忆文件需要重置")
    elif name == "/save":
        history = agent_instance.memory.get_history()
        if not history:
            print("没有对话可导出")
            return True
        os.makedirs("exports", exist_ok=True)
        fname = f"exports/{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"# 对话导出 - {agent_instance.agent_meta.get('agent_name', 'Agent')}\n\n")
            for msg in history:
                role = msg["role"]
                content = msg["content"] or ""
                f.write(f"## {role}\n\n{content}\n\n")
        print(_c(f"已导出到 {fname}", "green"))
    else:
        print(_c(f"未知命令: {name}，输入 /help 查看可用命令", "red"))
    return True


def _lsit_agents():
    """扫描 agents/ 目录，列出所有 .yaml 文件作为可用 Agent。"""
    agents_dir = "agents"
    if not os.path.isdir(agents_dir):
        print(f"错误：目录 {agents_dir} 不存在", file=sys.stderr)
        sys.exit(1)
    yamls = sorted(f for f in os.listdir(agents_dir) if f.endswith(".yaml"))
    if not yamls:
        print(f"{agents_dir}/ 下没有 .yaml 文件")
        return
    print("可用 Agent（用 --agent <name> 选择）：")
    for fname in yamls:
        path = os.path.join(agents_dir, fname)
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                meta = yaml.safe_load(f) or {}
            name = meta.get("agent_name","(未设置 agent_name)")
            role = meta.get("role","")
            print(f"  {fname[:-5]:<20}  name={name}  role={role[:40]}")
        except Exception as e:
            print(f"  {fname[:-5]:<20}  (解析失败: {e})")


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="MVP Agent 启动入口")
    parser.add_argument(
        "--agent",
        help="Agent 名称（如 coder）或 YAML 路径（如 agents/coder.yaml）。默认 agents/agent.yaml",
        default=None,
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出 agents/ 目录下所有可用的 Agent 配置"
    )

    parser.add_argument(
        "--model",
        help="临时指定模型，优先级高于 agent.yaml 和 .env",
        default=None,
    )

    args = parser.parse_args()

    if args.list:
        _lsit_agents()
        sys.exit(0)
    agent_yaml_path = _resolve_agent_path(args.agent) if args.agent else "agents/agent.yaml"
    agent_instance = agent.SimpleAgent(agent_yaml_path=agent_yaml_path)

    # 模型优先级：CLI --model > agent.yaml model > .env LLM_MODEL

    if args.model:
        agent_instance.model = args.model
    model_name = agent_instance.model
    print(f"=== {_c('Agent 启动', 'bold')} | config={agent_yaml_path} | name={agent_instance.agent_meta.get('agent_name', '?')} | model={model_name} ===")
    print(f"输入 {_c('/help', 'cyan')} 查看命令，{_c('exit', 'cyan')} 退出")


    while True:
        q = input("\n请输入问题: ").strip()
        if q in ["exit", "quit"]:
            break
        if q.startswith("/"):
            _handle_commond(q, agent_instance)
            continue
        if not q:
            continue
        print()
        for kind, payload in agent_instance.run_stream(q):
            if kind == "text":
                print(payload, end="", flush=True)
            elif kind == "tool_call":
                print(f" [TOOL CALL] {payload['name']} {payload['args']}", flush=True)
            elif kind == "tool_result":
                print(f"[TOOL RESULT] {payload['result']} ", flush=True)
            elif kind == "done":
                print()