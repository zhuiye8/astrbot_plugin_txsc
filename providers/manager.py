"""
Provider管理器
负责管理所有文生图服务提供商，提供统一的调用接口
"""

from typing import Dict, List, Optional, Any, Union
import asyncio
import random
from astrbot.api.logger import logger

from .base import (
    BaseImageProvider, GenerationParams, GenerationResult, 
    ProviderConfig, ProviderError, ResponseType
)


class LoadBalanceStrategy:
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    PRIORITY = "priority"
    FASTEST = "fastest"
    CHEAPEST = "cheapest"


class ProviderManager:
    """Provider管理器"""
    
    def __init__(self):
        self.providers: Dict[str, BaseImageProvider] = {}
        self.enabled_providers: List[str] = []
        self.load_balance_strategy = LoadBalanceStrategy.PRIORITY
        self.current_provider_index = 0
        self.provider_stats: Dict[str, Dict[str, Any]] = {}
        self.fallback_enabled = True
        
    def register_provider(self, provider: BaseImageProvider) -> None:
        """注册Provider"""
        self.providers[provider.name] = provider
        
        if provider.config.enabled:
            if provider.name not in self.enabled_providers:
                self.enabled_providers.append(provider.name)
        
        # 初始化统计信息
        self.provider_stats[provider.name] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0.0,
            "last_used": None,
            "health_status": "unknown"
        }
        
        logger.info(f"已注册Provider: {provider.name}")
    
    def unregister_provider(self, provider_name: str) -> None:
        """注销Provider"""
        if provider_name in self.providers:
            del self.providers[provider_name]
            
        if provider_name in self.enabled_providers:
            self.enabled_providers.remove(provider_name)
            
        if provider_name in self.provider_stats:
            del self.provider_stats[provider_name]
            
        logger.info(f"已注销Provider: {provider_name}")
    
    def get_provider(self, provider_name: str) -> Optional[BaseImageProvider]:
        """获取指定Provider"""
        return self.providers.get(provider_name)
    
    def get_enabled_providers(self) -> List[BaseImageProvider]:
        """获取所有启用的Provider"""
        return [self.providers[name] for name in self.enabled_providers 
                if name in self.providers]
    
    def set_load_balance_strategy(self, strategy: str) -> None:
        """设置负载均衡策略"""
        if strategy in [LoadBalanceStrategy.ROUND_ROBIN, LoadBalanceStrategy.RANDOM,
                       LoadBalanceStrategy.PRIORITY, LoadBalanceStrategy.FASTEST,
                       LoadBalanceStrategy.CHEAPEST]:
            self.load_balance_strategy = strategy
            logger.info(f"负载均衡策略已设置为: {strategy}")
        else:
            logger.warning(f"未知的负载均衡策略: {strategy}")
    
    def _select_provider(self, exclude_providers: List[str] = None) -> Optional[BaseImageProvider]:
        """根据负载均衡策略选择Provider"""
        exclude_providers = exclude_providers or []
        available_providers = [
            name for name in self.enabled_providers 
            if name not in exclude_providers and name in self.providers
        ]
        
        if not available_providers:
            return None
        
        if self.load_balance_strategy == LoadBalanceStrategy.ROUND_ROBIN:
            # 轮询策略
            if self.current_provider_index >= len(available_providers):
                self.current_provider_index = 0
            provider_name = available_providers[self.current_provider_index]
            self.current_provider_index += 1
            
        elif self.load_balance_strategy == LoadBalanceStrategy.RANDOM:
            # 随机策略
            provider_name = random.choice(available_providers)
            
        elif self.load_balance_strategy == LoadBalanceStrategy.PRIORITY:
            # 优先级策略（按配置顺序）
            provider_name = available_providers[0]
            
        elif self.load_balance_strategy == LoadBalanceStrategy.FASTEST:
            # 最快响应策略
            provider_name = min(available_providers, 
                              key=lambda x: self.provider_stats[x]["avg_response_time"])
            
        elif self.load_balance_strategy == LoadBalanceStrategy.CHEAPEST:
            # 最便宜策略（暂时按优先级）
            provider_name = available_providers[0]
            
        else:
            provider_name = available_providers[0]
        
        return self.providers.get(provider_name)
    
    async def generate_image(
        self, 
        params: GenerationParams,
        provider_name: Optional[str] = None,
        use_fallback: bool = None
    ) -> GenerationResult:
        """生成图片"""
        use_fallback = use_fallback if use_fallback is not None else self.fallback_enabled
        excluded_providers = []
        
        # 如果指定了Provider，优先使用
        if provider_name:
            provider = self.get_provider(provider_name)
            if provider and provider.config.enabled:
                result = await self._generate_with_provider(provider, params)
                if result.is_success or not use_fallback:
                    return result
                excluded_providers.append(provider_name)
            elif provider_name not in self.providers:
                return GenerationResult(
                    success=False,
                    error_message=f"Provider '{provider_name}' 不存在"
                )
            else:
                return GenerationResult(
                    success=False,
                    error_message=f"Provider '{provider_name}' 已禁用"
                )
        
        # 使用负载均衡选择Provider
        while True:
            provider = self._select_provider(excluded_providers)
            
            if not provider:
                return GenerationResult(
                    success=False,
                    error_message="没有可用的Provider"
                )
            
            result = await self._generate_with_provider(provider, params)
            
            if result.is_success:
                return result
            
            if not use_fallback:
                return result
            
            # 添加到排除列表，尝试下一个Provider
            excluded_providers.append(provider.name)
            logger.warning(f"Provider {provider.name} 生成失败，尝试下一个: {result.error_message}")
            
            # 如果所有Provider都尝试过了，返回最后的错误
            if len(excluded_providers) >= len(self.enabled_providers):
                return GenerationResult(
                    success=False,
                    error_message=f"所有Provider都生成失败，最后错误: {result.error_message}"
                )
    
    async def _generate_with_provider(
        self, 
        provider: BaseImageProvider, 
        params: GenerationParams
    ) -> GenerationResult:
        """使用指定Provider生成图片"""
        import time
        
        start_time = time.time()
        stats = self.provider_stats[provider.name]
        
        try:
            # 验证参数
            warnings = provider.validate_params(params)
            if warnings:
                logger.warning(f"Provider {provider.name} 参数警告: {'; '.join(warnings)}")
            
            # 生成图片
            result = await provider.generate_with_retry(params)
            
            # 更新统计信息
            end_time = time.time()
            response_time = end_time - start_time
            
            stats["total_requests"] += 1
            stats["last_used"] = end_time
            
            if result.is_success:
                stats["successful_requests"] += 1
                stats["health_status"] = "healthy"
                logger.info(f"Provider {provider.name} 生成成功，耗时 {response_time:.2f}s")
            else:
                stats["failed_requests"] += 1
                stats["health_status"] = "unhealthy"
                logger.error(f"Provider {provider.name} 生成失败: {result.error_message}")
            
            # 更新平均响应时间
            if stats["total_requests"] > 0:
                stats["avg_response_time"] = (
                    (stats["avg_response_time"] * (stats["total_requests"] - 1) + response_time) 
                    / stats["total_requests"]
                )
            
            return result
            
        except Exception as e:
            # 更新统计信息
            end_time = time.time()
            stats["total_requests"] += 1
            stats["failed_requests"] += 1
            stats["health_status"] = "error"
            stats["last_used"] = end_time
            
            logger.error(f"Provider {provider.name} 生成异常: {str(e)}")
            
            return GenerationResult(
                success=False,
                error_message=f"Provider {provider.name} 异常: {str(e)}"
            )
    
    async def batch_generate(
        self, 
        params_list: List[GenerationParams],
        max_concurrent: int = 3
    ) -> List[GenerationResult]:
        """批量生成图片"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_single(params):
            async with semaphore:
                return await self.generate_image(params)
        
        tasks = [generate_single(params) for params in params_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(GenerationResult(
                    success=False,
                    error_message=f"批量生成异常: {str(result)}"
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """对所有Provider进行健康检查"""
        results = {}
        
        tasks = []
        for provider_name, provider in self.providers.items():
            tasks.append(provider.health_check())
        
        if not tasks:
            return results
        
        health_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, (provider_name, provider) in enumerate(self.providers.items()):
            result = health_results[i]
            if isinstance(result, Exception):
                results[provider_name] = {
                    "status": "error",
                    "message": f"健康检查异常: {str(result)}",
                    "provider": provider_name
                }
            else:
                results[provider_name] = result
                # 更新统计信息中的健康状态
                self.provider_stats[provider_name]["health_status"] = result["status"]
        
        return results
    
    def get_provider_stats(self, provider_name: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, Dict[str, Any]]]:
        """获取Provider统计信息"""
        if provider_name:
            return self.provider_stats.get(provider_name, {})
        return self.provider_stats
    
    def reset_stats(self, provider_name: Optional[str] = None) -> None:
        """重置统计信息"""
        if provider_name:
            if provider_name in self.provider_stats:
                self.provider_stats[provider_name] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "avg_response_time": 0.0,
                    "last_used": None,
                    "health_status": "unknown"
                }
        else:
            for name in self.provider_stats:
                self.provider_stats[name] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "avg_response_time": 0.0,
                    "last_used": None,
                    "health_status": "unknown"
                }
    
    def enable_provider(self, provider_name: str) -> bool:
        """启用Provider"""
        if provider_name in self.providers:
            self.providers[provider_name].config.enabled = True
            if provider_name not in self.enabled_providers:
                self.enabled_providers.append(provider_name)
            logger.info(f"已启用Provider: {provider_name}")
            return True
        return False
    
    def disable_provider(self, provider_name: str) -> bool:
        """禁用Provider"""
        if provider_name in self.providers:
            self.providers[provider_name].config.enabled = False
            if provider_name in self.enabled_providers:
                self.enabled_providers.remove(provider_name)
            logger.info(f"已禁用Provider: {provider_name}")
            return True
        return False
    
    def get_summary(self) -> Dict[str, Any]:
        """获取管理器状态摘要"""
        total_providers = len(self.providers)
        enabled_providers = len(self.enabled_providers)
        
        total_requests = sum(stats["total_requests"] for stats in self.provider_stats.values())
        total_successful = sum(stats["successful_requests"] for stats in self.provider_stats.values())
        total_failed = sum(stats["failed_requests"] for stats in self.provider_stats.values())
        
        success_rate = (total_successful / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "total_providers": total_providers,
            "enabled_providers": enabled_providers,
            "load_balance_strategy": self.load_balance_strategy,
            "fallback_enabled": self.fallback_enabled,
            "total_requests": total_requests,
            "success_rate": f"{success_rate:.1f}%",
            "provider_list": list(self.providers.keys()),
            "enabled_provider_list": self.enabled_providers
        }
    
    def __str__(self):
        return f"ProviderManager(providers={len(self.providers)}, enabled={len(self.enabled_providers)})"
    
    def __repr__(self):
        return f"ProviderManager(providers={list(self.providers.keys())}, enabled={self.enabled_providers})"