"""
verify_config.py —— 验证 agent.yaml 配置是否真正生效。

运行方式（在项目根目录）：
    python verify_config.py
"""

from agents.agent import SimpleAgent

agent = SimpleAgent()

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