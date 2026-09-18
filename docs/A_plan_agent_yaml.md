# A 方案：把 agent.yaml 打通，做成"改配置就能造 Agent"

> 本文档是**改造方案**，不是已生效的代码。
> 你自己看过后，决定要不要把里面的代码复制进项目。
> 当前项目源码未被修改。

---

## 一、改造前 vs 改造后

### 改造前（现状）

```python
# agents/agent.py 的 __init__ 里

# ① 读了但没用
self.agent_meta = yaml.safe_load(f)   # agent_name/role/goal 存进来就废了

# ② 工具硬编码
self.tools_map = {
    "calculator": CalculatorTool(),
    "search_demo": SearchDemoTool(),
    "get_current_time": GetCurrentTimeTool(),
    "weather_query": WeatherQueryTool(),
}

# ③ 人设写死
with open("prompts/system.md") as f:
    self.system_prompt = f.read()      # 改人设必须改这个文件
```

**三个病症**：
- 改 `agent.yaml` 没任何效果（假配置）
- 加工具要改 `agent.py` 源码（硬编码）
- 换人设要重写 `system.md`（写死）

### 改造后

```python
# agents/agent.py 的 __init__ 里

# ① 读配置，真正使用
self.agent_meta = yaml.safe_load(f)       # 里面现在多了 tools 列表
self.tools_map = build_tools(self.agent_meta["tools"])   # 按配置动态建工具表

# ② 人设 = 模板 + 配置
self.system_prompt = render_system_prompt(
    self.agent_meta, self.tools_map
)   # 把 role/goal/tool 描述填进模板
```

**改配置就能换 Agent**：
- 改 `agent.yaml` 的 `role`/`goal` → 人设立刻变
- 改 `agent.yaml` 的 `tools` 列表 → 工具立刻变
- 复制一份 `agent.yaml` 改成 `writer.yaml` → 就是第二个 Agent

---

## 二、文件清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `agents/agent.yaml` | **重写** | 新增 `tools` 列表、`system_prompt` 字段 |
| `prompts/system.md` | **改成模板** | 加入 `{role}` `{goal}` `{tools}` 占位符 |
| `tools/registry.py` | **新增** | 工具注册表，名字 → 类 的映射 |
| `agents/agent.py` | **改 4 处** | 用注册表建 tools_map、用配置渲染提示词 |
| `verify_config.py` | **新增** | 验证脚本，跑一下就知道配置生效没 |

---

## 三、具体代码

### 3.1 `tools/registry.py`（新增文件）

工具注册表。它解决的问题是：**让"名字"和"工具类"能对上**，这样 YAML 里只写名字就行。

```python
"""
tools/registry.py —— 工具注册表。

作用：维护"工具名 → 工具类"的映射关系。
这样 agent.yaml 里只需写工具名（如 "calculator"），
程序就能靠这张表找到对应的类并创建实例。
"""

from tools import CalculatorTool, SearchDemoTool, GetCurrentTimeTool, WeatherQueryTool

# ★ 注册表：想加新工具，在这里加一行就够了。
#   这是全项目唯一需要改动的"工具清单"位置。
_TOOL_CLASSES = {
    "calculator": CalculatorTool,
    "search_demo": SearchDemoTool,
    "get_current_time": GetCurrentTimeTool,
    "weather_query": WeatherQueryTool,
}


def available_tool_names() -> list:
    """返回所有已注册的工具名，方便报错时提示用户可选哪些。"""
    return list(_TOOL_CLASSES.keys())


def build_tools(tool_names: list) -> dict:
    """根据配置里的工具名列表，创建 {名字: 实例} 的字典。

        参数：
          tool_names —— 如 ["calculator", "weather_query"]

        返回：
          {"calculator": <CalculatorTool对象>, "weather_query": <...>}

        ★ 早失败：如果 YAML 里写了不存在的工具名，直接报错并列出可选项，
          而不是静默跳过（否则你会困惑"为什么我配了工具却不生效"）。
        """
    result = {}
    for name in tool_names:
        if name not in _TOOL_CLASSES:
            raise ValueError(
                f"agent.yaml 里配置了未知工具 '{name}'。\n"
                f"可用的工具有：{', '.join(available_tool_names())}"
            )
        result[name] = _TOOL_CLASSES[name]()   # 类名加括号 = 创建实例
    return result
```

**为什么用"名字→类"而不是"名字→实例"？**
因为实例一旦创建就固定了，而类可以按需创建。更重要的是：将来如果想做"每个会话独立的工具实例"（比如带状态的工具），用类更灵活。

---

### 3.2 `agents/agent.yaml`（重写）

