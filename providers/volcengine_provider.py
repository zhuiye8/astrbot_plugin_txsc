"""
火山引擎文生图Provider实现
"""

import asyncio
import json
from typing import Optional, Dict, Any
from astrbot.api.logger import logger

from .base import (
    BaseImageProvider, ProviderConfig, ProviderCapabilities,
    GenerationParams, GenerationResult, ImageSize, ImageFormat,
    ResponseType, AuthenticationError, QuotaExceededError,
    RateLimitError, ServiceUnavailableError, InvalidParameterError
)


class VolcengineProvider(BaseImageProvider):
    """火山引擎文生图Provider"""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.access_key = config.api_key
        self.secret_key = config.api_secret
        self.model = config.model or "high_aes_general_v21_L"
        self.schedule_conf = config.extra_params.get("schedule_conf", "general_v20_9B_pe")
        self._visual_service = None
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        """返回火山引擎的能力说明"""
        return ProviderCapabilities(
            supported_sizes=[
                ImageSize(512, 512),
                ImageSize(640, 360),
                ImageSize(640, 480),
                ImageSize(768, 768),
                ImageSize(1024, 1024),
                ImageSize(1280, 720),
                ImageSize(1440, 720),
                ImageSize(720, 1440),
                ImageSize(768, 1344),
                ImageSize(1344, 768),
                ImageSize(864, 1152),
                ImageSize(1152, 864),
            ],
            supported_formats=[ImageFormat.JPG, ImageFormat.PNG],
            supported_styles=["美感版", "标准版"],
            supported_qualities=["standard", "high"],
            max_images_per_request=1,
            supports_negative_prompt=True,
            supports_seed=True,
            supports_guidance_scale=True,
            supports_steps=True,
            async_generation=False,
            estimated_time_seconds=15
        )
    
    async def validate_config(self) -> bool:
        """验证配置是否有效"""
        if not self.access_key or not self.secret_key:
            raise AuthenticationError("火山引擎需要access_key和secret_key", self.name)
        
        try:
            # 尝试导入SDK
            await self._ensure_sdk()
            return True
        except ImportError:
            logger.error("火山引擎SDK未安装，请运行: pip install volcengine")
            return False
        except Exception as e:
            logger.error(f"火山引擎配置验证失败: {e}")
            return False
    
    async def _ensure_sdk(self):
        """确保SDK可用"""
        try:
            from volcengine.visual.VisualService import VisualService
            
            if not self._visual_service:
                self._visual_service = VisualService()
                self._visual_service.set_ak(self.access_key)
                self._visual_service.set_sk(self.secret_key)
            
        except ImportError:
            raise ImportError("volcengine SDK未安装")
    
    def preprocess_params(self, params: GenerationParams) -> GenerationParams:
        """预处理参数以适配火山引擎"""
        params = super().preprocess_params(params)
        
        # 确保有默认尺寸
        if not params.size:
            params.size = ImageSize(1024, 1024)
        
        # 火山引擎只支持单张图片生成
        params.num_images = 1
        
        # 设置默认值
        if params.guidance_scale is None:
            params.guidance_scale = 3.5
        
        if params.steps is None:
            params.steps = 25
        
        return params
    
    async def generate_image(self, params: GenerationParams) -> GenerationResult:
        """使用火山引擎生成图片"""
        try:
            await self._ensure_sdk()
            
            # 构造请求参数
            form = self._build_request_form(params)
            
            logger.info(f"火山引擎生成参数: {json.dumps(form, ensure_ascii=False, indent=2)}")
            
            # 调用API
            response = await asyncio.to_thread(
                self._visual_service.cv_process, 
                form
            )
            
            # 处理响应
            return self._process_response(response)
            
        except Exception as e:
            return self._handle_error(e)
    
    def _build_request_form(self, params: GenerationParams) -> Dict[str, Any]:
        """构造火山引擎请求参数"""
        form = {
            "req_key": self.model,
            "prompt": params.prompt,
            "model_version": "general_v2.1_L",
            "req_schedule_conf": self.schedule_conf,
            "llm_seed": params.seed if params.seed is not None else -1,
            "seed": params.seed if params.seed is not None else -1,
            "scale": params.guidance_scale or 3.5,
            "ddim_steps": params.steps or 25,
            "width": params.size.width,
            "height": params.size.height,
            "use_pre_llm": True,
            "use_sr": True,
            "return_url": params.response_format == ResponseType.URL
        }
        
        # 添加反向提示词
        if params.negative_prompt:
            form["negative_prompt"] = params.negative_prompt
        
        return form
    
    def _process_response(self, response) -> GenerationResult:
        """处理火山引擎响应"""
        try:
            # 火山引擎返回Python字典
            if isinstance(response, dict):
                response_data = response
            else:
                response_str = str(response)
                try:
                    response_data = json.loads(response_str)
                except json.JSONDecodeError:
                    import ast
                    response_data = ast.literal_eval(response_str)
            
            logger.info(f"火山引擎响应: {response_data}")
            
            # 检查响应状态
            if response_data.get("code") != 10000:
                error_code = response_data.get("code")
                error_msg = response_data.get("message", "未知错误")
                return GenerationResult(
                    success=False,
                    error_message=f"火山引擎API错误: {error_msg} (代码:{error_code})"
                )
            
            # 提取图片URL
            data = response_data.get("data", {})
            image_urls = data.get("image_urls", [])
            
            if image_urls and len(image_urls) > 0:
                image_url = image_urls[0]
                logger.info(f"火山引擎生成成功: {image_url}")
                
                return GenerationResult(
                    success=True,
                    data=image_url,
                    response_type=ResponseType.URL,
                    metadata={
                        "provider": self.name,
                        "model": self.model,
                        "schedule_conf": self.schedule_conf
                    }
                )
            
            # 检查base64数据
            binary_data = data.get("binary_data_base64", [])
            if binary_data and len(binary_data) > 0:
                base64_data = binary_data[0]
                
                # 保存为临时文件
                temp_file = self._save_base64_image(base64_data)
                
                return GenerationResult(
                    success=True,
                    data=temp_file,
                    response_type=ResponseType.FILE_PATH,
                    metadata={
                        "provider": self.name,
                        "model": self.model,
                        "format": "base64"
                    }
                )
            
            return GenerationResult(
                success=False,
                error_message="火山引擎未返回图像数据"
            )
            
        except Exception as e:
            logger.error(f"火山引擎响应处理失败: {e}")
            return GenerationResult(
                success=False,
                error_message=f"响应处理失败: {str(e)}"
            )
    
    def _save_base64_image(self, base64_data: str) -> str:
        """保存base64图片为临时文件"""
        import base64
        import tempfile
        import os
        
        try:
            # 解码base64数据
            image_data = base64.b64decode(base64_data)
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                suffix='.png', 
                delete=False,
                prefix='volcengine_'
            ) as temp_file:
                temp_file.write(image_data)
                return temp_file.name
                
        except Exception as e:
            raise Exception(f"保存base64图片失败: {e}")
    
    def _handle_error(self, error: Exception) -> GenerationResult:
        """处理错误"""
        error_message = str(error)
        
        # 根据错误类型返回相应的异常
        if "volcengine" in error_message.lower() and "import" in error_message.lower():
            return GenerationResult(
                success=False,
                error_message="火山引擎SDK未安装，请运行: pip install volcengine"
            )
        
        # 解析API错误码
        if "错误码" in error_message or "code" in error_message:
            if "11203" in error_message or "配额" in error_message:
                raise QuotaExceededError("火山引擎配额不足", self.name)
            elif "10019" in error_message or "并发" in error_message:
                raise RateLimitError("火山引擎并发超限", self.name)
            elif "11200" in error_message or "11201" in error_message or "11202" in error_message:
                raise AuthenticationError("火山引擎认证失败", self.name)
            elif "10013" in error_message or "参数" in error_message:
                raise InvalidParameterError("火山引擎参数错误", self.name)
        
        logger.error(f"火山引擎生成失败: {error_message}")
        
        return GenerationResult(
            success=False,
            error_message=f"火山引擎生成失败: {error_message}"
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        result = await super().health_check()
        
        # 添加火山引擎特定信息
        result["metadata"] = {
            "model": self.model,
            "schedule_conf": self.schedule_conf,
            "access_key_masked": f"{self.access_key[:4]}****{self.access_key[-4:]}" if self.access_key else "未配置"
        }
        
        return result


def create_volcengine_provider(config: Dict[str, Any]) -> Optional[VolcengineProvider]:
    """创建火山引擎Provider的工厂函数"""
    
    # 检查必需配置
    access_key = config.get("volcengine_ak")
    secret_key = config.get("volcengine_sk")
    
    if not access_key or not secret_key:
        logger.warning("火山引擎配置不完整，跳过创建Provider")
        return None
    
    # 创建Provider配置
    provider_config = ProviderConfig(
        name="volcengine",
        enabled=True,
        api_key=access_key,
        api_secret=secret_key,
        model=config.get("volcengine_model", "high_aes_general_v21_L"),
        timeout=config.get("volcengine_timeout", 60),
        max_retries=config.get("volcengine_max_retries", 3),
        retry_delay=config.get("volcengine_retry_delay", 1.0),
        extra_params={
            "schedule_conf": config.get("fire_schedule_conf", "general_v20_9B_pe")
        }
    )
    
    return VolcengineProvider(provider_config)