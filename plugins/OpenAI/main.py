import io
import json
import re
import subprocess
import tomllib
from typing import Optional, Union, Dict, List, Tuple
import time
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from collections import defaultdict
from enum import Enum
import urllib.parse
import mimetypes
import base64

import aiohttp
import filetype
from loguru import logger
import os
from WechatAPI import WechatAPIClient
from database.XYBotDB import XYBotDB
from utils.decorators import *
from utils.plugin_base import PluginBase
from gtts import gTTS
import traceback
import shutil
from PIL import Image

# 常量定义
XYBOT_PREFIX = "-----老夏的金库-----\n"
OPENAI_ERROR_MESSAGE = "🙅对不起，OpenAI出现错误！\n"
INSUFFICIENT_POINTS_MESSAGE = "😭你的积分不够啦！需要 {price} 积分"
VOICE_TRANSCRIPTION_FAILED = "\n语音转文字失败"
TEXT_TO_VOICE_FAILED = "\n文本转语音失败"
CHAT_TIMEOUT = 3600  # 1小时超时
CHAT_AWAY_TIMEOUT = 1800  # 30分钟自动离开
MESSAGE_BUFFER_TIMEOUT = 10  # 消息缓冲区超时时间（秒）
MAX_BUFFERED_MESSAGES = 10  # 最大缓冲消息数

# 聊天室消息模板
CHAT_JOIN_MESSAGE = """✨ 欢迎来到聊天室！让我们开始愉快的对话吧~

💡 基础指引：
   📝 直接发消息与我对话
   🚪 发送"退出聊天"离开
   ⏰ 5分钟不说话自动暂离
   🔄 30分钟无互动将退出

🎮 聊天指令：
   📊 发送"查看状态"
   📈 发送"聊天室排行"
   👤 发送"我的统计"
   💤 发送"暂时离开"

开始聊天吧！期待与你的精彩对话~ 🌟"""

CHAT_LEAVE_MESSAGE = "👋 已退出聊天室，需要再次@我才能继续对话"
CHAT_TIMEOUT_MESSAGE = "由于您已经1小时没有活动，已被移出聊天室。如需继续对话，请重新发送消息。"
CHAT_AWAY_MESSAGE = "💤 已设置为离开状态，其他人将看到你正在休息"
CHAT_BACK_MESSAGE = "🌟 欢迎回来！已恢复活跃状态"
CHAT_AUTO_AWAY_MESSAGE = "由于您已经30分钟没有活动，已被自动设置为离开状态。"

class UserStatus(Enum):
    ACTIVE = "活跃"
    AWAY = "离开"
    INACTIVE = "未加入"

@dataclass
class UserStats:
    total_messages: int = 0
    total_chars: int = 0
    join_count: int = 0
    last_active: float = 0
    total_active_time: float = 0
    status: UserStatus = UserStatus.INACTIVE

@dataclass
class ChatRoomUser:
    wxid: str
    group_id: str
    last_active: float
    status: UserStatus = UserStatus.ACTIVE
    stats: UserStats = field(default_factory=UserStats)
    
@dataclass
class MessageBuffer:
    messages: list[str] = field(default_factory=list)
    last_message_time: float = 0.0
    timer_task: Optional[asyncio.Task] = None
    message_count: int = 0
    files: list[str] = field(default_factory=list)

