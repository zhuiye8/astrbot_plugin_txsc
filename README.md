# 通用文生图插件

这是一个为AstrBot开发的通用文生图插件，支持多家国内AI图像生成服务商的统一调用，提供便捷的文本到图像生成功能。

## 支持的服务商

| 服务商 | 命令 | 状态 | 说明 |
|--------|------|------|------|
| 智谱AI | `tti-zhipu` | ✅ | 支持cogview-4-250304模型 |
| 百度千帆 | `tti-qianfan` | ✅ | 支持flux.1-schnell等模型 |
| 阿里通义万相 | `tti-tongyi` | ✅ | 支持wanx-2.2模型 |
| PPIO | `tti-ppio` | ✅ | 支持sd15等模型，异步任务机制 |
| 火山引擎 | `tti-huoshan` | ✅ | 支持doubao-seedream-3-0-t2i-250415模型 |
| 科大讯飞 | `tti-xunfei` | ✅ | 支持spark-v2.1模型 |

> **注意**：境外服务商暂时不可用，已在代码中注释。(二开可以参考)

## 安装与配置

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置文件
在AstrBot配置文件中添加以下配置项：

```json
{
  "astrbot_plugin_universal_t2i": {
    "default_width": 512,
    "default_height": 512,
    
    "zhipu_api_key": "your_zhipu_api_key",
    "zhipu_base_url": "https://open.bigmodel.cn/api/paas/v4",
    "zhipu_model": "cogview-4-250304",
    
    "qianfan_access_token": "your_qianfan_access_token",
    "qianfan_model": "flux.1-schnell",
    "qianfan_steps": 4,
    
    "tongyi_api_key": "your_tongyi_api_key",
    "tongyi_base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
    "tongyi_model": "wanx-2.2",
    
    "ppio_api_key": "your_ppio_api_key",
    "ppio_base_url": "https://api.ppinfra.com",
    "ppio_model": "sd15",
    "ppio_steps": 20,
    "ppio_guidance_scale": 7.5,
    
    "volcengine_api_key": "your_volcengine_api_key",
    "volcengine_base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "volcengine_model": "doubao-seedream-3-0-t2i-250415",
    
    "xunfei_app_id": "your_xunfei_app_id",
    "xunfei_api_key": "your_xunfei_api_key",
    "xunfei_api_secret": "your_xunfei_api_secret"
  }
}
```

### 3. 获取API密钥

#### 智谱AI
1. 访问 [智谱AI开放平台](https://open.bigmodel.cn/)
2. 注册账号并实名认证
3. 创建API Key

#### 百度千帆
1. 访问 [百度千帆大模型平台](https://qianfan.cloud.baidu.com/)
2. 创建应用获取API Key和Secret Key
3. 使用API Key和Secret Key获取Access Token

#### 阿里通义万相
1. 访问 [阿里云控制台](https://dashscope.console.aliyun.com/)
2. 开通灵积模型服务
3. 创建API Key

#### PPIO
1. 访问 [PPIO开放平台](https://ppinfra.com/)
2. 注册账号并充值
3. 获取API Token

#### 火山引擎
1. 访问 [火山引擎控制台](https://console.volcengine.com/)
2. 开通豆包大模型服务
3. 创建推理接入点获取API Key

#### 科大讯飞
1. 访问 [讯飞开放平台](https://console.xfyun.cn/)
2. 创建文生图应用
3. 获取APPID、API Key和API Secret

## 使用方法

### 基本命令
- `/tti <描述文字>` - 自动选择可用的供应商生成图片
- `/文生图 <描述文字>` - 中文别名，功能相同

### 指定供应商命令
- `/tti-zhipu <描述>` - 使用智谱AI生成
- `/tti-qianfan <描述>` - 使用百度千帆生成
- `/tti-tongyi <描述>` - 使用阿里通义万相生成
- `/tti-ppio <描述>` - 使用PPIO生成
- `/tti-huoshan <描述>` - 使用火山引擎生成
- `/tti-xunfei <描述>` - 使用科大讯飞生成

### 使用示例
```
/tti 一只可爱的橘色小猫咪，坐在阳光明媚的窗台上
/tti-tongyi 科技感的未来城市夜景，霓虹灯闪烁
/tti-huoshan 美丽的山水风景画，中国风格
/tti-ppio anime style girl with blue hair
```

## 功能特点

### 1. 多供应商支持
- 支持6家主流国内AI图像生成服务
- 自动故障转移机制，单个供应商失败时自动尝试其他供应商
- 支持指定供应商生成，方便测试和调试

### 2. 异步任务处理
- PPIO使用异步任务机制，支持长时间生成任务
- 智能轮询机制，前6次每5秒轮询，后续每10秒
- 最多轮询12次，总计约2分钟超时

### 3. 智能错误处理
- 详细的错误信息反馈
- 区分配置错误、API错误和网络错误
- 支持多供应商错误汇总报告

### 4. 灵活配置
- 支持自定义图片尺寸
- 各供应商独立配置
- 支持自定义API端点和模型参数

## 故障排除

### 常见问题

#### Q: 提示"没有可用的文生图服务"
A: 检查配置文件中是否正确设置了至少一个供应商的API密钥

#### Q: 某个供应商一直失败
A: 
1. 检查API密钥是否正确
2. 检查网络连接
3. 查看日志获取详细错误信息
4. 确认账户余额是否充足

#### Q: PPIO生成时间很长
A: PPIO使用异步任务机制，需要等待模型处理，正常情况下需要30秒到2分钟

#### Q: 讯飞认证失败
A: 检查APPID、API Key和API Secret是否正确，确保时间同步

### 错误代码说明

- `HTTP 401` - API密钥无效或过期
- `HTTP 403` - 权限不足或余额不足
- `HTTP 404` - API端点不存在（检查base_url配置）
- `HTTP 429` - 请求频率过高
- `HTTP 500` - 服务器内部错误

### 日志调试

插件会输出详细的调试信息，包括：
- 供应商加载状态
- API请求参数
- 错误详情
- 生成结果

查看AstrBot日志获取更多信息。

## 开发说明

### 目录结构
```
astrbot_plugin_universal_t2i/
├── main.py                 # 主插件文件
├── _conf_schema.json      # 配置schema
├── requirements.txt       # 依赖列表
├── README.md             # 说明文档
└── providers/            # 供应商实现
    ├── __init__.py
    ├── base.py           # 基础抽象类
    ├── zhipu.py          # 智谱AI
    ├── qianfan.py        # 百度千帆
    ├── tongyi.py         # 阿里通义万相
    ├── ppio.py           # PPIO
    ├── volcengine.py     # 火山引擎
    └── xunfei.py         # 科大讯飞
```

### 添加新供应商

1. 在`providers/`目录下创建新的供应商实现文件
2. 继承`BaseProvider`类
3. 实现必要的抽象方法
4. 在`main.py`中添加导入和映射
5. 更新配置schema和README

### 贡献指南

欢迎提交Issue和Pull Request！

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request


## 许可证

本项目采用MIT许可证。