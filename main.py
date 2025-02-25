from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api.all import *
from astrbot.api.message_components import *
import subprocess
import sys
import importlib
import re
import asyncio

@register("astrbot_plugin_txsc", "zhuiye", "一个基于阿里云百炼 通义万相-文生图的插件", "1.0.0", "https://github.com/zhuiye8/astrbot_plugin_txsc")
class MyPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "wanx2.1-t2i-turbo")
        self.prompt_extend = config.get("prompt_extend",False)

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
    
    @filter.event_message_type(EventMessageType.ALL)
    async def generate_image(self, event: AstrMessageEvent):
        """监听所有消息,识别关键词进行图片生成"""
        message = event.message_str
        
        # 检查是否包含绘画相关关键词
        draw_keywords = ["画", "绘画", "画个", "画张", "画一个", "画一张", "生图", "画画", "img", "painting","draw"]
        if not any(keyword in message for keyword in draw_keywords):
            return  # 如果没有关键词就直接返回,不执行后续操作
            
        # 检查是否配置了API密钥
        if not self.api_key:
            yield event.plain_result("\n请联系管理员配置文生图API密钥")
            return

        # 定义反向提示词关键词
        negative_prompt_keywords =  ["不要", "避免", "无", "不包含", "不想要", "排除","没有"]

        # 初始化提示词和反向提示词
        prompt = ""
        negative_prompt = ""

        # 尝试从消息中提取反向提示词
        for keyword in negative_prompt_keywords:
            if keyword in message:
            # 提取反向提示词后面的文本
                match = re.search(rf"{keyword}(.+)", message)
                if match:
                    negative_prompt = match.group(1).strip()  # 获取反向提示词内容
                    message = message.replace(match.group(0), "")  # 从消息中删除反向提示词部分

        # 余下的部分就是提示词
        prompt = message.strip()
            
        if not prompt:
            yield event.plain_result("\n请提供绘画内容的描述!")
            return

        # 检查尺寸参数
        valid_sizes = ["1024*1024", "1440*720", "768*1344", "864*1152", 
                      "1344*768", "1152*864", "1440*720", "720*1440","1024x1024", "1440x720", "768x1344", "864x1152", 
                      "1344x768", "1152x864", "1440x720", "720x1440"]
        size = "1024*1024"  # 默认尺寸
        
        # 检查消息中是否包含尺寸信息
        for valid_size in valid_sizes:
            if valid_size in message:
                size = valid_size
                break
        
        # 发送正在生成的提示
        yield event.plain_result("\n正在生成图片，请稍候...")

        # 调用异步图像生成方法
        image_url = await self.generate_image_async(prompt, negative_prompt, size)
        if image_url:
            chain = [
                Plain(f"\n提示词：{prompt}\n反向提示词:{negative_prompt}\n大小：{size}\n"),
                Image.fromURL(image_url)
            ]
            yield event.chain_result(chain)
        else:
            yield event.plain_result("\n生成图片失败")
    
    async def generate_image_async(self, prompt, negative_prompt, size):
        """异步生成图像并返回图像URL"""
        try:
            # 转换尺寸格式，DashScope API 使用 "width*height"
            api_size = size.replace('x', '*')
            
            # 创建异步任务
            task_rsp = ImageSynthesis.async_call(
                api_key=self.api_key,
                model=self.model,
                prompt=prompt,
                negative_prompt=negative_prompt if negative_prompt else None,
                n=1,
                size=api_size
            )
            
            if task_rsp.status_code != 200:
                raise Exception(f"任务提交失败: {task_rsp.message}")
            
            # 等待任务完成
            result_rsp = await asyncio.to_thread(ImageSynthesis.wait, task_rsp, api_key=self.api_key)
            
            if result_rsp.status_code == 200:
                results = result_rsp.output.results
                if results:
                    image_url = results[0].url
                    return image_url
                else:
                    raise Exception("任务成功，但没有返回图像结果")
            else:
                raise Exception(f"任务失败: {result_rsp.message}")
        
        except Exception as e:
            print(f"生成图片失败: {str(e)}")
            return None
