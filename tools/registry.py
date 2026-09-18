import importlib
import pkgutil

from tools import BaseTool

_SCAN_PACKAGES = ("tools", "skills")
_discovered = False

def auto_discover() -> None:
    """扫描包目录并导入所有模块，触发 BaseTool.__init_subclass__ 自动注册。

        - 模块名以 _ 开头视为私有/测试辅助，跳过（如 _test_tools.py）
        - 幂等：重复调用只扫一次
        """
    global _discovered
    if _discovered:
        return
    for pkg_name in _SCAN_PACKAGES:
        pkg = importlib.import_module(pkg_name)
        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name.startswith("_"):
                continue
            importlib.import_module(f"{pkg_name}.{info.name}")
    _discovered = True


def available_tool_names() -> list:
    """返回所有已注册的工具名，方便报错时提示用户可选哪些。"""
    auto_discover()
    return sorted(BaseTool._registry.keys())

def build_tools(tool_names: list) -> dict:
    """按 YAML 配置的工具名列表实例化工具。未知工具名直接报错。"""
    auto_discover()
    result = {}
    for name in tool_names:
        if name not in BaseTool._registry:
            raise ValueError(
                f"agent.yaml 里配置了未知工具'{name}'"
            )
        result[name] = BaseTool._registry[name]()
    return result
