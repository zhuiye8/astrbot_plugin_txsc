"""
科大讯飞星火Provider实现
严格遵循AstrBot开发规范的文生图服务提供商
"""

import asyncio
import base64
import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Optional, Dict, Any, List
from astrbot.api.logger import logger
import httpx

from .base import BaseImageProvider, GenerationParams, GenerationResult, ResponseType, ProviderCapabilities


class XunfeiProvider(BaseImageProvider):
    """科大讯飞星火Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化讯飞Provider
        
        Args:
            config: 配置字典
        """
        super().__init__()
        self.name = "xunfei"
        self.display_name = "科大讯飞星火"
        
        # 读取配置
        self.app_id = config.get("xunfei_app_id", "")
        self.api_secret = config.get("xunfei_api_secret", "")
        self.api_key = config.get("xunfei_api_key", "")
        
        # API配置
        self.base_url = "https://spark-api.cn-huabei-1.xf-yun.com/v2.1/tti"
        
        # 能力描述
        self.capabilities = ProviderCapabilities(
            max_images_per_request=1,  # 讯飞单次生成1张
            supports_negative_prompt=False,  # 讯飞不直接支持负面提示词
            supports_style_control=True,
            supports_size_control=True,
            async_generation=True,
            supported_formats=["PNG", "JPEG"],
            max_prompt_length=500,
            max_negative_prompt_length=0
        )
        
        logger.info("科大讯飞星火Provider初始化")
    
    async def initialize(self) -> bool:
        """异步初始化Provider"""
        try:
            if not all([self.app_id, self.api_secret, self.api_key]):
                logger.warning("科大讯飞Provider: 未配置完整的认证信息")
                return False
            
            logger.info("科大讯飞星火Provider初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"科大讯飞Provider初始化失败: {e}")
            return False
    
    def _generate_signature(self, method: str, url: str, body: str) -> str:
        """生成讯飞API签名"""
        try:
            # 解析URL
            parsed_url = urllib.parse.urlparse(url)
            host = parsed_url.hostname
            path = parsed_url.path
            query = parsed_url.query
            
            # 构建签名字符串
            signature_string = f"{method}\n{path}"
            if query:
                signature_string += f"?{query}"
            signature_string += f"\n{host}\n"
            
            # 添加请求体摘要
            if body:
                body_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()
                signature_string += f"content-sha256:{body_hash}\n"
            
            # 生成签名
            signature = base64.b64encode(
                hmac.new(
                    self.api_secret.encode('utf-8'),
                    signature_string.encode('utf-8'),
                    hashlib.sha256
                ).digest()
            ).decode('utf-8')
            
            return signature
            
        except Exception as e:
            logger.error(f"生成讯飞API签名失败: {e}")
            raise
    
    def _build_auth_headers(self, method: str, url: str, body: str) -> Dict[str, str]:
        """构建认证头"""
        try:
            # 生成时间戳
            timestamp = str(int(time.time()))
            
            # 生成签名
            signature = self._generate_signature(method, url, body)
            
            # 构建认证头
            headers = {
                "Content-Type": "application/json",
                "X-Appid": self.app_id,
                "X-CurTime": timestamp,
                "X-Param": base64.b64encode(json.dumps({"auf": "audio/L16;rate=16000"}).encode()).decode(),
                "X-CheckSum": hashlib.md5((self.api_key + timestamp + signature).encode()).hexdigest(),
                "Authorization": f"api_key=\"{self.api_key}\", algorithm=\"hmac-sha256\", headers=\"content-sha256\", signature=\"{signature}\""
            }
            
            return headers
            
        except Exception as e:
            logger.error(f"构建讯飞认证头失败: {e}")
            raise
    
    async def generate_image(self, params: GenerationParams) -> GenerationResult:
        """
        生成图片
        
        Args:
            params: 生成参数
            
        Returns:
            生成结果
        """
        try:
            logger.info(f"科大讯飞开始生成图片: {params.prompt[:50]}...")
            
            # 构建请求参数
            request_body = await self._build_request_params(params)
            
            # 调用API生成图片
            result = await self._call_api(request_body)
            
            # 处理响应
            generation_result = await self._process_response(result, params)
            
            logger.info(f"科大讯飞生成完成: {generation_result.is_success}")
            return generation_result
            
        except Exception as e:
            logger.error(f"科大讯飞生成图片失败: {e}")
            return GenerationResult(
                is_success=False,
                error_message=f"生成失败: {str(e)}",
                provider_name=self.name
            )
    
    async def _build_request_params(self, params: GenerationParams) -> str:
        """构建API请求参数"""
        
        # 处理提示词
        prompt_text = params.prompt
        
        # 添加风格
        if params.style:
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
                prompt_text = f"{prompt_text}, {style_map[params.style]}"
        
        # 处理负面提示词（转换为正面描述）
        if params.negative_prompt:
            prompt_text = f"{prompt_text}, 避免{params.negative_prompt}"
        
        # 基础参数
        request_data = {
            "header": {
                "app_id": self.app_id,
                "uid": "user123"  # 用户标识
            },
            "parameter": {
                "chat": {
                    "domain": "image",  # 图像生成领域
                    "width": 512,  # 默认宽度
                    "height": 512   # 默认高度
                }
            },
            "payload": {
                "message": {
                    "text": [
                        {
                            "role": "user",
                            "content": prompt_text
                        }
                    ]
                }
            }
        }
        
        # 设置图片尺寸
        if params.size:
            # 讯飞支持的尺寸
            width = params.size.width
            height = params.size.height
            
            # 限制尺寸范围
            width = max(256, min(width, 1024))
            height = max(256, min(height, 1024))
            
            request_data["parameter"]["chat"]["width"] = width
            request_data["parameter"]["chat"]["height"] = height
        
        # 种子值
        if params.seed is not None:
            request_data["parameter"]["chat"]["random_seed"] = params.seed % 2147483647
        
        request_body = json.dumps(request_data, ensure_ascii=False)
        logger.debug(f"科大讯飞请求参数: {request_body}")
        
        return request_body
    
    async def _call_api(self, request_body: str) -> Dict[str, Any]:
        """调用讯飞API"""
        try:
            # 构建认证头
            headers = self._build_auth_headers("POST", self.base_url, request_body)
            
            # 发送请求
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    content=request_body
                )
                
                response.raise_for_status()
                result = response.json()
                
                # 检查响应
                if result.get("header", {}).get("code") != 0:
                    error_msg = result.get("header", {}).get("message", "Unknown error")
                    raise Exception(f"API错误: {error_msg}")
                
                return result
                
        except Exception as e:
            logger.error(f"科大讯飞API调用失败: {e}")
            raise
    
    async def _process_response(self, result: Dict[str, Any], params: GenerationParams) -> GenerationResult:
        """处理API响应"""
        try:
            # 解析响应数据
            payload = result.get("payload", {})
            choices = payload.get("choices", {})
            text_data = choices.get("text", [])
            
            if not text_data:
                raise Exception("API响应中没有图片数据")
            
            # 获取图片数据
            first_choice = text_data[0]
            content = first_choice.get("content", "")
            
            if not content:
                raise Exception("API响应中图片内容为空")
            
            # 讯飞返回的通常是base64编码的图片
            image_base64 = content
            
            # 构建元数据
            metadata = {
                "provider": self.name,
                "model": "讯飞星火图像生成",
                "prompt": params.prompt,
                "negative_prompt": params.negative_prompt,
                "size": f"{params.size.width}x{params.size.height}" if params.size else "512x512",
                "seed": params.seed,
                "count": 1,
                "api_usage": {
                    "request_id": result.get("header", {}).get("sid", ""),
                    "status": result.get("header", {}).get("status", 0)
                }
            }
            
            return GenerationResult(
                is_success=True,
                data=image_base64,
                response_type=ResponseType.BASE64,
                metadata=metadata,
                provider_name=self.name
            )
            
        except Exception as e:
            logger.error(f"科大讯飞响应处理失败: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not all([self.app_id, self.api_secret, self.api_key]):
                missing_fields = []
                if not self.app_id:
                    missing_fields.append("app_id")
                if not self.api_secret:
                    missing_fields.append("api_secret")
                if not self.api_key:
                    missing_fields.append("api_key")
                
                return {
                    "status": "unhealthy",
                    "message": f"未配置认证信息: {', '.join(missing_fields)}",
                    "details": {
                        "app_id_configured": bool(self.app_id),
                        "api_secret_configured": bool(self.api_secret),
                        "api_key_configured": bool(self.api_key),
                        "missing_fields": missing_fields
                    }
                }
            
            # 执行API测试
            test_result = await self._test_api_connection()
            
            if test_result["success"]:
                return {
                    "status": "healthy",
                    "message": "连接正常",
                    "details": {
                        "app_id_configured": True,
                        "api_secret_configured": True,
                        "api_key_configured": True,
                        "api_accessible": True,
                        "response_time": test_result.get("response_time", 0)
                    }
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": f"API连接失败: {test_result['error']}",
                    "details": {
                        "app_id_configured": True,
                        "api_secret_configured": True,
                        "api_key_configured": True,
                        "api_accessible": False,
                        "error": test_result["error"]
                    }
                }
                
        except Exception as e:
            logger.error(f"科大讯飞健康检查失败: {e}")
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
            test_body = await self._build_request_params(
                GenerationParams(prompt="test connection")
            )
            
            # 执行测试调用
            result = await self._call_api(test_body)
            
            response_time = time.time() - start_time
            
            if result and result.get("header", {}).get("code") == 0:
                return {
                    "success": True,
                    "response_time": response_time
                }
            else:
                error_msg = result.get("header", {}).get("message", "Unknown error")
                return {
                    "success": False,
                    "error": f"API测试失败: {error_msg}"
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
            "model": "讯飞星火图像生成",
            "version": "2.1",
            "capabilities": self.capabilities.__dict__,
            "supported_sizes": [
                "256x256", "512x512", "768x768", "1024x1024"
            ],
            "description": "科大讯飞星火认知大模型图像生成能力"
        }


def create_xunfei_provider(config: Dict[str, Any]) -> Optional[XunfeiProvider]:
    """
    创建讯飞Provider实例
    
    Args:
        config: 配置字典
        
    Returns:
        Provider实例或None
    """
    try:
        provider = XunfeiProvider(config)
        
        # 检查基础配置
        required_fields = ["xunfei_app_id", "xunfei_api_secret", "xunfei_api_key"]
        missing_fields = [field for field in required_fields if not config.get(field)]
        
        if missing_fields:
            logger.warning(f"科大讯飞Provider: 未配置 {', '.join(missing_fields)}，跳过初始化")
            return None
        
        logger.info("成功创建科大讯飞Provider")
        return provider
        
    except Exception as e:
        logger.error(f"创建科大讯飞Provider失败: {e}")
        return None