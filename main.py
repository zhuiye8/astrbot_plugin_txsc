import asyncio
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# 【新增】导入所需模块
import tempfile
import os
import base64

from astrbot.api import logger
from astrbot.api.star import Star, Context, register
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain, Image

from .providers.base import BaseProvider, GenerationConfig, ImageGenerationResult


@register(
    "astrbot_plugin_universal_t2i",
    "zhuiye", 
    "通用文生图插件，支持9个主流AI图像生成服务商的统一调用",
    "1.0.0"
)
class UniversalTextToImagePlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.providers: Dict[str, BaseProvider] = {}
        self.active_providers: List[str] = []
        
        self.plugin_name = "通用文生图插件"
        self.plugin_description = "支持多家供应商的文生图功能"
        self.plugin_version = "1.0.0"
        
        logger.info("初始化通用文生图插件")
        self._load_providers()
        self._initialize_providers()
    
    def _load_providers(self):
        """动态加载所有供应商"""
        try:
            from .providers.ppio import PPIOProvider
            from .providers.qianfan import QianfanProvider
            from .providers.tongyi import TongyiProvider
            from .providers.volcengine import VolcengineProvider
            from .providers.xunfei import XunfeiProvider
            from .providers.zhipu import ZhipuProvider
            
            provider_mappings = {
                'zhipu': (ZhipuProvider, 'zhipu'),
                'qianfan': (QianfanProvider, 'qianfan'),
                'ppio': (PPIOProvider, 'ppio'),
                'tongyi': (TongyiProvider, 'tongyi'),
                'volcengine': (VolcengineProvider, 'volcengine'),
                'xunfei': (XunfeiProvider, 'xunfei')
            }
            
            for provider_name, (provider_class, config_prefix) in provider_mappings.items():
                try:
                    provider_config = self._get_provider_config(config_prefix)
                    if provider_config:
                        self.providers[provider_name] = provider_class(provider_config)
                        logger.info(f"加载供应商: {provider_name}")
                except Exception as e:
                    logger.warning(f"加载供应商 {provider_name} 失败: {e}")
                    
        except ImportError as e:
            logger.error(f"导入供应商模块失败: {e}")
    
    def _get_provider_config(self, prefix: str) -> Dict[str, Any]:
        """从扁平化配置中提取供应商配置"""
        config = {}
        
        if prefix == 'zhipu':
            api_key = self.config.get('zhipu_api_key', '')
            if api_key:
                config = {
                    'api_key': api_key,
                    'base_url': self.config.get('zhipu_base_url'),
                    'model': self.config.get('zhipu_model')
                }
        elif prefix == 'qianfan':
            access_token = self.config.get('qianfan_access_token', '')
            if access_token:
                config = {
                    'access_token': access_token,
                    'model': self.config.get('qianfan_model'),
                    'steps': self.config.get('qianfan_steps')
                }
        elif prefix == 'ppio':
            api_key = self.config.get('ppio_api_key', '')
            if api_key:
                config = {
                    'api_key': api_key,
                    'base_url': self.config.get('ppio_base_url'),
                    'model': self.config.get('ppio_model'),
                    'steps': self.config.get('ppio_steps'),
                    'guidance_scale': self.config.get('ppio_guidance_scale')
                }
        elif prefix == 'tongyi':
            api_key = self.config.get('tongyi_api_key', '')
            if api_key:
                config = {
                    'api_key': api_key,
                    'base_url': self.config.get('tongyi_base_url'),
                    'model': self.config.get('tongyi_model')
                }
        elif prefix == 'volcengine':
            api_key = self.config.get('volcengine_api_key', '')
            if api_key:
                config = {
                    'api_key': api_key,
                    'base_url': self.config.get('volcengine_base_url'),
                    'model': self.config.get('volcengine_model')
                }
        elif prefix == 'xunfei':
            app_id = self.config.get('xunfei_app_id', '')
            api_key = self.config.get('xunfei_api_key', '')
            api_secret = self.config.get('xunfei_api_secret', '')
            if app_id and api_key and api_secret:
                config = {
                    'app_id': app_id,
                    'api_key': api_key,
                    'api_secret': api_secret
                }
        
        return config
    
    def _initialize_providers(self):
        """初始化可用的供应商"""
        for name, provider in self.providers.items():
            try:
                if provider.is_configured():
                    self.active_providers.append(name)
                    logger.info(f"供应商 {name} 已配置并可用")
                else:
                    logger.warning(f"供应商 {name} 配置不完整")
            except Exception as e:
                logger.error(f"初始化供应商 {name} 失败: {e}")
        
        if not self.active_providers:
            logger.warning("没有可用的文生图供应商")
        else:
            logger.info(f"已启用 {len(self.active_providers)} 个供应商: {', '.join(self.active_providers)}")

    @filter.command("tti", alias={"文生图"})
    async def text_to_image_command(self, event: AstrMessageEvent):
        """文生图命令"""
        async for result in self._handle_image_generation(event, None):
            yield result
    
    @filter.command("tti-zhipu")
    async def text_to_image_zhipu_command(self, event: AstrMessageEvent):
        """使用智谱AI生成图片"""
        async for result in self._handle_image_generation(event, "zhipu"):
            yield result
    
    @filter.command("tti-qianfan")
    async def text_to_image_qianfan_command(self, event: AstrMessageEvent):
        """使用百度千帆生成图片"""
        async for result in self._handle_image_generation(event, "qianfan"):
            yield result
    
    @filter.command("tti-tongyi")
    async def text_to_image_tongyi_command(self, event: AstrMessageEvent):
        """使用阿里通义万相生成图片"""
        async for result in self._handle_image_generation(event, "tongyi"):
            yield result
    
    @filter.command("tti-ppio")
    async def text_to_image_ppio_command(self, event: AstrMessageEvent):
        """使用PPIO生成图片"""
        async for result in self._handle_image_generation(event, "ppio"):
            yield result
    
    @filter.command("tti-huoshan")
    async def text_to_image_volcengine_command(self, event: AstrMessageEvent):
        """使用火山引擎生成图片"""
        async for result in self._handle_image_generation(event, "volcengine"):
            yield result
    
    @filter.command("tti-xunfei")
    async def text_to_image_xunfei_command(self, event: AstrMessageEvent):
        """使用科大讯飞生成图片"""
        async for result in self._handle_image_generation(event, "xunfei"):
            yield result
    
    async def _handle_image_generation(self, event: AstrMessageEvent, specific_provider: str = None):
        """统一的图像生成处理方法"""
        args = event.message_str.strip().split()[1:]
        if not args:
            yield event.plain_result(self._get_help_text())
            return
            
        prompt = " ".join(args)
        
        if specific_provider:
            if specific_provider not in self.active_providers:
                if specific_provider not in self.providers:
                    yield event.plain_result(f"供应商 {specific_provider} 未配置")
                else:
                    yield event.plain_result(f"供应商 {specific_provider} 配置无效或不可用")
                return
            available_providers = [specific_provider]
            yield event.plain_result(f"正在使用 {specific_provider} 生成图片: {prompt}")
        else:
            if not self.active_providers:
                yield event.plain_result("当前没有可用的文生图服务，请检查配置")
                return
            available_providers = self.active_providers
            yield event.plain_result(f"正在生成图片: {prompt}")
        
        config = GenerationConfig(
            prompt=prompt,
            width=self.config.get("default_width", 512),
            height=self.config.get("default_height", 512)
        )
        
        result = await self._generate_with_providers(config, available_providers)
        
        if result.success and result.has_image:
            if result.image_url:
                yield event.image_result(result.image_url)
            elif result.image_base64:
                # 最终解决方案：临时文件法
                tmp_file_path = None
                try:
                    # 1. 解码Base64
                    image_data = base64.b64decode(result.image_base64)
                    
                    # 2. 创建一个带.png后缀的临时文件
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                        # 3. 写入图片数据
                        tmp_file.write(image_data)
                        tmp_file_path = tmp_file.name
                    
                    # 4. 使用文件路径发送图片
                    yield event.image_result(tmp_file_path)

                except Exception as e:
                    logger.error(f"处理base64图片并发送时出错: {e}")
                    yield event.plain_result("图片已生成，但在发送时遇到问题。")
                finally:
                    # 5. 确保清理临时文件
                    if tmp_file_path and os.path.exists(tmp_file_path):
                        os.remove(tmp_file_path)
        else:
            error_msg = result.error_message or "生成图片失败"
            yield event.plain_result(f"生成失败: {error_msg}")
    
    async def _generate_with_providers(self, config: GenerationConfig, providers_list: list) -> ImageGenerationResult:
        """使用指定的供应商列表生成图片"""
        errors = []
        
        for provider_name in providers_list:
            if provider_name not in self.providers:
                errors.append(f"{provider_name}: 供应商未配置")
                continue
                
            provider = self.providers[provider_name]
            try:
                logger.info(f"尝试使用供应商: {provider_name}")
                result = await provider.generate_image(config)
                if result.success:
                    logger.info(f"供应商 {provider_name} 生成成功")
                    return result
                else:
                    error_msg = result.error_message or "未知错误"
                    logger.warning(f"供应商 {provider_name} 生成失败: {error_msg}")
                    errors.append(f"{provider_name}: {error_msg}")
            except Exception as e:
                error_msg = f"请求异常: {str(e)}"
                logger.error(f"供应商 {provider_name} 异常: {error_msg}")
                errors.append(f"{provider_name}: {error_msg}")
        
        if len(providers_list) == 1:
            error_message = errors[0].split(": ", 1)[1] if errors else "生成失败"
        else:
            error_message = f"所有供应商都无法生成图片。详细错误: {'; '.join(errors)}"
            
        return ImageGenerationResult(success=False, error_message=error_message)
    
    def _get_help_text(self) -> str:
        """生成帮助文本"""
        provider_commands = []
        provider_display = {
            'zhipu': 'zhipu',
            'qianfan': 'qianfan', 
            'tongyi': 'tongyi',
            'ppio': 'ppio',
            'volcengine': 'huoshan',
            'xunfei': 'xunfei'
        }
        
        for provider, cmd_name in provider_display.items():
            status = "✓" if provider in self.active_providers else "✗"
            provider_commands.append(f"  /tti-{cmd_name} <描述> - {status}")
        
        return f"""🎨 通用文生图插件使用帮助

📋 基本命令:
/tti <描述文字> - 自动选择供应商生成图片
/文生图 <描述文字> - 同上（中文别名）

🎯 指定供应商命令:
{chr(10).join(provider_commands)}

📊 当前可用供应商: {', '.join(self.active_providers) if self.active_providers else '无'}

💡 使用示例:
/tti 一只可爱的橘色小猫咪，坐在阳光明媚的窗台上
/tti-tongyi 科技感的未来城市夜景，霓虹灯闪烁
/tti-huoshan 美丽的山水风景画，中国风格

⚠️ 注意事项:
• PPIO使用异步任务机制，生成时间较长（30秒-2分钟）
• 请确保账户余额充足

📖 完整文档请参阅插件README.md
"""