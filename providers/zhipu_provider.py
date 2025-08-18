"""
智谱AI（智谱清言）Provider实现
严格遵循AstrBot开发规范的文生图服务提供商
"""

import asyncio
import base64
from typing import Optional, Dict, Any, List
from astrbot.api.logger import logger

from .base import BaseImageProvider, GenerationParams, GenerationResult, ResponseType, ProviderCapabilities


class ZhipuProvider(BaseImageProvider):
    """智谱AI（智谱清言）Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化智谱AI Provider
        
        Args:
            config: 配置字典
        """
        super().__init__()
        self.name = "zhipu"
        self.display_name = "智谱清言"
        
        # 读取配置
        self.api_key = config.get("zhipu_api_key", "")
        self.model = "cogview-3"  # 智谱AI的CogView-3模型
        
        # SDK客户端
        self.client = None
        
        # 能力描述
        self.capabilities = ProviderCapabilities(
            max_images_per_request=1,  # 智谱单次生成1张
            supports_negative_prompt=False,  # CogView-3不直接支持负面提示词
            supports_style_control=True,
            supports_size_control=True,
            async_generation=True,
            supported_formats=["PNG", "JPEG"],
            max_prompt_length=1000,  # 智谱支持较长的中文提示词
            max_negative_prompt_length=0
        )
        
        logger.info(f"智谱清言Provider初始化: model={self.model}")
    
    async def initialize(self) -> bool:
        """异步初始化Provider"""
        try:
            if not self.api_key:
                logger.warning("智谱清言Provider: 未配置API密钥")
                return False
            
            # 导入并初始化智谱AI SDK
            import zhipuai
            
            # 设置API密钥
            zhipuai.api_key = self.api_key
            
            # 创建客户端实例
            self.client = zhipuai
            
            logger.info("智谱清言Provider初始化成功")
            return True
            
        except ImportError as e:
            logger.error(f"智谱清言Provider初始化失败: zhipuai SDK未安装 - {e}")
            return False
        except Exception as e:
            logger.error(f"智谱清言Provider初始化失败: {e}")
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
            
            logger.info(f"智谱清言开始生成图片: {params.prompt[:50]}...")
            
            # 构建请求参数
            request_params = await self._build_request_params(params)
            
            # 调用API生成图片
            result = await self._call_api(request_params)
            
            # 处理响应
            generation_result = await self._process_response(result, params)
            
            logger.info(f"智谱清言生成完成: {generation_result.is_success}")
            return generation_result
            
        except Exception as e:
            logger.error(f"智谱清言生成图片失败: {e}")
            return GenerationResult(
                is_success=False,
                error_message=f"生成失败: {str(e)}",
                provider_name=self.name
            )
    
    async def _build_request_params(self, params: GenerationParams) -> Dict[str, Any]:
        """构建API请求参数"""
        
        # 处理提示词 - 智谱AI对中文支持很好
        prompt_text = params.prompt
        
        # 添加风格描述
        if params.style:
            # 智谱AI风格映射（更适合中文描述）
            style_map = {
                "realistic": "真实摄影风格",
                "cartoon": "卡通插画风格", 
                "anime": "日式动漫风格",
                "oil_painting": "古典油画风格",
                "watercolor": "中国水彩画风格",
                "sketch": "素描手绘风格",
                "cyberpunk": "赛博朋克科幻风格",
                "fantasy": "奇幻魔法风格",
                "chinese": "中国传统绘画风格",
                "modern": "现代艺术风格"
            }
            
            if params.style in style_map:
                prompt_text = f"{prompt_text}，{style_map[params.style]}"
        
        # 处理质量要求
        if params.quality:
            quality_map = {
                "high": "高质量渲染",
                "highest": "超高质量精细渲染",
                "standard": "标准质量",
                "fast": "快速生成"
            }
            
            if params.quality in quality_map:
                prompt_text = f"{prompt_text}，{quality_map[params.quality]}"
        
        # 处理负面提示词（转换为正面描述）
        if params.negative_prompt:
            # 智谱AI可以理解"避免"、"不要"等中文表达
            prompt_text = f"{prompt_text}，请避免出现{params.negative_prompt}"
        
        # 基础参数
        request_params = {
            "model": self.model,
            "prompt": prompt_text
        }
        
        # 图片尺寸设置
        if params.size:
            # 智谱AI支持的尺寸映射
            width = params.size.width
            height = params.size.height
            
            # CogView-3支持的常见尺寸
            supported_sizes = [
                (512, 512), (768, 768), (1024, 1024),
                (512, 768), (768, 512),
                (1024, 768), (768, 1024),
                (1024, 1536), (1536, 1024)
            ]
            
            # 找到最接近的支持尺寸
            target_size = (width, height)
            if target_size not in supported_sizes:
                # 选择最接近的尺寸
                closest_size = min(supported_sizes, 
                                 key=lambda s: abs(s[0]*s[1] - width*height))
                width, height = closest_size
                logger.warning(f"调整尺寸从 {params.size} 到 {width}x{height}")
            
            request_params.update({
                "size": f"{width}x{height}"
            })
        
        # 种子值
        if params.seed is not None:
            request_params["seed"] = params.seed
        
        # 生成数量
        request_params["n"] = 1  # 智谱单次生成1张
        
        logger.debug(f"智谱清言请求参数: {request_params}")
        return request_params
    
    async def _call_api(self, request_params: Dict[str, Any]) -> Any:
        """调用智谱AI API"""
        try:
            # 在线程池中执行同步API调用
            result = await asyncio.to_thread(
                self.client.model_api.invoke,
                **request_params
            )
            
            # 检查API响应状态
            if not result or not result.get("success", False):
                error_msg = result.get("msg", "未知错误") if result else "API调用无响应"
                raise Exception(f"API调用失败: {error_msg}")
            
            return result
            
        except Exception as e:
            logger.error(f"智谱清言API调用失败: {e}")
            raise
    
    async def _process_response(self, result: Any, params: GenerationParams) -> GenerationResult:
        """处理API响应"""
        try:
            # 解析智谱AI响应格式
            data = result.get("data", {})
            
            # 获取生成的图片数据
            if "url" in data:
                # URL格式返回
                image_url = data["url"]
                response_type = ResponseType.URL
                image_data = image_url
            elif "image" in data:
                # Base64格式返回
                image_base64 = data["image"]
                response_type = ResponseType.BASE64
                image_data = image_base64
            elif "task_id" in data:
                # 异步任务，需要轮询结果
                task_id = data["task_id"]
                image_data = await self._poll_async_result(task_id)
                response_type = ResponseType.BASE64
            else:
                raise Exception("API响应格式错误：缺少图片数据")
            
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
                    "task_id": data.get("task_id", ""),
                    "request_id": data.get("request_id", ""),
                    "usage": data.get("usage", {})
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
            logger.error(f"智谱清言响应处理失败: {e}")
            raise
    
    async def _poll_async_result(self, task_id: str, max_polls: int = 30) -> str:
        """轮询异步生成结果"""
        try:
            for i in range(max_polls):
                # 查询任务状态
                status_result = await asyncio.to_thread(
                    self.client.model_api.query_async_invoke_result,
                    task_id=task_id
                )
                
                if status_result.get("success"):
                    task_status = status_result.get("task_status", "")
                    
                    if task_status == "SUCCESS":
                        # 任务完成，获取结果
                        data = status_result.get("data", {})
                        if "image" in data:
                            return data["image"]
                        else:
                            raise Exception("异步任务完成但缺少图片数据")
                    
                    elif task_status == "FAIL":
                        error_msg = status_result.get("msg", "异步任务失败")
                        raise Exception(f"异步任务失败: {error_msg}")
                    
                    elif task_status in ["PROCESSING", "INIT"]:
                        # 任务处理中，等待后继续轮询
                        await asyncio.sleep(2)
                        continue
                
                else:
                    logger.warning(f"查询任务状态失败，重试中... ({i+1}/{max_polls})")
                    await asyncio.sleep(2)
            
            raise Exception("异步任务轮询超时")
            
        except Exception as e:
            logger.error(f"轮询异步结果失败: {e}")
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
                import zhipuai
                sdk_available = True
            except ImportError:
                sdk_available = False
            
            if not sdk_available:
                return {
                    "status": "unhealthy", 
                    "message": "zhipuai SDK未安装",
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
            logger.error(f"智谱清言健康检查失败: {e}")
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
                "prompt": "测试连接",
                "size": "512x512",
                "n": 1
            }
            
            # 执行测试调用
            result = await asyncio.to_thread(
                self.client.model_api.invoke,
                **test_params
            )
            
            response_time = time.time() - start_time
            
            if result and result.get("success", False):
                return {
                    "success": True,
                    "response_time": response_time
                }
            else:
                error_msg = result.get("msg", "未知错误") if result else "API无响应"
                return {
                    "success": False,
                    "error": f"API返回错误: {error_msg}"
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
            "version": "CogView-3",
            "capabilities": self.capabilities.__dict__,
            "supported_sizes": [
                "512x512", "768x768", "1024x1024",
                "512x768", "768x512", 
                "1024x768", "768x1024",
                "1024x1536", "1536x1024"
            ],
            "description": "智谱AI CogView-3多模态大模型，强大的中文理解和图像生成能力"
        }


def create_zhipu_provider(config: Dict[str, Any]) -> Optional[ZhipuProvider]:
    """
    创建智谱AI Provider实例
    
    Args:
        config: 配置字典
        
    Returns:
        Provider实例或None
    """
    try:
        provider = ZhipuProvider(config)
        
        # 检查基础配置
        if not config.get("zhipu_api_key"):
            logger.warning("智谱清言Provider: 未配置zhipu_api_key，跳过初始化")
            return None
        
        logger.info("成功创建智谱清言Provider")
        return provider
        
    except Exception as e:
        logger.error(f"创建智谱清言Provider失败: {e}")
        return None