"""
verify_config.py —— 验证 agent.yaml 配置是否真正生效。

运行方式（在项目根目录）：
    python verify_config.py                      # 验证默认 agents/agent.yaml
    python verify_config.py --agent coder        # 按 short name 验证
    python verify_config.py --agent agents/coder.yaml  # 按完整路径验证
"""

import argparse
import os.path
import sys

from agents.agent import SimpleAgent

# Windows 控制台默认 GBK，✓ 等字符会 UnicodeEncodeError，强制 UTF-8 输出
sys.stdout.reconfigure(encoding="utf-8")


def _resolve_agent_path(name_or_path: str) -> str:
    """把 --agent 的值解析成实际 YAML 路径。

    支持：--agent coder  →  agents/coder.yaml
          --agent agents/coder.yaml  →  原样使用
    """
    if os.path.exists(name_or_path):
        return name_or_path
    candidate = os.path.join("agents", f"{name_or_path}.yaml")
    if os.path.exists(candidate):
        return candidate
    print(f"错误：找不到 Agent 配置 '{name_or_path}'（也试过 {candidate}）", file=sys.stderr)
    sys.exit(1)


parser = argparse.ArgumentParser(description="验证 Agent YAML 配置是否生效")
parser.add_argument(
    "--agent",
    help="Agent 名称（如 coder）或 YAML 路径。默认 agents/agent.yaml",
    default=None,
)
args = parser.parse_args()

agent_yaml_path = _resolve_agent_path(args.agent) if args.agent else "agents/agent.yaml"
agent = SimpleAgent(agent_yaml_path=agent_yaml_path)

print(f"验证配置：{agent_yaml_path}")
print("=" * 60)
print("① 从 agent.yaml 读到的配置")
print("=" * 60)
for key, value in agent.agent_meta.items():
    print(f"  {key}: {value}")

print()
print("=" * 60)
print("② 根据配置创建的工具表")
print("=" * 60)
print(f"  共 {len(agent.tools_map)} 个工具")
for name in agent.tools_map:
    print(f"  - {name}")

print()
print("=" * 60)
print("③ 最终生成的 system prompt")
print("=" * 60)
print(agent.system_prompt)

print()
print("=" * 60)
print("④ 自动检查")
print("=" * 60)
ok = True

if "{role}" in agent.system_prompt or "{goal}" in agent.system_prompt:
    print("  ✗ 模板占位符没被替换，检查 system.md 和 .format() 参数名")
    ok = False
else:
    print("  ✓ 占位符已全部替换")

if agent.agent_meta.get("role", "")[:10] in agent.system_prompt:
    print("  ✓ YAML 的 role 已注入 system prompt")
else:
    print("  ✗ YAML 的 role 没有出现在 system prompt 里")
    ok = False

expected = agent.agent_meta.get("tools", [])
if set(expected) == set(agent.tools_map.keys()):
    print(f"  ✓ 工具表与配置一致（{len(expected)} 个）")
else:
    print(f"  ✗ 工具表与配置不一致：配置={expected}，实际={list(agent.tools_map)}")
    ok = False

print()
print("结论：" + ("全部通过，配置已生效" if ok else "存在问题，见上面 ✗ 项"))