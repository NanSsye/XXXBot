import asyncio
import json
import re
import tomllib
import traceback
from typing import List, Optional, Union

import aiohttp
import filetype
from loguru import logger
import random
import binascii

from WechatAPI import WechatAPIClient
from database.XYBotDB import XYBotDB
from utils.decorators import *
from utils.plugin_base import PluginBase
import os
import base64
import asyncio
import shutil
import subprocess  # 导入 subprocess 模块


class VideoSender(PluginBase):
    """
    一个点击链接获取视频并发送给用户的插件，支持多个视频源。
    """

    description = "点击链接获取视频并发送给用户的插件，支持多个视频源"
    author = "老夏的金库"
    version = "1.1.0"

    def __init__(self):
        super().__init__()
        # 确保 self.ffmpeg_path 始终有值
        self.ffmpeg_path = "/usr/bin/ffmpeg"  # 设置默认值
        try:
            with open("plugins/VideoSender/config.toml", "rb") as f:
                plugin_config = tomllib.load(f)
            config = plugin_config["VideoSender"]
            self.enable = config["enable"]
            self.commands = config["commands"]
            self.ffmpeg_path = config.get("ffmpeg_path", "/usr/bin/ffmpeg")  # ffmpeg 路径
            self.video_sources = config.get("video_sources", [])  # 视频源列表

            logger.info("VideoSender 插件配置加载成功")
        except FileNotFoundError:
            logger.error("VideoSender 插件配置文件未找到，插件已禁用。")
            self.enable = False
            self.commands = ["发送视频", "来个视频"]
            self.video_sources = []
        except Exception as e:
            logger.exception(f"VideoSender 插件初始化失败: {e}")
            self.enable = False
            self.commands = ["发送视频", "来个视频"]
            self.video_sources = []

        self.ffmpeg_available = self._check_ffmpeg()  # 在配置加载完成后检查 ffmpeg

    def _check_ffmpeg(self) -> bool:
        """检查 ffmpeg 是否可用"""
        try:
            process = subprocess.run([self.ffmpeg_path, "-version"], check=False, capture_output=True)
            if process.returncode == 0:
                logger.info(f"ffmpeg 可用，版本信息：{process.stdout.decode()}")
                return True
            else:
                logger.warning(f"ffmpeg 执行失败，返回码: {process.returncode}，错误信息: {process.stderr.decode()}")
                return False
        except FileNotFoundError:
            logger.warning(f"ffmpeg 未找到，路径: {self.ffmpeg_path}")
            return False
        except Exception as e:
            logger.exception(f"检查 ffmpeg 失败: {e}")
            return False

    async def _get_video_url(self, source_name: str = "") -> str:
        """
        根据视频源名称获取视频URL。

        Args:
            source_name (str, optional): 视频源名称. Defaults to "".

        Returns:
            str: 视频URL.
        """
        if not self.video_sources:
            logger.error("没有配置视频源")
            return ""

        if source_name:
            for source in self.video_sources:
                if source["name"] == source_name:
                    url = f"{source['url']}?type=json"  # 确保请求类型为 JSON
                    break
            else:
                logger.info(f"未找到{source_name}，随机选择视频源")
                url = f"{random.choice(self.video_sources)['url']}?type=json"
        else:
            source = random.choice(self.video_sources)
            url = f"{source['url']}?type=json"
            logger.info(f"随机使用视频源: {source['name']}")

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
                }
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        json_response = await response.json()  # 解析 JSON 响应
                        video_url = json_response.get("data")  # 提取视频 URL
                        logger.info(f"获取到视频链接")
                        return video_url
                    else:
                        logger.error(f"获取视频失败，状态码: {response.status}")
                        return ""
        except Exception as e:
            logger.exception(f"获取视频过程中发生异常: {e}")
            return ""

    async def _download_video(self, video_url: str) -> bytes:
        """下载视频文件"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(video_url) as response:
                    if response.status == 200:
                        video_data = await response.read()
                        # 降低日志级别为DEBUG
                        logger.debug(f"视频下载完成: {len(video_data) // 1024} KB")
                        return video_data
                    else:
                        logger.error(f"下载视频失败，状态码: {response.status}")
                        return b""  # 返回空字节
        except Exception as e:
            logger.exception(f"下载视频失败: {e}")
            return b""  # 返回空字节

    async def _fix_video_duration(self, video_data: bytes) -> bytes:
        """修复视频时长问题"""
        temp_dir = "temp_videos"
        os.makedirs(temp_dir, exist_ok=True)
        input_path = os.path.join(temp_dir, "input_video.mp4")
        output_path = os.path.join(temp_dir, "fixed_video.mp4")
        
        try:
            # 保存输入视频
            with open(input_path, "wb") as f:
                f.write(video_data)
                
            # 使用ffmpeg修复视频时长
            if self.ffmpeg_available:
                # 先获取视频信息
                info_process = await asyncio.create_subprocess_exec(
                    self.ffmpeg_path, "-i", input_path, 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                _, stderr = await info_process.communicate()
                stderr_str = stderr.decode()
                
                # 从ffmpeg输出中提取时长信息
                duration_match = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", stderr_str)
                if duration_match:
                    hours = int(duration_match.group(1))
                    minutes = int(duration_match.group(2))
                    seconds = int(duration_match.group(3))
                    milliseconds = int(duration_match.group(4))
                    
                    # 计算总秒数
                    total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 100
                    
                    logger.info(f"处理视频：时长{total_seconds}秒")
                    
                    # 将秒数除以1000，微信播放器会将毫秒当做秒显示
                    adjusted_seconds = total_seconds / 1000
                    
                    # 使用ffmpeg处理视频，设置调整后的时长元数据
                    process = await asyncio.create_subprocess_exec(
                        self.ffmpeg_path,
                        "-i", input_path,
                        "-c", "copy",  # 复制所有流，不重新编码
                        "-metadata:s:v", f"duration={adjusted_seconds}",  # 设置视频流的时长
                        "-metadata", f"duration={adjusted_seconds}",  # 设置全局时长
                        output_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                else:
                    logger.warning("无法提取时长信息，使用默认处理")
                    # 使用默认处理方法
                    process = await asyncio.create_subprocess_exec(
                        self.ffmpeg_path,
                        "-i", input_path,
                        "-c", "copy",  # 复制所有流，不重新编码
                        output_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    logger.error(f"修复视频时长失败")
                    return video_data  # 如果修复失败，返回原始视频数据
                
                # 读取修复后的视频
                with open(output_path, "rb") as f:
                    fixed_video_data = f.read()
                    
                logger.debug("视频时长处理完成")
                return fixed_video_data
            else:
                logger.warning("ffmpeg不可用，无法处理视频时长")
                return video_data
        except Exception as e:
            logger.exception(f"处理视频时长失败: {e}")
            return video_data  # 发生异常时返回原始视频数据
        finally:
            # 清理临时文件
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")

    async def _extract_thumbnail_from_video(self, video_data: bytes) -> Optional[str]:
        """从视频数据中提取缩略图"""
        temp_dir = "temp_videos"  # 创建临时文件夹
        os.makedirs(temp_dir, exist_ok=True)
        video_path = os.path.join(temp_dir, "temp_video.mp4")
        thumbnail_path = os.path.join(temp_dir, "temp_thumbnail.jpg")

        try:
            with open(video_path, "wb") as f:
                f.write(video_data)

            # 异步执行 ffmpeg 命令
            process = await asyncio.create_subprocess_exec(
                self.ffmpeg_path,
                "-i", video_path,
                "-ss", "00:00:01",  # 从视频的第 1 秒开始提取
                "-vframes", "1",
                thumbnail_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"ffmpeg 执行失败")
                return None

            with open(thumbnail_path, "rb") as image_file:
                image_data = image_file.read()
                image_base64 = base64.b64encode(image_data).decode("utf-8")
                return image_base64

        except FileNotFoundError:
            logger.error("ffmpeg 未找到")
            return None
        except Exception as e:
            logger.exception(f"提取缩略图失败: {e}")
            return None
        finally:
            # 清理临时文件
            shutil.rmtree(temp_dir, ignore_errors=True)  # 递归删除临时文件夹

    @on_text_message
    async def handle_text_message(self, bot: WechatAPIClient, message: dict):
        """处理文本消息，判断是否需要触发发送视频。"""
        if not self.enable:
            return True  # 插件未启用，继续执行后续处理

        content = message["Content"].strip()
        chat_id = message["FromWxid"]

        # 处理视频目录命令
        if content == "视频目录":
            source_names = [source["name"] for source in self.video_sources]
            source_list = "\n".join(source_names)
            await bot.send_text_message(chat_id, f"可用的视频系列：\n{source_list}")
            return False  # 返回 False，阻止后续执行
            
        # 处理随机视频命令
        if content == "随机视频":
            source_name = ""  # 空字符串表示随机选择
            logger.info(f"用户请求随机视频")
        else:
            # 检查是否匹配视频源名称
            for source in self.video_sources:
                if content == source["name"]:
                    source_name = source["name"]
                    logger.info(f"用户请求特定视频源: {source_name}")
                    break
            else:
                # 如果不是视频源名称也不是有效命令，继续执行后续处理
                return True

        try:
            video_url = await self._get_video_url(source_name)

            if video_url:
                logger.info(f"获取到视频链接: {video_url}")
                video_data = await self._download_video(video_url)

                if video_data:
                    # 修复视频时长问题
                    if self.ffmpeg_available:
                        logger.info("开始修复视频时长...")
                        video_data = await self._fix_video_duration(video_data)
                        
                    image_base64 = None
                    if self.ffmpeg_available:
                        # 获取缩略图
                        image_base64 = await self._extract_thumbnail_from_video(video_data)

                        if image_base64:
                            logger.info("成功提取缩略图")
                        else:
                            logger.warning("未能成功提取缩略图")
                    else:
                        await bot.send_text_message(chat_id, "由于 ffmpeg 未安装，无法提取缩略图。")

                    try:
                        video_base64 = base64.b64encode(video_data).decode("utf-8")
                        logger.debug(f"视频 Base64 长度: {len(video_base64) if video_base64 else '无效'}")
                        logger.debug(f"图片 Base64 长度: {len(image_base64) if image_base64 else '无效'}")

                        # 发送视频消息
                        await bot.send_video_message(chat_id, video=video_base64, image=image_base64 or "None")
                        logger.info(f"成功发送视频到 {chat_id}")

                    except binascii.Error as e:
                        logger.error(f"Base64 编码失败： {e}")
                        await bot.send_text_message(chat_id, "视频编码失败，请稍后重试。")

                    except Exception as e:
                        logger.exception(f"发送视频过程中发生异常: {e}")
                        await bot.send_text_message(chat_id, f"发送视频过程中发生异常，请稍后重试: {e}")

                else:
                    logger.warning(f"未能下载到有效的视频数据")
                    await bot.send_text_message(chat_id, "未能下载到有效的视频，请稍后重试。")

            else:
                logger.warning(f"未能获取到有效的视频链接")
                await bot.send_text_message(chat_id, "未能获取到有效的视频，请稍后重试。")

        except Exception as e:
            logger.exception(f"处理视频请求时发生异常: {e}")
            await bot.send_text_message(chat_id, f"发生错误，请稍后重试：{str(e)}")

        return False  # 返回 False，阻止后续执行

    async def close(self):
        """插件关闭时执行的操作。"""
        logger.info("VideoSender 插件已关闭")
