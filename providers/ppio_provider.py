"""
PPIO图像生成Provider实现
严格遵循AstrBot开发规范的文生图服务提供商
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from astrbot.api.logger import logger
import httpx

from .base import BaseImageProvider, GenerationParams, GenerationResult, ResponseType, ProviderCapabilities


class PPIOProvider(BaseImageProvider):
    """PPIO图像生成Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化PPIO Provider
        
        Args:
            config: 配置字典
        """
        super().__init__()
        self.name = "ppio"
        self.display_name = "PPIO图像生成"
        
        # 读取配置
        self.api_key = config.get("ppio_api_key", "")
        
        # API配置
        self.base_url = "https://api.ppio.cloud/v1"  # PPIO API基础URL
        self.model = "ppio-diffusion-v1"  # PPIO默认模型
        
        # 能力描述
        self.capabilities = ProviderCapabilities(
            max_images_per_request=4,  # PPIO支持批量生成
            supports_negative_prompt=True,  # 支持负面提示词
            supports_style_control=True,
            supports_size_control=True,
            async_generation=True,
            supported_formats=["PNG", "JPEG"],
            max_prompt_length=1000,
            max_negative_prompt_length=500
        )
        
        logger.info(f"PPIO图像生成Provider初始化: model={self.model}")
    
    async def initialize(self) -> bool:
        """异步初始化Provider"""
        try:
            if not self.api_key:
                logger.warning("PPIO图像生成Provider: 未配置API密钥")
                return False
            
            logger.info("PPIO图像生成Provider初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"PPIO图像生成Provider初始化失败: {e}")
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
            logger.info(f"PPIO图像生成开始生成图片: {params.prompt[:50]}...")
            
            # 构建请求参数
            request_data = await self._build_request_params(params)
            
            # 调用API生成图片
            result = await self._call_api(request_data)
            
            # 处理响应
            generation_result = await self._process_response(result, params)
            
            logger.info(f"PPIO图像生成完成: {generation_result.is_success}")
            return generation_result
            
        except Exception as e:
            logger.error(f"PPIO图像生成失败: {e}")
            return GenerationResult(
                is_success=False,
                error_message=f"生成失败: {str(e)}",
                provider_name=self.name
            )
    
    async def _build_request_params(self, params: GenerationParams) -> Dict[str, Any]:
        """构建API请求参数"""
        
        # 基础参数
        request_data = {
            "model": self.model,
            "prompt": params.prompt,
            "num_images": min(params.count, self.capabilities.max_images_per_request)
        }
        
        # 负面提示词
        if params.negative_prompt:
            request_data["negative_prompt"] = params.negative_prompt
        
        # 图片尺寸
        if params.size:
            # PPIO支持自定义尺寸
            request_data["width"] = params.size.width
            request_data["height"] = params.size.height
        else:
            # 默认尺寸
            request_data["width"] = 1024
            request_data["height"] = 1024
        
        # 种子值
        if params.seed is not None:
            request_data["seed"] = params.seed
        
        # 风格控制
        if params.style:
            # PPIO风格映射
            style_map = {
                "realistic": "photorealistic",
                "cartoon": "cartoon",
                "anime": "anime",
                "oil_painting": "oil_painting",
                "watercolor": "watercolor",
                "sketch": "sketch",
                "cyberpunk": "cyberpunk",
                "fantasy": "fantasy",
                "minimalist": "minimalist",
                "abstract": "abstract"
            }
            
            if params.style in style_map:
                # PPIO可能支持style参数或在prompt中添加
                style_prompt = f"{params.prompt}, {style_map[params.style]} style"
                request_data["prompt"] = style_prompt
        
        # 质量设置
        if params.quality:
            quality_map = {
                "fast": {"steps": 20, "cfg_scale": 7.0},
                "standard": {"steps": 30, "cfg_scale": 7.5},
                "high": {"steps": 50, "cfg_scale": 8.0},
                "highest": {"steps": 100, "cfg_scale": 9.0}
            }
            
            if params.quality in quality_map:
                quality_settings = quality_map[params.quality]
                request_data.update(quality_settings)
        else:
            # 默认质量设置
            request_data.update({"steps": 30, "cfg_scale": 7.5})
        
        logger.debug(f"PPIO图像生成请求参数: {request_data}")
        return request_data
    
    async def _call_api(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """调用PPIO API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 发送请求
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/text2image",
                    headers=headers,
                    json=request_data
                )
                
                response.raise_for_status()
                result = response.json()
                
                # 检查响应格式
                if not result.get("success", True):
                    error_msg = result.get("error", {}).get("message", "API调用失败")
                    raise Exception(f"PPIO API错误: {error_msg}")
                
                return result
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise Exception("API密钥无效或已过期")
            elif e.response.status_code == 429:
                raise Exception("请求频率过高，请稍后重试")
            elif e.response.status_code == 500:
                raise Exception("PPIO服务器内部错误")
            else:
                raise Exception(f"HTTP错误 {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"PPIO API调用失败: {e}")
            raise
    
    async def _process_response(self, result: Dict[str, Any], params: GenerationParams) -> GenerationResult:
        """处理API响应"""
        try:
            # 解析PPIO响应格式
            images = result.get("images", [])
            
            if not images:
                raise Exception("API响应中没有图片数据")
            
            # 获取第一张图片
            first_image = images[0]
            
            # PPIO可能返回URL或base64数据
            if "url" in first_image:
                image_data = first_image["url"]
                response_type = ResponseType.URL
            elif "base64" in first_image:
                image_data = first_image["base64"]
                response_type = ResponseType.BASE64
            else:
                raise Exception("API响应中缺少图片数据")
            
            # 构建元数据
            metadata = {
                "provider": self.name,
                "model": self.model,
                "prompt": params.prompt,
                "negative_prompt": params.negative_prompt,
                "size": f"{params.size.width}x{params.size.height}" if params.size else "1024x1024",
                "seed": params.seed,
                "count": len(images),
                "api_usage": {
                    "task_id": result.get("task_id", ""),
                    "cost": result.get("cost", 0),
                    "generation_time": result.get("generation_time", 0)
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
            logger.error(f"PPIO响应处理失败: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self.api_key:
                return {
                    "status": "unhealthy",
                    "message": "未配置API密钥",
                    "details": {
                        "api_key_configured": False
                    }
                }
            
            # 执行API测试
            test_result = await self._test_api_connection()
            
            if test_result["success"]:
                return {
                    "status": "healthy",
                    "message": "连接正常",
                    "details": {
                        "api_key_configured": True,
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
                        "api_accessible": False,
                        "base_url": self.base_url,
                        "error": test_result["error"]
                    }
                }
                
        except Exception as e:
            logger.error(f"PPIO健康检查失败: {e}")
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
            
            # 首先尝试获取模型信息（较快的测试）
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    # 尝试获取账户信息或模型列表
                    response = await client.get(
                        f"{self.base_url}/models",
                        headers=headers
                    )
                    
                    response_time = time.time() - start_time
                    
                    if response.status_code == 200:
                        return {
                            "success": True,
                            "response_time": response_time
                        }
                    elif response.status_code == 401:
                        return {
                            "success": False,
                            "error": "API密钥无效"
                        }
                    else:
                        # 如果模型接口不可用，尝试最小的生成测试
                        return await self._test_minimal_generation(start_time)
                        
            except httpx.ConnectError:
                return {
                    "success": False,
                    "error": "无法连接到PPIO服务器"
                }
            except Exception as e:
                # 如果其他接口失败，尝试最小生成测试
                return await self._test_minimal_generation(start_time)
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _test_minimal_generation(self, start_time: float) -> Dict[str, Any]:
        """执行最小的生成测试"""
        try:
            # 构建最小测试请求
            test_data = {
                "model": self.model,
                "prompt": "test",
                "width": 512,
                "height": 512,
                "num_images": 1,
                "steps": 10  # 最少步数以加快测试
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/text2image",
                    headers=headers,
                    json=test_data
                )
                
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success", True) and result.get("images"):
                        return {
                            "success": True,
                            "response_time": response_time
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"生成测试失败: {result.get('error', '未知错误')}"
                        }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"生成测试异常: {str(e)}"
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": self.name,
            "model": self.model,
            "version": "v1",
            "capabilities": self.capabilities.__dict__,
            "supported_sizes": [
                "512x512", "768x768", "1024x1024",
                "512x768", "768x512",
                "1024x768", "768x1024",
                "1536x1024", "1024x1536"
            ],
            "description": "PPIO去中心化AI图像生成服务，性价比高，支持多种艺术风格"
        }


def create_ppio_provider(config: Dict[str, Any]) -> Optional[PPIOProvider]:
    """
    创建PPIO Provider实例
    
    Args:
        config: 配置字典
        
    Returns:
        Provider实例或None
    """
    try:
        provider = PPIOProvider(config)
        
        # 检查基础配置
        if not config.get("ppio_api_key"):
            logger.warning("PPIO图像生成Provider: 未配置ppio_api_key，跳过初始化")
            return None
        
        logger.info("成功创建PPIO图像生成Provider")
        return provider
        
    except Exception as e:
        logger.error(f"创建PPIO图像生成Provider失败: {e}")
        return None