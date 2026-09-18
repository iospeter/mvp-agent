import argparse
import os.path
import sys

from agents import agent

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
    args = parser.parse_args()

    if args.list:
        _lsit_agents()
        sys.exit(0)
    agent_yaml_path = _resolve_agent_path(args.agent) if args.agent else "agents/agent.yaml"
    agent_instance = agent.SimpleAgent(agent_yaml_path=agent_yaml_path)
    print(f"=== Agent 启动（流式输出） | config={agent_yaml_path} | name={agent_instance.agent_meta.get('agent_name', '?')} ===")


    while True:
        q = input("\n请输入问题: ").strip()
        if q in ["exit", "quit"]:
            break
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