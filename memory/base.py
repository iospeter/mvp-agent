from abc import ABC, abstractmethod
from typing import Dict, List

class BaseMemory(ABC):

    @abstractmethod
    def add(self,role:str, content:str):
        pass

    @abstractmethod
    def get_history(self) -> List[Dict]:
        pass

    @abstractmethod
    def clear(self):
        pass