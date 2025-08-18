"""
图片处理工具
严格遵循AstrBot开发规范的图片处理实现
"""

import os
import tempfile
import base64
import hashlib
import aiofiles
import asyncio
from typing import Optional, Union, BinaryIO
from PIL import Image
import httpx
from astrbot.api import logger


class ImageProcessor:
    """图片处理器 - 遵循AstrBot异步编程规范"""
    
    def __init__(self, temp_dir: Optional[str] = None, max_file_size: int = 10 * 1024 * 1024):
        """
        初始化图片处理器
        
        Args:
            temp_dir: 临时文件目录，None使用系统默认
            max_file_size: 最大文件大小限制 (字节)，默认10MB
        """
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.max_file_size = max_file_size
        self.temp_files = set()  # 跟踪临时文件用于清理
        
        # 确保临时目录存在
        os.makedirs(self.temp_dir, exist_ok=True)
        
        logger.info(f"图片处理器初始化完成，临时目录: {self.temp_dir}")
    
    async def save_base64_image(
        self, 
        base64_data: str, 
        filename_prefix: str = "generated_image",
        format: str = "PNG"
    ) -> str:
        """
        异步保存base64图片为临时文件
        
        Args:
            base64_data: base64编码的图片数据
            filename_prefix: 文件名前缀
            format: 图片格式 (PNG, JPEG, WEBP)
            
        Returns:
            临时文件路径
            
        Raises:
            ValueError: base64数据无效
            IOError: 文件保存失败
        """
        try:
            # 解码base64数据
            if base64_data.startswith('data:'):
                # 处理完整的data URL格式
                header, base64_data = base64_data.split(',', 1)
            
            image_data = base64.b64decode(base64_data)
            
            # 检查文件大小
            if len(image_data) > self.max_file_size:
                raise ValueError(f"图片大小超出限制 ({len(image_data)} > {self.max_file_size} 字节)")
            
            # 生成临时文件路径
            file_hash = hashlib.md5(image_data).hexdigest()[:8]
            filename = f"{filename_prefix}_{file_hash}.{format.lower()}"
            file_path = os.path.join(self.temp_dir, filename)
            
            # 异步写入文件
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(image_data)
            
            # 验证图片有效性
            await self._validate_image(file_path)
            
            # 记录临时文件
            self.temp_files.add(file_path)
            
            logger.info(f"成功保存base64图片: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"保存base64图片失败: {e}")
            raise IOError(f"保存base64图片失败: {str(e)}")
    
    async def download_image(
        self, 
        url: str, 
        filename_prefix: str = "downloaded_image",
        timeout: int = 30
    ) -> str:
        """
        异步下载网络图片
        
        Args:
            url: 图片URL
            filename_prefix: 文件名前缀
            timeout: 超时时间（秒）
            
        Returns:
            本地文件路径
            
        Raises:
            httpx.RequestError: 网络请求失败
            IOError: 文件保存失败
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.info(f"开始下载图片: {url}")
                
                response = await client.get(url)
                response.raise_for_status()
                
                # 检查Content-Type
                content_type = response.headers.get('content-type', '')
                if not content_type.startswith('image/'):
                    raise ValueError(f"URL返回的不是图片类型: {content_type}")
                
                # 检查文件大小
                content_length = int(response.headers.get('content-length', 0))
                if content_length > self.max_file_size:
                    raise ValueError(f"图片大小超出限制: {content_length} 字节")
                
                image_data = response.content
                
                # 根据Content-Type确定文件扩展名
                format_map = {
                    'image/png': 'png',
                    'image/jpeg': 'jpg', 
                    'image/jpg': 'jpg',
                    'image/webp': 'webp',
                    'image/gif': 'gif'
                }
                file_ext = format_map.get(content_type, 'jpg')
                
                # 生成文件路径
                file_hash = hashlib.md5(image_data).hexdigest()[:8]
                filename = f"{filename_prefix}_{file_hash}.{file_ext}"
                file_path = os.path.join(self.temp_dir, filename)
                
                # 异步保存文件
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(image_data)
                
                # 验证图片
                await self._validate_image(file_path)
                
                # 记录临时文件
                self.temp_files.add(file_path)
                
                logger.info(f"成功下载图片: {file_path}")
                return file_path
                
        except Exception as e:
            logger.error(f"下载图片失败 {url}: {e}")
            raise IOError(f"下载图片失败: {str(e)}")
    
    async def process_file_to_url(self, file_path: str) -> str:
        """
        将本地文件处理为可访问的URL
        
        注意：这是一个占位实现，实际需要根据AstrBot的文件服务进行适配
        
        Args:
            file_path: 本地文件路径
            
        Returns:
            可访问的URL
        """
        try:
            # 验证文件存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            await self._validate_image(file_path)
            
            # TODO: 这里需要根据AstrBot的具体实现来适配
            # 可能的实现方式:
            # 1. 上传到AstrBot的文件服务
            # 2. 使用临时文件服务
            # 3. 转换为base64 data URL
            
            # 临时实现：转换为base64 data URL
            async with aiofiles.open(file_path, 'rb') as f:
                image_data = await f.read()
            
            base64_data = base64.b64encode(image_data).decode()
            
            # 检测图片格式
            format_type = await self._detect_image_format(file_path)
            mime_type = f"image/{format_type.lower()}"
            
            data_url = f"data:{mime_type};base64,{base64_data}"
            
            logger.info(f"文件转换为data URL: {file_path}")
            return data_url
            
        except Exception as e:
            logger.error(f"文件转URL失败 {file_path}: {e}")
            raise IOError(f"文件转URL失败: {str(e)}")
    
    async def resize_image(
        self, 
        file_path: str, 
        max_width: int = 1024, 
        max_height: int = 1024,
        quality: int = 85
    ) -> str:
        """
        异步调整图片大小
        
        Args:
            file_path: 原始文件路径
            max_width: 最大宽度
            max_height: 最大高度
            quality: JPEG质量 (1-100)
            
        Returns:
            调整后的文件路径
        """
        try:
            # 在线程池中执行PIL操作
            resized_path = await asyncio.to_thread(
                self._resize_image_sync, 
                file_path, max_width, max_height, quality
            )
            
            # 记录临时文件
            self.temp_files.add(resized_path)
            
            logger.info(f"图片调整完成: {file_path} -> {resized_path}")
            return resized_path
            
        except Exception as e:
            logger.error(f"调整图片大小失败 {file_path}: {e}")
            raise IOError(f"调整图片大小失败: {str(e)}")
    
    def _resize_image_sync(
        self, 
        file_path: str, 
        max_width: int, 
        max_height: int, 
        quality: int
    ) -> str:
        """同步图片调整（在线程池中执行）"""
        with Image.open(file_path) as img:
            # 计算新尺寸
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # 生成新文件路径
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            new_filename = f"{base_name}_resized.jpg"
            new_path = os.path.join(self.temp_dir, new_filename)
            
            # 转换为RGB模式（处理RGBA）
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            
            # 保存调整后的图片
            img.save(new_path, 'JPEG', quality=quality, optimize=True)
            
        return new_path
    
    async def _validate_image(self, file_path: str) -> None:
        """验证图片文件有效性"""
        try:
            await asyncio.to_thread(self._validate_image_sync, file_path)
        except Exception as e:
            raise ValueError(f"图片文件无效: {str(e)}")
    
    def _validate_image_sync(self, file_path: str) -> None:
        """同步图片验证（在线程池中执行）"""
        with Image.open(file_path) as img:
            img.verify()  # 验证图片完整性
    
    async def _detect_image_format(self, file_path: str) -> str:
        """检测图片格式"""
        try:
            format_type = await asyncio.to_thread(self._detect_image_format_sync, file_path)
            return format_type
        except Exception:
            return "jpeg"  # 默认格式
    
    def _detect_image_format_sync(self, file_path: str) -> str:
        """同步格式检测（在线程池中执行）"""
        with Image.open(file_path) as img:
            return img.format.lower() if img.format else "jpeg"
    
    async def cleanup_temp_file(self, file_path: str) -> None:
        """清理单个临时文件"""
        try:
            if file_path in self.temp_files:
                self.temp_files.remove(file_path)
            
            if os.path.exists(file_path):
                await asyncio.to_thread(os.unlink, file_path)
                logger.debug(f"已清理临时文件: {file_path}")
                
        except Exception as e:
            logger.warning(f"清理临时文件失败 {file_path}: {e}")
    
    async def cleanup_all(self) -> None:
        """清理所有临时文件"""
        cleanup_tasks = [
            self.cleanup_temp_file(file_path) 
            for file_path in list(self.temp_files)
        ]
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            logger.info(f"已清理 {len(cleanup_tasks)} 个临时文件")
    
    async def get_image_info(self, file_path: str) -> dict:
        """获取图片信息"""
        try:
            info = await asyncio.to_thread(self._get_image_info_sync, file_path)
            return info
        except Exception as e:
            logger.error(f"获取图片信息失败 {file_path}: {e}")
            return {}
    
    def _get_image_info_sync(self, file_path: str) -> dict:
        """同步获取图片信息（在线程池中执行）"""
        with Image.open(file_path) as img:
            return {
                'format': img.format,
                'mode': img.mode,
                'size': img.size,
                'width': img.size[0],
                'height': img.size[1],
                'file_size': os.path.getsize(file_path)
            }
    
    def __del__(self):
        """析构函数 - 确保资源清理"""
        # 注意：在异步环境中，析构函数不能调用异步方法
        # 这里只是同步清理，推荐显式调用cleanup_all()
        for file_path in list(self.temp_files):
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception:
                pass