class ChatRoomManager:
    def __init__(self):
        self.active_users = {}
        self.message_buffers = defaultdict(lambda: MessageBuffer([], 0.0, None))
        self.user_stats: Dict[tuple[str, str], UserStats] = defaultdict(UserStats)
        
    def add_user(self, group_id: str, user_wxid: str) -> None:
        key = (group_id, user_wxid)
        self.active_users[key] = ChatRoomUser(
            wxid=user_wxid,
            group_id=group_id,
            last_active=time.time()
        )
        stats = self.user_stats[key]
        stats.join_count += 1
        stats.last_active = time.time()
        stats.status = UserStatus.ACTIVE
        
    def remove_user(self, group_id: str, user_wxid: str) -> None:
        key = (group_id, user_wxid)
        if key in self.active_users:
            user = self.active_users[key]
            stats = self.user_stats[key]
            stats.total_active_time += time.time() - stats.last_active
            stats.status = UserStatus.INACTIVE
            del self.active_users[key]
        if key in self.message_buffers:
            buffer = self.message_buffers[key]
            if buffer.timer_task and not buffer.timer_task.done():
                buffer.timer_task.cancel()
            del self.message_buffers[key]
            
    def update_user_activity(self, group_id: str, user_wxid: str) -> None:
        key = (group_id, user_wxid)
        if key in self.active_users:
            self.active_users[key].last_active = time.time()
            stats = self.user_stats[key]
            stats.total_messages += 1
            stats.last_active = time.time()
            
    def set_user_status(self, group_id: str, user_wxid: str, status: UserStatus) -> None:
        key = (group_id, user_wxid)
        if key in self.active_users:
            self.active_users[key].status = status
            self.user_stats[key].status = status
            
    def get_user_status(self, group_id: str, user_wxid: str) -> UserStatus:
        key = (group_id, user_wxid)
        if key in self.active_users:
            return self.active_users[key].status
        return UserStatus.INACTIVE
        
    def get_user_stats(self, group_id: str, user_wxid: str) -> UserStats:
        return self.user_stats[(group_id, user_wxid)]
        
    def get_room_stats(self, group_id: str) -> List[tuple[str, UserStats]]:
        stats = []
        for (g_id, wxid), user_stats in self.user_stats.items():
            if g_id == group_id:
                stats.append((wxid, user_stats))
        return sorted(stats, key=lambda x: x[1].total_messages, reverse=True)
        
    def get_active_users_count(self, group_id: str) -> tuple[int, int, int]:
        active = 0
        away = 0
        total = 0
        for (g_id, _), user in self.active_users.items():
            if g_id == group_id:
                total += 1
                if user.status == UserStatus.ACTIVE:
                    active += 1
                elif user.status == UserStatus.AWAY:
                    away += 1
        return active, away, total

    async def add_message_to_buffer(self, group_id: str, user_wxid: str, message: str, files: list[str] = None) -> None:
        """添加消息到缓冲区"""
        if files is None:
            files = []
        
        key = (group_id, user_wxid)
        if key not in self.message_buffers:
            self.message_buffers[key] = MessageBuffer()
        
        buffer = self.message_buffers[key]
        buffer.messages.append(message)
        buffer.last_message_time = time.time()
        buffer.message_count += 1
        buffer.files.extend(files)  # 添加文件ID到缓冲区
        
        logger.debug(f"成功添加消息到缓冲区 - 用户: {user_wxid}, 消息: {message}, 当前消息数: {buffer.message_count}, 文件: {files}")

    def get_and_clear_buffer(self, group_id: str, user_wxid: str) -> Tuple[str, list[str]]:
        """获取并清空缓冲区"""
        key = (group_id, user_wxid)
        buffer = self.message_buffers.get(key)
        if buffer:
            messages = "\n".join(buffer.messages)
            files = buffer.files.copy()  # 复制文件ID列表
            logger.debug(f"合并并清空缓冲区 - 用户: {user_wxid}, 合并消息: {messages}, 文件: {files}")
            buffer.messages.clear()
            buffer.message_count = 0
            buffer.files.clear()  # 清空文件ID列表
            return messages, files
        return "", []

    def is_user_active(self, group_id: str, user_wxid: str) -> bool:
        key = (group_id, user_wxid)
        if key not in self.active_users:
            return False
        
        user = self.active_users[key]
        if time.time() - user.last_active > CHAT_TIMEOUT:
            self.remove_user(group_id, user_wxid)
            return False
        return True
        
    def check_and_remove_inactive_users(self) -> list[tuple[str, str]]:
        current_time = time.time()
        inactive_users = []
        
        for (group_id, user_wxid), user in list(self.active_users.items()):
            if user.status == UserStatus.ACTIVE and current_time - user.last_active > CHAT_AWAY_TIMEOUT:
                self.set_user_status(group_id, user_wxid, UserStatus.AWAY)
                inactive_users.append((group_id, user_wxid, "away"))
            elif current_time - user.last_active > CHAT_TIMEOUT:
                inactive_users.append((group_id, user_wxid, "timeout"))
                self.remove_user(group_id, user_wxid)
                
        return inactive_users

    def format_user_stats(self, group_id: str, user_wxid: str, nickname: str = "未知用户") -> str:
        stats = self.get_user_stats(group_id, user_wxid)
        status = self.get_user_status(group_id, user_wxid)
        active_time = int(stats.total_active_time / 60)
        return f"""📊 {nickname} 的聊天室数据：

🏷️ 当前状态：{status.value}
💬 发送消息：{stats.total_messages} 条
📝 总字数：{stats.total_chars} 字
🔄 加入次数：{stats.join_count} 次
⏱️ 活跃时间：{active_time} 分钟"""

    def format_room_status(self, group_id: str) -> str:
        active, away, total = self.get_active_users_count(group_id)
        return f"""🏠 聊天室状态：

👥 当前成员：{total} 人
✨ 活跃成员：{active} 人
💤 暂离成员：{away} 人"""

    async def format_room_ranking(self, group_id: str, bot: WechatAPIClient, limit: int = 5) -> str:
        stats = self.get_room_stats(group_id)
        result = ["🏆 聊天室排行榜：\n"]
        
        for i, (wxid, user_stats) in enumerate(stats[:limit], 1):
            try:
                nickname = await bot.get_nickname(wxid) or "未知用户"
            except:
                nickname = "未知用户"
            result.append(f"{self._get_rank_emoji(i)} {nickname}")
            result.append(f"   💬 {user_stats.total_messages}条消息")
            result.append(f"   📝 {user_stats.total_chars}字")
        return "\n".join(result)

    @staticmethod
    def _get_rank_emoji(rank: int) -> str:
        if rank == 1:
            return "🥇"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        return f"{rank}."

@dataclass
class ModelConfig:
    api_key: str
    base_url: str
    model: str
    trigger_words: list[str]
    price: int
    wakeup_words: list[str] = field(default_factory=list)

