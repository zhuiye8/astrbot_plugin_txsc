"""
OpenAI达芬奇Provider实现
严格遵循AstrBot开发规范的文生图服务提供商
"""

import asyncio
import base64
from typing import Optional, Dict, Any, List
from astrbot.api.logger import logger

from .base import BaseImageProvider, GenerationParams, GenerationResult, ResponseType, ProviderCapabilities


class OpenAIProvider(BaseImageProvider):
    """OpenAI达芬奇Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化OpenAI Provider
        
        Args:
            config: 配置字典
        """
        super().__init__()
        self.name = "openai"
        self.display_name = "OpenAI达芬奇"
        
        # 读取配置
        self.api_key = config.get("openai_api_key", "")
        self.base_url = config.get("openai_base_url", "https://api.openai.com/v1")
        self.model = "dall-e-3"  # 使用最新的DALL-E 3模型
        
        # SDK客户端
        self.client = None
        
        # 能力描述
        self.capabilities = ProviderCapabilities(
            max_images_per_request=1,  # DALL-E 3单次生成1张
            supports_negative_prompt=False,  # DALL-E通过prompt修正处理
            supports_style_control=True,
            supports_size_control=True,
            async_generation=True,
            supported_formats=["PNG"],
            max_prompt_length=4000,  # DALL-E 3支持很长的提示词
            max_negative_prompt_length=0
        )
        
        logger.info(f"OpenAI达芬奇Provider初始化: model={self.model}")
    
    async def initialize(self) -> bool:
        """异步初始化Provider"""
        try:
            if not self.api_key:
                logger.warning("OpenAI达芬奇Provider: 未配置API密钥")
                return False
            
            # 导入并初始化OpenAI SDK
            import openai
            
            # 创建异步客户端
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            logger.info("OpenAI达芬奇Provider初始化成功")
            return True
            
        except ImportError as e:
            logger.error(f"OpenAI达芬奇Provider初始化失败: openai SDK未安装 - {e}")
            return False
        except Exception as e:
            logger.error(f"OpenAI达芬奇Provider初始化失败: {e}")
            return False
    
    async def generate_image(self, params: GenerationParams) -> GenerationResult:
        """
        生成图片
        
        Args:
            params: 生成参数
            
        Returns:
            生成结果
        """
        try:
            if not self.client:
                raise Exception("Provider未正确初始化")
            
            logger.info(f"OpenAI达芬奇开始生成图片: {params.prompt[:50]}...")
            
            # 构建请求参数
            request_params = await self._build_request_params(params)
            
            # 调用API生成图片
            result = await self._call_api(request_params)
            
            # 处理响应
            generation_result = await self._process_response(result, params)
            
            logger.info(f"OpenAI达芬奇生成完成: {generation_result.is_success}")
            return generation_result
            
        except Exception as e:
            logger.error(f"OpenAI达芬奇生成图片失败: {e}")
            return GenerationResult(
                is_success=False,
                error_message=f"生成失败: {str(e)}",
                provider_name=self.name
            )
    
    async def _build_request_params(self, params: GenerationParams) -> Dict[str, Any]:
        """构建API请求参数"""
        
        # 处理提示词 - DALL-E 3会自动优化prompt
        prompt_text = params.prompt
        
        # 添加风格描述
        if params.style:
            # OpenAI DALL-E 3风格映射（英文描述）
            style_map = {
                "realistic": "photorealistic, high-resolution photography",
                "cartoon": "cartoon illustration style", 
                "anime": "anime art style",
                "oil_painting": "oil painting masterpiece",
                "watercolor": "watercolor painting",
                "sketch": "pencil sketch drawing",
                "cyberpunk": "cyberpunk futuristic style",
                "fantasy": "fantasy art style",
                "minimalist": "minimalist clean design",
                "abstract": "abstract artistic style",
                "vintage": "vintage retro style",
                "modern": "modern contemporary art"
            }
            
            if params.style in style_map:
                prompt_text = f"{prompt_text}, {style_map[params.style]}"
        
        # 处理质量要求
        if params.quality:
            quality_map = {
                "high": "high quality, detailed",
                "highest": "ultra high quality, extremely detailed, masterpiece",
                "standard": "good quality"
            }
            
            if params.quality in quality_map:
                prompt_text = f"{prompt_text}, {quality_map[params.quality]}"
        
        # 处理负面提示词（DALL-E通过正面描述来避免）
        if params.negative_prompt:
            # 将负面描述转换为正面要求
            avoid_terms = params.negative_prompt.split(',')
            positive_terms = []
            for term in avoid_terms:
                term = term.strip()
                if term:
                    positive_terms.append(f"without {term}")
            
            if positive_terms:
                prompt_text = f"{prompt_text}, {', '.join(positive_terms)}"
        
        # 基础参数
        request_params = {
            "model": self.model,
            "prompt": prompt_text,
            "n": 1,  # DALL-E 3只支持生成1张
            "response_format": "url"  # 默认返回URL
        }
        
        # 图片尺寸设置
        if params.size:
            # DALL-E 3支持的尺寸
            width = params.size.width
            height = params.size.height
            
            # DALL-E 3标准尺寸映射
            if width == height:
                # 正方形
                request_params["size"] = "1024x1024"
            elif width > height:
                # 横向
                request_params["size"] = "1792x1024"
            else:
                # 纵向
                request_params["size"] = "1024x1792"
        else:
            request_params["size"] = "1024x1024"  # 默认尺寸
        
        # 质量设置（DALL-E 3特有）
        if params.quality in ["high", "highest"]:
            request_params["quality"] = "hd"
        else:
            request_params["quality"] = "standard"
        
        # 风格设置（DALL-E 3特有的style参数）
        if params.style in ["realistic", "natural"]:
            request_params["style"] = "natural"
        else:
            request_params["style"] = "vivid"  # 默认鲜艳风格
        
        logger.debug(f"OpenAI达芬奇请求参数: {request_params}")
        return request_params
    
    async def _call_api(self, request_params: Dict[str, Any]) -> Any:
        """调用OpenAI API"""
        try:
            # 调用DALL-E API
            response = await self.client.images.generate(**request_params)
            
            return response
            
        except Exception as e:
            logger.error(f"OpenAI达芬奇API调用失败: {e}")
            raise
    
    async def _process_response(self, result: Any, params: GenerationParams) -> GenerationResult:
        """处理API响应"""
        try:
            # 解析OpenAI响应格式
            if not result.data:
                raise Exception("API响应中没有图片数据")
            
            # 获取第一张图片
            first_image = result.data[0]
            image_url = first_image.url
            
            if not image_url:
                raise Exception("API响应中缺少图片URL")
            
            # 构建元数据
            metadata = {
                "provider": self.name,
                "model": self.model,
                "prompt": params.prompt,
                "negative_prompt": params.negative_prompt,
                "size": f"{params.size.width}x{params.size.height}" if params.size else "1024x1024",
                "seed": params.seed,
                "count": 1,
                "api_usage": {
                    "revised_prompt": getattr(first_image, "revised_prompt", ""),  # DALL-E 3的prompt修正
                    "created": getattr(result, "created", 0)
                }
            }
            
            return GenerationResult(
                is_success=True,
                data=image_url,
                response_type=ResponseType.URL,
                metadata=metadata,
                provider_name=self.name
            )
            
        except Exception as e:
            logger.error(f"OpenAI达芬奇响应处理失败: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self.api_key:
                return {
                    "status": "unhealthy",
                    "message": "未配置API密钥",
                    "details": {
                        "api_key_configured": False,
                        "sdk_available": False
                    }
                }
            
            # 检查SDK可用性
            try:
                import openai
                sdk_available = True
            except ImportError:
                sdk_available = False
            
            if not sdk_available:
                return {
                    "status": "unhealthy", 
                    "message": "openai SDK未安装",
                    "details": {
                        "api_key_configured": True,
                        "sdk_available": False
                    }
                }
            
            # 执行简单的API测试
            test_result = await self._test_api_connection()
            
            if test_result["success"]:
                return {
                    "status": "healthy",
                    "message": "连接正常",
                    "details": {
                        "api_key_configured": True,
                        "sdk_available": True,
                        "api_accessible": True,
                        "model": self.model,
                        "base_url": self.base_url,
                        "response_time": test_result.get("response_time", 0)
                    }
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": f"API连接失败: {test_result['error']}",
                    "details": {
                        "api_key_configured": True,
                        "sdk_available": True,
                        "api_accessible": False,
                        "base_url": self.base_url,
                        "error": test_result["error"]
                    }
                }
                
        except Exception as e:
            logger.error(f"OpenAI达芬奇健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "message": f"健康检查异常: {str(e)}",
                "details": {
                    "error": str(e)
                }
            }
    
    async def _test_api_connection(self) -> Dict[str, Any]:
        """测试API连接"""
        try:
            import time
            start_time = time.time()
            
            # 尝试调用模型列表API进行连接测试（比生成图片更快）
            try:
                models = await self.client.models.list()
                response_time = time.time() - start_time
                
                # 检查是否有DALL-E模型
                dalle_models = [m for m in models.data if "dall-e" in m.id.lower()]
                
                if dalle_models:
                    return {
                        "success": True,
                        "response_time": response_time,
                        "available_models": [m.id for m in dalle_models]
                    }
                else:
                    return {
                        "success": False,
                        "error": "账户没有DALL-E模型访问权限"
                    }
                    
            except Exception as api_error:
                # 如果模型列表失败，尝试直接生成测试（某些API密钥可能没有模型列表权限）
                test_params = {
                    "model": self.model,
                    "prompt": "A simple test image",
                    "size": "1024x1024",
                    "n": 1,
                    "quality": "standard"
                }
                
                result = await self.client.images.generate(**test_params)
                response_time = time.time() - start_time
                
                if result and result.data:
                    return {
                        "success": True,
                        "response_time": response_time
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API测试生成失败: {str(api_error)}"
                    }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": self.name,
            "model": self.model,
            "version": "DALL-E 3",
            "capabilities": self.capabilities.__dict__,
            "supported_sizes": [
                "1024x1024", "1792x1024", "1024x1792"
            ],
            "supported_qualities": ["standard", "hd"],
            "supported_styles": ["natural", "vivid"],
            "description": "OpenAI DALL-E 3，业界领先的AI图像生成模型，支持高质量图片生成和prompt自动优化"
        }


def create_openai_provider(config: Dict[str, Any]) -> Optional[OpenAIProvider]:
    """
    创建OpenAI Provider实例
    
    Args:
        config: 配置字典
        
    Returns:
        Provider实例或None
    """
    try:
        provider = OpenAIProvider(config)
        
        # 检查基础配置
        if not config.get("openai_api_key"):
            logger.warning("OpenAI达芬奇Provider: 未配置openai_api_key，跳过初始化")
            return None
        
        logger.info("成功创建OpenAI达芬奇Provider")
        return provider
        
    except Exception as e:
        logger.error(f"创建OpenAI达芬奇Provider失败: {e}")
        return None