from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass


@dataclass
class ImageGenerationResult:
    success: bool
    image_url: Optional[str] = None
    image_base64: Optional[str] = None
    error_message: Optional[str] = None
    
    @property
    def has_image(self) -> bool:
        return self.image_url is not None or self.image_base64 is not None


@dataclass
class GenerationConfig:
    prompt: str
    width: int = 512
    height: int = 512
    model: Optional[str] = None
    quality: Optional[str] = None
    style: Optional[str] = None


class BaseProvider(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider_name = self.__class__.__name__.lower().replace('provider', '')
    
    @abstractmethod
    async def generate_image(self, config: GenerationConfig) -> ImageGenerationResult:
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        pass
    
    @property
    @abstractmethod
    def required_config_keys(self) -> list[str]:
        pass
    
    @property
    @abstractmethod
    def default_model(self) -> str:
        pass
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)
    
    def is_configured(self) -> bool:
        try:
            return all(
                self.get_config_value(key) is not None 
                for key in self.required_config_keys
            ) and self.validate_config()
        except Exception:
            return False