from abc import ABC, abstractmethod
from typing import Type
from pydantic import BaseModel


class BaseTool(ABC):
    """所有工具的抽象基类。

        约定：子类必须定义 name、description、Input（Pydantic 模型）和 run 方法。
        在子类定义时自动校验，缺字段会立即报错，避免运行时才发现。
        """
    name:str = ""
    description:str = ""
    Input:Type[BaseModel]  # 每个工具必须定义

    # 自动注册表：key=工具名，value=工具类。registry.py 从这里读取
    _registry: dict = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.name: raise ValueError(f"工具类 {cls.__name__} 必须定义非空的 name")
        if not cls.description: raise ValueError(f"工具类 {cls.__name__} 必须定义非空的 description")
        if not getattr(cls, "Input", None): raise ValueError(f"工具类 {cls.__name__} 必须定义 Input Pydantic 模型")

        # 只注册"自己声明了 name"的具体子类：抽象中间层、继承父类 name 的子类跳过
        if "name" not in cls.__dict__:
            return
        if getattr(cls, "__abstractmethods__", frozenset()):
            return

        if cls.name in BaseTool._registry:
            existinig = BaseTool._registry[cls.name]
            raise ValueError(
                f"工具名冲突: '{cls.name}' 已被 {existinig.__module__}.{existinig.__qualname__} 注册,"
                f"冲突方：{cls.__module__}.{cls.__name__}"
            )
        BaseTool._registry[cls.name] = cls

    @abstractmethod
    def run(self, **kwargs) -> str:
        """执行工具，返回字符串结果。"""
        pass

