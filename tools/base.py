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

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.name: raise ValueError(f"工具类 {cls.__name__} 必须定义非空的 name")
        if not cls.description: raise ValueError(f"工具类 {cls.__name__} 必须定义非空的 description")
        if not getattr(cls, "Input", None): raise ValueError(f"工具类 {cls.__name__} 必须定义 Input Pydantic 模型")

    @abstractmethod
    def run(self, **kwargs) -> str:
        """执行工具，返回字符串结果。"""
        pass

