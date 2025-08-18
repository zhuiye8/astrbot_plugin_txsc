"""
谷歌双子座（Gemini）Provider实现
严格遵循AstrBot开发规范的文生图服务提供商
"""

import asyncio
import base64
from typing import Optional, Dict, Any, List
from astrbot.api.logger import logger

from .base import BaseImageProvider, GenerationParams, GenerationResult, ResponseType, ProviderCapabilities


class GeminiProvider(BaseImageProvider):
    """谷歌双子座（Gemini）Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Gemini Provider
        
        Args:
            config: 配置字典
        """
        super().__init__()
        self.name = "gemini"
        self.display_name = "谷歌双子座"
        
        # 读取配置
        self.api_key = config.get("gemini_api_key", "")
        self.model = "imagen-2"  # Google Imagen 2模型
        
        # SDK客户端
        self.client = None
        
        # 能力描述
        self.capabilities = ProviderCapabilities(
            max_images_per_request=4,  # Gemini支持批量生成
            supports_negative_prompt=True,  # Imagen支持负面提示词
            supports_style_control=True,
            supports_size_control=True,
            async_generation=True,
            supported_formats=["PNG", "JPEG"],
            max_prompt_length=2000,  # Gemini支持较长提示词
            max_negative_prompt_length=1000
        )
        
        logger.info(f"谷歌双子座Provider初始化: model={self.model}")
    
    async def initialize(self) -> bool:
        """异步初始化Provider"""
        try:
            if not self.api_key:
                logger.warning("谷歌双子座Provider: 未配置API密钥")
                return False
            
            # 导入并初始化Google Generative AI SDK
            import google.generativeai as genai
            
            # 配置API密钥
            genai.configure(api_key=self.api_key)
            
            # 创建客户端
            self.client = genai
            
            logger.info("谷歌双子座Provider初始化成功")
            return True
            
        except ImportError as e:
            logger.error(f"谷歌双子座Provider初始化失败: google-generativeai SDK未安装 - {e}")
            return False
        except Exception as e:
            logger.error(f"谷歌双子座Provider初始化失败: {e}")
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
            
            logger.info(f"谷歌双子座开始生成图片: {params.prompt[:50]}...")
            
            # 构建请求参数
            request_params = await self._build_request_params(params)
            
            # 调用API生成图片
            result = await self._call_api(request_params)
            
            # 处理响应
            generation_result = await self._process_response(result, params)
            
            logger.info(f"谷歌双子座生成完成: {generation_result.is_success}")
            return generation_result
            
        except Exception as e:
            logger.error(f"谷歌双子座生成图片失败: {e}")
            return GenerationResult(
                is_success=False,
                error_message=f"生成失败: {str(e)}",
                provider_name=self.name
            )
    
    async def _build_request_params(self, params: GenerationParams) -> Dict[str, Any]:
        """构建API请求参数"""
        
        # 处理提示词
        prompt_text = params.prompt
        
        # 添加风格描述（Gemini支持自然语言风格描述）
        if params.style:
            # Gemini/Imagen风格映射
            style_map = {
                "realistic": "photorealistic, professional photography",
                "cartoon": "cartoon illustration style", 
                "anime": "anime manga art style",
                "oil_painting": "classical oil painting masterpiece",
                "watercolor": "delicate watercolor painting",
                "sketch": "pencil sketch artwork",
                "cyberpunk": "cyberpunk futuristic digital art",
                "fantasy": "fantasy magical art style",
                "minimalist": "clean minimalist design",
                "abstract": "abstract expressionist art",
                "vintage": "vintage retro aesthetic",
                "modern": "contemporary modern art style"
            }
            
            if params.style in style_map:
                prompt_text = f"{prompt_text}, {style_map[params.style]}"
        
        # 处理质量要求
        if params.quality:
            quality_map = {
                "high": "high quality, detailed, sharp focus",
                "highest": "ultra high quality, extremely detailed, masterpiece, award winning",
                "standard": "good quality",
                "fast": "quick generation"
            }
            
            if params.quality in quality_map:
                prompt_text = f"{prompt_text}, {quality_map[params.quality]}"
        
        # 基础参数
        request_params = {
            "prompt": prompt_text,
            "number_of_images": min(params.count, self.capabilities.max_images_per_request)
        }
        
        # 负面提示词
        if params.negative_prompt:
            request_params["negative_prompt"] = params.negative_prompt
        
        # 图片尺寸设置
        if params.size:
            # Imagen 2支持的尺寸
            width = params.size.width
            height = params.size.height
            
            # 支持的尺寸范围检查
            min_size, max_size = 256, 1536
            width = max(min_size, min(width, max_size))
            height = max(min_size, min(height, max_size))
            
            # 确保尺寸是8的倍数（Imagen要求）
            width = (width // 8) * 8
            height = (height // 8) * 8
            
            request_params.update({
                "width": width,
                "height": height
            })
        else:
            # 默认尺寸
            request_params.update({
                "width": 1024,
                "height": 1024
            })
        
        # 种子值
        if params.seed is not None:
            request_params["seed"] = params.seed
        
        # Imagen 2特有参数
        request_params.update({
            "safety_filter": "strict",  # 安全过滤
            "person_generation": "allow",  # 允许生成人物
            "aspect_ratio": f"{request_params.get('width', 1024)}:{request_params.get('height', 1024)}"
        })
        
        logger.debug(f"谷歌双子座请求参数: {request_params}")
        return request_params
    
    async def _call_api(self, request_params: Dict[str, Any]) -> Any:
        """调用Gemini API"""
        try:
            # 构建请求 - 注意Google的API可能有特殊的调用方式
            
            # 由于Gemini的图像生成API可能还在开发中，这里提供一个框架实现
            # 实际使用时可能需要根据Google的最新API文档调整
            
            # 方法1: 如果有专门的图像生成方法
            if hasattr(self.client, 'ImageGeneration'):
                result = await asyncio.to_thread(
                    self.client.ImageGeneration.generate,
                    **request_params
                )
            # 方法2: 如果通过通用模型接口
            elif hasattr(self.client, 'GenerativeModel'):
                model = self.client.GenerativeModel(self.model)
                result = await asyncio.to_thread(
                    model.generate_image,
                    **request_params
                )
            # 方法3: 如果通过文本生成模型的多模态能力
            else:
                # 这里可能需要构建特殊的请求格式
                generation_config = {
                    "temperature": 0.7,
                    "max_output_tokens": 1024,
                }
                
                model = self.client.GenerativeModel(
                    model_name="gemini-pro-vision",  # 可能需要使用支持图像的模型
                    generation_config=generation_config
                )
                
                # 构建包含图像生成指令的提示
                image_prompt = f"Generate an image: {request_params['prompt']}"
                
                result = await asyncio.to_thread(
                    model.generate_content,
                    image_prompt
                )
            
            return result
            
        except Exception as e:
            logger.error(f"谷歌双子座API调用失败: {e}")
            raise
    
    async def _process_response(self, result: Any, params: GenerationParams) -> GenerationResult:
        """处理API响应"""
        try:
            # 由于Gemini的图像生成API格式可能变化，这里提供灵活的处理方式
            
            image_data = None
            response_type = ResponseType.URL
            
            # 尝试多种可能的响应格式
            if hasattr(result, 'images'):
                # 格式1: 直接的images字段
                images = result.images
                if images and len(images) > 0:
                    first_image = images[0]
                    if hasattr(first_image, 'url'):
                        image_data = first_image.url
                        response_type = ResponseType.URL
                    elif hasattr(first_image, 'data'):
                        image_data = first_image.data
                        response_type = ResponseType.BASE64
            
            elif hasattr(result, 'candidates'):
                # 格式2: candidates格式
                candidates = result.candidates
                if candidates and len(candidates) > 0:
                    candidate = candidates[0]
                    if hasattr(candidate, 'content'):
                        # 可能包含图像的内容
                        content = candidate.content
                        # 进一步解析content中的图像数据
                        if hasattr(content, 'parts'):
                            for part in content.parts:
                                if hasattr(part, 'inline_data'):
                                    image_data = part.inline_data.data
                                    response_type = ResponseType.BASE64
                                    break
            
            elif hasattr(result, 'content'):
                # 格式3: 直接的content字段
                content = result.content
                # 可能需要进一步解析content
                if isinstance(content, str) and content.startswith('data:image'):
                    # Data URL格式
                    image_data = content
                    response_type = ResponseType.BASE64
                elif isinstance(content, str) and content.startswith('http'):
                    # URL格式
                    image_data = content
                    response_type = ResponseType.URL
            
            # 如果没有找到图像数据，抛出异常
            if not image_data:
                raise Exception("API响应中没有找到图片数据")
            
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
                    "safety_ratings": getattr(result, "safety_ratings", []),
                    "finish_reason": getattr(result, "finish_reason", ""),
                    "usage_metadata": getattr(result, "usage_metadata", {})
                }
            }
            
            return GenerationResult(
                is_success=True,
                data=image_data,
                response_type=response_type,
                metadata=metadata,
                provider_name=self.name
            )
            
        except Exception as e:
            logger.error(f"谷歌双子座响应处理失败: {e}")
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
                import google.generativeai as genai
                sdk_available = True
            except ImportError:
                sdk_available = False
            
            if not sdk_available:
                return {
                    "status": "unhealthy", 
                    "message": "google-generativeai SDK未安装",
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
                        "error": test_result["error"]
                    }
                }
                
        except Exception as e:
            logger.error(f"谷歌双子座健康检查失败: {e}")
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
            
            # 首先尝试列出可用模型（比生成图片更快）
            try:
                models = await asyncio.to_thread(
                    list,
                    self.client.list_models()
                )
                
                response_time = time.time() - start_time
                
                # 检查是否有图像生成相关的模型
                image_models = [m for m in models if 'image' in m.name.lower() or 'imagen' in m.name.lower()]
                
                if models:  # 如果能够获取模型列表，说明API密钥有效
                    return {
                        "success": True,
                        "response_time": response_time,
                        "available_models": [m.name for m in models[:5]],  # 只显示前5个模型
                        "image_models": [m.name for m in image_models]
                    }
                else:
                    return {
                        "success": False,
                        "error": "无法获取模型列表"
                    }
                    
            except Exception as list_error:
                # 如果列表模型失败，尝试简单的文本生成测试
                try:
                    model = self.client.GenerativeModel('gemini-pro')
                    response = await asyncio.to_thread(
                        model.generate_content,
                        "Hello"
                    )
                    
                    response_time = time.time() - start_time
                    
                    if response:
                        return {
                            "success": True,
                            "response_time": response_time,
                            "test_method": "text_generation"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"文本生成测试失败: {str(list_error)}"
                        }
                        
                except Exception as gen_error:
                    return {
                        "success": False,
                        "error": f"API连接测试失败: {str(gen_error)}"
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
            "version": "Imagen 2",
            "capabilities": self.capabilities.__dict__,
            "supported_sizes": [
                "256x256", "512x512", "768x768", "1024x1024",
                "512x768", "768x512",
                "1024x768", "768x1024", 
                "1536x1024", "1024x1536"
            ],
            "description": "Google Imagen 2多模态生成模型，支持高质量图像生成和多语言理解"
        }


def create_gemini_provider(config: Dict[str, Any]) -> Optional[GeminiProvider]:
    """
    创建Gemini Provider实例
    
    Args:
        config: 配置字典
        
    Returns:
        Provider实例或None
    """
    try:
        provider = GeminiProvider(config)
        
        # 检查基础配置
        if not config.get("gemini_api_key"):
            logger.warning("谷歌双子座Provider: 未配置gemini_api_key，跳过初始化")
            return None
        
        logger.info("成功创建谷歌双子座Provider")
        return provider
        
    except Exception as e:
        logger.error(f"创建谷歌双子座Provider失败: {e}")
        return None