class OpenAI(PluginBase):
    description = "OpenAI插件"
    author = "老夏的金库"
    version = "1.0.0"

    def __init__(self):
        super().__init__()
        self.chat_manager = ChatRoomManager()
        self.user_models = {}  # 存储用户当前使用的模型
        try:
            with open("main_config.toml", "rb") as f:
                config = tomllib.load(f)
            self.admins = config["XYBot"]["admins"]
        except (FileNotFoundError, tomllib.TOMLDecodeError) as e:
            logger.error(f"加载主配置文件失败: {e}")
            raise

        try:
            with open("plugins/OpenAI/config.toml", "rb") as f:
                config = tomllib.load(f)
            plugin_config = config["OpenAI"]
            self.enable = plugin_config["enable"]
            self.default_model = plugin_config["default-model"]
            self.command_tip = plugin_config["command-tip"]
            self.commands = plugin_config["commands"]
            self.admin_ignore = plugin_config["admin_ignore"]
            self.whitelist_ignore = plugin_config["whitelist_ignore"]
            self.http_proxy = plugin_config["http-proxy"]
            self.voice_reply_all = plugin_config["voice_reply_all"]
            self.robot_names = plugin_config.get("robot-names", [])
            self.remember_user_model = plugin_config.get("remember_user_model", True)
            self.chatroom_enable = plugin_config.get("chatroom_enable", True)

            # 加载所有模型配置
            self.models = {}
            for model_name, model_config in plugin_config.get("models", {}).items():
                self.models[model_name] = ModelConfig(
                    api_key=model_config["api-key"],
                    base_url=model_config["base-url"],
                    model=model_config["model"],
                    trigger_words=model_config["trigger-words"],
                    price=model_config["price"],
                    wakeup_words=model_config.get("wakeup-words", [])
                )
            
            # 设置当前使用的模型
            self.current_model = self.models[self.default_model]
        except (FileNotFoundError, tomllib.TOMLDecodeError) as e:
            logger.error(f"加载OpenAI插件配置文件失败: {e}")
            raise

        self.db = XYBotDB()
        self.image_cache = {}
        self.image_cache_timeout = 60
        # 添加文件存储目录配置
        self.files_dir = "files"
        # 创建文件存储目录
        os.makedirs(self.files_dir, exist_ok=True)

        # 创建唤醒词到模型的映射
        self.wakeup_word_to_model = {}
        logger.info("开始加载唤醒词配置:")
        for model_name, model_config in self.models.items():
            logger.info(f"处理模型 '{model_name}' 的唤醒词列表: {model_config.wakeup_words}")
            for wakeup_word in model_config.wakeup_words:
                if wakeup_word in self.wakeup_word_to_model:
                    old_model = next((name for name, config in self.models.items() 
                                     if config == self.wakeup_word_to_model[wakeup_word]), '未知')
                    logger.warning(f"唤醒词冲突! '{wakeup_word}' 已绑定到模型 '{old_model}'，"
                                  f"现在被覆盖绑定到 '{model_name}'")
                self.wakeup_word_to_model[wakeup_word] = model_config
                logger.info(f"唤醒词 '{wakeup_word}' 成功绑定到模型 '{model_name}'")
        
        logger.info(f"唤醒词映射完成，共加载 {len(self.wakeup_word_to_model)} 个唤醒词")

    def get_user_model(self, user_id: str) -> ModelConfig:
        """获取用户当前使用的模型"""
        if self.remember_user_model and user_id in self.user_models:
            return self.user_models[user_id]
        return self.current_model

    def set_user_model(self, user_id: str, model: ModelConfig):
        """设置用户当前使用的模型"""
        if self.remember_user_model:
            self.user_models[user_id] = model

    def get_model_from_message(self, content: str, user_id: str) -> tuple[ModelConfig, str, bool]:
        """根据消息内容判断使用哪个模型，并返回是否是切换模型的命令"""
        original_content = content  # 保留原始内容
        content = content.lower()  # 只在检测时使用小写版本
        
        # 检查是否是切换模型的命令
        if content.endswith("切换"):
            for model_name, model_config in self.models.items():
                for trigger in model_config.trigger_words:
                    if content.startswith(trigger.lower()):
                        self.set_user_model(user_id, model_config)
                        logger.info(f"用户 {user_id} 切换模型到 {model_name}")
                        return model_config, "", True
            return self.get_user_model(user_id), original_content, False

        # 检查是否使用了唤醒词
        logger.debug(f"检查消息 '{content}' 是否包含唤醒词")
        for wakeup_word, model_config in self.wakeup_word_to_model.items():
            wakeup_lower = wakeup_word.lower()
            content_lower = content.lower()
            if content_lower.startswith(wakeup_lower) or f" {wakeup_lower}" in content_lower:
                model_name = next((name for name, config in self.models.items() if config == model_config), '未知')
                logger.info(f"消息中检测到唤醒词 '{wakeup_word}'，临时使用模型 '{model_name}'")
                
                # 更精确地替换唤醒词
                # 先找到原文中唤醒词的实际位置和形式
                original_wakeup = None
                if content_lower.startswith(wakeup_lower):
                    # 如果以唤醒词开头，直接取对应长度的原始文本
                    original_wakeup = original_content[:len(wakeup_lower)]
                else:
                    # 如果唤醒词在中间，找到它的位置并获取原始形式
                    wakeup_pos = content_lower.find(f" {wakeup_lower}") + 1  # +1 是因为包含了前面的空格
                    if wakeup_pos > 0:
                        original_wakeup = original_content[wakeup_pos:wakeup_pos+len(wakeup_lower)]
                
                if original_wakeup:
                    # 使用原始形式进行替换，保留大小写
                    query = original_content.replace(original_wakeup, "", 1).strip()
                    logger.debug(f"唤醒词处理后的查询: '{query}'")
                    return model_config, query, False
        
        # 检查是否是临时使用其他模型
        for model_name, model_config in self.models.items():
            for trigger in model_config.trigger_words:
                if trigger.lower() in content:
                    logger.info(f"消息中包含触发词 '{trigger}'，临时使用模型 '{model_name}'")
                    query = original_content.replace(trigger, "", 1).strip()  # 使用原始内容替换原始触发词
                    return model_config, query, False

        # 使用用户当前的模型
        current_model = self.get_user_model(user_id)
        model_name = next((name for name, config in self.models.items() if config == current_model), '默认')
        logger.debug(f"未检测到特定模型指示，使用用户 {user_id} 当前默认模型 '{model_name}'")
        return current_model, original_content, False 

    async def check_and_notify_inactive_users(self, bot: WechatAPIClient):
        # 如果聊天室功能关闭，则直接返回，不进行检查和提醒
        if not self.chatroom_enable:
            return
        
        inactive_users = self.chat_manager.check_and_remove_inactive_users()
        for group_id, user_wxid, status in inactive_users:
            if status == "away":
                await bot.send_at_message(group_id, "\n" + CHAT_AUTO_AWAY_MESSAGE, [user_wxid])
            elif status == "timeout":
                await bot.send_at_message(group_id, "\n" + CHAT_TIMEOUT_MESSAGE, [user_wxid])

    async def process_buffered_messages(self, bot: WechatAPIClient, group_id: str, user_wxid: str):
        logger.debug(f"开始处理缓冲消息 - 用户: {user_wxid}, 群组: {group_id}")
        messages, files = self.chat_manager.get_and_clear_buffer(group_id, user_wxid)
        logger.debug(f"从缓冲区获取到的消息: {messages}")
        logger.debug(f"从缓冲区获取到的文件: {files}")
        
        if messages is not None and messages.strip():
            logger.debug(f"合并后的消息: {messages}")
            message = {
                "FromWxid": group_id,
                "SenderWxid": user_wxid,
                "Content": messages,
                "IsGroup": True,
                "MsgType": 1
            }
            logger.debug(f"准备检查积分")
            if await self._check_point(bot, message):
                logger.debug("积分检查通过，开始调用 OpenAI API")
                try:
                    # 检查是否有唤醒词或触发词
                    model, processed_query, is_switch = self.get_model_from_message(messages, user_wxid)
                    await self.openai(bot, message, processed_query, files=files, specific_model=model)
                    logger.debug("成功调用 OpenAI API 并发送消息")
                except Exception as e:
                    logger.error(f"调用 OpenAI API 失败: {e}")
                    logger.error(traceback.format_exc())
                    await bot.send_at_message(group_id, "\n消息处理失败，请稍后重试。", [user_wxid])
        else:
            logger.debug("缓冲区为空或消息无效，无需处理")

    async def _delayed_message_processing(self, bot: WechatAPIClient, group_id: str, user_wxid: str):
        key = (group_id, user_wxid)
        try:
            logger.debug(f"开始延迟处理 - 用户: {user_wxid}, 群组: {group_id}")
            await asyncio.sleep(MESSAGE_BUFFER_TIMEOUT)
            
            buffer = self.chat_manager.message_buffers.get(key)
            if buffer and buffer.messages:
                logger.debug(f"缓冲区消息数: {len(buffer.messages)}")
                logger.debug(f"最后消息时间: {time.time() - buffer.last_message_time:.2f}秒前")
                
                if time.time() - buffer.last_message_time >= MESSAGE_BUFFER_TIMEOUT:
                    logger.debug("开始处理缓冲消息")
                    await self.process_buffered_messages(bot, group_id, user_wxid)
                else:
                    logger.debug("跳过处理 - 有新消息，重新调度")
                    await self.schedule_message_processing(bot, group_id, user_wxid)
        except asyncio.CancelledError:
            logger.debug(f"定时器被取消 - 用户: {user_wxid}, 群组: {group_id}")
        except Exception as e:
            logger.error(f"处理消息缓冲区时出错: {e}")
            await bot.send_at_message(group_id, "\n消息处理发生错误，请稍后重试。", [user_wxid])

    async def schedule_message_processing(self, bot: WechatAPIClient, group_id: str, user_wxid: str):
        key = (group_id, user_wxid)
        if key not in self.chat_manager.message_buffers:
            self.chat_manager.message_buffers[key] = MessageBuffer()
        
        buffer = self.chat_manager.message_buffers[key]
        logger.debug(f"安排消息处理 - 用户: {user_wxid}, 群组: {group_id}")
        
        # 获取buffer中的消息内容
        buffer_content = "\n".join(buffer.messages) if buffer.messages else ""
        
        # 检查是否有最近的图片
        image_content = await self.get_cached_image(group_id)
        if image_content:
            try:
                logger.debug("发现最近的图片，准备上传到 OpenAI")
                # 先检查是否有唤醒词获取对应模型
                wakeup_model = None
                for wakeup_word, model_config in self.wakeup_word_to_model.items():
                    wakeup_lower = wakeup_word.lower()
                    buffer_content_lower = buffer_content.lower()
                    if buffer_content_lower.startswith(wakeup_lower) or f" {wakeup_lower}" in buffer_content_lower:
                        wakeup_model = model_config
                        break
                
                # 如果没有找到唤醒词对应的模型，则使用用户当前的模型
                model_config = wakeup_model or self.get_user_model(user_wxid)
                
                file_path = os.path.join(self.files_dir, f"{time.time()}.jpg")
                with open(file_path, 'wb') as f:
                    f.write(image_content)
                buffer.files.append(file_path)
                logger.debug(f"图片已保存到: {file_path}")
            except Exception as e:
                logger.error(f"处理图片失败: {e}")
        
        if buffer.message_count >= MAX_BUFFERED_MESSAGES:
            logger.debug("缓冲区已满，立即处理消息")
            await self.process_buffered_messages(bot, group_id, user_wxid)
            return
            
        if buffer.timer_task and not buffer.timer_task.done():
            logger.debug("取消已有定时器")
            buffer.timer_task.cancel()
        
        logger.debug("创建新定时器")
        buffer.timer_task = asyncio.create_task(
            self._delayed_message_processing(bot, group_id, user_wxid)
        )
        logger.debug(f"定时器任务已创建 - 用户: {user_wxid}")

    async def openai(self, bot: WechatAPIClient, message: dict, query: str, files=None, specific_model=None):
        """发送消息到OpenAI API"""
        if files is None:
            files = []

        # 如果提供了specific_model，直接使用；否则根据消息内容选择模型
        if specific_model:
            model = specific_model
            processed_query = query
            is_switch = False
            model_name = next((name for name, config in self.models.items() if config == model), '未知')
            logger.info(f"使用指定的模型 '{model_name}'")
        else:
            # 根据消息内容选择模型
            model, processed_query, is_switch = self.get_model_from_message(query, message["SenderWxid"])
            model_name = next((name for name, config in self.models.items() if config == model), '默认')
            logger.info(f"从消息内容选择模型 '{model_name}'")
            
            # 如果是切换模型的命令
            if is_switch:
                model_name = next(name for name, config in self.models.items() if config == model)
                await bot.send_text_message(
                    message["FromWxid"], 
                    f"已切换到{model_name.upper()}模型，将一直使用该模型直到下次切换。"
                )
                return

        # 记录将要使用的模型配置
        logger.info(f"模型API密钥: {model.api_key[:5]}...{model.api_key[-5:] if len(model.api_key) > 10 else ''}")
        logger.info(f"模型API端点: {model.base_url}")
        logger.info(f"使用模型: {model.model}")
        
        try:
            logger.debug(f"开始调用 OpenAI API - 用户消息: {processed_query}")
            
            # 获取历史对话
            conversation_id = self.db.get_llm_thread_id(message["FromWxid"], namespace="openai")
            
            # 准备消息格式
            messages = []
            
            # 添加系统消息
            messages.append({
                "role": "system",
                "content": "你是一个友好、有帮助的AI助手。尽可能提供精确和有用的回答。"
            })
            
            # 如果有会话历史且不为空，添加到消息中
            if conversation_id:
                # 这里可以添加历史消息，但需要实现获取历史消息的功能
                # 暂时使用一个空列表表示没有历史
                pass
            
            # 添加用户消息
            user_message = {"role": "user", "content": []}
            
            # 添加文本内容
            if processed_query:
                user_message["content"].append({
                    "type": "text",
                    "text": processed_query
                })
            
            # 处理图片文件
            for file_path in files:
                if os.path.exists(file_path):
                    try:
                        # 使用base64编码图片
                        with open(file_path, "rb") as f:
                            file_data = f.read()
                            # 检测MIME类型
                            mime_type = filetype.guess_mime(file_data)
                            if mime_type and mime_type.startswith("image/"):
                                # 将图片转为base64
                                base64_data = base64.b64encode(file_data).decode("utf-8")
                                # 添加图片内容
                                user_message["content"].append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{base64_data}"
                                    }
                                })
                                logger.debug(f"已添加图片: {file_path}")
                    except Exception as e:
                        logger.error(f"处理图片文件失败: {e}")
            
            # 将用户消息添加到消息列表
            if user_message["content"]:
                messages.append(user_message)
            
            headers = {
                "Authorization": f"Bearer {model.api_key}",
                "Content-Type": "application/json"
            }
            
            # 准备请求数据
            payload = {
                "model": model.model,
                "messages": messages,
                "stream": True
            }
            
            logger.debug(f"发送请求到 OpenAI - URL: {model.base_url}/chat/completions")
            
            ai_resp = ""
            async with aiohttp.ClientSession(proxy=self.http_proxy) as session:
                async with session.post(
                    f"{model.base_url}/chat/completions", 
                    headers=headers, 
                    json=payload
                ) as resp:
                    if resp.status == 200:
                        async for line in resp.content:
                            line = line.decode("utf-8").strip()
                            if not line or line == "data: [DONE]":
                                continue
                            
                            if line.startswith("data: "):
                                line = line[6:]  # 移除"data: "前缀
                            
                            try:
                                resp_json = json.loads(line)
                                delta = resp_json.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    ai_resp += content
                            except json.JSONDecodeError:
                                logger.error(f"OpenAI返回的JSON解析错误: {line}")
                                continue
                        
                        if not conversation_id:
                            # 如果是新会话，生成一个随机ID
                            new_con_id = f"openai_{int(time.time())}"
                            self.db.save_llm_thread_id(message["FromWxid"], new_con_id, "openai")
                        
                        logger.debug(f"OpenAI响应: {ai_resp}")
                    else:
                        # 处理错误情况
                        error_json = await resp.json()
                        error_message = error_json.get("error", {}).get("message", "未知错误")
                        logger.error(f"OpenAI API错误: {error_message}")
                        await bot.send_text_message(
                            message["FromWxid"], 
                            f"{XYBOT_PREFIX}{OPENAI_ERROR_MESSAGE}错误信息: {error_message}"
                        )
                        return
            
            # 处理并发送OpenAI的响应
            if ai_resp:
                # 处理并发送文本响应
                if message["MsgType"] == 34 or self.voice_reply_all:  # 语音消息或启用全语音回复
                    await self.text_to_voice_message(bot, message, ai_resp)
                else:
                    # 发送文本消息
                    await self.handle_openai_text_response(bot, message, ai_resp)
            else:
                logger.warning("OpenAI未返回有效响应")
                await bot.send_text_message(
                    message["FromWxid"], 
                    f"{XYBOT_PREFIX}{OPENAI_ERROR_MESSAGE}未获取到有效响应"
                )
        except Exception as e:
            logger.error(f"OpenAI API调用失败: {e}")
            logger.error(traceback.format_exc())
            await bot.send_text_message(
                message["FromWxid"], 
                f"{XYBOT_PREFIX}{OPENAI_ERROR_MESSAGE}错误: {str(e)}"
            )

    async def handle_openai_text_response(self, bot: WechatAPIClient, message: dict, text: str):
        """处理OpenAI的文本响应"""
        # 检查消息长度，如果太长则分段发送
        max_msg_len = 2000  # 微信消息最大长度限制
        
        if len(text) <= max_msg_len:
            await bot.send_text_message(message["FromWxid"], text)
        else:
            # 按段落分割消息
            paragraphs = re.split(r'\n\s*\n', text)
            current_msg = ""
            
            for paragraph in paragraphs:
                # 如果当前段落加上现有内容超过限制，先发送现有内容
                if len(current_msg) + len(paragraph) + 2 > max_msg_len:
                    if current_msg:
                        await bot.send_text_message(message["FromWxid"], current_msg)
                        current_msg = paragraph + "\n\n"
                    else:
                        # 如果单个段落超过限制，则需要再分割
                        await self.send_long_paragraph(bot, message, paragraph)
                else:
                    current_msg += paragraph + "\n\n"
            
            # 发送最后剩余的内容
            if current_msg:
                await bot.send_text_message(message["FromWxid"], current_msg)

    async def send_long_paragraph(self, bot: WechatAPIClient, message: dict, paragraph: str):
        """发送长段落，按句子分割"""
        max_msg_len = 2000
        sentences = re.split(r'([.!?。！？])', paragraph)
        current_msg = ""
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            ending = sentences[i+1] if i+1 < len(sentences) else ""
            full_sentence = sentence + ending
            
            if len(current_msg) + len(full_sentence) > max_msg_len:
                if current_msg:
                    await bot.send_text_message(message["FromWxid"], current_msg)
                    current_msg = full_sentence
                else:
                    # 如果单个句子太长，按字符直接截断
                    await self.send_chunked_text(bot, message, full_sentence)
            else:
                current_msg += full_sentence
        
        if current_msg:
            await bot.send_text_message(message["FromWxid"], current_msg)

    async def send_chunked_text(self, bot: WechatAPIClient, message: dict, text: str):
        """按固定长度分割并发送文本"""
        max_msg_len = 2000
        for i in range(0, len(text), max_msg_len):
            chunk = text[i:i+max_msg_len]
            await bot.send_text_message(message["FromWxid"], chunk)

    async def text_to_voice_message(self, bot: WechatAPIClient, message: dict, text: str):
        """将文本转换为语音消息"""
        try:
            # 使用gTTS将文本转为语音
            temp_mp3 = "temp_voice.mp3"
            tts = gTTS(text=text, lang='zh-cn')
            tts.save(temp_mp3)
            
            # 读取MP3文件并发送
            with open(temp_mp3, "rb") as f:
                voice_data = f.read()
                await bot.send_voice_message(message["FromWxid"], voice=voice_data, format="mp3")
            
            # 删除临时文件
            os.remove(temp_mp3)
        except Exception as e:
            logger.error(f"文本转语音失败: {e}")
            # 如果转语音失败，发送原文本
            await bot.send_text_message(message["FromWxid"], text + TEXT_TO_VOICE_FAILED) 

    async def _check_point(self, bot: WechatAPIClient, message: dict, model_config=None) -> bool:
        """检查用户积分是否足够"""
        wxid = message["SenderWxid"]
        if wxid in self.admins and self.admin_ignore:
            return True
        elif self.db.get_whitelist(wxid) and self.whitelist_ignore:
            return True
        else:
            if self.db.get_points(wxid) < (model_config or self.current_model).price:
                await bot.send_text_message(message["FromWxid"],
                                            XYBOT_PREFIX +
                                            INSUFFICIENT_POINTS_MESSAGE.format(price=(model_config or self.current_model).price))
                return False
            self.db.add_points(wxid, -((model_config or self.current_model).price))
            return True

    async def get_cached_image(self, user_wxid: str) -> Optional[bytes]:
        """获取用户最近的图片"""
        if user_wxid in self.image_cache:
            cache_data = self.image_cache[user_wxid]
            if time.time() - cache_data["timestamp"] <= self.image_cache_timeout:
                try:
                    # 确保我们有有效的二进制数据
                    image_content = cache_data["content"]
                    if not isinstance(image_content, bytes):
                        logger.error("缓存的图片内容不是二进制格式")
                        del self.image_cache[user_wxid]
                        return None
                    
                    # 尝试验证图片数据
                    try:
                        Image.open(io.BytesIO(image_content))
                    except Exception as e:
                        logger.error(f"缓存的图片数据无效: {e}")
                        del self.image_cache[user_wxid]
                        return None
                    
                    # 清除缓存
                    del self.image_cache[user_wxid]
                    return image_content
                except Exception as e:
                    logger.error(f"处理缓存图片失败: {e}")
                    del self.image_cache[user_wxid]
                    return None
            else:
                # 超时清除
                del self.image_cache[user_wxid]
        return None

    @on_text_message(priority=20)
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = message["Content"].strip()
        command = content.split(" ")[0] if content else ""

        await self.check_and_notify_inactive_users(bot)

        if not message["IsGroup"]:
            # 先检查唤醒词或触发词，获取对应模型
            model, processed_query, is_switch = self.get_model_from_message(content, message["SenderWxid"])
            
            # 检查是否有最近的图片
            image_content = await self.get_cached_image(message["FromWxid"])
            files = []
            if image_content:
                try:
                    logger.debug("发现最近的图片，准备处理")
                    file_path = os.path.join(self.files_dir, f"{time.time()}.jpg")
                    with open(file_path, 'wb') as f:
                        f.write(image_content)
                    files = [file_path]
                    logger.debug(f"图片已保存到: {file_path}")
                except Exception as e:
                    logger.error(f"处理图片失败: {e}")

            if command in self.commands:
                query = content[len(command):].strip()
            else:
                query = content
                
            # 检查API密钥是否可用 - 使用检测到的模型，而非默认模型
            if query and model.api_key:
                if await self._check_point(bot, message, model):  # 传递模型到_check_point
                    if is_switch:
                        model_name = next(name for name, config in self.models.items() if config == model)
                        await bot.send_text_message(
                            message["FromWxid"], 
                            f"已切换到{model_name.upper()}模型，将一直使用该模型直到下次切换。"
                        )
                        return
                    # 使用获取到的模型处理请求
                    await self.openai(bot, message, processed_query, files=files, specific_model=model)
                else:
                    logger.info(f"积分检查失败或模型API密钥无效，无法处理请求")
            else:
                if not query:
                    logger.debug("查询内容为空，不处理")
                elif not model.api_key:
                    logger.error(f"模型 {next((name for name, config in self.models.items() if config == model), '未知')} 的API密钥未配置")
                    await bot.send_text_message(message["FromWxid"], "所选模型的API密钥未配置，请联系管理员")
            return

        # 以下是群聊处理逻辑
        group_id = message["FromWxid"]
        user_wxid = message["SenderWxid"]
            
        if content == "退出聊天":
            if self.chat_manager.is_user_active(group_id, user_wxid):
                self.chat_manager.remove_user(group_id, user_wxid)
                await bot.send_at_message(group_id, "\n" + CHAT_LEAVE_MESSAGE, [user_wxid])
            return

        # 添加对切换模型命令的特殊处理
        if content.endswith("切换"):
            for model_name, model_config in self.models.items():
                for trigger in model_config.trigger_words:
                    if content.lower().startswith(trigger.lower()):
                        self.set_user_model(user_wxid, model_config)
                        await bot.send_at_message(
                            group_id,
                            f"\n已切换到{model_name.upper()}模型，将一直使用该模型直到下次切换。",
                            [user_wxid]
                        )
                        return

        is_at = self.is_at_message(message)
        is_command = command in self.commands

        # 先检查是否有唤醒词
        wakeup_detected = False
        wakeup_model = None
        processed_wakeup_query = ""
        
        for wakeup_word, model_config in self.wakeup_word_to_model.items():
            # 改用更精确的匹配方式，避免错误识别
            wakeup_lower = wakeup_word.lower()
            content_lower = content.lower()
            if content_lower.startswith(wakeup_lower) or f" {wakeup_lower}" in content_lower:
                wakeup_detected = True
                wakeup_model = model_config
                model_name = next((name for name, config in self.models.items() if config == model_config), '未知')
                logger.info(f"检测到唤醒词 '{wakeup_word}'，触发模型 '{model_name}'，原始内容: '{content}'")
                
                # 更精确地替换唤醒词
                original_wakeup = None
                if content_lower.startswith(wakeup_lower):
                    original_wakeup = content[:len(wakeup_lower)]
                else:
                    wakeup_pos = content_lower.find(f" {wakeup_lower}") + 1
                    if wakeup_pos > 0:
                        original_wakeup = content[wakeup_pos:wakeup_pos+len(wakeup_lower)]
                
                if original_wakeup:
                    processed_wakeup_query = content.replace(original_wakeup, "", 1).strip()
                    logger.info(f"处理后的查询内容: '{processed_wakeup_query}'")
                break
        
        # 检查是否有最近的图片 - 无论聊天室功能是否启用都获取图片
        files = []
        image_content = await self.get_cached_image(group_id)
        if image_content:
            try:
                logger.debug("发现最近的图片，准备处理")
                # 如果检测到唤醒词，使用对应模型；否则使用用户当前模型
                file_path = os.path.join(self.files_dir, f"{time.time()}.jpg")
                with open(file_path, 'wb') as f:
                    f.write(image_content)
                files = [file_path]
                logger.debug(f"图片已保存到: {file_path}")
            except Exception as e:
                logger.error(f"处理图片失败: {e}")
                
        # 如果检测到唤醒词，处理唤醒词请求
        if wakeup_detected and wakeup_model and processed_wakeup_query:
            if wakeup_model.api_key:  # 检查唤醒词对应模型的API密钥
                if await self._check_point(bot, message, wakeup_model):  # 传递模型到_check_point
                    logger.info(f"使用唤醒词对应模型处理请求")
                    await self.openai(bot, message, processed_wakeup_query, files=files, specific_model=wakeup_model)
                    return
                else:
                    logger.info(f"积分检查失败，无法处理唤醒词请求")
            else:
                model_name = next((name for name, config in self.models.items() if config == wakeup_model), '未知')
                logger.error(f"唤醒词对应模型 '{model_name}' 的API密钥未配置")
                await bot.send_at_message(group_id, f"\n此模型API密钥未配置，请联系管理员", [user_wxid])
            return

        # 继续处理@或命令的情况
        if is_at or is_command:
            # 群聊处理逻辑
            if not self.chat_manager.is_user_active(group_id, user_wxid):
                if is_at or is_command:
                    # 根据配置决定是否加入聊天室
                    if self.chatroom_enable:
                        self.chat_manager.add_user(group_id, user_wxid)
                        await bot.send_at_message(group_id, "\n" + CHAT_JOIN_MESSAGE, [user_wxid])
                    
                    query = content
                    for robot_name in self.robot_names:
                        query = query.replace(f"@{robot_name}", "").strip()
                    if command in self.commands:
                        query = query[len(command):].strip()
                    if query:
                        if await self._check_point(bot, message):
                            # 检查是否有唤醒词或触发词
                            model, processed_query, is_switch = self.get_model_from_message(query, message["SenderWxid"])
                            await self.openai(bot, message, processed_query, files=files, specific_model=model)
            return

        # 如果聊天室功能被禁用，则所有消息都需要@或命令触发
        if not self.chatroom_enable:
            if is_at or is_command:
                query = content
                for robot_name in self.robot_names:
                    query = query.replace(f"@{robot_name}", "").strip()
                if command in self.commands:
                    query = query[len(command):].strip()
                if query:
                    if await self._check_point(bot, message):
                        await self.openai(bot, message, query, files=files)
            return
            
        # 以下是聊天室功能处理
        if content == "查看状态":
            status_msg = self.chat_manager.format_room_status(group_id)
            await bot.send_at_message(group_id, "\n" + status_msg, [user_wxid])
            return
        elif content == "暂时离开":
            self.chat_manager.set_user_status(group_id, user_wxid, UserStatus.AWAY)
            await bot.send_at_message(group_id, "\n" + CHAT_AWAY_MESSAGE, [user_wxid])
            return
        elif content == "回来了":
            self.chat_manager.set_user_status(group_id, user_wxid, UserStatus.ACTIVE)
            await bot.send_at_message(group_id, "\n" + CHAT_BACK_MESSAGE, [user_wxid])
            return
        elif content == "我的统计":
            try:
                nickname = await bot.get_nickname(user_wxid) or "未知用户"
            except:
                nickname = "未知用户"
            stats_msg = self.chat_manager.format_user_stats(group_id, user_wxid, nickname)
            await bot.send_at_message(group_id, "\n" + stats_msg, [user_wxid])
            return
        elif content == "聊天室排行":
            ranking_msg = await self.chat_manager.format_room_ranking(group_id, bot)
            await bot.send_at_message(group_id, "\n" + ranking_msg, [user_wxid])
            return

        self.chat_manager.update_user_activity(group_id, user_wxid)
        
        if self.chat_manager.get_user_status(group_id, user_wxid) == UserStatus.AWAY:
            self.chat_manager.set_user_status(group_id, user_wxid, UserStatus.ACTIVE)
            await bot.send_at_message(group_id, "\n" + CHAT_BACK_MESSAGE, [user_wxid])

        if content:
            if is_at or is_command:
                query = content
                for robot_name in self.robot_names:
                    query = query.replace(f"@{robot_name}", "").strip()
                if command in self.commands:
                    query = query[len(command):].strip()
                if query:
                    if await self._check_point(bot, message):
                        # 检查是否有唤醒词或触发词
                        model, processed_query, is_switch = self.get_model_from_message(query, message["SenderWxid"])
                        if is_switch:
                            model_name = next(name for name, config in self.models.items() if config == model)
                            await bot.send_at_message(
                                message["FromWxid"], 
                                f"\n已切换到{model_name.upper()}模型，将一直使用该模型直到下次切换。", 
                                [message["SenderWxid"]]
                            )
                            return
                        await self.openai(bot, message, processed_query, files=files, specific_model=model)
            else:
                # 只有在聊天室功能开启时，才缓冲普通消息
                if self.chatroom_enable and self.chat_manager.is_user_active(group_id, user_wxid):
                    await self.chat_manager.add_message_to_buffer(group_id, user_wxid, content, files)
                    await self.schedule_message_processing(bot, group_id, user_wxid)
        return

    @on_at_message(priority=20)
    async def handle_at(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        if not self.current_model.api_key:
            await bot.send_at_message(message["FromWxid"], "\n你还没配置OpenAI API密钥！", [message["SenderWxid"]])
            return False

        await self.check_and_notify_inactive_users(bot)

        content = message["Content"].strip()
        query = content
        for robot_name in self.robot_names:
            query = query.replace(f"@{robot_name}", "").strip()

        group_id = message["FromWxid"]
        user_wxid = message["SenderWxid"]

        if query == "退出聊天":
            if self.chat_manager.is_user_active(group_id, user_wxid):
                self.chat_manager.remove_user(group_id, user_wxid)
                await bot.send_at_message(group_id, "\n" + CHAT_LEAVE_MESSAGE, [user_wxid])
            return False

        if not self.chat_manager.is_user_active(group_id, user_wxid):
            # 根据配置决定是否加入聊天室并发送欢迎消息
            self.chat_manager.add_user(group_id, user_wxid)
            if self.chatroom_enable:
                await bot.send_at_message(group_id, "\n" + CHAT_JOIN_MESSAGE, [user_wxid])

        logger.debug(f"提取到的 query: {query}")

        if not query:
            await bot.send_at_message(message["FromWxid"], "\n请输入你的问题或指令。", [message["SenderWxid"]])
            return False

        # 检查唤醒词或触发词，在图片上传前获取对应模型
        model, processed_query, is_switch = self.get_model_from_message(query, message["SenderWxid"])
        if is_switch:
            model_name = next(name for name, config in self.models.items() if config == model)
            await bot.send_at_message(
                message["FromWxid"], 
                f"\n已切换到{model_name.upper()}模型，将一直使用该模型直到下次切换。", 
                [message["SenderWxid"]]
            )
            return False

        # 检查模型API密钥是否可用
        if not model.api_key:
            model_name = next((name for name, config in self.models.items() if config == model), '未知')
            logger.error(f"所选模型 '{model_name}' 的API密钥未配置")
            await bot.send_at_message(message["FromWxid"], f"\n此模型API密钥未配置，请联系管理员", [message["SenderWxid"]])
            return False

        # 检查是否有最近的图片
        files = []
        image_content = await self.get_cached_image(group_id)
        if image_content:
            try:
                logger.debug("@消息中发现最近的图片，准备处理")
                file_path = os.path.join(self.files_dir, f"{time.time()}.jpg")
                with open(file_path, 'wb') as f:
                    f.write(image_content)
                files = [file_path]
                logger.debug(f"图片已保存到: {file_path}")
            except Exception as e:
                logger.error(f"处理图片失败: {e}")

        if await self._check_point(bot, message, model):  # 传递正确的模型参数
            # 使用上面已经获取的模型和处理过的查询
            logger.info(f"@消息使用模型 '{next((name for name, config in self.models.items() if config == model), '未知')}' 处理请求")
            await self.openai(bot, message, processed_query, files=files, specific_model=model)
        else:
            logger.info(f"积分检查失败，无法处理@消息请求")
        return False

    @on_voice_message(priority=20)
    async def handle_voice(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        if message["IsGroup"]:
            return

        if not self.current_model.api_key:
            await bot.send_text_message(message["FromWxid"], "OpenAI API密钥未配置！")
            return False

        # 需要实现语音转文本功能，暂时返回提示
        await bot.send_text_message(message["FromWxid"], "目前暂不支持语音识别，请发送文字消息。")
        return False

    @on_image_message(priority=20)
    async def handle_image(self, bot: WechatAPIClient, message: dict):
        """处理图片消息"""
        if not self.enable:
            return

        try:
            # 解析XML获取图片信息
            xml_content = message.get("Content")
            if isinstance(xml_content, str):
                try:
                    # 从XML中提取base64图片数据
                    image_base64 = xml_content.split(',')[-1]  # 获取base64部分
                    # 转换base64为二进制
                    try:
                        image_content = base64.b64decode(image_base64)
                        # 验证是否为有效的图片数据
                        Image.open(io.BytesIO(image_content))
                        
                        self.image_cache[message["FromWxid"]] = {
                            "content": image_content,
                            "timestamp": time.time()
                        }
                        logger.debug(f"已缓存用户 {message['FromWxid']} 的图片")
                    except Exception as e:
                        logger.error(f"图片数据无效: {e}")
                except Exception as e:
                    logger.error(f"处理base64数据失败: {e}")
                    logger.debug(f"Base64数据: {image_base64[:100]}...")  # 只打印前100个字符
            else:
                logger.error("图片消息内容不是字符串格式")
            
        except Exception as e:
            logger.error(f"处理图片消息失败: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")

    def is_at_message(self, message: dict) -> bool:
        if not message["IsGroup"]:
            return False
        content = message["Content"]
        for robot_name in self.robot_names:
            if f"@{robot_name}" in content:
                return True
        return False 