from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api.all import *
from astrbot.api.message_components import *
import subprocess
import sys
import importlib
import re
import asyncio
from abc import ABC, abstractmethod
import json

@register("astrbot_plugin_text2img", "zhuiye", "通用文生图插件，支持阿里云通义万相和火山引擎", "1.0.0", "https://github.com/zhuiye8/astrbot_plugin_text2img")
class Text2ImgPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        # 将中文服务商名称映射到内部标识符
        self.provider_map = {
            "阿里": "alibaba",
            "火山": "volcengine"
        }
        # 解析默认服务商配置
        self.provider = self.provider_map.get(config.get("default_provider", "阿里"), "alibaba")
        # 从配置读取触发关键词
        self.draw_keywords = config.get("draw_keywords", "画,绘画,画个,画张,画一个,画一张,生图,画画,img,painting,draw").split(",")
        # 从配置读取反向提示词处理开关
        self.enable_negative_prompt_processing = config.get("enable_negative_prompt_processing", True)
        # 从配置读取反向提示词关键词
        self.negative_prompt_keywords = config.get("negative_prompt_keywords", "不要,避免,无,不包含,不想要,排除,没有").split(",")

        self.generators = {}
        
        # 初始化生成器
        self._init_generators()
    
    def _init_generators(self):
        """初始化所有配置的图像生成器"""
        # 阿里云通义万相
        if self.config.get("alibaba_api_key"):
            self.generators["alibaba"] = AlibabaTongYiGenerator(self.config.get("alibaba_api_key"), 
                                                             self.config.get("alibaba_model", "wanx2.1-t2i-turbo"),
                                                             self.config.get("prompt_extend", False))
        
        # 火山引擎
        if self.config.get("volcengine_ak") and self.config.get("volcengine_sk"):
            self.generators["volcengine"] = VolcengineGenerator(self.config.get("volcengine_ak"),
                                                             self.config.get("volcengine_sk"),
                                                             self.config.get("volcengine_model", "high_aes_general_v21_L"),
                                                             self.config.get("fire_schedule_conf", "general_v20_9B_pe"))
        
        # 如果没有可用的生成器，打印警告
        if not self.generators:
            print("警告: 没有配置任何文生图服务的API密钥")
    
    @filter.event_message_type(EventMessageType.ALL)
    async def generate_image(self, event: AstrMessageEvent):
        """监听所有消息,识别关键词进行图片生成"""
        message = event.message_str
        
        # 检查是否包含绘画相关关键词
        if not any(keyword in message for keyword in self.draw_keywords):
            return  # 如果没有关键词就直接返回,不执行后续操作
        
        # 为调试添加记录
        print(f"收到文生图请求: {message}")    
            
        # 确定使用哪个提供商
        provider = self._detect_provider(message) or self.provider
        
        # 检查是否有该提供商的生成器
        if provider not in self.generators:
            available_providers = []
            for key in self.generators.keys():
                if key == "alibaba":
                    available_providers.append("阿里")
                elif key == "volcengine":
                    available_providers.append("火山")
            
            available_providers_str = ", ".join(available_providers)
            if not available_providers:
                yield event.plain_result("\n请联系管理员配置文生图API密钥")
            else:
                provider_display = "阿里" if provider == "alibaba" else "火山"
                yield event.plain_result(f"\n未配置{provider_display}的API密钥，可用的服务商: {available_providers_str}")
            return

        # 初始化提示词和反向提示词
        prompt = ""
        negative_prompt = ""

        # 提取服务商标记并移除
        message = self._remove_provider_tag(message)

        # 尝试从消息中提取反向提示词
        if self.enable_negative_prompt_processing:
            for keyword in self.negative_prompt_keywords:
                if keyword in message:
                    # 使用正则表达式查找关键词后的所有内容
                    match = re.search(rf"{keyword}(.*)", message, re.DOTALL)
                    if match:
                        # 提取反向提示词，并去除首尾空格
                        negative_prompt = match.group(1).strip()
                        # 从原始消息中移除关键词和反向提示词
                        message = message.replace(match.group(0), "").strip()
                        # 找到一个匹配后就跳出循环
                        break

        # 余下的部分就是提示词
        prompt = message.strip()
            
        if not prompt:
            yield event.plain_result("\n请提供绘画内容的描述!")
            return

        # 检查尺寸参数
        valid_sizes = ["1024*1024", "1440*720", "768*1344", "864*1152", 
                      "1344*768", "1152*864", "1440*720", "720*1440", "1024x1024", "1440x720", "768x1344", "864x1152", 
                      "1344x768", "1152x864", "1440x720", "720x1440"]
        size = "1024*1024"  # 默认尺寸
        
        # 检查消息中是否包含尺寸信息
        for valid_size in valid_sizes:
            if valid_size in message:
                size = valid_size
                prompt = prompt.replace(valid_size, "").strip()
                break
        
        # 获取用于显示的服务商名称
        provider_display = "阿里云通义万相" if provider == "alibaba" else "火山引擎"
        
        # 发送正在生成的提示
        yield event.plain_result(f"\n正在使用{provider_display}生成图片，请稍候...")

        try:
            # 调用生成器生成图像
            generator = self.generators[provider]
            print(f"正在使用{provider_display}生成图片，提示词: {prompt}")
            image_url = await generator.generate_image(prompt, negative_prompt, size)
            
            if image_url:
                chain = [
                    Plain(f"\n提供商: {provider_display}\n提示词：{prompt}\n反向提示词: {negative_prompt}\n大小：{size}\n"),
                    Image.fromURL(image_url)
                ]
                yield event.chain_result(chain)
            else:
                # 生成失败，但没有异常，可能是API返回空结果
                yield event.plain_result(f"\n生成图片失败，服务返回空结果，请稍后再试")
        except Exception as e:
            # 捕获并显示错误给用户
            error_message = str(e)
            # 限制错误信息长度
            if len(error_message) > 100:
                error_message = error_message[:97] + "..."
            yield event.plain_result(f"\n生成图片失败: {error_message}")
            # 记录完整错误
            import traceback
            print(f"文生图错误: {traceback.format_exc()}")
    
    def _detect_provider(self, message):
        """从消息中检测服务提供商"""
        if "@阿里" in message:
            return "alibaba"
        elif "@火山" in message:
            return "volcengine"
        return None
    
    def _remove_provider_tag(self, message):
        """移除服务商标记"""
        provider_tags = ["@阿里", "@火山"]
        for tag in provider_tags:
            message = message.replace(tag, "")
        return message.strip()


