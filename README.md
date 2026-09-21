<div align="center">

# mvp_agent

**从零手写的极简 AI Agent 框架 —— 不依赖 LangChain，只用 OpenAI 兼容协议的官方 SDK 把 Agent 的核心机制自己实现一遍。**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![OpenAI SDK](https://img.shields.io/badge/OpenAI-SDK%20v1-412991?style=flat-square&logo=openai&logoColor=white)](https://github.com/openai/openai-python)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat-square&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![License](https://img.shields.io/badge/License-MIT-3DA639?style=flat-square)](LICENSE)
[![No Framework](https://img.shields.io/badge/framework-none-ff69b4?style=flat-square)](#)

**目标不是"能跑起来"，是能说清楚"用户敲一行字，程序内部到底发生了什么"。**

[快速开始](#快速开始) · [核心机制](#核心机制) · [配置 Agent](#配置-agent) · [踩过的坑](#踩过的坑) · [设计取舍](#设计取舍)

</div>

---

## 为什么写它

市面上的 Agent 教程大多停在"调 API"这一层：装个框架、填个 Key、跑通 demo。但你真的知道 `tool_calls` 是怎么变成一次真实函数调用的吗？流式输出的时候，那些碎片的 tool call 参数是怎么拼回来的？

这个项目就是把这些**全部拆开重写一遍**。不引入任何 Agent 框架，只用最底层的 SDK 原语。

| 你能学到 | 在哪个文件 |
|---|---|
| ReAct / function calling 主循环怎么转 | `agents/agent.py` |
| 流式 tool_calls 的碎片怎么按 index 拼装 | `agents/agent.py` |
| 怎么用 `__init_subclass__` 做插件式自动注册 | `tools/base.py` |
| 配置驱动的人设注入（模板 + `.format()`） | `agents/base.py` |
| 滑动窗口记忆 + 滚动摘要 | `memory/history_store.py` |
| AST 白名单实现安全求值 | `tools/calculator.py` |
| 怎么给依赖外部服务的代码写确定性的测试 | `tests/test_agent.py` |

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 复制模板并填入自己的密钥
cp .env.example .env

# 3. 启动（默认加载 agents/agent.yaml）
python main.py
```

`.env` 需要填三项：

```ini
LLM_BASE_URL=https://你的服务地址/v1
LLM_API_KEY=你的密钥
LLM_MODEL=模型名
```

任何兼容 OpenAI 协议的服务都能用，`.env.example` 里给了 DeepSeek / 智谱 GLM / 火山方舟的参考配置。

### 常用命令

```bash
python main.py --list                          # 列出所有可用 Agent
python main.py --agent coder                   # 换个 Agent
python main.py --agent planner --model glm-4-flash   # 临时指定模型（优先级最高）
```

**模型优先级**：`--model` > `agent.yaml` 的 `model` 字段 > `.env` 的 `LLM_MODEL`

### 开箱可用的三份配置

| 名称 | 类型 | 工具 | 说明 |
|---|---|:--:|---|
| `agent` | `simple` | 5 个 | 默认全能助手 |
| `coder` | `simple` | 无 | 纯代码审查，`tool_choice: none` |
| `planner` | `plan_execute` | 3 个 | 演示先规划后执行 |

---

## 核心机制

### 主循环：ReAct / function calling

```
问模型 → 模型说要调工具 → 执行工具 → 结果塞回对话 → 再问模型
```

反复几轮，直到模型不再需要工具、直接给出回答。两个关键细节：

- **最后一轮强制撤掉工具清单**（`tools=[]` + `tool_choice="none"`），逼模型基于已有信息收尾，防止循环耗尽后返回空字符串。
- **每轮的 `assistant` 消息、工具结果都要按协议塞回 `messages`**，否则模型会丢失上下文。流式模式下这一步最容易写错。

### 两种 Agent 形态

| `agent_type` | 类 | 行为 |
|---|---|---|
| `simple` | `SimpleAgent` | 标准主循环，一步一次工具调用 |
| `plan_execute` | `PlanExecuteAgent` | 先规划后执行：先用**禁用工具**的请求逼模型输出编号步骤，再把计划注入问题交给标准循环 |

两者是继承关系（`PlanExecuteAgent(SimpleAgent)`），只覆写 `run` / `run_stream` 和记忆注入钩子 `to_memory_query` / `to_context_query`。

### 流式事件协议

用生成器把增量文本、工具调用、工具结果作为事件流推给上层，实现打字机效果：

| 事件 | payload | 含义 |
|---|---|---|
| `text` | `str` | 回答的增量文本片段 |
| `tool_call` | `{name, args}` | 即将执行工具 |
| `tool_result` | `{name, result}` | 工具执行结果 |
| `done` | `str` | 本轮最终完整文本 |

### 插件式自动发现

加工具不用改任何注册表。继承基类、声明字段即可：

```python
class MyTool(BaseTool):
    name = "my_tool"
    description = "这个工具干什么用"
    class Input(BaseModel):
        arg: str
    def run(self, arg: str) -> str:
        return "结果"
```

框架自动扫描 `tools/` 和 `skills/` 目录并注册（模块名以 `_` 开头的跳过）。Agent 同理，声明 `agent_type` 即被工厂按 YAML 创建，重复注册会在导入时直接抛错。

### 其他能力

死循环检测（工具名 + 参数签名重复 N 次即中断）· 记忆滑动窗口 + 滚动摘要 + JSON 持久化 · Bing 国内版联网搜索（附首条正文摘录）· wttr.in 实时天气 · IANA 时区时间 · 交互式 CLI 斜杠命令 · 提交前密钥自检

---

## 配置 Agent

**换一份 YAML 就是换一个 Agent，不改一行代码。**

```yaml
agent_name: CoderAgent
role: "你是一个严谨的代码审查助手。"
goal: "找出代码里的 bug 和坏味道，给出具体修改建议。"
tools: []
tool_choice: "none"
```

`role` / `goal` / 工具清单会渲染进 `prompts/system.md` 模板：

```markdown
{role}

你的目标：{goal}

输出语言使用{language}。

# 你可以使用的工具

{tools}
```

### 字段说明

| 字段 | 必填 | 说明 |
|---|:--:|---|
| `agent_name` | ✅ | Agent 名字，启动横幅和导出文件里会显示 |
| `role` | ✅ | 角色定位，注入 system prompt，决定说话风格 |
| `goal` | ✅ | 存在意义，引导模型优先做对的事 |
| `agent_type` | | `simple`（默认）/ `plan_execute` |
| `tools` | | 工具名列表，必须是列表；名字写错直接报错 |
| `tool_choice` | | `auto`（默认）/ `none`（禁用） |
| `memory_file` | | 持久化路径。不填则每次启动都是新会话 |
| `language` | | 回答语言，不填用模板默认值"中文" |
| `model` | | 指定模型，不填则用 `.env` 的 `LLM_MODEL` |

> 必填字段缺了会在启动时直接抛 `ValueError`（`BaseAgent._validate_agent_meta`），不会带着错配置跑到线上。

---

## CLI 命令

| 命令 | 作用 |
|---|---|
| `/help` | 显示帮助 |
| `/tools` | 列出当前 Agent 可用工具及其描述 |
| `/memory` | 查看当前记忆条数 |
| `/clear` | 清空当前会话记忆（内存） |
| `/reset` | 删除记忆文件，完全重置 |
| `/save` | 导出对话为 Markdown（写入 `exports/`） |
| `exit` / `quit` | 退出 |

---

## 项目结构

```
mvp_agent/
├── main.py                   # 入口：CLI 交互循环 + 斜杠命令
├── settings.json             # 全局配置（记忆窗口长度）
├── requirements.txt
├── .env.example              # 环境变量模板（可提交，.env 不行）
├── agents/
│   ├── base.py               # BaseAgent：配置加载/校验、记忆、工具、prompt 渲染
│   ├── agent.py              # SimpleAgent：标准主循环（run / run_stream）
│   ├── plan_execute_agent.py # PlanExecuteAgent：先规划后执行
│   ├── registry.py           # Agent 工厂：按 YAML 的 agent_type 创建
│   ├── _dead_loop.py         # 死循环检测
│   ├── agent.yaml            # 默认全能助手
│   ├── coder.yaml            # 代码审查（无工具）
│   └── planner.yaml          # 规划执行型
├── tools/
│   ├── base.py               # BaseTool：子类定义时即校验（fail-fast）
│   ├── registry.py           # 工具自动发现 + 按名构建
│   ├── calculator.py         # AST 白名单安全求值
│   ├── weather_tool.py       # wttr.in 实时天气
│   ├── time_tool.py          # IANA 时区时间
│   ├── web_search.py         # Bing 国内版搜索 + 首条正文摘录
│   └── search_demo.py        # 假实现，演示用的空壳
├── skills/
│   └── data_skill.py         # AnalysisSkill：组合 calculator + web_search
├── memory/
│   ├── base.py               # BaseMemory 抽象基类
│   └── history_store.py      # 滑动窗口 + 滚动摘要 + JSON 持久化
├── prompts/
│   └── system.md             # system prompt 模板
├── tests/
│   ├── test_agent.py         # 需要 .env 有效，会真实调用模型
│   └── test_dead_loop.py     # 纯本地，不联网
├── docs/
│   └── A_plan_agent_yaml.md  # 配置驱动改造的设计文档（留作记录）
├── check_secrets.py          # 提交前密钥自检
└── verify_config.py          # 配置生效验证
```

---

## 扩展：加工具 / 加 Agent

<details>
<summary><b>加一个新工具</b>（两处，都不用碰 <code>__init__.py</code>）</summary>

1. 在 `tools/` 下写类，继承 `BaseTool`，定义 `name` / `description` / `Input` / `run`
2. 在某个 `agent.yaml` 的 `tools` 列表加上这个名字

`tools/registry.py` 会扫描 `tools/` 和 `skills/` 两个目录，模块名以 `_` 开头的（如 `_test_tools.py`）视为私有，跳过。

</details>

<details>
<summary><b>加一个新 Agent</b></summary>

1. 在 `agents/` 下写类，继承 `BaseAgent`（或 `SimpleAgent`），声明 `agent_type = "xxx"`，覆写 `run` / `run_stream`
2. 写一份 YAML，`agent_type: xxx`

`agent_type` 重复会在导入时直接抛错，不会静默覆盖。

</details>

---

## 验证与测试

```bash
# 1. 配置生效验证 —— 改了 YAML 之后先跑这个
python verify_config.py
python verify_config.py --agent coder

# 2. 单元测试
python -m pytest tests/ -v
```

`verify_config.py` 会输出四段：读到的配置 / 建出的工具表 / 最终 system prompt / 自动检查。全通过时打印 `结论：全部通过，配置已生效`。

### 测试现状（务必注意）

| 文件 | 用例数 | 联网 | 说明 |
|---|:--:|:--:|---|
| `tests/test_dead_loop.py` | 5 | ❌ | 纯本地、结果完全确定，必过 |
| `tests/test_agent.py` | 5 | ✅ | 真实调用模型，慢且花钱 |

- 没有 `.env` 时，`test_agent.py` 全部报 `OpenAIError: api_key client option must be set`，这是**预期行为，不是代码 bug**。
- 其中 `test_force_tool_call` 用 mock 伪造模型响应，是给"依赖外部服务的代码"写确定性测试的参考做法。
- ⚠️ 用例结构受 `agents/agent.yaml` 影响：它断言 `1+2` 会调用 `calculator`。**改默认配置前先想一下测试。**

---

## 踩过的坑

> 写在这里省得你再踩一次。

<details>
<summary><b>流式 tool_calls 必须按 index 累积</b></summary>

流式的 tool call 是碎片式的：第一个 chunk 带 `id` 和函数名，后续 chunk 只带 `arguments` 的字符串片段。必须按 `tc.index` 建累积器拼装。

**并且回填 `messages` 时要用累积器里的 `id`，不能用循环变量 `tc.id`** —— 多数厂商只在首个 chunk 带 id，后面是 `None`。

</details>

<details>
<summary><b><code>.env</code> 曾把真实密钥提交上去过</b></summary>

所以现在有 `check_secrets.py`。靠人记住"别提交 .env"是不可靠的，得让机器兜住：

```bash
python check_secrets.py
```

它扫描 git 暂存区文件，命中疑似密钥（`sk-*`、`api_key=`、Bearer token、云厂商密钥格式）就报警并返回退出码 1。建议接成 pre-commit 钩子，接法见脚本文件末尾注释。

</details>

<details>
<summary><b><code>verify_config.py</code> 用的类写死的是 <code>SimpleAgent</code></b></summary>

拿它验证 `planner.yaml`（`agent_type: plan_execute`）时，Agent 类型其实是错的，只能用来核对 role/tools 有没有正确注入，别当成完整验证。

</details>

<details>
<summary><b>配置路径是相对路径</b></summary>

所有脚本都必须在项目根目录运行，否则找不到 `agents/agent.yaml`。后续可以改成 `Path(__file__).parent` 定位。

</details>

---

## 设计取舍

| 决策 | 理由 |
|---|---|
| **工具出错返回字符串，不抛异常** | 让模型自己决定怎么回应用户，而不是让整个 Agent 崩掉 |
| **工具基类在子类定义时就校验** | 用 `__init_subclass__`，写 `class Xxx(BaseTool):` 那行就检查 `name`/`description`/`Input`。宁可导入时炸，不要带着错配置跑到线上炸 |
| **只注册"自己声明了字段"的子类** | 抽象中间层、继承父类 `name` 的子类会被跳过，避免意外覆盖 registry |
| **JSON Schema 由 Pydantic 自动生成** | 只写三行 `arg: str`，转发给模型的 schema 就出来了 |
| **记忆返回副本而非引用** | `get_history()` 返回 `.copy()`，防止外部意外修改内部状态 |
| **记忆溢出折入摘要而非丢弃** | 抽取式摘要（不依赖 LLM 调用），标注"可能不完整"，且有字符上限 |
| **安全求值是白名单，不是黑名单** | AST 遍历只允许数字常量和四则运算，拒绝函数调用/属性访问/import。黑名单永远列不全 |
| **`tool_choice` 默认值用 `None`** | 才能区分"调用方没传"和"明确想要 auto"，没传时去 YAML 查配置 |

---

## 说明

这是个人学习项目，用来把 Agent 的底层机制跑通一遍。代码里有大量中文注释，解释每一步为什么这么写。

如果这个项目帮你搞懂了 Agent 内部怎么转，给个 ⭐ 就行。

[MIT License](LICENSE)
