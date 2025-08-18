"""
SDK自动安装工具
严格遵循AstrBot开发规范的SDK管理实现
"""

import sys
import subprocess
import importlib
import asyncio
from typing import Dict, List, Optional, Tuple
from astrbot.api import logger


class SDKInstaller:
    """SDK自动安装器 - 遵循AstrBot异步编程规范"""
    
    # SDK包映射配置
    SDK_PACKAGES = {
        "tongyi": {
            "package": "dashscope",
            "version": ">=1.22.1",
            "import_name": "dashscope",
            "description": "阿里云通义万相SDK"
        },
        "volcengine": {
            "package": "volcengine",
            "version": ">=1.0.0", 
            "import_name": "volcengine",
            "description": "火山引擎SDK"
        },
        "qianfan": {
            "package": "qianfan",
            "version": ">=0.3.0",
            "import_name": "qianfan",
            "description": "百度千帆SDK"
        },
        "xunfei": {
            "package": "requests",
            "version": ">=2.25.0",
            "import_name": "requests", 
            "description": "科大讯飞HTTP请求库"
        },
        "ppio": {
            "package": "httpx",
            "version": ">=0.25.0",
            "import_name": "httpx",
            "description": "PPIO异步HTTP客户端"
        },
        "zhipu": {
            "package": "zhipuai",
            "version": ">=2.0.0",
            "import_name": "zhipuai",
            "description": "智谱AI SDK"
        },
        "openai": {
            "package": "openai",
            "version": ">=1.0.0",
            "import_name": "openai",
            "description": "OpenAI SDK"
        },
        "gemini": {
            "package": "google-generativeai",
            "version": ">=0.3.0",
            "import_name": "google.generativeai",
            "description": "Google Gemini SDK"
        },
        "grok": {
            "package": "openai",
            "version": ">=1.0.0",
            "import_name": "openai",
            "description": "Grok兼容OpenAI SDK"
        }
    }
    
    def __init__(self):
        """初始化SDK安装器"""
        self.installation_cache = {}  # 缓存安装状态
        logger.info("SDK安装器初始化完成")
    
    async def check_sdk_availability(self, provider_name: str) -> bool:
        """
        异步检查SDK是否可用
        
        Args:
            provider_name: Provider名称
            
        Returns:
            SDK是否可用
        """
        try:
            if provider_name not in self.SDK_PACKAGES:
                logger.warning(f"未知的Provider: {provider_name}")
                return False
            
            sdk_config = self.SDK_PACKAGES[provider_name]
            import_name = sdk_config["import_name"]
            
            # 在线程池中执行导入检查
            is_available = await asyncio.to_thread(self._check_import_sync, import_name)
            
            if is_available:
                logger.debug(f"{provider_name} SDK可用")
            else:
                logger.debug(f"{provider_name} SDK不可用")
                
            return is_available
            
        except Exception as e:
            logger.error(f"检查SDK可用性失败 {provider_name}: {e}")
            return False
    
    def _check_import_sync(self, import_name: str) -> bool:
        """同步检查模块导入（在线程池中执行）"""
        try:
            importlib.import_module(import_name)
            return True
        except ImportError:
            return False
    
    async def install_sdk(self, provider_name: str, force_reinstall: bool = False) -> bool:
        """
        异步安装SDK
        
        Args:
            provider_name: Provider名称
            force_reinstall: 是否强制重新安装
            
        Returns:
            安装是否成功
        """
        try:
            if provider_name not in self.SDK_PACKAGES:
                logger.error(f"不支持的Provider: {provider_name}")
                return False
            
            sdk_config = self.SDK_PACKAGES[provider_name]
            
            # 检查缓存
            cache_key = f"{provider_name}_{sdk_config['package']}_{sdk_config['version']}"
            if not force_reinstall and self.installation_cache.get(cache_key):
                logger.debug(f"{provider_name} SDK已安装（缓存）")
                return True
            
            # 检查是否已安装
            if not force_reinstall and await self.check_sdk_availability(provider_name):
                logger.info(f"{provider_name} SDK已安装")
                self.installation_cache[cache_key] = True
                return True
            
            # 执行安装
            logger.info(f"开始安装 {sdk_config['description']}...")
            
            success = await self._install_package(
                sdk_config["package"],
                sdk_config["version"],
                sdk_config["description"]
            )
            
            if success:
                # 验证安装
                if await self.check_sdk_availability(provider_name):
                    logger.info(f"{sdk_config['description']} 安装成功")
                    self.installation_cache[cache_key] = True
                    return True
                else:
                    logger.error(f"{sdk_config['description']} 安装后验证失败")
                    return False
            else:
                logger.error(f"{sdk_config['description']} 安装失败")
                return False
                
        except Exception as e:
            logger.error(f"安装SDK失败 {provider_name}: {e}")
            return False
    
    async def _install_package(self, package: str, version: str, description: str) -> bool:
        """
        异步安装Python包
        
        Args:
            package: 包名
            version: 版本要求
            description: 包描述
            
        Returns:
            安装是否成功
        """
        try:
            # 构建安装命令
            install_cmd = [
                sys.executable, "-m", "pip", "install", 
                f"{package}{version}",
                "--upgrade"
            ]
            
            logger.info(f"执行安装命令: {' '.join(install_cmd)}")
            
            # 在线程池中执行subprocess
            result = await asyncio.to_thread(
                subprocess.run,
                install_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                logger.info(f"{description} 安装成功")
                if result.stdout:
                    logger.debug(f"安装输出: {result.stdout}")
                return True
            else:
                logger.error(f"{description} 安装失败，返回码: {result.returncode}")
                if result.stderr:
                    logger.error(f"错误输出: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"{description} 安装超时")
            return False
        except Exception as e:
            logger.error(f"{description} 安装异常: {e}")
            return False
    
    async def batch_check_sdks(self, provider_names: List[str]) -> Dict[str, bool]:
        """
        批量检查多个SDK的可用性
        
        Args:
            provider_names: Provider名称列表
            
        Returns:
            检查结果字典
        """
        try:
            tasks = [
                self.check_sdk_availability(provider_name)
                for provider_name in provider_names
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            status_dict = {}
            for i, provider_name in enumerate(provider_names):
                result = results[i]
                if isinstance(result, Exception):
                    logger.error(f"检查 {provider_name} SDK时发生异常: {result}")
                    status_dict[provider_name] = False
                else:
                    status_dict[provider_name] = result
            
            return status_dict
            
        except Exception as e:
            logger.error(f"批量检查SDK失败: {e}")
            return {name: False for name in provider_names}
    
    async def batch_install_sdks(
        self, 
        provider_names: List[str], 
        force_reinstall: bool = False,
        max_concurrent: int = 3
    ) -> Dict[str, bool]:
        """
        批量安装多个SDK
        
        Args:
            provider_names: Provider名称列表
            force_reinstall: 是否强制重新安装
            max_concurrent: 最大并发安装数
            
        Returns:
            安装结果字典
        """
        try:
            # 使用信号量限制并发
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def install_single(provider_name: str) -> Tuple[str, bool]:
                async with semaphore:
                    result = await self.install_sdk(provider_name, force_reinstall)
                    return provider_name, result
            
            tasks = [install_single(name) for name in provider_names]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            status_dict = {}
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"批量安装时发生异常: {result}")
                else:
                    provider_name, success = result
                    status_dict[provider_name] = success
            
            return status_dict
            
        except Exception as e:
            logger.error(f"批量安装SDK失败: {e}")
            return {name: False for name in provider_names}
    
    async def get_sdk_info(self, provider_name: str) -> Optional[Dict[str, any]]:
        """
        获取SDK信息
        
        Args:
            provider_name: Provider名称
            
        Returns:
            SDK信息字典
        """
        try:
            if provider_name not in self.SDK_PACKAGES:
                return None
            
            sdk_config = self.SDK_PACKAGES[provider_name].copy()
            
            # 检查可用性
            is_available = await self.check_sdk_availability(provider_name)
            sdk_config["available"] = is_available
            
            # 获取版本信息（如果已安装）
            if is_available:
                version = await self._get_package_version(sdk_config["package"])
                sdk_config["installed_version"] = version
            
            return sdk_config
            
        except Exception as e:
            logger.error(f"获取SDK信息失败 {provider_name}: {e}")
            return None
    
    async def _get_package_version(self, package_name: str) -> Optional[str]:
        """获取已安装包的版本"""
        try:
            version = await asyncio.to_thread(self._get_package_version_sync, package_name)
            return version
        except Exception:
            return None
    
    def _get_package_version_sync(self, package_name: str) -> Optional[str]:
        """同步获取包版本（在线程池中执行）"""
        try:
            import pkg_resources
            return pkg_resources.get_distribution(package_name).version
        except Exception:
            return None
    
    async def auto_install_for_providers(self, provider_names: List[str]) -> Dict[str, bool]:
        """
        为指定的Provider自动安装必要的SDK
        
        Args:
            provider_names: 需要安装SDK的Provider列表
            
        Returns:
            安装结果字典
        """
        try:
            logger.info(f"开始为Provider自动安装SDK: {', '.join(provider_names)}")
            
            # 首先检查哪些需要安装
            availability = await self.batch_check_sdks(provider_names)
            
            need_install = [
                name for name, available in availability.items()
                if not available
            ]
            
            if not need_install:
                logger.info("所有SDK都已安装")
                return {name: True for name in provider_names}
            
            logger.info(f"需要安装SDK的Provider: {', '.join(need_install)}")
            
            # 批量安装
            install_results = await self.batch_install_sdks(need_install)
            
            # 合并结果
            final_results = {}
            for name in provider_names:
                if name in need_install:
                    final_results[name] = install_results.get(name, False)
                else:
                    final_results[name] = True  # 已经可用
            
            success_count = sum(1 for success in final_results.values() if success)
            logger.info(f"SDK安装完成: {success_count}/{len(provider_names)} 成功")
            
            return final_results
            
        except Exception as e:
            logger.error(f"自动安装SDK失败: {e}")
            return {name: False for name in provider_names}
    
    def get_supported_providers(self) -> List[str]:
        """获取支持的Provider列表"""
        return list(self.SDK_PACKAGES.keys())
    
    def clear_cache(self) -> None:
        """清除安装缓存"""
        self.installation_cache.clear()
        logger.info("SDK安装缓存已清除")