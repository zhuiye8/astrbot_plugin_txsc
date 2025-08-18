"""
百度千帆Provider实现
严格遵循AstrBot开发规范的文生图服务提供商
"""

import asyncio
import base64
from typing import Optional, Dict, Any, List
from astrbot.api import logger

from .base import BaseImageProvider, GenerationParams, GenerationResult, ResponseType, ProviderCapabilities


class QianfanProvider(BaseImageProvider):
    """百度千帆Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化千帆Provider
        
        Args:
            config: 配置字典
        """
        super().__init__()
        self.name = "qianfan"
        self.display_name = "百度千帆"
        
        # 读取配置
        self.api_key = config.get("baidu_api_key", "")
        self.secret_key = config.get("baidu_secret_key", "")
        
        # SDK客户端
        self.client = None
        self.access_token = None
        
        # 能力描述
        self.capabilities = ProviderCapabilities(
            max_images_per_request=1,  # 千帆目前单次只支持1张
            supports_negative_prompt=False,  # 千帆不直接支持负面提示词
            supports_style_control=True,
            supports_size_control=True,
            async_generation=True,
            supported_formats=["PNG", "JPEG"],
            max_prompt_length=1000,
            max_negative_prompt_length=0
        )
        
        logger.info("百度千帆Provider初始化")
    
    async def initialize(self) -> bool:
        """异步初始化Provider"""
        try:
            if not self.api_key or not self.secret_key:
                logger.warning("百度千帆Provider: 未配置API密钥或Secret密钥")
                return False
            
            # 导入千帆SDK
            import qianfan
            
            # 设置认证信息
            qianfan.AK = self.api_key
            qianfan.SK = self.secret_key
            
            # 创建文生图客户端
            self.client = qianfan.Text2Image()
            
            # 获取access token
            await self._get_access_token()
            
            logger.info("百度千帆Provider初始化成功")
            return True
            
        except ImportError as e:
            logger.error(f"百度千帆Provider初始化失败: qianfan SDK未安装 - {e}")
            return False
        except Exception as e:
            logger.error(f"百度千帆Provider初始化失败: {e}")
            return False
    
    async def _get_access_token(self) -> Optional[str]:
        """获取access token"""
        try:
            import httpx
            
            # 百度OAuth API
            token_url = "https://aip.baidubce.com/oauth/2.0/token"
            params = {
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.secret_key
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                if "access_token" in data:
                    self.access_token = data["access_token"]
                    logger.debug("百度千帆access token获取成功")
                    return self.access_token
                else:
                    raise Exception(f"获取access token失败: {data}")
                    
        except Exception as e:
            logger.error(f"获取百度千帆access token失败: {e}")
            return None
    
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
            
            logger.info(f"百度千帆开始生成图片: {params.prompt[:50]}...")
            
            # 构建请求参数
            request_params = await self._build_request_params(params)
            
            # 调用API生成图片
            result = await self._call_api(request_params)
            
            # 处理响应
            generation_result = await self._process_response(result, params)
            
            logger.info(f"百度千帆生成完成: {generation_result.is_success}")
            return generation_result
            
        except Exception as e:
            logger.error(f"百度千帆生成图片失败: {e}")
            return GenerationResult(
                is_success=False,
                error_message=f"生成失败: {str(e)}",
                provider_name=self.name
            )
    
    async def _build_request_params(self, params: GenerationParams) -> Dict[str, Any]:
        """构建API请求参数"""
        
        # 基础参数
        request_params = {
            "prompt": params.prompt
        }
        
        # 图片尺寸
        if params.size:
            # 千帆支持的尺寸映射
            size_map = {
                (1024, 1024): "1024x1024",
                (1024, 1792): "1024x1792", 
                (1792, 1024): "1792x1024",
                (512, 512): "512x512",
                (768, 768): "768x768"
            }
            
            size_key = (params.size.width, params.size.height)
            if size_key in size_map:
                request_params["size"] = size_map[size_key]
            else:
                request_params["size"] = "1024x1024"
                logger.warning(f"不支持的尺寸 {params.size}，使用默认尺寸 1024x1024")
        
        # 风格控制
        if params.style:
            # 千帆风格映射
            style_map = {
                "realistic": "写实风格",
                "cartoon": "卡通风格", 
                "anime": "动漫风格",
                "oil_painting": "油画风格",
                "watercolor": "水彩风格",
                "sketch": "素描风格",
                "cyberpunk": "赛博朋克风格",
                "fantasy": "奇幻风格"
            }
            
            if params.style in style_map:
                # 在提示词中添加风格描述
                style_text = style_map[params.style]
                request_params["prompt"] = f"{params.prompt}, {style_text}"
        
        # 质量设置
        if params.quality:
            quality_map = {
                "high": "高质量",
                "highest": "最高质量",
                "standard": "标准质量"
            }
            
            if params.quality in quality_map:
                quality_text = quality_map[params.quality]
                request_params["prompt"] = f"{params.prompt}, {quality_text}"
        
        # 处理负面提示词（千帆不直接支持，我们将其转换为正面描述）
        if params.negative_prompt:
            # 将负面提示词转换为避免的描述
            avoid_text = f"避免{params.negative_prompt}"
            request_params["prompt"] = f"{request_params['prompt']}, {avoid_text}"
        
        # 种子值（千帆不直接支持，但我们可以记录）
        if params.seed is not None:
            request_params["seed"] = params.seed
        
        logger.debug(f"百度千帆请求参数: {request_params}")
        return request_params
    
    async def _call_api(self, request_params: Dict[str, Any]) -> Any:
        """调用千帆API"""
        try:
            # 千帆使用同步接口，在线程池中执行
            result = await asyncio.to_thread(
                self.client.do,
                **request_params
            )
            
            # 检查响应
            if not result or "result" not in result:
                raise Exception(f"API调用失败: 无效响应")
            
            return result
            
        except Exception as e:
            logger.error(f"百度千帆API调用失败: {e}")
            raise
    
    async def _process_response(self, result: Any, params: GenerationParams) -> GenerationResult:
        """处理API响应"""
        try:
            # 千帆返回格式分析
            result_data = result.get("result", {})
            
            # 获取图片数据（通常是base64）
            image_data = result_data.get("data", [])
            if not image_data:
                raise Exception("API响应中没有图片数据")
            
            # 取第一张图片
            first_image = image_data[0] if isinstance(image_data, list) else image_data
            
            # 千帆通常返回base64格式的图片
            if isinstance(first_image, dict):
                image_base64 = first_image.get("b64_image", "")
                if not image_base64:
                    raise Exception("API响应中缺少图片base64数据")
            else:
                image_base64 = first_image
            
            # 构建元数据
            metadata = {
                "provider": self.name,
                "model": "千帆文生图",
                "prompt": params.prompt,
                "negative_prompt": params.negative_prompt,
                "size": f"{params.size.width}x{params.size.height}" if params.size else "1024x1024",
                "seed": params.seed,
                "count": 1,
                "api_usage": result.get("usage", {})
            }
            
            return GenerationResult(
                is_success=True,
                data=image_base64,
                response_type=ResponseType.BASE64,
                metadata=metadata,
                provider_name=self.name
            )
            
        except Exception as e:
            logger.error(f"百度千帆响应处理失败: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self.api_key or not self.secret_key:
                return {
                    "status": "unhealthy",
                    "message": "未配置API密钥或Secret密钥",
                    "details": {
                        "api_key_configured": bool(self.api_key),
                        "secret_key_configured": bool(self.secret_key),
                        "sdk_available": False
                    }
                }
            
            # 检查SDK可用性
            try:
                import qianfan
                sdk_available = True
            except ImportError:
                sdk_available = False
            
            if not sdk_available:
                return {
                    "status": "unhealthy",
                    "message": "qianfan SDK未安装",
                    "details": {
                        "api_key_configured": True,
                        "secret_key_configured": True,
                        "sdk_available": False
                    }
                }
            
            # 检查access token
            if not self.access_token:
                token_result = await self._get_access_token()
                if not token_result:
                    return {
                        "status": "unhealthy",
                        "message": "无法获取access token",
                        "details": {
                            "api_key_configured": True,
                            "secret_key_configured": True,
                            "sdk_available": True,
                            "token_accessible": False
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
                        "secret_key_configured": True,
                        "sdk_available": True,
                        "token_accessible": True,
                        "api_accessible": True,
                        "response_time": test_result.get("response_time", 0)
                    }
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": f"API连接失败: {test_result['error']}",
                    "details": {
                        "api_key_configured": True,
                        "secret_key_configured": True,
                        "sdk_available": True,
                        "token_accessible": True,
                        "api_accessible": False,
                        "error": test_result["error"]
                    }
                }
                
        except Exception as e:
            logger.error(f"百度千帆健康检查失败: {e}")
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
                "prompt": "test connection",
                "size": "512x512"
            }
            
            # 执行测试调用
            result = await asyncio.to_thread(
                self.client.do,
                **test_params
            )
            
            response_time = time.time() - start_time
            
            if result and "result" in result:
                return {
                    "success": True,
                    "response_time": response_time
                }
            else:
                return {
                    "success": False,
                    "error": f"API测试调用失败: {result}"
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
            "model": "千帆文生图",
            "version": "1.0",
            "capabilities": self.capabilities.__dict__,
            "supported_sizes": [
                "512x512", "768x768", "1024x1024", 
                "1024x1792", "1792x1024"
            ],
            "description": "百度千帆文生图模型，支持多种风格的图片生成"
        }


def create_qianfan_provider(config: Dict[str, Any]) -> Optional[QianfanProvider]:
    """
    创建千帆Provider实例
    
    Args:
        config: 配置字典
        
    Returns:
        Provider实例或None
    """
    try:
        provider = QianfanProvider(config)
        
        # 检查基础配置
        if not config.get("baidu_api_key") or not config.get("baidu_secret_key"):
            logger.warning("百度千帆Provider: 未配置baidu_api_key或baidu_secret_key，跳过初始化")
            return None
        
        logger.info("成功创建百度千帆Provider")
        return provider
        
    except Exception as e:
        logger.error(f"创建百度千帆Provider失败: {e}")
        return None