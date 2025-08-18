"""
Grok图像生成Provider实现
严格遵循AstrBot开发规范的文生图服务提供商
"""

import asyncio
import base64
from typing import Optional, Dict, Any, List
from astrbot.api.logger import logger

from .base import BaseImageProvider, GenerationParams, GenerationResult, ResponseType, ProviderCapabilities


class GrokProvider(BaseImageProvider):
    """Grok图像生成Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Grok Provider
        
        Args:
            config: 配置字典
        """
        super().__init__()
        self.name = "grok"
        self.display_name = "Grok图像生成"
        
        # 读取配置
        self.api_key = config.get("grok_api_key", "")
        self.base_url = config.get("grok_base_url", "https://api.x.ai/v1")
        self.model = "grok-vision"  # Grok的视觉模型
        
        # SDK客户端
        self.client = None
        
        # 能力描述
        self.capabilities = ProviderCapabilities(
            max_images_per_request=1,  # Grok单次生成1张
            supports_negative_prompt=False,  # Grok通过prompt优化处理
            supports_style_control=True,
            supports_size_control=True,
            async_generation=True,
            supported_formats=["PNG", "JPEG"],
            max_prompt_length=2000,  # Grok支持较长提示词
            max_negative_prompt_length=0
        )
        
        logger.info(f"Grok图像生成Provider初始化: model={self.model}")
    
    async def initialize(self) -> bool:
        """异步初始化Provider"""
        try:
            if not self.api_key:
                logger.warning("Grok图像生成Provider: 未配置API密钥")
                return False
            
            # 导入OpenAI SDK（Grok兼容OpenAI接口）
            import openai
            
            # 创建异步客户端，使用Grok的API端点
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            logger.info("Grok图像生成Provider初始化成功")
            return True
            
        except ImportError as e:
            logger.error(f"Grok图像生成Provider初始化失败: openai SDK未安装 - {e}")
            return False
        except Exception as e:
            logger.error(f"Grok图像生成Provider初始化失败: {e}")
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
            
            logger.info(f"Grok图像生成开始生成图片: {params.prompt[:50]}...")
            
            # 构建请求参数
            request_params = await self._build_request_params(params)
            
            # 调用API生成图片
            result = await self._call_api(request_params)
            
            # 处理响应
            generation_result = await self._process_response(result, params)
            
            logger.info(f"Grok图像生成完成: {generation_result.is_success}")
            return generation_result
            
        except Exception as e:
            logger.error(f"Grok图像生成失败: {e}")
            return GenerationResult(
                is_success=False,
                error_message=f"生成失败: {str(e)}",
                provider_name=self.name
            )
    
    async def _build_request_params(self, params: GenerationParams) -> Dict[str, Any]:
        """构建API请求参数"""
        
        # 处理提示词 - Grok有独特的创意风格
        prompt_text = params.prompt
        
        # 添加风格描述（Grok偏好创意和幽默风格）
        if params.style:
            # Grok风格映射（融入其独特的创意特色）
            style_map = {
                "realistic": "photorealistic, professional photography",
                "cartoon": "witty cartoon illustration", 
                "anime": "creative anime art style",
                "oil_painting": "artistic oil painting masterpiece",
                "watercolor": "expressive watercolor art",
                "sketch": "creative sketch artwork",
                "cyberpunk": "futuristic cyberpunk digital art",
                "fantasy": "imaginative fantasy art",
                "minimalist": "clean minimalist design",
                "abstract": "creative abstract art",
                "humorous": "funny and creative style",  # Grok特色
                "innovative": "innovative and original design",  # Grok特色
                "witty": "clever and witty visual style"  # Grok特色
            }
            
            if params.style in style_map:
                prompt_text = f"{prompt_text}, {style_map[params.style]}"
        
        # 处理质量要求
        if params.quality:
            quality_map = {
                "high": "high quality, detailed, creative",
                "highest": "ultra high quality, extremely detailed, innovative masterpiece",
                "standard": "good quality, creative",
                "fast": "quick creative generation"
            }
            
            if params.quality in quality_map:
                prompt_text = f"{prompt_text}, {quality_map[params.quality]}"
        
        # 处理负面提示词（Grok通过正面创意描述来引导）
        if params.negative_prompt:
            # 将负面描述转换为创意正面要求
            avoid_terms = params.negative_prompt.split(',')
            creative_terms = []
            for term in avoid_terms:
                term = term.strip()
                if term:
                    creative_terms.append(f"creatively avoiding {term}")
            
            if creative_terms:
                prompt_text = f"{prompt_text}, {', '.join(creative_terms)}"
        
        # 基础参数（兼容OpenAI格式）
        request_params = {
            "model": self.model,
            "prompt": prompt_text,
            "n": 1,  # Grok单次生成1张
            "response_format": "url"  # 返回URL格式
        }
        
        # 图片尺寸设置
        if params.size:
            # Grok支持的尺寸（可能与OpenAI类似）
            width = params.size.width
            height = params.size.height
            
            # 根据比例选择最合适的尺寸
            if width == height:
                # 正方形
                request_params["size"] = "1024x1024"
            elif width > height:
                # 横向
                if width / height > 1.5:
                    request_params["size"] = "1792x1024"
                else:
                    request_params["size"] = "1344x768"
            else:
                # 纵向
                if height / width > 1.5:
                    request_params["size"] = "1024x1792"
                else:
                    request_params["size"] = "768x1344"
        else:
            request_params["size"] = "1024x1024"  # 默认尺寸
        
        # Grok特色参数（如果支持）
        request_params.update({
            "creativity": "high",  # 高创意度
            "style_strength": 0.8,  # 风格强度
            "innovation_mode": True  # 创新模式
        })
        
        # 种子值
        if params.seed is not None:
            request_params["seed"] = params.seed
        
        logger.debug(f"Grok图像生成请求参数: {request_params}")
        return request_params
    
    async def _call_api(self, request_params: Dict[str, Any]) -> Any:
        """调用Grok API"""
        try:
            # 由于Grok可能有专门的图像生成端点，先尝试图像生成API
            try:
                # 尝试Grok专用的图像生成API
                response = await self.client.images.generate(**request_params)
                return response
            except Exception as image_api_error:
                # 如果专用API不可用，尝试通过聊天API生成图像
                logger.warning(f"Grok图像API调用失败，尝试聊天API: {image_api_error}")
                
                # 构建聊天请求
                chat_request = {
                    "model": "grok-beta",  # 使用Grok的聊天模型
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a creative AI image generator. Generate detailed image descriptions and create images."
                        },
                        {
                            "role": "user", 
                            "content": f"Generate an image: {request_params['prompt']}"
                        }
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.8  # 保持创意性
                }
                
                response = await self.client.chat.completions.create(**chat_request)
                return response
            
        except Exception as e:
            logger.error(f"Grok API调用失败: {e}")
            raise
    
    async def _process_response(self, result: Any, params: GenerationParams) -> GenerationResult:
        """处理API响应"""
        try:
            # 处理图像生成API响应
            if hasattr(result, 'data') and result.data:
                # 标准图像生成响应
                first_image = result.data[0]
                image_url = first_image.url
                
                if not image_url:
                    raise Exception("API响应中缺少图片URL")
                
                response_type = ResponseType.URL
                image_data = image_url
                
                metadata = {
                    "provider": self.name,
                    "model": self.model,
                    "prompt": params.prompt,
                    "negative_prompt": params.negative_prompt,
                    "size": f"{params.size.width}x{params.size.height}" if params.size else "1024x1024",
                    "seed": params.seed,
                    "count": 1,
                    "api_usage": {
                        "created": getattr(result, "created", 0),
                        "revised_prompt": getattr(first_image, "revised_prompt", "")
                    }
                }
                
            elif hasattr(result, 'choices') and result.choices:
                # 聊天API响应，可能包含图像描述或链接
                choice = result.choices[0]
                content = choice.message.content
                
                # 尝试从响应中提取图像URL或描述
                if "http" in content and ("image" in content.lower() or "generated" in content.lower()):
                    # 假设包含了图像URL
                    import re
                    url_pattern = r'https?://[^\s<>"]+\.(?:jpg|jpeg|png|gif|webp)'
                    urls = re.findall(url_pattern, content)
                    
                    if urls:
                        image_data = urls[0]
                        response_type = ResponseType.URL
                    else:
                        # 如果没有找到URL，返回描述作为错误
                        raise Exception(f"聊天API响应未包含有效图像链接: {content}")
                else:
                    # 可能是图像描述，但不是实际图像
                    raise Exception(f"Grok返回了描述而非图像: {content}")
                
                metadata = {
                    "provider": self.name,
                    "model": getattr(result, "model", "grok-beta"),
                    "prompt": params.prompt,
                    "negative_prompt": params.negative_prompt,
                    "size": f"{params.size.width}x{params.size.height}" if params.size else "1024x1024",
                    "seed": params.seed,
                    "count": 1,
                    "api_usage": {
                        "usage": getattr(result, "usage", {}),
                        "response_text": content[:200] + "..." if len(content) > 200 else content
                    }
                }
            else:
                raise Exception("API响应格式不符合预期")
            
            return GenerationResult(
                is_success=True,
                data=image_data,
                response_type=response_type,
                metadata=metadata,
                provider_name=self.name
            )
            
        except Exception as e:
            logger.error(f"Grok响应处理失败: {e}")
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
            logger.error(f"Grok健康检查失败: {e}")
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
            
            # 首先尝试获取模型列表
            try:
                models = await self.client.models.list()
                response_time = time.time() - start_time
                
                # 检查是否有Grok相关模型
                grok_models = [m for m in models.data if "grok" in m.id.lower()]
                
                if models.data:
                    return {
                        "success": True,
                        "response_time": response_time,
                        "available_models": [m.id for m in models.data[:5]],
                        "grok_models": [m.id for m in grok_models]
                    }
                else:
                    return {
                        "success": False,
                        "error": "无法获取模型列表"
                    }
                    
            except Exception as models_error:
                # 如果模型列表失败，尝试聊天API测试
                try:
                    response = await self.client.chat.completions.create(
                        model="grok-beta",
                        messages=[
                            {"role": "system", "content": "You are Grok, a helpful AI assistant."},
                            {"role": "user", "content": "Hello, this is a connection test."}
                        ],
                        max_tokens=50,
                        temperature=0.1
                    )
                    
                    response_time = time.time() - start_time
                    
                    if response and response.choices:
                        return {
                            "success": True,
                            "response_time": response_time,
                            "test_method": "chat_completion"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"聊天API测试失败: {str(models_error)}"
                        }
                        
                except Exception as chat_error:
                    return {
                        "success": False,
                        "error": f"API连接测试失败: {str(chat_error)}"
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
            "version": "Grok Vision",
            "capabilities": self.capabilities.__dict__,
            "supported_sizes": [
                "1024x1024", "1792x1024", "1024x1792",
                "1344x768", "768x1344"
            ],
            "description": "xAI Grok图像生成模型，具有独特的创意和幽默风格，支持创新的视觉内容生成"
        }


def create_grok_provider(config: Dict[str, Any]) -> Optional[GrokProvider]:
    """
    创建Grok Provider实例
    
    Args:
        config: 配置字典
        
    Returns:
        Provider实例或None
    """
    try:
        provider = GrokProvider(config)
        
        # 检查基础配置
        if not config.get("grok_api_key"):
            logger.warning("Grok图像生成Provider: 未配置grok_api_key，跳过初始化")
            return None
        
        logger.info("成功创建Grok图像生成Provider")
        return provider
        
    except Exception as e:
        logger.error(f"创建Grok图像生成Provider失败: {e}")
        return None