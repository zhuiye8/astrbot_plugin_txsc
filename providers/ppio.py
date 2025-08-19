import aiohttp
import json
import asyncio
from typing import Dict, Any
from .base import BaseProvider, GenerationConfig, ImageGenerationResult
from astrbot.api import logger



class PPIOProvider(BaseProvider):
    @property
    def required_config_keys(self) -> list[str]:
        return ["api_key"]
    
    @property
    def default_model(self) -> str:
        return "sd15"
    
    def validate_config(self) -> bool:
        api_key = self.get_config_value("api_key")
        return isinstance(api_key, str) and api_key.strip() != ""
    
    async def generate_image(self, config: GenerationConfig) -> ImageGenerationResult:
        api_key = self.get_config_value("api_key")
        base_url = self.get_config_value("base_url", "https://api.ppinfra.com")
        model = config.model or self.get_config_value("model", self.default_model)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model_name": model,
            "prompt": config.prompt,
            "width": config.width,
            "height": config.height,
            "steps": self.get_config_value("steps", 20),
            "guidance_scale": self.get_config_value("guidance_scale", 9),
            "sampler_name": self.get_config_value("sampler", "DPM++ 2M Karras"),
            "image_num": 1
        }
        logger.info(f"PPIO提交任务: {data}")
        
        try:
            # 第一步：提交异步任务
            task_id = await self._submit_task(base_url, headers, data)
            if not task_id:
                return ImageGenerationResult(
                    success=False,
                    error_message="提交PPIO任务失败"
                )
            
            logger.info(f"PPIO任务已提交，任务ID: {task_id}")
            
            # 第二步：轮询任务状态
            return await self._poll_task_result(base_url, headers, task_id)
            
        except Exception as e:
            return ImageGenerationResult(
                success=False,
                error_message=f"PPIO请求异常: {str(e)}"
            )
    
    async def _submit_task(self, base_url: str, headers: dict, data: dict) -> str:
        """提交异步任务，返回任务ID"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/v3/async/txt2img",
                headers=headers,
                json={"request": data},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("task_id")
                else:
                    error_text = await response.text()
                    logger.error(f"PPIO提交任务失败: {response.status} - {error_text}")
                    return None
    
    async def _poll_task_result(self, base_url: str, headers: dict, task_id: str, max_attempts: int = 12) -> ImageGenerationResult:
        """轮询任务结果"""
        async with aiohttp.ClientSession() as session:
            for attempt in range(max_attempts):
                try:
                    await asyncio.sleep(5 if attempt < 6 else 10)  # 前6次每5秒，后续每10秒
                    
                    async with session.get(
                        f"{base_url}/v3/async/task-result",
                        headers=headers,
                        params={"task_id": task_id},
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            task_info = result.get("task", {})
                            status = task_info.get("status")
                            
                            if status == "TASK_STATUS_SUCCEED":
                                images = result.get("images", [])
                                if images and images[0].get("image_url"):
                                    logger.info(f"PPIO任务完成，第{attempt + 1}次轮询")
                                    return ImageGenerationResult(
                                        success=True,
                                        image_url=images[0]["image_url"]
                                    )
                                else:
                                    return ImageGenerationResult(
                                        success=False,
                                        error_message="PPIO任务完成但没有找到图片URL"
                                    )
                            elif status == "TASK_STATUS_FAILED":
                                error_msg = result.get("message", "任务失败")
                                return ImageGenerationResult(
                                    success=False,
                                    error_message=f"PPIO任务失败: {error_msg}"
                                )
                            elif status == "TASK_STATUS_PROCESSING":
                                logger.info(f"PPIO任务进行中，状态: {status}，第{attempt + 1}次轮询")
                                continue
                            elif status == "TASK_STATUS_QUEUED":
                                logger.info(f"PPIO任务排队中，状态: {status}，第{attempt + 1}次轮询")
                                continue
                            else:
                                logger.warning(f"PPIO任务未知状态: {status}")
                                continue
                        else:
                            logger.warning(f"PPIO轮询失败: {response.status}")
                            continue
                            
                except asyncio.TimeoutError:
                    logger.warning(f"PPIO轮询超时，第{attempt + 1}次")
                    continue
                except Exception as e:
                    logger.warning(f"PPIO轮询异常，第{attempt + 1}次: {str(e)}")
                    continue
            
            return ImageGenerationResult(
                success=False,
                error_message=f"PPIO任务超时，已轮询{max_attempts}次但未完成"
            )