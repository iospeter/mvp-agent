from agents import agent

if __name__ == '__main__':
    agent = agent.SimpleAgent()
    print("=== Demo Agent启动 ===")
    while True:
        q = input("\n请输入问题: ")
        if q in ["exit","quit"]:
            break
        res = agent.run(q)
        print(f"\n Agent输出:{res}")