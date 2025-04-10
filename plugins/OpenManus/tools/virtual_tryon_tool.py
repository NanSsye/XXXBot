import json
import aiohttp
import asyncio
import base64
import time
import os
import re
import uuid
import tempfile
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger

from ..agent.mcp import Tool

class VirtualTryOnTool(Tool):
    """AI虚拟试衣工具"""
    
    def __init__(self, api_base: str = "https://kwai-kolors-kolors-virtual-try-on.ms.show",
                 modelscope_cookies: str = None, modelscope_csrf_token: str = None, max_wait_time: int = 120):
        """初始化虚拟试衣工具
        
        Args:
            api_base: AI试衣API基础URL
            modelscope_cookies: ModelScope网站Cookie字符串
            modelscope_csrf_token: ModelScope网站CSRF Token
            max_wait_time: 最大等待时间(秒)
        """
        super().__init__(
            name="virtual_tryon",
            description="AI虚拟试衣，给人物穿上指定的衣服",
            parameters={
                "person_image": {
                    "type": "string",
                    "description": "人物图片的路径或URL"
                },
                "clothes_image": {
                    "type": "string",
                    "description": "衣服图片的路径或URL"
                }
            }
        )
        self.api_base = api_base.rstrip('/')
        self.max_wait_time = max_wait_time
        self.modelscope_cookies = modelscope_cookies
        self.modelscope_csrf_token = modelscope_csrf_token
        
        # 尝试从环境变量获取Cookie和CSRF Token（如果未直接提供）
        if not self.modelscope_cookies:
            self.modelscope_cookies = os.environ.get("MODELSCOPE_COOKIES", "")
        if not self.modelscope_csrf_token:
            self.modelscope_csrf_token = os.environ.get("MODELSCOPE_CSRF_TOKEN", "")
        
        # 创建临时目录存储图片
        self.temp_dir = "temp_images"
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 保存会话ID，避免重复获取
        self.studio_token = None
        
    async def execute(self, person_image: str, clothes_image: str) -> Dict[str, Any]:
        """执行虚拟试衣操作
        
        Args:
            person_image: 人物图片路径或URL
            clothes_image: 衣服图片路径或URL
            
        Returns:
            Dict: 包含生成图像的结果
        """
        try:
            # 1. 获取或验证会话令牌
            if not self.studio_token:
                self.studio_token = await self._get_studio_token()
                if not self.studio_token:
                    return {"success": False, "error": "无法获取会话令牌，请检查网络或ModelScope账号状态"}
            
            # 2. 下载图片（如果是URL）
            person_image_path = await self._ensure_local_image(person_image)
            clothes_image_path = await self._ensure_local_image(clothes_image)
            
            if not person_image_path or not clothes_image_path:
                return {"success": False, "error": "无法获取图片，请提供有效的图片路径或URL"}
            
            # 3. 上传人物图片
            logger.info(f"上传人物图片: {person_image_path}")
            person_upload_id = f"{uuid.uuid4().hex[:10]}"
            person_result = await self._upload_image(person_image_path, person_upload_id)
            if not person_result.get("success"):
                return {"success": False, "error": f"上传人物图片失败: {person_result.get('error', '未知错误')}"}
            
            person_image_id = person_result.get("image_id", "")
            logger.info(f"人物图片上传成功，ID: {person_image_id}")
            
            # 4. 上传衣服图片
            logger.info(f"上传衣服图片: {clothes_image_path}")
            clothes_upload_id = f"{uuid.uuid4().hex[:10]}"
            clothes_result = await self._upload_image(clothes_image_path, clothes_upload_id)
            if not clothes_result.get("success"):
                return {"success": False, "error": f"上传衣服图片失败: {clothes_result.get('error', '未知错误')}"}
            
            clothes_image_id = clothes_result.get("image_id", "")
            logger.info(f"衣服图片上传成功，ID: {clothes_image_id}")
            
            # 5. 提交合成任务
            logger.info(f"提交换衣合成任务...")
            task_result = await self._submit_task(person_image_id, clothes_image_id)
            if not task_result.get("success"):
                return {"success": False, "error": f"提交换衣任务失败: {task_result.get('error', '未知错误')}"}
            
            session_hash = task_result.get("session_hash", "")
            logger.info(f"换衣任务提交成功，会话ID: {session_hash}")
            
            # 6. 等待并获取结果
            logger.info(f"等待换衣结果...")
            result = await self._wait_for_result(session_hash)
            if not result.get("success"):
                return {"success": False, "error": f"获取换衣结果失败: {result.get('error', '未知错误')}"}
            
            # 7. 下载结果图片（如果有URL）
            result_url = result.get("image_url", "")
            if result_url:
                local_path = await self._download_image(result_url, "tryon_result")
                if local_path:
                    result["local_path"] = local_path
            
            return result
            
        except Exception as e:
            logger.exception(f"虚拟试衣过程中出错: {e}")
            return {"success": False, "error": f"执行虚拟试衣失败: {str(e)}"}
    
    async def _get_studio_token(self) -> Optional[str]:
        """获取Studio Token
        
        Returns:
            Optional[str]: 成功返回token，失败返回None
        """
        try:
            # 检查ModelScope Studio状态
            status_url = "https://www.modelscope.cn/api/v1/studio/Kwai-Kolors/Kolors-Virtual-Try-On/status"
            
            async with aiohttp.ClientSession() as session:
                # 构建请求头
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Origin": "https://www.modelscope.cn",
                    "Referer": "https://www.modelscope.cn/studios/Kwai-Kolors/Kolors-Virtual-Try-On"
                }
                
                if self.modelscope_csrf_token:
                    headers["x-csrf-token"] = self.modelscope_csrf_token
                
                cookies = {}
                if self.modelscope_cookies:
                    # 简单解析cookie字符串转成字典
                    cookie_parts = self.modelscope_cookies.split(';')
                    for part in cookie_parts:
                        if '=' in part:
                            name, value = part.strip().split('=', 1)
                            cookies[name] = value
                
                # 检查状态
                async with session.get(status_url, headers=headers, cookies=cookies) as response:
                    if response.status != 200:
                        logger.error(f"获取ModelScope Studio状态失败，状态码: {response.status}")
                        return None
                    
                    status_data = await response.json()
                    if not status_data.get("Success"):
                        logger.error(f"ModelScope Studio状态异常: {status_data}")
                        return None
                
                # 访问Studio页面获取token
                studio_url = f"{self.api_base}/?t={int(time.time() * 1000)}"
                async with session.get(studio_url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"访问AI试衣Studio失败，状态码: {response.status}")
                        return None
                    
                    # 从响应头中提取studio_token
                    cookies_list = response.headers.getall('Set-Cookie', [])
                    for cookie in cookies_list:
                        if 'studio_token=' in cookie:
                            match = re.search(r'studio_token=([^;]+)', cookie)
                            if match:
                                return match.group(1)
            
            logger.error("无法从响应中提取studio_token")
            return None
            
        except Exception as e:
            logger.exception(f"获取Studio Token异常: {e}")
            return None
    
    async def _ensure_local_image(self, image_path_or_url: str) -> Optional[str]:
        """确保图片在本地可访问
        
        Args:
            image_path_or_url: 图片路径或URL
            
        Returns:
            Optional[str]: 本地图片路径，失败返回None
        """
        try:
            # 检查是否是URL
            if image_path_or_url.startswith(('http://', 'https://')):
                # 下载图片
                return await self._download_image(image_path_or_url)
            
            # 检查本地路径是否存在
            if os.path.exists(image_path_or_url) and os.path.isfile(image_path_or_url):
                return image_path_or_url
            
            logger.error(f"图片不存在或无效: {image_path_or_url}")
            return None
            
        except Exception as e:
            logger.exception(f"处理图片路径异常: {e}")
            return None
    
    async def _download_image(self, image_url: str, prefix: str = "image") -> Optional[str]:
        """下载图片并保存到本地
        
        Args:
            image_url: 图片URL
            prefix: 文件名前缀
            
        Returns:
            Optional[str]: 本地图片路径，失败返回None
        """
        try:
            # 创建唯一的文件名
            filename = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
            local_path = os.path.join(self.temp_dir, filename)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        logger.error(f"下载图片失败，状态码: {response.status}")
                        return None
                    
                    # 读取图片内容并保存
                    image_data = await response.read()
                    with open(local_path, "wb") as f:
                        f.write(image_data)
                    
                    logger.info(f"图片已下载并保存到: {local_path}")
                    return local_path
                    
        except Exception as e:
            logger.exception(f"下载图片异常: {e}")
            return None
    
    async def _upload_image(self, image_path: str, upload_id: str) -> Dict[str, Any]:
        """上传图片到服务器
        
        Args:
            image_path: 本地图片路径
            upload_id: 上传ID
            
        Returns:
            Dict: 上传结果，包含image_id等信息
        """
        try:
            if not self.studio_token:
                return {"success": False, "error": "未获取会话令牌，请先调用_get_studio_token"}
            
            if not os.path.exists(image_path):
                return {"success": False, "error": f"图片文件不存在: {image_path}"}
            
            # 上传图片
            upload_url = f"{self.api_base}/upload?upload_id={upload_id}"
            
            async with aiohttp.ClientSession() as session:
                # 构建请求头
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Origin": self.api_base,
                    "Referer": f"{self.api_base}/?t={int(time.time() * 1000)}&__theme=light&studio_token={self.studio_token}&backend_url=/",
                    "x-studio-token": self.studio_token
                }
                
                # 构建表单数据
                with open(image_path, 'rb') as f:
                    file_data = f.read()
                
                form = aiohttp.FormData()
                form.add_field('file', file_data, filename=os.path.basename(image_path), content_type='image/png')
                
                # 上传图片
                async with session.post(upload_url, headers=headers, data=form) as response:
                    if response.status != 200:
                        logger.error(f"上传图片失败，状态码: {response.status}")
                        return {"success": False, "error": f"上传图片失败，状态码: {response.status}"}
                    
                    # 解析响应
                    response_data = await response.json()
                    if not response_data.get("id"):
                        logger.error(f"上传图片响应异常: {response_data}")
                        return {"success": False, "error": "上传后未返回图片ID"}
                    
                    # 查询上传进度（可选，有些API可能需要）
                    progress_url = f"{self.api_base}/upload_progress?upload_id={upload_id}"
                    async with session.get(progress_url, headers=headers) as progress_response:
                        # 这里主要是为了完成整个流程，实际上不需要处理返回结果
                        pass
                    
                    return {
                        "success": True,
                        "image_id": response_data.get("id"),
                        "name": response_data.get("name", os.path.basename(image_path))
                    }
                    
        except Exception as e:
            logger.exception(f"上传图片异常: {e}")
            return {"success": False, "error": f"上传图片异常: {str(e)}"}
    
    async def _submit_task(self, person_image_id: str, clothes_image_id: str) -> Dict[str, Any]:
        """提交换衣任务
        
        Args:
            person_image_id: 人物图片ID
            clothes_image_id: 衣服图片ID
            
        Returns:
            Dict: 任务提交结果
        """
        try:
            if not self.studio_token:
                return {"success": False, "error": "未获取会话令牌，请先调用_get_studio_token"}
            
            # 构建任务提交URL
            current_time = int(time.time() * 1000)
            queue_url = f"{self.api_base}/queue/join?t={current_time}&__theme=light&studio_token={self.studio_token}&backend_url=%2F"
            
            async with aiohttp.ClientSession() as session:
                # 构建请求头
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Origin": self.api_base,
                    "Referer": f"{self.api_base}/?t={current_time}&__theme=light&studio_token={self.studio_token}&backend_url=/",
                    "x-studio-token": self.studio_token
                }
                
                # 构建任务数据
                task_data = {
                    "fn_index": 0,
                    "data": [
                        person_image_id,  # 人物图片ID
                        clothes_image_id, # 衣服图片ID
                        None,            # 可选参数，预留位置
                        False,           # remove_background，是否移除背景
                        False,           # preserve_skin，是否保留皮肤
                        "default"        # 处理模式: "default", "high_quality" 等
                    ],
                    "session_hash": f"{uuid.uuid4().hex[:10]}"
                }
                
                # 提交任务
                async with session.post(queue_url, headers=headers, json=task_data) as response:
                    if response.status != 200:
                        logger.error(f"提交换衣任务失败，状态码: {response.status}")
                        return {"success": False, "error": f"提交换衣任务失败，状态码: {response.status}"}
                    
                    # 解析响应
                    response_data = await response.json()
                    if not response_data.get("success"):
                        logger.error(f"提交换衣任务响应异常: {response_data}")
                        return {"success": False, "error": "提交任务失败，服务端返回错误"}
                    
                    return {
                        "success": True,
                        "session_hash": task_data["session_hash"],
                        "eta": response_data.get("eta", 0),
                        "queue_position": response_data.get("queue_position", 0)
                    }
                    
        except Exception as e:
            logger.exception(f"提交换衣任务异常: {e}")
            return {"success": False, "error": f"提交换衣任务异常: {str(e)}"}
    
    async def _wait_for_result(self, session_hash: str) -> Dict[str, Any]:
        """等待并获取换衣结果
        
        Args:
            session_hash: 会话哈希值
            
        Returns:
            Dict: 处理结果，包含生成图像URL等信息
        """
        try:
            if not self.studio_token:
                return {"success": False, "error": "未获取会话令牌，请先调用_get_studio_token"}
            
            # 构建结果查询URL
            queue_data_url = f"{self.api_base}/queue/data?session_hash={session_hash}&studio_token={self.studio_token}"
            
            async with aiohttp.ClientSession() as session:
                # 构建请求头
                headers = {
                    "Accept": "*/*",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": f"{self.api_base}/?t={int(time.time() * 1000)}&__theme=light&studio_token={self.studio_token}&backend_url=/",
                    "x-studio-token": self.studio_token
                }
                
                # 使用超时保护
                start_time = time.time()
                
                # 轮询查询处理状态和结果
                while time.time() - start_time < self.max_wait_time:
                    async with session.get(queue_data_url, headers=headers) as response:
                        if response.status != 200:
                            logger.error(f"查询换衣结果失败，状态码: {response.status}")
                            await asyncio.sleep(2)
                            continue
                        
                        # 尝试解析EventStream响应
                        content_type = response.headers.get('Content-Type', '')
                        if 'text/event-stream' in content_type:
                            # 读取SSE事件流
                            async for line in response.content:
                                line_text = line.decode('utf-8').strip()
                                
                                # 解析事件数据
                                if line_text.startswith('data: '):
                                    try:
                                        data_json = json.loads(line_text[6:])
                                        
                                        if data_json.get("msg") == "process_completed":
                                            # 处理完成，提取结果
                                            output_data = data_json.get("output", {})
                                            if isinstance(output_data, dict) and "data" in output_data:
                                                result_data = output_data["data"]
                                                
                                                # 第一个元素通常是结果图片
                                                if len(result_data) > 0 and isinstance(result_data[0], list):
                                                    image_data = result_data[0]
                                                    image_url = None
                                                    
                                                    # 查找图片URL
                                                    for item in image_data:
                                                        if isinstance(item, dict) and "url" in item:
                                                            image_url = item["url"]
                                                            break
                                                    
                                                    if image_url:
                                                        logger.info(f"获取到换衣结果图片URL: {image_url}")
                                                        return {
                                                            "success": True,
                                                            "image_url": image_url,
                                                            "session_hash": session_hash
                                                        }
                                            
                                            logger.error(f"无法解析处理结果: {output_data}")
                                            return {"success": False, "error": "无法从处理结果中获取图片URL"}
                                            
                                        elif data_json.get("msg") == "process_starts":
                                            logger.info(f"换衣处理开始...")
                                            
                                        elif data_json.get("msg") == "estimation":
                                            progress = data_json.get("progress", 0)
                                            eta = data_json.get("eta", 0)
                                            logger.info(f"换衣处理进度: {progress:.1f}%, 预计剩余时间: {eta}秒")
                                            
                                        elif data_json.get("msg") == "queue_full":
                                            logger.warning("队列已满，请稍后重试")
                                            return {"success": False, "error": "处理队列已满，请稍后重试"}
                                            
                                        elif data_json.get("msg") == "process_failed":
                                            error = data_json.get("error", "未知错误")
                                            logger.error(f"换衣处理失败: {error}")
                                            return {"success": False, "error": f"换衣处理失败: {error}"}
                                            
                                    except json.JSONDecodeError:
                                        logger.warning(f"解析事件数据失败: {line_text}")
                        else:
                            # 非SSE响应，尝试普通JSON解析
                            response_data = await response.json()
                            logger.warning(f"收到非事件流响应: {response_data}")
                    
                    # 等待一段时间后再次查询
                    await asyncio.sleep(2)
                
                # 超时
                logger.warning(f"等待换衣结果超时，已等待{self.max_wait_time}秒")
                return {"success": False, "error": f"等待换衣结果超时，已等待{self.max_wait_time}秒"}
                
        except Exception as e:
            logger.exception(f"获取换衣结果异常: {e}")
            return {"success": False, "error": f"获取换衣结果异常: {str(e)}"}
    
    async def send_generated_image(self, bot, target_id: str, image_url: str) -> bool:
        """将生成的图片发送给用户
        
        Args:
            bot: 微信API客户端实例
            target_id: 发送目标ID
            image_url: 图片URL
            
        Returns:
            bool: 发送成功返回True，否则返回False
        """
        try:
            # 下载图片
            local_path = await self._download_image(image_url, "tryon_result")
            if not local_path:
                logger.error(f"无法下载虚拟试衣结果图片: {image_url}")
                return False
            
            # 发送图片
            logger.info(f"发送虚拟试衣结果图片: {local_path}")
            with open(local_path, "rb") as img_file:
                image_data = img_file.read()
                await bot.send_image(target_id, image_data)
            
            return True
            
        except Exception as e:
            logger.exception(f"发送虚拟试衣结果图片异常: {e}")
            return False 