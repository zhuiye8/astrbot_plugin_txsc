"""
文生图Provider基础抽象类
定义统一的接口规范，所有具体的Provider都要继承此类
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Union, List
from dataclasses import dataclass
from enum import Enum
import asyncio


class ImageFormat(Enum):
    """支持的图片格式"""
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"
    WEBP = "webp"


class ResponseType(Enum):
    """响应类型"""
    URL = "url"
    BASE64 = "base64"
    FILE_PATH = "file_path"


@dataclass
class ImageSize:
    """图片尺寸"""
    width: int
    height: int
    
    def __str__(self):
        return f"{self.width}x{self.height}"
    
    @classmethod
    def from_string(cls, size_str: str):
        """从字符串创建尺寸对象"""
        if 'x' in size_str:
            w, h = size_str.split('x')
        elif '*' in size_str:
            w, h = size_str.split('*')
        else:
            raise ValueError(f"Invalid size format: {size_str}")
        return cls(int(w), int(h))


@dataclass
class GenerationParams:
    """统一的生成参数"""
    prompt: str
    negative_prompt: Optional[str] = None
    size: Optional[ImageSize] = None
    style: Optional[str] = None
    quality: Optional[str] = None
    num_images: int = 1
    seed: Optional[int] = None
    guidance_scale: Optional[float] = None
    steps: Optional[int] = None
    response_format: ResponseType = ResponseType.URL
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {"prompt": self.prompt}
        
        if self.negative_prompt:
            result["negative_prompt"] = self.negative_prompt
        if self.size:
            result["size"] = str(self.size)
        if self.style:
            result["style"] = self.style
        if self.quality:
            result["quality"] = self.quality
        if self.num_images > 1:
            result["num_images"] = self.num_images
        if self.seed is not None:
            result["seed"] = self.seed
        if self.guidance_scale is not None:
            result["guidance_scale"] = self.guidance_scale
        if self.steps is not None:
            result["steps"] = self.steps
        
        return result


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    data: Optional[Union[str, List[str]]] = None  # URL、文件路径或base64数据
    error_message: Optional[str] = None
    response_type: ResponseType = ResponseType.URL
    metadata: Optional[Dict[str, Any]] = None  # 额外信息
    
    @property
    def is_success(self) -> bool:
        return self.success and self.data is not None
    
    @property
    def image_url(self) -> Optional[str]:
        """获取图片URL（如果是URL类型）"""
        if self.response_type == ResponseType.URL and isinstance(self.data, str):
            return self.data
        return None
    
    @property
    def image_urls(self) -> List[str]:
        """获取图片URL列表"""
        if self.response_type == ResponseType.URL:
            if isinstance(self.data, str):
                return [self.data]
            elif isinstance(self.data, list):
                return self.data
        return []


@dataclass
class ProviderConfig:
    """Provider配置"""
    name: str
    enabled: bool = True
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    extra_params: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}


class ProviderCapabilities:
    """Provider能力说明"""
    
    def __init__(
        self,
        supported_sizes: List[ImageSize],
        supported_formats: List[ImageFormat],
        supported_styles: List[str] = None,
        supported_qualities: List[str] = None,
        max_images_per_request: int = 1,
        supports_negative_prompt: bool = True,
        supports_seed: bool = True,
        supports_guidance_scale: bool = False,
        supports_steps: bool = False,
        async_generation: bool = False,
        estimated_time_seconds: int = 30
    ):
        self.supported_sizes = supported_sizes
        self.supported_formats = supported_formats
        self.supported_styles = supported_styles or []
        self.supported_qualities = supported_qualities or []
        self.max_images_per_request = max_images_per_request
        self.supports_negative_prompt = supports_negative_prompt
        self.supports_seed = supports_seed
        self.supports_guidance_scale = supports_guidance_scale
        self.supports_steps = supports_steps
        self.async_generation = async_generation
        self.estimated_time_seconds = estimated_time_seconds
    
    def validate_params(self, params: GenerationParams) -> List[str]:
        """验证参数是否支持，返回警告信息列表"""
        warnings = []
        
        # 检查图片数量
        if params.num_images > self.max_images_per_request:
            warnings.append(f"请求生成{params.num_images}张图片，但最大支持{self.max_images_per_request}张")
        
        # 检查尺寸
        if params.size and params.size not in self.supported_sizes:
            supported_sizes_str = ", ".join(str(s) for s in self.supported_sizes)
            warnings.append(f"尺寸{params.size}不受支持，支持的尺寸: {supported_sizes_str}")
        
        # 检查风格
        if params.style and self.supported_styles and params.style not in self.supported_styles:
            warnings.append(f"风格'{params.style}'不受支持，支持的风格: {', '.join(self.supported_styles)}")
        
        # 检查质量
        if params.quality and self.supported_qualities and params.quality not in self.supported_qualities:
            warnings.append(f"质量'{params.quality}'不受支持，支持的质量: {', '.join(self.supported_qualities)}")
        
        # 检查反向提示词
        if params.negative_prompt and not self.supports_negative_prompt:
            warnings.append("该Provider不支持反向提示词")
        
        # 检查种子
        if params.seed is not None and not self.supports_seed:
            warnings.append("该Provider不支持自定义种子")
        
        # 检查引导强度
        if params.guidance_scale is not None and not self.supports_guidance_scale:
            warnings.append("该Provider不支持guidance_scale参数")
        
        # 检查步数
        if params.steps is not None and not self.supports_steps:
            warnings.append("该Provider不支持自定义步数")
        
        return warnings


class BaseImageProvider(ABC):
    """文生图Provider基类"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name
        self._capabilities: Optional[ProviderCapabilities] = None
    
    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """返回Provider的能力说明"""
        pass
    
    @abstractmethod
    async def validate_config(self) -> bool:
        """验证配置是否有效"""
        pass
    
    @abstractmethod
    async def generate_image(self, params: GenerationParams) -> GenerationResult:
        """生成图片的核心方法"""
        pass
    
    async def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            return await self.validate_config()
        except Exception:
            return False
    
    def preprocess_params(self, params: GenerationParams) -> GenerationParams:
        """预处理参数，子类可以重写此方法来适配特定的参数"""
        # 设置默认尺寸
        if not params.size and self.capabilities.supported_sizes:
            params.size = self.capabilities.supported_sizes[0]
        
        # 限制图片数量
        if params.num_images > self.capabilities.max_images_per_request:
            params.num_images = self.capabilities.max_images_per_request
        
        return params
    
    def validate_params(self, params: GenerationParams) -> List[str]:
        """验证参数并返回警告信息"""
        return self.capabilities.validate_params(params)
    
    async def generate_with_retry(self, params: GenerationParams) -> GenerationResult:
        """带重试的生成方法"""
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                # 预处理参数
                processed_params = self.preprocess_params(params)
                
                # 生成图片
                result = await self.generate_image(processed_params)
                
                if result.is_success:
                    return result
                else:
                    last_error = result.error_message
                    
            except Exception as e:
                last_error = str(e)
                
            # 如果不是最后一次尝试，等待后重试
            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
        
        return GenerationResult(
            success=False,
            error_message=f"重试{self.config.max_retries}次后仍然失败: {last_error}"
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        result = {
            "provider": self.name,
            "status": "unknown",
            "message": "",
            "capabilities": {
                "supported_sizes": [str(s) for s in self.capabilities.supported_sizes],
                "supported_formats": [f.value for f in self.capabilities.supported_formats],
                "max_images": self.capabilities.max_images_per_request,
                "async_generation": self.capabilities.async_generation,
                "estimated_time": self.capabilities.estimated_time_seconds
            }
        }
        
        try:
            is_healthy = await self.test_connection()
            result["status"] = "healthy" if is_healthy else "unhealthy"
            result["message"] = "Provider工作正常" if is_healthy else "Provider连接失败"
        except Exception as e:
            result["status"] = "error"
            result["message"] = f"健康检查失败: {str(e)}"
        
        return result
    
    def __str__(self):
        return f"{self.__class__.__name__}({self.name})"
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', enabled={self.config.enabled})"


class ProviderError(Exception):
    """Provider异常基类"""
    
    def __init__(self, message: str, provider_name: str = "", error_code: str = ""):
        super().__init__(message)
        self.provider_name = provider_name
        self.error_code = error_code


class AuthenticationError(ProviderError):
    """认证错误"""
    pass


class QuotaExceededError(ProviderError):
    """配额超限错误"""
    pass


class RateLimitError(ProviderError):
    """请求频率超限错误"""
    pass


class ContentPolicyError(ProviderError):
    """内容政策违规错误"""
    pass


class InvalidParameterError(ProviderError):
    """参数错误"""
    pass


class ServiceUnavailableError(ProviderError):
    """服务不可用错误"""
    pass