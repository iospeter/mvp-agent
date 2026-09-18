
from tools import CalculatorTool, SearchDemoTool,WeatherQueryTool,GetCurrentTimeTool, WebSearchTool
from skills.data_skill import AnalysisSkill
# ★ 注册表：想加新工具，在这里加一行就够了。 #   这是全项目唯一需要改动的"工具清单"位置。
_TOOLS_CLASSES = {
    "calculator": CalculatorTool,
    "search_demo": SearchDemoTool,
    "weather_query": WeatherQueryTool,
    "get_current_time": GetCurrentTimeTool,
    "analysis": AnalysisSkill,
    "web_search": WebSearchTool
}


def available_tool_names() -> list:
    """返回所有已注册的工具名，方便报错时提示用户可选哪些。"""
    return list(_TOOLS_CLASSES.keys())

def build_tools(tool_names: list) -> dict:
    result = {}
    for name in tool_names:
        if name not in _TOOLS_CLASSES:
            raise ValueError(
                f"agent.yaml 里配置了未知工具"
                f"可用的工具有： {', '.join(available_tool_names())} "
            )
        result[name] = _TOOLS_CLASSES[name]()
    return result