class ImageGeneratorBase(ABC):
    """图像生成器基类"""
    
    @abstractmethod
    async def generate_image(self, prompt, negative_prompt, size):
        """生成图像并返回URL"""
        pass


class AlibabaTongYiGenerator(ImageGeneratorBase):
    """阿里云通义万相图像生成器"""
    
    def __init__(self, api_key, model="wanx2.1-t2i-turbo", prompt_extend=False):
        self.api_key = api_key
        self.model = model
        self.prompt_extend = prompt_extend
        
        # 检查并安装 dashscope
        if not self._check_dashscope():
            self._install_dashscope()
        
        # 导入 dashscope
        global ImageSynthesis
        from dashscope import ImageSynthesis
    
    def _check_dashscope(self) -> bool:
        """检查是否安装了 dashscope"""
        try:
            importlib.import_module('dashscope')
            return True
        except ImportError:
            return False

    def _install_dashscope(self):
        """安装 dashscope 包"""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "dashscope"])
            print("成功安装 dashscope 包")
        except subprocess.CalledProcessError as e:
            print(f"安装 dashscope 包失败: {str(e)}")
            raise
    
    async def generate_image(self, prompt, negative_prompt, size):
        """使用阿里云通义万相生成图像"""
        try:
            # 转换尺寸格式
            api_size = size.replace('x', '*')
            
            print(f"阿里云请求参数: model={self.model}, prompt={prompt}, negative_prompt={negative_prompt}, size={api_size}")
            
            # 创建异步任务
            task_rsp = ImageSynthesis.async_call(
                api_key=self.api_key,
                model=self.model,
                prompt=prompt,
                negative_prompt=negative_prompt if negative_prompt else None,
                n=1,
                size=api_size
            )
            
            print(f"阿里云提交响应状态码: {task_rsp.status_code}")
            
            if task_rsp.status_code != 200:
                raise Exception(f"任务提交失败: {task_rsp.message}")
            
            # 等待任务完成
            result_rsp = await asyncio.to_thread(ImageSynthesis.wait, task_rsp, api_key=self.api_key)
            
            print(f"阿里云结果响应状态码: {result_rsp.status_code}")
            
            if result_rsp.status_code == 200:
                results = result_rsp.output.results
                if results:
                    image_url = results[0].url
                    print(f"阿里云生成图片成功，URL: {image_url}")
                    return image_url
                else:
                    raise Exception("任务成功，但没有返回图像结果")
            else:
                raise Exception(f"任务失败: {result_rsp.message}")
        
        except Exception as e:
            # 详细打印完整错误信息
            import traceback
            error_message = f"阿里云通义万相生成图片失败: {str(e)}\n{traceback.format_exc()}"
            print(error_message)
            return None