```yaml
# agents/agent.yaml —— Agent 的角色与能力定义
#
# ★ 这个文件决定了"这是个什么 Agent"。
#   复制它成 writer.yaml、coder.yaml，就是另一个 Agent。

agent_name: DemoAgent

# 角色定位。会注入 system prompt，直接影响模型的说话风格。
role: "你是一个实用助手，擅长用工具解决用户的实际问题。"

# 目标。告诉模型它存在的意义，引导它优先做对的事。
goal: "准确回答用户问题，需要数据时优先调用工具，绝不编造信息。"

# ★ 新增：这个 Agent 能使用哪些工具。
#   名字必须和 tools/registry.py 里的一致。
#   删掉某一行，模型就再也看不到这个工具。
tools:
  - calculator
  - weather_query
  - get_current_time

# 可选：回答语言。留空则用 system.md 模板里的默认值。
language: "中文"

# 可选：是否允许模型自己决定用哪个工具。
#   auto = 允许（默认）；none = 完全禁用工具
tool_choice: "auto"
```

**注意我特意没放 `search_demo`**。因为它是假实现，放进配置会让模型真的去调它然后拿到一句废话。你可以自己决定要不要加回来。

---

### 3.3 `prompts/system.md`（改成模板）

关键是把角色部分换成占位符：

```markdown
{role}

你的目标：{goal}

输出语言使用{language}。

# 你可以使用的工具

{tools}

# 工具调用纪律

1. 当你已经获得足够回答用户的信息时，直接用自然语言给出最终答案，不要继续调用工具。
2. 如果判断需要多步操作，可以连续调用工具，但每次调用都要基于上一次工具结果。
3. 不要重复调用相同参数的工具，避免陷入死循环。
4. 如果工具返回错误或未找到结果，告知用户现状，不要臆测数据。
5. 需要计算或查询实时信息时，优先调用工具，不要凭记忆瞎编。
```

**为什么用 `{xxx}` 这种占位符？**
因为 Python 的字符串有内置的 `.format()` 方法，能直接替换：

```python
"你好{name}".format(name="老游")   # → "你好老游"
```

不用引入任何第三方模板引擎。简单、够用。

**⚠️ 有个坑要注意**：如果文本里本来就有花括号（比如 JSON 示例 `{"a":1}`），`.format()` 会把它当占位符解析然后报错。解决办法是用双花括号转义 `{{` `}}`。这个模板里目前没有花括号，安全。

---

### 3.4 `agents/agent.py`（改 4 处）

只列改动部分，其余代码不动。

#### 改动 1：导入注册表

```python
# 原来这行可以删掉（不再直接依赖具体工具类）
# from tools import CalculatorTool, SearchDemoTool, GetCurrentTimeTool, WeatherQueryTool

# 改成导入注册表
from tools.registry import build_tools
```

#### 改动 2：`__init__` 里用配置建工具表

```python
    def __init__(self, settings_path: str = "settings.json", agent_yaml_path="agents/agent.yaml"):
        with open(settings_path, "r", encoding="utf-8") as f:
            self.settings = json.load(f)

        with open(agent_yaml_path, "r", encoding="utf-8") as f:
            self.agent_meta = yaml.safe_load(f)

        self.client = OpenAI(
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LLM_API_KEY"),
        )
        self.model = os.getenv("LLM_MODEL")

        self.memory = ChatHistoryMemory(max_len=self.settings["memory_max_history"])

        # ★★★ 改动点：工具表从配置来，不再硬编码 ★★★
        self.tools_map = build_tools(self.agent_meta.get("tools", []))

        # ★★★ 改动点：人设 = 模板 + 配置渲染 ★★★
        # 原来的 `self.system_prompt = f.read()` 换成下面这个
        self.system_prompt = self._render_system_prompt(
            template_path="prompts/system.md",
            tools_map=self.tools_map,
        )
```

#### 改动 3：新增渲染方法

```python
    def _render_system_prompt(self, template_path: str, tools_map: dict) -> str:
        """把 agent.yaml 的配置和工具清单填进 system.md 模板。

            ★ 这是"配置驱动"的核心：
              以后改人设只需改 YAML，不用碰这个文件，也不用碰模板。
            """
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        # ---- 拼出工具说明文本 ----
        # 格式："- calculator: 执行数学计算，输入表达式字符串"
        # 不用 list_tool_desc() 了，那个方法格式不适合直接放进提示词
        lines = []
        for name, tool in tools_map.items():
            lines.append(f"- {name}: {tool.description}")

        tools_text = "\n".join(lines) if lines else "（本 Agent 当前没有可用工具）"

        # ---- 填模板 ----
        # .get(键, 默认值) 保证 YAML 里没写这个字段也不会崩
        return template.format(
            role=self.agent_meta.get("role", "你是一个实用的AI助手。"),
            goal=self.agent_meta.get("goal", "准确回答用户的问题。"),
            tools=tools_text,
            language=self.agent_meta.get("language", "中文"),
        )
```

#### 改动 4：让 `tool_choice` 也支持配置

在 `run()` 和 `run_stream()` 的方法签名里，把默认值改成从配置读：

