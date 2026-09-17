from agents import agent

# if __name__ == '__main__':
#     agent = agent.SimpleAgent()
#     print("=== Demo Agent启动 ===")
#     while True:
#         q = input("\n请输入问题: ")
#         if q in ["exit","quit"]:
#             break
#         res = agent.run_stream(q)
#         print(f"\n Agent输出:{res}")

if __name__ == '__main__':
    agent = agent.SimpleAgent()
    print("=== Demo Agent 启动（流式输出） ===")
    while True:
        q = input("\n请输入问题: ").strip()
        if q in ["exit","quit"]:
            break
        print()
        for kind, payload in agent.run_stream(q):
            if kind == "text":
                print(payload, end="", flush=True)
            elif kind == "tool_call":
                print(f" [TOOL CALL] {payload['name']} {payload['args']}", flush=True)
            elif kind == "tool_result":
                print(f"[TOOL RESULT] {payload['result']} ", flush=True)
            elif kind == "done":
                print()