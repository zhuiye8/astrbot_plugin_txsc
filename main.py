"""
AstrBot通用文生图插件
支持9个主流文生图服务商的统一接口
"""

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.all import *
from astrbot.api.message_components import *
from astrbot.api.logger import logger
import re
import asyncio
import os
from typing import Optional, Dict, Any, List

from .providers.manager import ProviderManager
from .providers.base import GenerationParams, ImageSize, ResponseType
from .utils.config_validator import ConfigValidator
from .utils.image_processor import ImageProcessor
from .utils.message_parser import MessageParser

@register("astrbot_plugin_text2img", "zhuiye", "通用文生图插件，支持9个主流文生图服务商", "2.0.0", "https://github.com/zhuiye8/astrbot_plugin_text2img")
class UniversalText2ImgPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.context = context
        
        # 初始化配置验证器
        self.config_validator = ConfigValidator()
        
        # 初始化图片处理器
        self.image_processor = ImageProcessor()
        
        # 初始化消息解析器
        self.message_parser = MessageParser()
        
        # 服务商中文名称映射
        self.provider_display_map = {
            "tongyi": "阿里云通义万相",
            "volcengine": "字节跳动火山引擎", 
            "qianfan": "百度智能云千帆",
            "xunfei": "科大讯飞星火",
            "ppio": "PPIO图像生成",
            "zhipu": "智谱清言",
            "openai": "OpenAI达芬奇",
            "gemini": "谷歌双子座",
            "grok": "Grok图像生成"
        }
        
        # 服务商标识符映射（支持中文别名）
        self.provider_alias_map = {
            "阿里": "tongyi",
            "阿里云": "tongyi",
            "通义": "tongyi", 
            "万相": "tongyi",
            "通义万相": "tongyi",
            "火山": "volcengine",
            "字节": "volcengine",
            "火山引擎": "volcengine",
            "百度": "qianfan",
            "千帆": "qianfan",
            "智能云": "qianfan",
            "讯飞": "xunfei",
            "科大讯飞": "xunfei",
            "星火": "xunfei",
            "智谱": "zhipu",
            "清言": "zhipu",
            "智谱清言": "zhipu",
            "chatglm": "zhipu",
            "openai": "openai",
            "达芬奇": "openai",
            "dall-e": "openai",
            "gemini": "gemini",
            "双子座": "gemini",
            "谷歌": "gemini",
            "google": "gemini",
            "grok": "grok",
            "x.ai": "grok"
        }
        
        # 从配置读取触发关键词
        self.draw_keywords = self._parse_keywords(
            config.get("draw_keywords", "画,绘画,画个,画张,画一个,画一张,生图,画画,img,painting,draw")
        )
        
        # 从配置读取反向提示词处理开关
        self.enable_negative_prompt_processing = config.get("enable_negative_prompt_processing", True)
        
        # 从配置读取反向提示词关键词
        self.negative_prompt_keywords = self._parse_keywords(
            config.get("negative_prompt_keywords", "不要,避免,无,不包含,不想要,排除,没有")
        )
        
        # 初始化Provider管理器
        self.provider_manager = ProviderManager()
        
        # 异步初始化
        asyncio.create_task(self._async_init())
    
    async def _async_init(self):
        """异步初始化Provider"""
        try:
            # 验证配置
            validation_result = self.config_validator.validate_config(self.config)
            if not validation_result.is_valid:
                logger.warning(f"配置验证警告: {'; '.join(validation_result.warnings)}")
            
            # 初始化所有Provider
            await self._init_providers()
            
            # 执行健康检查
            await self._health_check()
            
            logger.info("文生图插件初始化完成")
            
        except Exception as e:
            logger.error(f"文生图插件初始化失败: {e}")
    
    async def _init_providers(self):
        """初始化所有Provider"""
        from .providers import (
            create_tongyi_provider,
            create_volcengine_provider, 
            create_qianfan_provider,
            create_xunfei_provider,
            create_ppio_provider,
            create_zhipu_provider,
            create_openai_provider,
            create_gemini_provider,
            create_grok_provider
        )
        
        # Provider工厂函数映射
        provider_factories = {
            "tongyi": create_tongyi_provider,
            "volcengine": create_volcengine_provider,
            "qianfan": create_qianfan_provider,
            "xunfei": create_xunfei_provider,
            "ppio": create_ppio_provider,
            "zhipu": create_zhipu_provider,
            "openai": create_openai_provider,
            "gemini": create_gemini_provider,
            "grok": create_grok_provider
        }
        
        # 初始化每个Provider
        for provider_name, factory_func in provider_factories.items():
            try:
                provider = factory_func(self.config)
                if provider:
                    self.provider_manager.register_provider(provider)
                    logger.info(f"成功注册Provider: {provider_name}")
            except Exception as e:
                logger.warning(f"初始化Provider {provider_name} 失败: {e}")
        
        # 检查是否有可用的Provider
        enabled_providers = self.provider_manager.get_enabled_providers()
        if not enabled_providers:
            logger.warning("没有配置任何可用的文生图服务，请检查配置")
        else:
            provider_names = [p.name for p in enabled_providers]
            logger.info(f"已启用的Provider: {', '.join(provider_names)}")
    
    async def _health_check(self):
        """执行健康检查"""
        health_results = await self.provider_manager.health_check_all()
        healthy_count = sum(1 for result in health_results.values() if result["status"] == "healthy")
        total_count = len(health_results)
        logger.info(f"Provider健康检查完成: {healthy_count}/{total_count} 健康")
    
    def _parse_keywords(self, keywords_str: str) -> List[str]:
        """解析关键词字符串"""
        if not keywords_str:
            return []
        return [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
    
    @filter.event_message_type(EventMessageType.ALL)
    async def handle_text_to_image(self, event: AstrMessageEvent):
        """处理文生图请求"""
        message = event.message_str
        
        # 检查是否为命令消息
        if message.startswith("/t2i"):
            await self._handle_command(event)
            return
        
        # 检查是否包含绘画相关关键词
        if not any(keyword in message for keyword in self.draw_keywords):
            return
        
        logger.info(f"收到文生图请求: {message}")
        
        try:
            # 解析消息并生成图片
            await self._process_generation_request(event, message)
        except Exception as e:
            logger.error(f"处理文生图请求失败: {e}")
            yield event.plain_result(f"\n图片生成请求处理失败: {str(e)}")
    
    async def _handle_command(self, event: AstrMessageEvent):
        """处理命令消息"""
        message = event.message_str
        command_parts = message.split()
        
        if len(command_parts) < 2:
            yield event.plain_result(self._get_help_text())
            return
        
        command = command_parts[1].lower()
        
        if command == "help":
            yield event.plain_result(self._get_help_text())
        elif command == "status":
            await self._handle_status_command(event)
        elif command == "providers":
            await self._handle_providers_command(event)
        elif command == "test":
            provider_name = command_parts[2] if len(command_parts) > 2 else None
            await self._handle_test_command(event, provider_name)
        elif command == "stats":
            await self._handle_stats_command(event)
        else:
            yield event.plain_result(f"\n未知命令: {command}\n\n{self._get_help_text()}")
    
    async def _process_generation_request(self, event: AstrMessageEvent, message: str):
        """处理生成请求"""
        # 解析消息参数
        params = await self._parse_message(message)
        
        if not params.prompt:
            yield event.plain_result("\n🎨 请提供您想要生成的图片内容描述！")
            return
        
        # 检查是否有可用的Provider
        enabled_providers = self.provider_manager.get_enabled_providers()
        if not enabled_providers:
            yield event.plain_result("\n⚠️ 当前没有可用的图像生成服务，请联系管理员配置至少一个服务商的API密钥")
            return
        
        # 确定使用的Provider
        provider_name = params.provider_name or self.config.get("default_provider", "tongyi")
        
        # 如果是别名，转换为实际Provider名称
        if provider_name in self.provider_alias_map:
            provider_name = self.provider_alias_map[provider_name]
        
        provider_display = self.provider_display_map.get(provider_name, provider_name)
        
        # 发送生成提示
        yield event.plain_result(f"\n正在使用{provider_display}生成图片，请稍候...")
        
        try:
            # 调用Provider管理器生成图片
            result = await self.provider_manager.generate_image(
                params.generation_params, 
                provider_name=provider_name,
                use_fallback=self.config.get("enable_fallback", True)
            )
            
            if result.is_success:
                # 处理成功结果
                await self._handle_success_result(event, result, params)
            else:
                # 处理失败结果
                yield event.plain_result(f"\n图片生成失败: {result.error_message}")
                
        except Exception as e:
            logger.error(f"生成图片异常: {e}")
            yield event.plain_result(f"\n图片生成过程中发生异常: {str(e)}")
    
    async def _handle_success_result(self, event: AstrMessageEvent, result, params):
        """处理成功的生成结果"""
        try:
            # 构建结果消息
            info_text = self._build_result_info(result, params)
            
            # 处理图片
            if result.response_type == ResponseType.URL:
                # URL类型，直接使用Image.fromURL
                chain = [
                    Plain(info_text),
                    Image.fromURL(result.image_url)
                ]
            elif result.response_type == ResponseType.FILE_PATH:
                # 文件路径类型，转换为URL或base64
                image_url = await self.image_processor.process_file_to_url(result.data)
                chain = [
                    Plain(info_text),
                    Image.fromURL(image_url)
                ]
            else:
                # Base64类型，保存为临时文件
                image_path = await self.image_processor.save_base64_image(result.data)
                image_url = await self.image_processor.process_file_to_url(image_path)
                chain = [
                    Plain(info_text),
                    Image.fromURL(image_url)
                ]
            
            yield event.chain_result(chain)
            
        except Exception as e:
            logger.error(f"处理生成结果失败: {e}")
            yield event.plain_result(f"\n图片生成成功，但处理结果时出错: {str(e)}")
    
    async def _parse_message(self, message: str):
        """解析消息内容"""
        try:
            # 使用消息解析器解析消息
            parsed = await self.message_parser.parse_message(
                message=message,
                negative_keywords=self.negative_prompt_keywords,
                default_provider=self.config.get("default_provider", "tongyi")
            )
            
            # 验证解析结果
            validation_errors = self.message_parser.validate_parsed_message(parsed)
            if validation_errors:
                logger.warning(f"消息解析验证警告: {'; '.join(validation_errors)}")
            
            return parsed
            
        except Exception as e:
            logger.error(f"消息解析失败: {e}")
            # 返回基础解析结果
            from .utils.message_parser import ParsedMessage
            return ParsedMessage(
                prompt=message,
                raw_message=message,
                provider_name=self.config.get("default_provider", "tongyi")
            )
    
    def _build_result_info(self, result, params) -> str:
        """构建结果信息文本"""
        provider_name = result.metadata.get("provider", "未知")
        provider_display = self.provider_display_map.get(provider_name, provider_name)
        
        info_parts = [
            f"✨ 提供商: {provider_display}",
            f"📝 提示词: {params.generation_params.prompt}"
        ]
        
        if params.generation_params.negative_prompt:
            info_parts.append(f"🚫 反向提示词: {params.generation_params.negative_prompt}")
        
        if params.generation_params.size:
            info_parts.append(f"📐 尺寸: {params.generation_params.size}")
        
        return "\n" + "\n".join(info_parts) + "\n"
    
    def _get_help_text(self) -> str:
        """获取帮助文本"""
        return """
📖 AstrBot通用文生图插件帮助

🎨 基础用法:
• 画一只可爱的小猫咪
• @火山 画个风景图 1024x1024
• 生成一张海边日落的图片 不要建筑物

🔧 命令用法:
• /t2i help - 显示此帮助
• /t2i status - 查看服务状态
• /t2i providers - 列出可用服务商
• /t2i test <provider> - 测试指定服务商
• /t2i stats - 查看使用统计

🏷️ 支持的服务商标签:
@阿里云 @火山引擎 @百度千帆 @科大讯飞 @智谱清言 @OpenAI达芬奇 @谷歌双子座 @Grok图像生成

📏 支持的尺寸格式:
1024x1024, 1024x1792, 768x1024 等
        """
    
    async def _handle_status_command(self, event: AstrMessageEvent):
        """处理状态查询命令"""
        try:
            health_results = await self.provider_manager.health_check_all()
            status_lines = ["🔍 服务商状态检查:"]
            
            for provider_name, result in health_results.items():
                display_name = self.provider_display_map.get(provider_name, provider_name)
                status_icon = "✅" if result["status"] == "healthy" else "❌"
                status_lines.append(f"{status_icon} {display_name}: {result['message']}")
            
            yield event.plain_result("\n" + "\n".join(status_lines))
            
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            yield event.plain_result(f"\n获取状态失败: {str(e)}")
    
    async def _handle_providers_command(self, event: AstrMessageEvent):
        """处理Provider列表命令"""
        try:
            enabled_providers = self.provider_manager.get_enabled_providers()
            provider_lines = ["📋 可用的文生图服务商:"]
            
            for provider in enabled_providers:
                display_name = self.provider_display_map.get(provider.name, provider.name)
                capabilities = provider.capabilities
                
                # 构建能力描述
                features = []
                if capabilities.supports_negative_prompt:
                    features.append("反向提示词")
                if capabilities.max_images_per_request > 1:
                    features.append(f"批量生成({capabilities.max_images_per_request}张)")
                if capabilities.async_generation:
                    features.append("异步生成")
                
                feature_str = "、".join(features) if features else "基础功能"
                provider_lines.append(f"• {display_name} - {feature_str}")
            
            if not enabled_providers:
                provider_lines.append("⚠️ 暂无可用的服务商，请检查API密钥配置")
            
            yield event.plain_result("\n" + "\n".join(provider_lines))
            
        except Exception as e:
            logger.error(f"获取Provider列表失败: {e}")
            yield event.plain_result(f"\n获取Provider列表失败: {str(e)}")
    
    async def _handle_test_command(self, event: AstrMessageEvent, provider_name: Optional[str]):
        """处理测试命令"""
        if not provider_name:
            yield event.plain_result("\n🔧 请指定要测试的服务商，例如: /t2i test volcengine")
            return
        
        # 查找Provider
        provider = self.provider_manager.get_provider(provider_name)
        if not provider:
            # 尝试通过别名查找
            real_name = self.provider_alias_map.get(provider_name)
            if real_name:
                provider = self.provider_manager.get_provider(real_name)
        
        if not provider:
            yield event.plain_result(f"\n❌ 未找到服务商: {provider_name}，请检查名称是否正确")
            return
        
        display_name = self.provider_display_map.get(provider.name, provider.name)
        yield event.plain_result(f"\n正在测试 {display_name}...")
        
        try:
            # 执行健康检查
            health_result = await provider.health_check()
            
            if health_result["status"] == "healthy":
                yield event.plain_result(f"\n✅ {display_name} 连接正常")
            else:
                yield event.plain_result(f"\n❌ {display_name} 连接异常: {health_result['message']}")
                
        except Exception as e:
            logger.error(f"测试Provider {provider_name} 失败: {e}")
            yield event.plain_result(f"\n❌ 测试失败: {str(e)}")
    
    async def _handle_stats_command(self, event: AstrMessageEvent):
        """处理统计查询命令"""
        try:
            stats = self.provider_manager.get_provider_stats()
            summary = self.provider_manager.get_summary()
            
            stats_lines = [
                "📊 使用统计:",
                f"总Provider数: {summary['total_providers']}",
                f"已启用: {summary['enabled_providers']}",
                f"总请求数: {summary['total_requests']}",
                f"成功率: {summary['success_rate']}",
                ""
            ]
            
            # 各Provider详细统计
            for provider_name, stat in stats.items():
                if stat["total_requests"] > 0:
                    display_name = self.provider_display_map.get(provider_name, provider_name)
                    success_rate = (stat["successful_requests"] / stat["total_requests"] * 100) if stat["total_requests"] > 0 else 0
                    
                    stats_lines.append(
                        f"• {display_name}: {stat['total_requests']}次请求, "
                        f"成功率 {success_rate:.1f}%, "
                        f"平均耗时 {stat['avg_response_time']:.2f}s"
                    )
            
            yield event.plain_result("\n" + "\n".join(stats_lines))
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            yield event.plain_result(f"\n获取统计信息失败: {str(e)}")
    
    async def terminate(self):
        """插件终止时的清理工作"""
        try:
            # 清理资源
            if hasattr(self, 'image_processor'):
                await self.image_processor.cleanup_all()
            
            logger.info("文生图插件已清理资源")
            
        except Exception as e:
            logger.error(f"插件清理失败: {e}")