```python
    def run_stream(self, user_query: str, tool_choice=None, max_iterations: int = 5):
        # ★ 改动点：调用方没传就用配置里的值
        if tool_choice is None:
            tool_choice = self.agent_meta.get("tool_choice", "auto")

        # ... 下面代码完全不变
```

`run()` 同理改。

**为什么用 `None` 当默认值而不是直接写 `"auto"`？**
因为如果默认值写成 `"auto"`，就没法区分"调用方没传"和"调用方明确想要 auto"。用 `None` 做哨兵值，才能实现"没传就查配置"。

---

### 3.5 `verify_config.py`（新增，验证用）

```python
"""
verify_config.py —— 验证 agent.yaml 配置是否真正生效。

运行方式（在项目根目录）：
    python verify_config.py

它会打印出最终生成的 system prompt，
你就能直观看到 YAML 里的 role/goal/tools 有没有被注入。
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
```

**这个脚本的价值**：改造完成后，跑一下立刻知道通没通。比"启动 Agent 问一句看反应"可靠得多。

---

## 四、动手顺序（建议）

按这个顺序做，每步都能验证，不会卡住：

| 步骤 | 做什么 | 怎么验证 |
|---|---|---|
| 1 | 新建 `tools/registry.py` | `python -c "from tools.registry import available_tool_names; print(available_tool_names())"` 应输出 4 个工具名 |
| 2 | 重写 `agents/agent.yaml` | 用 `python -c "import yaml; print(yaml.safe_load(open('agents/agent.yaml',encoding='utf-8')))"` 检查能否解析 |
| 3 | 改 `prompts/system.md` 为模板 | 先别急，等第 4 步一起测 |
| 4 | 改 `agents/agent.py` 的 4 处 | 跑 `python verify_config.py` |
| 5 | 端到端测试 | `python main.py`，问"1+2等于几"和"上海天气" |
| 6 | 跑回归测试 | `python -m pytest tests/ -v`（5 个应该仍全过） |

---

## 五、做完之后能干什么

这一步打通后，你会得到**三个立刻可用的能力**：

### 1. 造不同的 Agent，只改 YAML

复制 `agent.yaml` 成 `coder.yaml`：

```yaml
agent_name: CoderAgent
role: "你是一个严谨的代码审查助手。"
goal: "找出代码里的 bug 和坏味道，给出具体修改建议。"
tools:
  - calculator
language: "中文"
tool_choice: "none"      # 代码审查不需要工具
```

然后在 `main.py` 里换成 `SimpleAgent(agent_yaml_path="agents/coder.yaml")`——这就是另一个 Agent。

### 2. 加工具只需要改两个地方

以前要改 `agent.py`、`tools/__init__.py`、可能还有别处。现在：
- 写工具类（`tools/xxx.py`）
- 在 `tools/registry.py` 的 `_TOOL_CLASSES` 加一行
- 在 `agent.yaml` 的 `tools` 列表加个名字

**这就是你希望的"配置驱动"。**

### 3. 顺带解决了 skills 孤儿问题

`skills/` 那个模块之所以是孤儿，是因为它没接进 `tools_map`。

现在有了注册表，只要把技能也注册进去：

```python
# tools/registry.py 里加
from skills import AnalysisSkill

_TOOL_CLASSES = {
    ...
    "analysis": AnalysisSkill,     # 就这一行
}
```

**⚠️ 但有个前提**：`AnalysisSkill` 现在不是 `BaseTool` 的子类，所以不能直接注册。需要先改造它——让它继承 `BaseTool`、定义 `name`/`description`/`Input`。这个改造我建议放到下一步单独做，别和这次混在一起，否则出问题不好定位。

---

## 六、改动风险提示

| 风险 | 说明 | 应对 |
|---|---|---|
| `.format()` 和花括号冲突 | 如果 system.md 里出现 `{` `}`（如 JSON 示例），会报 KeyError | 用 `{{` `}}` 转义；或改用 `string.Template` 的 `$role` 语法 |
| YAML 工具名写错 | 会直接抛 ValueError | 这是好事，报错信息里会列出所有可用工具名 |
| 现有测试可能失败 | `test_force_tool_call` 强制调 `calculator`，如果 YAML 里删了它就会失败 | 保持 YAML 里包含 `calculator` |
| 配置文件路径 | 仍是相对路径，必须在项目根目录运行 | 后续可改成 `Path(__file__).parent` 定位 |

---

## 七、可选进阶（本次不做）

如果这一步做完你觉得顺手了，下一步可以：

1. **多 Agent 并存**：`agents/` 下放多个 yaml，`main.py` 启动时选一个
2. **工具级开关**：在 YAML 里给每个工具加 `enabled: true/false`
3. **技能层**：把 `AnalysisSkill` 改造成 BaseTool 子类，真正接入
4. **配置校验**：启动时检查 YAML 必填字段，缺了就报错（参考 `BaseTool.__init_subclass__` 的早失败思路）
