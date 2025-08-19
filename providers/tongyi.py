import aiohttp
import json
from typing import Dict, Any

from .base import BaseProvider, GenerationConfig, ImageGenerationResult


class TongyiProvider(BaseProvider):
    @property
    def required_config_keys(self) -> list[str]:
        return ["api_key"]
    
    @property
    def default_model(self) -> str:
        return "wanx-2.2"
    
    def validate_config(self) -> bool:
        api_key = self.get_config_value("api_key")
        return isinstance(api_key, str) and api_key.strip() != ""
    
    async def generate_image(self, config: GenerationConfig) -> ImageGenerationResult:
        api_key = self.get_config_value("api_key")
        base_url = self.get_config_value("base_url", "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis")
        model = config.model or self.get_config_value("model", self.default_model)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 映射尺寸
        size = self._map_size(config.width, config.height)
        
        data = {
            "model": model,
            "input": {
                "prompt": config.prompt
            },
            "parameters": {
                "size": size,
                "n": 1,
                "seed": self.get_config_value("seed"),
                "style": config.style
            }
        }
        
        # 移除None值
        data["parameters"] = {k: v for k, v in data["parameters"].items() if v is not None}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    base_url,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if "output" in result and "results" in result["output"]:
                            image_url = result["output"]["results"][0]["url"]
                            return ImageGenerationResult(
                                success=True,
                                image_url=image_url
                            )
                        else:
                            error_msg = result.get("message", "未知错误")
                            return ImageGenerationResult(
                                success=False,
                                error_message=f"通义万相API错误: {error_msg}"
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
                            error_message=f"通义万相API错误: {error_msg}"
                        )
        except Exception as e:
            return ImageGenerationResult(
                success=False,
                error_message=f"通义万相请求异常: {str(e)}"
            )
    
    def _map_size(self, width: int, height: int) -> str:
        """映射尺寸到通义万相支持的格式"""
        if width == height:
            if width <= 512:
                return "512*512"
            elif width <= 768:
                return "768*768"
            else:
                return "1024*1024"
        elif width > height:
            return "1280*720"
        else:
            return "720*1280"