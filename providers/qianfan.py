import aiohttp
import json
from typing import Dict, Any

from .base import BaseProvider, GenerationConfig, ImageGenerationResult


class QianfanProvider(BaseProvider):
    @property
    def required_config_keys(self) -> list[str]:
        return ["access_token"]
    
    @property
    def default_model(self) -> str:
        return "flux.1-schnell"
    
    def validate_config(self) -> bool:
        access_token = self.get_config_value("access_token")
        return isinstance(access_token, str) and access_token.strip() != ""
    
    async def generate_image(self, config: GenerationConfig) -> ImageGenerationResult:
        access_token = self.get_config_value("access_token")
        model = config.model or self.get_config_value("model", self.default_model)
        
        # 使用新的V2 API
        base_url = "https://qianfan.baidubce.com/v2/images/generations"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        # 映射尺寸
        size_str = self._map_size(config.width, config.height)
        
        data = {
            "model": model,
            "prompt": config.prompt,
            "size": size_str,
            "n": 1
        }
        
        # 根据模型添加特定参数
        if model == "flux.1-schnell":
            data["steps"] = self.get_config_value("steps", 4)
            
        url = base_url
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if "data" in result and result["data"]:
                            # 新API返回的是 URL 而不是 base64
                            image_url = result["data"][0]["url"]
                            return ImageGenerationResult(
                                success=True,
                                image_url=image_url
                            )
                        else:
                            error_msg = result.get("message", "未知错误")
                            return ImageGenerationResult(
                                success=False,
                                error_message=f"千帆API错误: {error_msg}"
                            )
                    else:
                        error_text = await response.text()
                        try:
                            error_data = json.loads(error_text)
                            error_msg = error_data.get("message", f"HTTP {response.status}")
                        except:
                            error_msg = f"HTTP {response.status}: {error_text}"
                        return ImageGenerationResult(
                            success=False,
                            error_message=f"千帆API错误: {error_msg}"
                        )
        except Exception as e:
            return ImageGenerationResult(
                success=False,
                error_message=f"千帆请求异常: {str(e)}"
            )
    
    def _map_size(self, width: int, height: int) -> str:
        """映射尺寸到千帆支持的格式"""
        # 新API支持更多尺寸选项
        if width == height:
            if width <= 512:
                return "512x512"
            elif width <= 768:
                return "768x768"
            elif width <= 1024:
                return "1024x1024"
            elif width <= 1536:
                return "1536x1536"
            else:
                return "2048x2048"
        elif width > height:
            if width <= 1024:
                return "1024x768"
            else:
                return "2048x1536"
        else:
            if height <= 1024:
                return "768x1024"
            else:
                return "1536x2048"