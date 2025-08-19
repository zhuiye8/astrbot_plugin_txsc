import aiohttp
import json
from typing import Dict, Any

from .base import BaseProvider, GenerationConfig, ImageGenerationResult


class XAIProvider(BaseProvider):
    @property
    def required_config_keys(self) -> list[str]:
        return ["api_key"]
    
    @property
    def default_model(self) -> str:
        return "grok-2-image"
    
    def validate_config(self) -> bool:
        api_key = self.get_config_value("api_key")
        return isinstance(api_key, str) and api_key.strip() != ""
    
    async def generate_image(self, config: GenerationConfig) -> ImageGenerationResult:
        api_key = self.get_config_value("api_key")
        base_url = self.get_config_value("base_url", "https://api.x.ai/v1")
        model = config.model or self.get_config_value("model", self.default_model)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 映射尺寸
        size = self._map_size(config.width, config.height)
        quality = config.quality or "standard"
        
        data = {
            "model": model,
            "prompt": config.prompt,
            "size": size,
            "quality": quality,
            "n": 1
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/images/generations",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        image_url = result["data"][0]["url"]
                        return ImageGenerationResult(
                            success=True,
                            image_url=image_url
                        )
                    else:
                        error_text = await response.text()
                        try:
                            error_data = json.loads(error_text)
                            error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status}")
                        except:
                            error_msg = f"HTTP {response.status}: {error_text}"
                        return ImageGenerationResult(
                            success=False,
                            error_message=f"xAI API错误: {error_msg}"
                        )
        except Exception as e:
            return ImageGenerationResult(
                success=False,
                error_message=f"xAI请求异常: {str(e)}"
            )
    
    def _map_size(self, width: int, height: int) -> str:
        """将宽高映射到xAI支持的尺寸"""
        if width == height:
            if width <= 512:
                return "512x512"
            elif width <= 1024:
                return "1024x1024"
            else:
                return "1024x1024"
        elif width > height:
            return "1792x1024"
        else:
            return "1024x1792"