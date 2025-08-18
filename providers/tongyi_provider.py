"""
阿里云通义万相Provider实现
严格遵循AstrBot开发规范的文生图服务提供商
"""

import asyncio
import base64
from typing import Optional, Dict, Any, List
from astrbot.api.logger import logger

from .base import BaseImageProvider, GenerationParams, GenerationResult, ResponseType, ProviderCapabilities


class TongyiProvider(BaseImageProvider):
    """阿里云通义万相Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化通义万相Provider
        
        Args:
            config: 配置字典
        """
        super().__init__()
        self.name = "tongyi"
        self.display_name = "阿里云通义万相"
        
        # 读取配置
        self.api_key = config.get("alibaba_api_key", "")
        self.model = config.get("alibaba_model", "wanx2.1-t2i-turbo")
        self.enable_prompt_extend = config.get("prompt_extend", False)
        
        # SDK客户端
        self.client = None
        
        # 能力描述
        self.capabilities = ProviderCapabilities(
            max_images_per_request=4,
            supports_negative_prompt=True,
            supports_style_control=True,
            supports_size_control=True,
            async_generation=True,
            supported_formats=["PNG", "JPEG"],
            max_prompt_length=500,
            max_negative_prompt_length=200
        )
        
        logger.info(f"通义万相Provider初始化: model={self.model}")
    
    async def initialize(self) -> bool:
        """异步初始化Provider"""
        try:
            if not self.api_key:
                logger.warning("通义万相Provider: 未配置API密钥")
                return False
            
            # 导入并初始化DashScope SDK
            import dashscope
            dashscope.api_key = self.api_key
            
            # 设置基础配置
            dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
            
            self.client = dashscope
            
            logger.info("通义万相Provider初始化成功")
            return True
            
        except ImportError as e:
            logger.error(f"通义万相Provider初始化失败: DashScope SDK未安装 - {e}")
            return False
        except Exception as e:
            logger.error(f"通义万相Provider初始化失败: {e}")
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
            
            logger.info(f"通义万相开始生成图片: {params.prompt[:50]}...")
            
            # 构建请求参数
            request_params = await self._build_request_params(params)
            
            # 调用API生成图片
            result = await self._call_api(request_params)
            
            # 处理响应
            generation_result = await self._process_response(result, params)
            
            logger.info(f"通义万相生成完成: {generation_result.is_success}")
            return generation_result
            
        except Exception as e:
            logger.error(f"通义万相生成图片失败: {e}")
            return GenerationResult(
                is_success=False,
                error_message=f"生成失败: {str(e)}",
                provider_name=self.name
            )
    
    async def _build_request_params(self, params: GenerationParams) -> Dict[str, Any]:
        """构建API请求参数"""
        
        # 基础参数
        request_params = {
            "model": self.model,
            "input": {
                "prompt": params.prompt
            },
            "parameters": {}
        }
        
        # 反向提示词
        if params.negative_prompt:
            request_params["input"]["negative_prompt"] = params.negative_prompt
        
        # 图片尺寸
        if params.size:
            # 通义万相支持的尺寸格式
            size_map = {
                (1024, 1024): "1024*1024",
                (1280, 720): "1280*720", 
                (720, 1280): "720*1280",
                (1024, 1792): "1024*1792",
                (1792, 1024): "1792*1024",
                (512, 512): "512*512",
                (768, 768): "768*768"
            }
            
            size_key = (params.size.width, params.size.height)
            if size_key in size_map:
                request_params["parameters"]["size"] = size_map[size_key]
            else:
                # 默认尺寸
                request_params["parameters"]["size"] = "1024*1024"
                logger.warning(f"不支持的尺寸 {params.size}，使用默认尺寸 1024*1024")
        
        # 生成数量
        if params.count and 1 <= params.count <= self.capabilities.max_images_per_request:
            request_params["parameters"]["n"] = params.count
        
        # 种子值
        if params.seed is not None:
            request_params["parameters"]["seed"] = params.seed
        
        # 风格控制
        if params.style:
            # 通义万相风格映射
            style_map = {
                "realistic": "<auto>",
                "cartoon": "<cartoon>", 
                "anime": "<anime>",
                "oil_painting": "<oil painting>",
                "watercolor": "<watercolor>",
                "sketch": "<sketch>",
                "cyberpunk": "<cyberpunk>",
                "fantasy": "<fantasy>"
            }
            
            if params.style in style_map:
                # 在提示词前添加风格标签
                style_prompt = f"{style_map[params.style]} {params.prompt}"
                request_params["input"]["prompt"] = style_prompt
        
        # Prompt增强
        if self.enable_prompt_extend and len(params.prompt) < 100:
            request_params["parameters"]["ref_mode"] = "repaint"
        
        logger.debug(f"通义万相请求参数: {request_params}")
        return request_params
    
    async def _call_api(self, request_params: Dict[str, Any]) -> Any:
        """调用通义万相API"""
        try:
            # 在线程池中执行同步API调用
            result = await asyncio.to_thread(
                self.client.ImageSynthesis.call,
                **request_params
            )
            
            # 检查API响应状态
            if result.status_code != 200:
                raise Exception(f"API调用失败: {result.status_code} - {result.message}")
            
            return result
            
        except Exception as e:
            logger.error(f"通义万相API调用失败: {e}")
            raise
    
    async def _process_response(self, result: Any, params: GenerationParams) -> GenerationResult:
        """处理API响应"""
        try:
            output = result.output
            
            if not output or "results" not in output:
                raise Exception("API响应格式错误：缺少results字段")
            
            results = output["results"]
            if not results:
                raise Exception("API响应为空")
            
            # 处理第一张图片（通义万相返回的是URL）
            first_result = results[0]
            image_url = first_result.get("url")
            
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
                "count": len(results),
                "api_usage": {
                    "request_id": getattr(result, "request_id", ""),
                    "total_tokens": output.get("usage", {}).get("total_tokens", 0)
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
            logger.error(f"通义万相响应处理失败: {e}")
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
                import dashscope
                sdk_available = True
            except ImportError:
                sdk_available = False
            
            if not sdk_available:
                return {
                    "status": "unhealthy", 
                    "message": "DashScope SDK未安装",
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
            logger.error(f"通义万相健康检查失败: {e}")
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
            
            # 构建最小测试请求
            test_params = {
                "model": self.model,
                "input": {
                    "prompt": "test connection"
                },
                "parameters": {
                    "size": "512*512",
                    "n": 1
                }
            }
            
            # 执行测试调用
            result = await asyncio.to_thread(
                self.client.ImageSynthesis.call,
                **test_params
            )
            
            response_time = time.time() - start_time
            
            if result.status_code == 200:
                return {
                    "success": True,
                    "response_time": response_time
                }
            else:
                return {
                    "success": False,
                    "error": f"API返回错误: {result.status_code} - {result.message}"
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
            "version": "wanx2.1",
            "capabilities": self.capabilities.__dict__,
            "supported_sizes": [
                "512*512", "768*768", "1024*1024", 
                "1280*720", "720*1280",
                "1024*1792", "1792*1024"
            ],
            "description": "阿里云通义万相文生图模型，支持高质量图片生成"
        }


def create_tongyi_provider(config: Dict[str, Any]) -> Optional[TongyiProvider]:
    """
    创建通义万相Provider实例
    
    Args:
        config: 配置字典
        
    Returns:
        Provider实例或None
    """
    try:
        provider = TongyiProvider(config)
        
        # 检查基础配置
        if not config.get("alibaba_api_key"):
            logger.warning("通义万相Provider: 未配置alibaba_api_key，跳过初始化")
            return None
        
        logger.info("成功创建通义万相Provider")
        return provider
        
    except Exception as e:
        logger.error(f"创建通义万相Provider失败: {e}")
        return None