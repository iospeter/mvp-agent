# mvp_agent

一个从零手写的极简 AI Agent 框架。不依赖 LangChain 等任何 Agent 库，只用 OpenAI 兼容协议的 SDK，把 Agent 的核心机制完整实现一遍。

写完这个项目的收获是：**能说清楚"用户敲一行字，程序内部到底发生了什么"**，而不是只会调框架的 API。

## 它实现了什么

**核心主循环** — 手写的 ReAct / function calling 循环：

```
问模型 → 模型说要调工具 → 执行工具 → 结果塞回对话 → 再问模型
```

反复几轮，直到模型不再需要工具、直接给出回答。最后一轮会强制撤掉工具清单，逼模型基于已有信息收尾（防止循环耗尽后返回空）。

**两种 Agent 形态** — 用同一个基类派生：

| 类型 | 说明 |
|---|---|
| `simple` | 标准主循环：一步一调用工具 |
| `plan_execute` | 先规划后执行：先让模型列出步骤，再逐步执行 |

**配置驱动** — 换一个 YAML 就是换一个 Agent：

```yaml
agent_name: CoderAgent
role: "你是一个严谨的代码审查助手。"
goal: "找出代码里的 bug 和坏味道，给出具体修改建议。"
tools:
  - calculator
tool_choice: "none"
```

角色描述和工具清单会注入 system prompt，不用改任何代码。

**插件式自动发现** — 新增工具或 Agent 不需要改任何注册表。继承基类、声明字段即可：

```python
class MyTool(BaseTool):
    name = "my_tool"
    description = "这个工具干什么用"
    class Input(BaseModel):
        arg: str
```

框架会自动扫描 `tools/` 和 `skills/` 目录并注册。Agent 同理，声明 `agent_type` 就能被工厂按 YAML 配置创建。

**流式输出** — 用生成器把增量文本、工具调用、工具结果作为事件流推给上层，实现打字机效果。工具调用的流式拼装（按 index 累积 JSON 片段）是这块最容易踩坑的地方，代码里有注释说明。

**安全求值** — 计算器工具用 AST 白名单实现，只允许数字和基本运算，拒绝函数调用、属性访问、import 等一切有注入风险的节点。**不是黑名单**（永远列不全），而是白名单。

**其他** — 死循环检测、对话记忆滑动窗口与持久化、联网搜索、实时天气、交互式 CLI（斜杠命令）、提交前密钥自检。

## 快速开始

```bash
pip install -r requirements.txt

# 复制模板并填入自己的密钥
cp .env.example .env

# 启动
python main.py

# 换个 Agent
python main.py --agent coder

# 看看有哪些 Agent
python main.py --list
```

`.env` 需要填三项：

```
LLM_BASE_URL=https://你的服务地址/v1
LLM_API_KEY=你的密钥
LLM_MODEL=模型名
```

任何兼容 OpenAI 协议的服务都能用（DeepSeek、智谱、火山方舟等，`.env.example` 里有参考配置）。

## CLI 命令

| 命令 | 作用 |
|---|---|
| `/help` | 显示帮助 |
| `/tools` | 列出当前 Agent 可用工具 |
| `/memory` | 查看记忆条数 |
| `/clear` | 清空当前会话记忆 |
| `/reset` | 删除记忆文件，完全重置 |
| `/save` | 导出对话为 Markdown |
| `exit` / `quit` | 退出 |

## 目录结构

```
mvp_agent/
├── main.py                  # 入口，CLI 交互循环
├── settings.json            # 全局配置
├── requirements.txt
├── agents/
│   ├── base.py              # Agent 基类（模板方法 + 自动注册）
│   ├── agent.py             # SimpleAgent：标准主循环
│   ├── plan_execute_agent.py# PlanExecuteAgent：先规划后执行
│   ├── registry.py          # Agent 工厂，按 YAML 的 agent_type 创建
│   ├── _dead_loop.py        # 死循环检测
│   └── *.yaml               # 各 Agent 的角色与能力配置
├── tools/
│   ├── base.py              # 工具基类（子类定义时即校验，早失败）
│   ├── registry.py          # 工具自动发现
│   ├── calculator.py        # AST 白名单安全求值
│   ├── weather_tool.py      # 实时天气
│   ├── time_tool.py         # 时区时间
│   └── web_search.py        # 联网搜索
├── skills/
│   └── data_skill.py        # 组合多个工具的技能
├── memory/
│   ├── base.py              # 记忆基类
│   └── history_store.py     # 滑动窗口 + JSON 持久化
├── prompts/
│   └── system.md            # system prompt 模板（占位符由 YAML 填充）
├── tests/
├── check_secrets.py         # 提交前密钥自检
└── verify_config.py         # 配置生效验证
```

## 几个设计取舍

**工具出错返回字符串，不抛异常。** 工具执行失败时，把错误信息作为结果返回给模型，让模型自己决定怎么回应用户，而不是让整个 Agent 崩掉。

**工具基类在子类定义时就校验。** 用 `__init_subclass__` 实现——写 `class XxxTool(BaseTool):` 这行代码的瞬间就检查 name / description / Input 有没有填，缺了当场报错。这是 fail-fast：宁可现在炸，不要带着错误配置跑到线上再炸。

**工具参数的 JSON Schema 由 Pydantic 自动生成。** 你只写三行 `expr: str`，转发给模型的 schema 就出来了，不用手写。

**记忆返回副本而非引用。** `get_history()` 返回 `.copy()`，防止外部意外修改内部状态。

## 测试

```bash
python -m pytest tests/ -v
```

其中 `test_force_tool_call` 用 mock 伪造模型响应，**不联网、不花钱、结果完全确定**，是给"依赖外部服务的代码"写测试的参考做法。其他几个用例会真实调用模型，需要 `.env` 配置正确。

## 说明

这是个人学习项目，用来把 Agent 的底层机制跑通一遍。代码里有大量中文注释，解释每一步为什么这么写。

MIT License
