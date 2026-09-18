from abc import ABC, abstractmethod
from typing import Dict, List

class BaseMemory(ABC):

    @abstractmethod
    def add(self, role:str, content:str):
        pass

    @abstractmethod
    def get_history(self) -> List[Dict]:
        pass

    @abstractmethod
    def clear(self):
        pass

    def save_to(self, path:str)->None:
        """从文件加载历史记录。文件不存在视为空记忆，不报错。"""
        pass

    def load_from(self, path:str)->None:
        """从文件加载历史记录。文件不存在视为空记忆，不报错。"""
        pass