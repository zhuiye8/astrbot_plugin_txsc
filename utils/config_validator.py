"""
配置验证工具
"""

from typing import Dict, Any, List, NamedTuple
from astrbot.api import logger


class ValidationResult(NamedTuple):
    """验证结果"""
    is_valid: bool
    warnings: List[str]
    errors: List[str]


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        # 必需的配置字段映射
        self.required_fields = {
            "tongyi": ["tongyi_api_key"],
            "volcengine": ["volcengine_ak", "volcengine_sk"],
            "qianfan": ["qianfan_api_key", "qianfan_secret_key"],
            "xunfei": ["xunfei_app_id", "xunfei_api_key", "xunfei_api_secret"],
            "ppio": ["ppio_api_token"],
            "zhipu": ["zhipu_api_key"],
            "openai": ["openai_api_key"],
            "gemini": ["gemini_api_key"],
            "grok": ["grok_api_key"]
        }
        
        # 可选配置字段
        self.optional_fields = {
            "tongyi": ["tongyi_model", "tongyi_timeout"],
            "volcengine": ["volcengine_model", "volcengine_schedule_conf"],
            "qianfan": ["qianfan_model"],
            "xunfei": ["xunfei_model"],
            "ppio": ["ppio_model", "ppio_timeout"],
            "zhipu": ["zhipu_model"],
            "openai": ["openai_model", "openai_base_url"],
            "gemini": ["gemini_model"],
            "grok": ["grok_model"]
        }
    
    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """验证配置"""
        warnings = []
        errors = []
        
        # 检查是否至少配置了一个Provider
        configured_providers = []
        
        for provider_name, required_fields in self.required_fields.items():
            if self._is_provider_configured(config, required_fields):
                configured_providers.append(provider_name)
                
                # 验证具体Provider配置
                provider_warnings, provider_errors = self._validate_provider_config(
                    config, provider_name, required_fields
                )
                warnings.extend(provider_warnings)
                errors.extend(provider_errors)
        
        if not configured_providers:
            errors.append("未配置任何文生图服务商，请至少配置一个")
        else:
            logger.info(f"已配置的Provider: {', '.join(configured_providers)}")
        
        # 验证基础配置
        base_warnings = self._validate_base_config(config)
        warnings.extend(base_warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            warnings=warnings,
            errors=errors
        )
    
    def _is_provider_configured(self, config: Dict[str, Any], required_fields: List[str]) -> bool:
        """检查Provider是否已配置"""
        for field in required_fields:
            if not config.get(field):
                return False
        return True
    
    def _validate_provider_config(
        self, 
        config: Dict[str, Any], 
        provider_name: str, 
        required_fields: List[str]
    ) -> tuple[List[str], List[str]]:
        """验证特定Provider的配置"""
        warnings = []
        errors = []
        
        # 检查必需字段
        for field in required_fields:
            value = config.get(field)
            if not value:
                errors.append(f"{provider_name}: 缺少必需配置 {field}")
            elif isinstance(value, str) and len(value.strip()) == 0:
                errors.append(f"{provider_name}: 配置 {field} 不能为空")
        
        # 检查可选字段的合理性
        optional_fields = self.optional_fields.get(provider_name, [])
        for field in optional_fields:
            value = config.get(field)
            if value is not None:
                field_warnings = self._validate_field_value(provider_name, field, value)
                warnings.extend(field_warnings)
        
        return warnings, errors
    
    def _validate_field_value(self, provider_name: str, field: str, value: Any) -> List[str]:
        """验证字段值的合理性"""
        warnings = []
        
        # 超时配置验证
        if "timeout" in field and isinstance(value, (int, float)):
            if value < 10:
                warnings.append(f"{provider_name}: {field} 设置过小，建议至少10秒")
            elif value > 300:
                warnings.append(f"{provider_name}: {field} 设置过大，建议不超过300秒")
        
        # API Key格式验证（简单检查）
        if "api_key" in field and isinstance(value, str):
            if len(value) < 10:
                warnings.append(f"{provider_name}: {field} 长度过短，请检查是否正确")
            elif " " in value:
                warnings.append(f"{provider_name}: {field} 包含空格，请检查是否正确")
        
        # 模型名称验证
        if "model" in field and isinstance(value, str):
            if not value.strip():
                warnings.append(f"{provider_name}: {field} 不能为空字符串")
        
        return warnings
    
    def _validate_base_config(self, config: Dict[str, Any]) -> List[str]:
        """验证基础配置"""
        warnings = []
        
        # 检查默认Provider
        default_provider = config.get("default_provider")
        if default_provider:
            # 检查默认Provider是否已配置
            provider_mapping = {
                "通义": "tongyi",
                "阿里": "tongyi", 
                "火山": "volcengine",
                "千帆": "qianfan",
                "百度": "qianfan",
                "讯飞": "xunfei",
                "智谱": "zhipu",
                "openai": "openai",
                "gemini": "gemini",
                "grok": "grok"
            }
            
            real_provider = provider_mapping.get(default_provider, default_provider)
            if real_provider in self.required_fields:
                required_fields = self.required_fields[real_provider]
                if not self._is_provider_configured(config, required_fields):
                    warnings.append(f"默认Provider '{default_provider}' 未正确配置")
        
        # 检查触发关键词
        draw_keywords = config.get("draw_keywords", "")
        if not draw_keywords or not draw_keywords.strip():
            warnings.append("触发关键词未设置，将使用默认关键词")
        
        # 检查负载均衡设置
        load_balance_strategy = config.get("load_balance_strategy")
        if load_balance_strategy and load_balance_strategy not in [
            "round_robin", "random", "priority", "fastest", "cheapest"
        ]:
            warnings.append(f"未知的负载均衡策略: {load_balance_strategy}")
        
        return warnings
    
    def get_provider_status(self, config: Dict[str, Any]) -> Dict[str, str]:
        """获取各Provider的配置状态"""
        status = {}
        
        for provider_name, required_fields in self.required_fields.items():
            if self._is_provider_configured(config, required_fields):
                status[provider_name] = "已配置"
            else:
                missing_fields = [
                    field for field in required_fields 
                    if not config.get(field)
                ]
                status[provider_name] = f"未配置 (缺少: {', '.join(missing_fields)})"
        
        return status