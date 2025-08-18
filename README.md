# AstrBot通用文生图插件 v2.0.0

![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-blue)
![Version](https://img.shields.io/badge/version-v2.0.0-green)
![Python](https://img.shields.io/badge/python-3.8+-yellow)
![License](https://img.shields.io/badge/license-MIT-red)

一个支持9个主流AI图像生成服务商的AstrBot通用文生图插件，提供统一的调用接口和智能的负载均衡机制。

## ✨ 特性

- 🎨 **9大服务商支持**：集成阿里云通义万相、字节跳动火山引擎、百度智能云千帆、科大讯飞星火、智谱清言、OpenAI达芬奇、谷歌双子座、PPIO图像生成、Grok图像生成
- 🚀 **异步高性能**：完全异步架构，支持并发处理和智能排队
- 🔄 **智能故障转移**：自动切换服务商，确保服务可用性
- 📏 **多尺寸支持**：支持各种图片尺寸，自动适配不同服务商
- 🎭 **风格控制**：支持多种艺术风格，满足不同创作需求
- 🚫 **负面提示词**：智能处理反向提示词，提升生成质量
- 📊 **状态监控**：实时健康检查和使用统计
- 🔧 **智能解析**：自动识别Provider、尺寸、风格等参数
- 🛠️ **自动安装**：智能SDK依赖管理和安装

## 🚀 快速开始

### 安装

1. **下载插件**
   ```bash
   git clone https://github.com/zhuiye8/astrbot_plugin_txsc.git
   cd astrbot_plugin_txsc
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置插件**
   在AstrBot管理界面配置至少一个服务商的API密钥

### 基础使用

```
# 基础生成
画一只可爱的小猫咪

# 指定服务商
@阿里云 画一张海边日落的风景图

# 指定尺寸和风格
画一张1024x1792的卡通风格小狗图片

# 使用负面提示词
生成一张森林图片 不要建筑物 不要人物

# 高质量生成
画一张超高质量的山水画
```

### 命令使用

```
# 查看帮助
/tti help

# 查看服务商状态
/tti status

# 列出可用服务商
/tti providers

# 测试指定服务商
/tti test volcengine

# 查看使用统计
/tti stats
```

## 🎯 支持的服务商

| 服务商 | 中文名称 | 模型 | 特色功能 |
|--------|----------|------|----------|
| tongyi | 阿里云通义万相 | wanx2.1-t2i-turbo | 强大的中文理解、多尺寸支持 |
| volcengine | 字节跳动火山引擎 | high_aes_general_v21_L | 高美感生成、调度配置 |
| qianfan | 百度智能云千帆 | 千帆文生图 | 中文优化、风格多样 |
| xunfei | 科大讯飞星火 | 星火图像生成 | 中文语义理解优秀 |
| zhipu | 智谱清言 | CogView-3 | 多模态生成、创意表达 |
| openai | OpenAI达芬奇 | DALL-E 3 | 业界领先质量、prompt优化 |
| gemini | 谷歌双子座 | Imagen 2 | 多语言支持、安全过滤 |
| ppio | PPIO图像生成 | ppio-diffusion-v1 | 去中心化、性价比高 |
| grok | Grok图像生成 | grok-vision | 创意幽默、独特风格 |

## ⚙️ 配置说明

### 基础配置

```json
{
  "default_provider": "tongyi",
  "enable_fallback": true,
  "draw_keywords": "画,绘画,画个,画张,画一个,画一张,生图,画画,img,painting,draw",
  "enable_negative_prompt_processing": true,
  "negative_prompt_keywords": "不要,避免,无,不包含,不想要,排除,没有",
  "prompt_extend": false
}
```

## 🎨 高级功能

### 智能参数解析

插件支持从自然语言中智能提取以下参数：

- **服务商选择**：`@阿里云`、`@火山引擎`、`使用OpenAI生成`
- **图片尺寸**：`1024x1024`、`方形`、`横版`、`竖版`
- **艺术风格**：`写实`、`卡通`、`动漫`、`油画`、`水彩`、`素描`
- **生成数量**：`3张图片`、`生成5个`
- **质量设置**：`高质量`、`超高质量`、`快速生成`
- **种子值**：`seed:12345`、`随机种子:67890`

### 负载均衡策略

- **轮询模式**：依次使用各个服务商
- **随机模式**：随机选择可用服务商
- **优先级模式**：按配置顺序优先使用
- **最快响应**：选择响应时间最短的服务商

### 故障转移机制

- 自动检测服务商健康状态
- 智能切换到可用服务商
- 详细的错误日志和状态报告
- 服务恢复后自动重新启用

## 📊 监控与统计

### 健康检查
```
/tti status
```
显示所有服务商的连接状态、API可用性和响应时间。

### 使用统计
```
/tti stats
```
查看各服务商的请求数量、成功率、平均响应时间等详细统计。

## 🔧 开发说明

### 项目结构
```
astrbot_plugin_txsc/
├── main.py                    # 主插件文件
├── providers/                 # 服务商实现
│   ├── base.py               # 基础Provider抽象
│   ├── manager.py            # Provider管理器
│   ├── tongyi_provider.py    # 阿里云通义万相
│   ├── volcengine_provider.py # 字节跳动火山引擎
│   ├── qianfan_provider.py   # 百度智能云千帆
│   ├── xunfei_provider.py    # 科大讯飞星火
│   ├── zhipu_provider.py     # 智谱清言
│   ├── openai_provider.py    # OpenAI达芬奇
│   ├── gemini_provider.py    # 谷歌双子座
│   ├── ppio_provider.py      # PPIO图像生成
│   └── grok_provider.py      # Grok图像生成
├── utils/                     # 工具模块
│   ├── config_validator.py   # 配置验证
│   ├── image_processor.py    # 图片处理
│   ├── message_parser.py     # 消息解析
│   └── sdk_installer.py      # SDK自动安装
├── _conf_schema.json         # 配置schema
├── metadata.yaml             # 插件元数据
└── requirements.txt          # 依赖列表
```

### 代码规范

- 严格遵循AstrBot开发规范
- 使用完整的中文注释
- 支持异步并发处理
- 完善的错误处理机制
- 统一的日志记录格式

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📄 许可证

本项目采用 MIT 许可证。

## 🙏 致谢

- [AstrBot](https://github.com/Soulter/AstrBot) - 优秀的多平台聊天机器人框架
- 各AI图像生成服务商提供的强大API支持

---

**开发者**: zhuiye  
**项目地址**: https://github.com/zhuiye8/astrbot_plugin_txsc  
**版本**: v2.0.0