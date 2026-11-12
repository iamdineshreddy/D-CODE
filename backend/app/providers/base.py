from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class ProviderAdapter(ABC):
    name: str = "base"

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def discover_models(self) -> List[Dict[str, Any]]:
        ...

    async def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    def metadata(self) -> Dict[str, Any]:
        return {"name": self.name}