class VolcengineGenerator(ImageGeneratorBase):
    """火山引擎图像生成器"""
    
    def __init__(self, access_key, secret_key, model="high_aes_general_v21_L", schedule_conf="general_v20_9B_pe"):
        self.access_key = access_key
        self.secret_key = secret_key
        self.model = model
        self.schedule_conf = schedule_conf
        
        # 检查并安装 volcengine
        if not self._check_volcengine():
            self._install_volcengine()
    
    def _check_volcengine(self) -> bool:
        """检查是否安装了 volcengine"""
        try:
            importlib.import_module('volcengine')
            return True
        except ImportError:
            return False

    def _install_volcengine(self):
        """安装 volcengine 包"""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "volcengine"])
            print("成功安装 volcengine 包")
        except subprocess.CalledProcessError as e:
            print(f"安装 volcengine 包失败: {str(e)}")
            raise
    
    async def generate_image(self, prompt, negative_prompt, size):
        """使用火山引擎生成图像"""
        try:
            # 导入火山引擎SDK
            from volcengine import visual
            from volcengine.visual.VisualService import VisualService
            
            # 打印完整的认证信息（注意隐藏部分敏感信息）
            ak_masked = self.access_key[:4] + "****" + self.access_key[-4:] if len(self.access_key) > 8 else "****"
            sk_masked = self.secret_key[:4] + "****" + self.secret_key[-4:] if len(self.secret_key) > 8 else "****"
            print(f"火山引擎认证信息: AK={ak_masked}, SK={sk_masked}")
            
            # 创建服务实例
            visual_service = VisualService()
            visual_service.set_ak(self.access_key)
            visual_service.set_sk(self.secret_key)
            
            # 解析尺寸
            width, height = self._parse_size(size)
            print(f"尺寸解析结果: 原始尺寸={size}, 解析后 width={width}, height={height}")
            
            # 准备请求参数 (直接使用同步接口CV Process)
            form = {
                "req_key": self.model,
                "prompt": prompt,
                "model_version": "general_v2.1_L",
                "req_schedule_conf": self.schedule_conf,
                "llm_seed": -1,
                "seed": -1,
                "scale": 3.5,
                "ddim_steps": 25,
                "width": width,
                "height": height,
                "use_pre_llm": True,
                "use_sr": True,
                "return_url": True
            }
            
            # 添加反向提示词（如果有）
            if negative_prompt:
                form["negative_prompt"] = negative_prompt
            
            # 打印完整参数
            print(f"火山引擎完整请求参数: {json.dumps(form, ensure_ascii=False, indent=2)}")
            
            try:
                # 获取SDK版本
                import pkg_resources
                volcano_version = pkg_resources.get_distribution("volcengine").version
                print(f"volcengine SDK版本: {volcano_version}")
            except Exception as e:
                print(f"无法获取volcengine版本: {e}")
            
            # 使用同步接口直接处理
            print("开始调用火山引擎同步接口...")
            response = await asyncio.to_thread(visual_service.cv_process, form)
            
            # 打印原始响应
            print(f"火山引擎原始响应类型: {type(response)}")
            
            # 处理响应数据
            # 火山引擎返回的是Python字典，不需要JSON解析
            if isinstance(response, dict):
                response_data = response
                print(f"火山引擎返回Python字典响应: {response_data}")
            else:
                # 如果不是字典，尝试转换为字符串
                response_str = str(response)
                print(f"非字典响应转为字符串: {response_str}")
                # 尝试JSON解析
                try:
                    response_data = json.loads(response_str)
                except Exception as parse_err:
                    print(f"解析响应字符串失败: {parse_err}")
                    # 如果以上方法都失败，作为最后尝试，用eval直接评估Python表达式（不安全但可能有效）
                    try:
                        if response_str.startswith('{') and response_str.endswith('}'):
                            import ast
                            response_data = ast.literal_eval(response_str)
                            print(f"使用ast.literal_eval解析后: {response_data}")
                        else:
                            raise Exception("响应格式不是有效的Python字典字符串")
                    except Exception as e:
                        print(f"所有解析尝试都失败: {e}")
                        raise Exception(f"无法处理火山引擎响应: {response}")
            
            # 检查响应状态
            if response_data.get("code") != 10000:
                error_code = response_data.get("code")
                error_msg = response_data.get("message", "未知错误")
                print(f"火山引擎API错误: 代码={error_code}, 消息={error_msg}")
                raise Exception(f"处理失败: {error_msg}, 错误码: {error_code}")
            
            # 从响应中获取图像URL
            image_urls = response_data.get("data", {}).get("image_urls", [])
            if image_urls and len(image_urls) > 0:
                image_url = image_urls[0]
                print(f"火山引擎生成图片成功，URL: {image_url}")
                return image_url
            else:
                # 检查是否有binary_data_base64
                binary_data = response_data.get("data", {}).get("binary_data_base64", [])
                if binary_data and len(binary_data) > 0:
                    # 这里需要处理base64编码的图片数据，但我们期望的是URL，所以返回错误
                    print("火山引擎返回了base64编码的图片而非URL")
                    raise Exception("火山引擎返回了base64编码的图片而非URL")
                else:
                    raise Exception("火山引擎未返回图像数据")
            
        except Exception as e:
            # 详细打印完整错误信息
            import traceback
            error_message = f"火山引擎生成图片失败: {str(e)}\n{traceback.format_exc()}"
            print(error_message)
            return None
    
    def _parse_size(self, size):
        """解析尺寸字符串为宽度和高度"""
        if '*' in size:
            parts = size.split('*')
        elif 'x' in size:
            parts = size.split('x')
        else:
            # 默认尺寸
            return 512, 512
        
        if len(parts) == 2:
            try:
                width = int(parts[0])
                height = int(parts[1])
                return width, height
            except ValueError:
                pass
        
        # 默认尺寸
        return 512, 512