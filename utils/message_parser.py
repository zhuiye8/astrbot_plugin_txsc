"""
消息解析器
严格遵循AstrBot开发规范的智能消息解析实现
"""

import re
import asyncio
from typing import Optional, Dict, Any, List, Tuple, NamedTuple
from dataclasses import dataclass
from astrbot.api import logger

from ..providers.base import GenerationParams, ImageSize, ResponseType


@dataclass
class ParsedMessage:
    """解析后的消息参数"""
    prompt: str = ""
    negative_prompt: str = ""
    provider_name: Optional[str] = None
    size: Optional[ImageSize] = None
    style: Optional[str] = None
    count: int = 1
    seed: Optional[int] = None
    quality: Optional[str] = None
    raw_message: str = ""
    
    @property
    def generation_params(self) -> GenerationParams:
        """转换为GenerationParams对象"""
        return GenerationParams(
            prompt=self.prompt,
            negative_prompt=self.negative_prompt if self.negative_prompt else None,
            size=self.size,
            style=self.style,
            count=self.count,
            seed=self.seed,
            quality=self.quality,
            response_type=ResponseType.URL  # 默认返回URL
        )


class MessageParser:
    """消息解析器 - 遵循AstrBot异步编程规范"""
    
    def __init__(self):
        """初始化消息解析器"""
        
        # Provider别名映射
        self.provider_aliases = {
            "阿里": "tongyi",
            "通义": "tongyi", 
            "万相": "tongyi",
            "tongyi": "tongyi",
            "火山": "volcengine",
            "volcengine": "volcengine",
            "百度": "qianfan",
            "千帆": "qianfan",
            "qianfan": "qianfan",
            "讯飞": "xunfei",
            "星火": "xunfei",
            "xunfei": "xunfei",
            "ppio": "ppio",
            "智谱": "zhipu",
            "zhipu": "zhipu",
            "chatglm": "zhipu",
            "openai": "openai",
            "dall-e": "openai",
            "dalle": "openai",
            "gemini": "gemini",
            "google": "gemini",
            "grok": "grok",
            "x.ai": "grok"
        }
        
        # 尺寸模式映射
        self.size_patterns = {
            # 标准格式
            r"(\d+)[x×](\d+)": lambda m: ImageSize(int(m.group(1)), int(m.group(2))),
            # 预设格式
            r"方形|正方形|square": lambda m: ImageSize(1024, 1024),
            r"横版|横图|landscape": lambda m: ImageSize(1792, 1024),
            r"竖版|竖图|portrait": lambda m: ImageSize(1024, 1792),
            r"超宽|ultrawide": lambda m: ImageSize(1792, 1024),
            r"高清|hd": lambda m: ImageSize(1024, 1024),
            r"4k": lambda m: ImageSize(2048, 2048),
            # 常用尺寸
            r"小图|small": lambda m: ImageSize(512, 512),
            r"中图|medium": lambda m: ImageSize(768, 768),
            r"大图|large": lambda m: ImageSize(1024, 1024),
            r"超大|xlarge": lambda m: ImageSize(1536, 1536)
        }
        
        # 风格关键词映射
        self.style_keywords = {
            "写实": "realistic",
            "卡通": "cartoon", 
            "动漫": "anime",
            "油画": "oil_painting",
            "水彩": "watercolor",
            "素描": "sketch",
            "黑白": "black_white",
            "赛博朋克": "cyberpunk",
            "蒸汽朋克": "steampunk",
            "简约": "minimalist",
            "抽象": "abstract",
            "科幻": "sci_fi",
            "奇幻": "fantasy",
            "恐怖": "horror",
            "可爱": "cute",
            "清新": "fresh",
            "暗黑": "dark",
            "明亮": "bright",
            "梦幻": "dreamy",
            "复古": "vintage",
            "现代": "modern",
            "古典": "classical"
        }
        
        # 质量关键词
        self.quality_keywords = {
            "高质量": "high",
            "最高质量": "highest", 
            "标准质量": "standard",
            "快速": "fast",
            "精细": "detailed",
            "粗糙": "rough"
        }
        
        logger.info("消息解析器初始化完成")
    
    async def parse_message(
        self, 
        message: str, 
        negative_keywords: List[str] = None,
        default_provider: str = "tongyi"
    ) -> ParsedMessage:
        """
        异步解析用户消息
        
        Args:
            message: 用户消息
            negative_keywords: 反向提示词关键词列表
            default_provider: 默认Provider
            
        Returns:
            解析后的消息参数
        """
        try:
            # 在线程池中执行解析逻辑
            parsed = await asyncio.to_thread(
                self._parse_message_sync, 
                message, 
                negative_keywords or [], 
                default_provider
            )
            
            logger.debug(f"消息解析完成: {message[:50]}...")
            return parsed
            
        except Exception as e:
            logger.error(f"消息解析失败: {e}")
            # 返回基础解析结果
            return ParsedMessage(
                prompt=message,
                raw_message=message,
                provider_name=default_provider
            )
    
    def _parse_message_sync(
        self, 
        message: str, 
        negative_keywords: List[str], 
        default_provider: str
    ) -> ParsedMessage:
        """同步消息解析（在线程池中执行）"""
        
        result = ParsedMessage(raw_message=message)
        
        # 1. 提取Provider标签
        result.provider_name = self._extract_provider(message) or default_provider
        
        # 2. 提取尺寸信息
        result.size = self._extract_size(message)
        
        # 3. 提取风格信息
        result.style = self._extract_style(message)
        
        # 4. 提取数量信息
        result.count = self._extract_count(message)
        
        # 5. 提取种子信息
        result.seed = self._extract_seed(message)
        
        # 6. 提取质量信息
        result.quality = self._extract_quality(message)
        
        # 7. 分离正向和反向提示词
        prompt, negative_prompt = self._extract_prompts(message, negative_keywords)
        result.prompt = prompt
        result.negative_prompt = negative_prompt
        
        return result
    
    def _extract_provider(self, message: str) -> Optional[str]:
        """提取Provider信息"""
        
        # 查找@标签格式
        at_pattern = r"@([^\s@]+)"
        at_matches = re.findall(at_pattern, message, re.IGNORECASE)
        
        for match in at_matches:
            provider = self.provider_aliases.get(match.lower())
            if provider:
                logger.debug(f"从@标签提取Provider: {match} -> {provider}")
                return provider
        
        # 查找使用xxx生成的格式
        use_pattern = r"(?:使用|用)([^\s，,。]+?)(?:生成|画|绘制)"
        use_matches = re.findall(use_pattern, message, re.IGNORECASE)
        
        for match in use_matches:
            provider = self.provider_aliases.get(match.lower())
            if provider:
                logger.debug(f"从使用格式提取Provider: {match} -> {provider}")
                return provider
        
        # 查找直接提及Provider名称
        for alias, provider in self.provider_aliases.items():
            if alias in message.lower():
                logger.debug(f"从直接提及提取Provider: {alias} -> {provider}")
                return provider
        
        return None
    
    def _extract_size(self, message: str) -> Optional[ImageSize]:
        """提取尺寸信息"""
        
        for pattern, size_func in self.size_patterns.items():
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                try:
                    size = size_func(match)
                    logger.debug(f"提取尺寸: {pattern} -> {size}")
                    return size
                except Exception as e:
                    logger.warning(f"尺寸解析失败 {pattern}: {e}")
                    continue
        
        return None
    
    def _extract_style(self, message: str) -> Optional[str]:
        """提取风格信息"""
        
        # 查找风格关键词
        for keyword, style in self.style_keywords.items():
            if keyword in message:
                logger.debug(f"提取风格: {keyword} -> {style}")
                return style
        
        # 查找风格描述格式
        style_patterns = [
            r"(?:风格|样式)[:：]?\s*([^\s，,。]+)",
            r"([^\s，,。]+)(?:风格|样式)",
            r"(?:做成|制作成|设计成)\s*([^\s，,。]+)",
        ]
        
        for pattern in style_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                style_text = match.group(1).strip()
                # 检查是否为已知风格
                style = self.style_keywords.get(style_text)
                if style:
                    logger.debug(f"从格式提取风格: {style_text} -> {style}")
                    return style
                # 返回原文本作为自定义风格
                logger.debug(f"自定义风格: {style_text}")
                return style_text
        
        return None
    
    def _extract_count(self, message: str) -> int:
        """提取生成数量"""
        
        count_patterns = [
            r"(\d+)\s*张",
            r"(\d+)\s*个",
            r"(\d+)\s*幅",
            r"生成\s*(\d+)",
            r"画\s*(\d+)",
            r"(\d+)\s*pics?",
            r"(\d+)\s*images?"
        ]
        
        for pattern in count_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                try:
                    count = int(match.group(1))
                    # 限制数量范围
                    count = max(1, min(count, 10))
                    logger.debug(f"提取数量: {count}")
                    return count
                except ValueError:
                    continue
        
        return 1  # 默认1张
    
    def _extract_seed(self, message: str) -> Optional[int]:
        """提取种子信息"""
        
        seed_patterns = [
            r"seed[:：]?\s*(\d+)",
            r"种子[:：]?\s*(\d+)",
            r"随机种子[:：]?\s*(\d+)"
        ]
        
        for pattern in seed_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                try:
                    seed = int(match.group(1))
                    logger.debug(f"提取种子: {seed}")
                    return seed
                except ValueError:
                    continue
        
        return None
    
    def _extract_quality(self, message: str) -> Optional[str]:
        """提取质量信息"""
        
        for keyword, quality in self.quality_keywords.items():
            if keyword in message:
                logger.debug(f"提取质量: {keyword} -> {quality}")
                return quality
        
        return None
    
    def _extract_prompts(self, message: str, negative_keywords: List[str]) -> Tuple[str, str]:
        """分离正向和反向提示词"""
        
        # 移除Provider标签
        cleaned_message = re.sub(r"@[^\s@]+", "", message)
        
        # 移除尺寸信息
        for pattern in self.size_patterns.keys():
            cleaned_message = re.sub(pattern, "", cleaned_message, flags=re.IGNORECASE)
        
        # 移除风格信息
        for keyword in self.style_keywords.keys():
            cleaned_message = cleaned_message.replace(keyword, "")
        
        # 移除数量信息
        count_patterns = [r"\d+\s*张", r"\d+\s*个", r"\d+\s*幅", r"生成\s*\d+", r"画\s*\d+"]
        for pattern in count_patterns:
            cleaned_message = re.sub(pattern, "", cleaned_message, flags=re.IGNORECASE)
        
        # 移除质量信息
        for keyword in self.quality_keywords.keys():
            cleaned_message = cleaned_message.replace(keyword, "")
        
        # 移除触发词
        trigger_words = ["画", "绘画", "画个", "画张", "画一个", "画一张", "生图", "画画", "生成", "制作", "创建"]
        for word in trigger_words:
            cleaned_message = cleaned_message.replace(word, "")
        
        # 分离反向提示词
        negative_prompt = ""
        positive_prompt = cleaned_message
        
        if negative_keywords:
            # 查找反向提示词
            negative_parts = []
            
            for keyword in negative_keywords:
                # 查找"不要xxx"、"避免xxx"等格式
                pattern = rf"{re.escape(keyword)}\s*([^，,。；;]+)"
                matches = re.findall(pattern, positive_prompt, re.IGNORECASE)
                
                for match in matches:
                    negative_parts.append(match.strip())
                    # 从正向提示词中移除
                    remove_pattern = rf"{re.escape(keyword)}\s*{re.escape(match)}"
                    positive_prompt = re.sub(remove_pattern, "", positive_prompt, flags=re.IGNORECASE)
            
            negative_prompt = ", ".join(negative_parts)
        
        # 清理提示词
        positive_prompt = re.sub(r"[，,。；;]+", " ", positive_prompt)
        positive_prompt = re.sub(r"\s+", " ", positive_prompt).strip()
        
        logger.debug(f"提取提示词 - 正向: {positive_prompt}, 反向: {negative_prompt}")
        
        return positive_prompt, negative_prompt
    
    async def parse_command_message(self, message: str) -> Dict[str, Any]:
        """
        解析命令消息
        
        Args:
            message: 命令消息
            
        Returns:
            解析后的命令参数
        """
        try:
            # 在线程池中执行命令解析
            result = await asyncio.to_thread(self._parse_command_sync, message)
            return result
            
        except Exception as e:
            logger.error(f"命令解析失败: {e}")
            return {"command": "unknown", "args": []}
    
    def _parse_command_sync(self, message: str) -> Dict[str, Any]:
        """同步命令解析（在线程池中执行）"""
        
        # 解析/t2i命令格式
        if not message.startswith("/t2i"):
            return {"command": "unknown", "args": []}
        
        parts = message.split()
        if len(parts) < 2:
            return {"command": "help", "args": []}
        
        command = parts[1].lower()
        args = parts[2:] if len(parts) > 2 else []
        
        return {
            "command": command,
            "args": args,
            "raw_message": message
        }
    
    def validate_parsed_message(self, parsed: ParsedMessage) -> List[str]:
        """
        验证解析结果
        
        Args:
            parsed: 解析后的消息
            
        Returns:
            验证错误列表
        """
        errors = []
        
        # 检查提示词
        if not parsed.prompt or len(parsed.prompt.strip()) < 2:
            errors.append("提示词不能为空或过短")
        
        # 检查尺寸
        if parsed.size:
            if parsed.size.width < 256 or parsed.size.height < 256:
                errors.append("图片尺寸不能小于256x256")
            if parsed.size.width > 2048 or parsed.size.height > 2048:
                errors.append("图片尺寸不能大于2048x2048")
        
        # 检查数量
        if parsed.count < 1 or parsed.count > 10:
            errors.append("生成数量必须在1-10之间")
        
        # 检查种子值
        if parsed.seed is not None and (parsed.seed < 0 or parsed.seed > 2**32 - 1):
            errors.append("种子值必须在有效范围内")
        
        return errors
    
    def get_supported_providers(self) -> List[str]:
        """获取支持的Provider列表"""
        return list(set(self.provider_aliases.values()))
    
    def get_provider_aliases(self) -> Dict[str, str]:
        """获取Provider别名映射"""
        return self.provider_aliases.copy()
    
    def get_supported_sizes(self) -> List[str]:
        """获取支持的尺寸格式示例"""
        return [
            "1024x1024 (标准格式)",
            "方形/正方形 (1024x1024)",
            "横版/横图 (1792x1024)",
            "竖版/竖图 (1024x1792)",
            "小图 (512x512)",
            "中图 (768x768)",
            "大图 (1024x1024)",
            "4k (2048x2048)"
        ]
    
    def get_supported_styles(self) -> List[str]:
        """获取支持的风格列表"""
        return list(self.style_keywords.keys())