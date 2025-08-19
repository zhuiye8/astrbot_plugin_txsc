import aiohttp
import json
import base64
import hashlib
import hmac
from datetime import datetime
from urllib.parse import urlparse, urlencode
from typing import Dict, Any

from .base import BaseProvider, GenerationConfig, ImageGenerationResult
from astrbot.api import logger

# 导入用于生成标准RFC1123格式日期的库
from time import mktime
from wsgiref.handlers import format_date_time

class XunfeiProvider(BaseProvider):
    @property
    def required_config_keys(self) -> list[str]:
        return ["app_id", "api_key", "api_secret"]
    
    @property
    def default_model(self) -> str:
        return "v2.1"
    
    def validate_config(self) -> bool:
        return True
    
    def _build_authenticated_url(self, request_url: str, method: str = "POST") -> str:
        parsed_url = urlparse(request_url)
        host = parsed_url.netloc
        path = parsed_url.path
        date = format_date_time(mktime(datetime.now().timetuple()))
        signature_origin = f"host: {host}\ndate: {date}\n{method.upper()} {path} HTTP/1.1"
        api_secret = self.get_config_value("api_secret")
        signature_sha = hmac.new(
            api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_base64 = base64.b64encode(signature_sha).decode('utf-8')
        api_key = self.get_config_value("api_key")
        authorization_origin = (
            f'api_key="{api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature_base64}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        auth_params = { "host": host, "date": date, "authorization": authorization }
        return f"{request_url}?{urlencode(auth_params)}"

    async def generate_image(self, config: GenerationConfig) -> ImageGenerationResult:
        base_url = "https://spark-api.cn-huabei-1.xf-yun.com/v2.1/tti"
        authenticated_url = self._build_authenticated_url(base_url, method="POST")
        headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' }
        width, height = self._map_size(config.width, config.height)
        payload = {
            "header": { "app_id": self.get_config_value("app_id") },
            "parameter": { "chat": { "domain": "s2.1", "width": width, "height": height } },
            "payload": { "message": { "text": [ { "role": "user", "content": config.prompt } ] } }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(authenticated_url, headers=headers, data=json.dumps(payload), timeout=60) as response:
                    if response.status == 200:
                        # 【规范化改造】不再依赖Content-Type，直接尝试解析
                        try:
                            # 优先尝试作为JSON解析，使用 content_type=None 忽略响应头检查
                            result = await response.json(content_type=None)
                            header = result.get('header', {})
                            if header.get('code') == 0:
                                content = result['payload']['choices']['text'][0]['content']
                                return ImageGenerationResult(success=True, image_base64=content)
                            else:
                                error_msg = f"Code: {header.get('code')}, Message: {header.get('message')}"
                                return ImageGenerationResult(success=False, error_message=f"讯飞API业务错误: {error_msg}")
                        except (aiohttp.ContentTypeError, json.JSONDecodeError):
                            # 如果JSON解析失败，则认定为图片二进制流
                            image_bytes = await response.read()
                            if not image_bytes:
                                return ImageGenerationResult(success=False, error_message="讯飞返回了空的成功响应")
                            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                            return ImageGenerationResult(success=True, image_base64=image_base64)
                    else:
                        error_text = await response.text()
                        return ImageGenerationResult(success=False, error_message=f"讯飞API HTTP错误: {response.status} - {error_text}")
        except Exception as e:
            return ImageGenerationResult(success=False, error_message=f"请求讯飞时发生异常: {e}")

    def _map_size(self, width: int, height: int) -> tuple:
        supported_sizes = [
            (512, 512), (640, 360), (640, 480), (640, 640), (680, 512), (512, 680),
            (768, 768), (720, 1280), (1280, 720), (1024, 1024)
        ]
        target_ratio = width / height
        def size_difference(size):
            s_width, s_height = size
            ratio_diff = abs((s_width / s_height) - target_ratio)
            area_diff = abs(s_width * s_height - width * height)
            return ratio_diff * 0.7 + area_diff * 0.3
        best_size = min(supported_sizes, key=size_difference)
        return best_size