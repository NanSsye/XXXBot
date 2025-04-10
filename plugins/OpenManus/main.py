import os
import json
import asyncio
import tomli
import uuid # For temporary file names
import aiofiles # For async file operations
import base64 # <-- Import base64
import math # <-- Import math for ceiling division
from pydub import AudioSegment # <-- Import pydub
import io # Already imported by fish_audio_sdk, but good practice
from typing import Dict, List, Any, Optional, Tuple, AsyncGenerator
from loguru import logger
from datetime import datetime
import time
import re
import aiohttp

from WechatAPI import WechatAPIClient
from utils.decorators import on_text_message, on_at_message
from utils.plugin_base import PluginBase

from .api_client import GeminiClient, TTSClient, MinimaxTTSClient
from .agent.mcp import MCPAgent, Tool
from .tools import CalculatorTool, DateTimeTool, SearchTool, WeatherTool, CodeTool, ModelScopeDrawingTool
from .tools.stock_tool import StockTool
from .tools.virtual_tryon_tool import VirtualTryOnTool
from .memory import MessageMemory

# Define a constant for max duration in milliseconds
MAX_AUDIO_DURATION_MS = 59000 # 59 seconds to be safe

def split_text_at_natural_breaks(text, max_duration_seconds=55):
    """
    在句子和自然段落处分割文本，确保每段音频不超过微信限制
    
    参数:
        text: 要分割的文本
        max_duration_seconds: 每段最大时长(秒)
    
    返回:
        分割后的文本片段列表
    """
    # 估算每个字符的音频时长 (中文约0.2-0.3秒/字)
    CHARS_PER_SECOND = 3.5  # 大约每秒可以说3.5个汉字
    
    # 句子结束标记
    sentence_endings = ['。', '！', '？', '；', '.', '!', '?', ';']
    # 自然段落标记
    paragraph_breaks = ['\n\n', '\r\n\r\n']
    
    # 估算文本对应的音频时长
    def estimate_duration(text_chunk):
        return len(text_chunk) / CHARS_PER_SECOND
    
    segments = []
    current_segment = ""
    
    # 按段落先分割
    paragraphs = []
    text_remains = text
    
    # 先按自然段落分割
    for break_mark in paragraph_breaks:
        if break_mark in text_remains:
            parts = text_remains.split(break_mark)
            for i, part in enumerate(parts):
                if i < len(parts) - 1:  # 不是最后一部分
                    paragraphs.append(part + break_mark)
                else:  # 最后一部分
                    text_remains = part
    
    # 处理剩余部分
    if text_remains:
        paragraphs.append(text_remains)
    
    # 如果没有找到段落，将整个文本作为一个段落
    if not paragraphs:
        paragraphs = [text]
    
    # 逐段处理
    for paragraph in paragraphs:
        # 如果段落估计时长已超限，直接作为独立片段
        if estimate_duration(paragraph) > max_duration_seconds:
            # 按句子再分割
            current_sentence = ""
            for char in paragraph:
                current_sentence += char
                
                # 遇到句子结束
                if char in sentence_endings:
                    # 检查添加这个句子是否超过时长限制
                    if estimate_duration(current_segment + current_sentence) <= max_duration_seconds:
                        current_segment += current_sentence
                        current_sentence = ""
                    else:
                        # 当前段已接近限制，保存并开始新段
                        segments.append(current_segment)
                        current_segment = current_sentence
                        current_sentence = ""
            
            # 处理段落中最后剩余的句子
            if current_sentence:
                if estimate_duration(current_segment + current_sentence) <= max_duration_seconds:
                    current_segment += current_sentence
                else:
                    segments.append(current_segment)
                    current_segment = current_sentence
        else:
            # 段落不超限，检查添加整段是否超限
            if estimate_duration(current_segment + paragraph) <= max_duration_seconds:
                current_segment += paragraph
            else:
                segments.append(current_segment)
                current_segment = paragraph
    
    # 添加最后一段
    if current_segment:
        segments.append(current_segment)
    
    return segments

class OpenManus(PluginBase):
    """OpenManus插件主类 (使用Gemini + TTS)"""
    description = "基于Gemini的智能代理插件，支持文本转语音输出"
    author = "OpenManus Team (Gemini+TTS Adaptation)"
    version = "0.4.0" # Version bump
    
    def __init__(self, config_path: str = "plugins/OpenManus/config.toml"):
        """初始化OpenManus插件 (Gemini+TTS版)
        
        Args:
            config_path: 配置文件路径
        """
        super().__init__()
        
        self.name = "OpenManus"
        self.version = "0.4.0"
        self.config = self._load_config(config_path)
        self.enabled = self.config.get("basic", {}).get("enable", True)
        self.trigger_word = self.config.get("basic", {}).get("trigger_keyword", "agent")
        
        # Gemini API 配置
        gemini_config = self.config.get("gemini", {})
        self.gemini_api_key = gemini_config.get("api_key", "")
        self.gemini_base_url = gemini_config.get("base_url", "https://generativelanguage.googleapis.com/v1beta")
        
        # Agent 配置
        agent_config = self.config.get("agent", {})
        self.model = agent_config.get("default_model", "gemini-2.0-flash")
        self.max_tokens = agent_config.get("max_tokens", 8192)
        self.temperature = agent_config.get("temperature", 0.7)
        self.max_steps = agent_config.get("max_steps", 10)
        
        # MCP配置
        mcp_config = self.config.get("mcp", {})
        self.enable_mcp = mcp_config.get("enable_mcp", True)  # 读取是否启用MCP
        self.thinking_steps = mcp_config.get("thinking_steps", 3)
        self.force_thinking = mcp_config.get("force_thinking", True)
        self.thinking_prompt = mcp_config.get("thinking_prompt", "请深入思考这个问题，分析多个角度并考虑是否需要查询额外信息")
        
        # 工具配置
        tools_config = self.config.get("tools", {})
        self.enable_search = tools_config.get("enable_search", True)
        self.enable_calculator = tools_config.get("enable_calculator", True)
        self.enable_datetime = tools_config.get("enable_datetime", True)
        self.enable_weather = tools_config.get("enable_weather", True)
        self.enable_code = tools_config.get("enable_code", True)
        self.enable_stock = tools_config.get("enable_stock", True)  # 是否启用股票工具
        self.stock_data_cache_days = tools_config.get("stock_data_cache_days", 60)  # 股票数据缓存天数
        self.bing_api_key = tools_config.get("bing_api_key", "")
        self.serper_api_key = tools_config.get("serper_api_key", "") # Corrected key name if needed
        self.search_engine = tools_config.get("search_engine", "serper")
        
        # TTS 配置
        tts_config = self.config.get("tts", {})
        self.tts_enabled = tts_config.get("enable", False) 
        self.tts_api_key = tts_config.get("api_key", "")
        self.tts_base_url = tts_config.get("base_url", "") # Still read, though SDK might not use it
        self.tts_reference_id = tts_config.get("reference_id", None) # <-- Read reference_id
        # self.tts_model = tts_config.get("model", "speech-1.5") # <-- No longer needed
        self.tts_format = tts_config.get("format", "mp3")
        self.tts_mp3_bitrate = tts_config.get("mp3_bitrate", 128)
        
        # MiniMax TTS 配置
        minimax_tts_config = self.config.get("minimax_tts", {})
        self.minimax_tts_enabled = minimax_tts_config.get("enable", False)
        self.minimax_tts_api_key = minimax_tts_config.get("api_key", "")
        self.minimax_tts_group_id = minimax_tts_config.get("group_id", "")
        self.minimax_tts_base_url = minimax_tts_config.get("base_url", "https://api.minimax.chat/v1/t2a_v2")
        self.minimax_tts_model = minimax_tts_config.get("model", "speech-02-hd")
        self.minimax_tts_voice_id = minimax_tts_config.get("voice_id", "male-qn-qingse")
        self.minimax_tts_format = minimax_tts_config.get("format", "mp3")
        self.minimax_tts_sample_rate = minimax_tts_config.get("sample_rate", 32000)
        self.minimax_tts_bitrate = minimax_tts_config.get("bitrate", 128000)
        self.minimax_tts_speed = minimax_tts_config.get("speed", 1.0)
        self.minimax_tts_vol = minimax_tts_config.get("vol", 1.0)
        self.minimax_tts_pitch = minimax_tts_config.get("pitch", 0.0)
        self.minimax_tts_language_boost = minimax_tts_config.get("language_boost", "auto")
        self.minimax_tts_emotion = minimax_tts_config.get("emotion", "neutral")  # 添加情绪参数读取
        
        self.temp_audio_dir = "temp_audio" # Directory for temporary audio files
        os.makedirs(self.temp_audio_dir, exist_ok=True) # Ensure temp dir exists

        # 其他配置
        self.private_chat_enabled = self.config.get("basic", {}).get("allow_private_chat", True)
        self.group_at_enabled = self.config.get("basic", {}).get("respond_to_at", True)
        self.separate_context = self.config.get("memory", {}).get("separate_context", True)
        
        # 记忆相关配置
        memory_config = self.config.get("memory", {})
        self.enable_memory = memory_config.get("enable_memory", True)
        self.max_history = memory_config.get("max_history", 5)
        self.memory_expire_hours = memory_config.get("memory_expire_hours", 24)
        
        # 提示词相关配置
        prompts_config = self.config.get("prompts", {})
        self.enable_custom_prompt = prompts_config.get("enable_custom_prompt", False)
        self.custom_system_prompt = prompts_config.get("system_prompt", "")
        self.greeting = prompts_config.get("greeting", "")
        
        # 启用绘图工具
        self.enable_drawing = self.config.get("enable_drawing", True)
        
        # 初始化 API 客户端 (Gemini and TTS)
        self.gemini_client = None
        self.tts_client = None
        self.minimax_tts_client = None
        self._init_clients() # Renamed
        
        # 用于记录响应状态的字典
        self.responding_to = {}
        
        logger.info(f"OpenManus插件(Gemini+TTS)初始化完成，版本: {self.version}")
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from the given path."""
        try:
            import tomllib
        except ImportError:
            try:
                import toml as tomllib
            except ImportError:
                logger.error("TOML库未安装，请使用'pip install tomli' (Python 3.11以下) 或使用Python 3.11+")
                return {}
                
        try:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
                
            # Load basic configuration
            basic_config = config.get("basic", {})
            self.enable = basic_config.get("enable", True)
            self.trigger_keyword = basic_config.get("trigger_keyword", "agent")
            self.respond_to_at = basic_config.get("respond_to_at", True)
            self.allow_private_chat = basic_config.get("allow_private_chat", True)
            
            # Load API configuration
            gemini_config = config.get("gemini", {})
            self.api_key = gemini_config.get("api_key", "")
            self.base_url = gemini_config.get("base_url", "https://generativelanguage.googleapis.com/v1beta")
            
            # Load agent configuration
            agent_config = config.get("agent", {})
            self.model = agent_config.get("default_model", "gemini-1.5-pro")
            self.max_steps = agent_config.get("max_steps", 10)
            self.max_tokens = agent_config.get("max_tokens", 8000)
            self.temperature = agent_config.get("temperature", 0.7)
            
            # Load MCP configuration
            mcp_config = config.get("mcp", {})
            self.enable_mcp = mcp_config.get("enable_mcp", True)
            self.thinking_steps = mcp_config.get("thinking_steps", 3)
            self.force_thinking = mcp_config.get("force_thinking", True)
            self.thinking_prompt = mcp_config.get("thinking_prompt", "")
            
            # Load tools configuration
            tools_config = config.get("tools", {})
            self.enable_search = tools_config.get("enable_search", True)
            self.enable_calculator = tools_config.get("enable_calculator", True)
            self.enable_datetime = tools_config.get("enable_datetime", True)
            self.enable_weather = tools_config.get("enable_weather", True)
            self.enable_code = tools_config.get("enable_code", True)
            self.search_engine = tools_config.get("search_engine", "bing")
            self.bing_api_key = tools_config.get("bing_api_key", "")
            self.serper_api_key = tools_config.get("serper_api_key", "")
            self.enable_stock = tools_config.get("enable_stock", True)
            self.stock_data_cache_days = tools_config.get("stock_data_cache_days", 60)
            self.enable_drawing = tools_config.get("enable_drawing", True)
            
            # Load memory configuration
            memory_config = config.get("memory", {})
            self.enable_memory = memory_config.get("enable_memory", True)
            self.max_history = memory_config.get("max_history", 20)
            self.separate_context = memory_config.get("separate_context", True)
            self.memory_expire_hours = memory_config.get("memory_expire_hours", 24)
            
            # Load TTS configuration
            tts_config = config.get("tts", {})
            self.tts_enabled = tts_config.get("enable", False)
            self.tts_base_url = tts_config.get("base_url", "https://api.fish.audio")
            self.tts_api_key = tts_config.get("api_key", "")
            self.tts_reference_id = tts_config.get("reference_id", "")
            self.tts_format = tts_config.get("format", "mp3")
            self.tts_mp3_bitrate = tts_config.get("mp3_bitrate", 128)
            
            # Load MiniMax TTS configuration
            minimax_tts_config = config.get("minimax_tts", {})
            self.minimax_tts_enabled = minimax_tts_config.get("enable", False)
            self.minimax_tts_base_url = minimax_tts_config.get("base_url", "https://api.minimax.chat/v1/t2a_v2")
            self.minimax_tts_api_key = minimax_tts_config.get("api_key", "")
            self.minimax_tts_group_id = minimax_tts_config.get("group_id", "")
            self.minimax_tts_model = minimax_tts_config.get("model", "speech-02-hd")
            self.minimax_tts_voice_id = minimax_tts_config.get("voice_id", "saoqi_yujie")
            self.minimax_tts_format = minimax_tts_config.get("format", "mp3")
            self.minimax_tts_sample_rate = minimax_tts_config.get("sample_rate", 32000)
            self.minimax_tts_bitrate = minimax_tts_config.get("bitrate", 128000)
            self.minimax_tts_speed = minimax_tts_config.get("speed", 0.6)
            self.minimax_tts_vol = minimax_tts_config.get("vol", 1.0)
            self.minimax_tts_pitch = minimax_tts_config.get("pitch", 0.0)
            self.minimax_tts_language_boost = minimax_tts_config.get("language_boost", "auto")
            self.minimax_tts_emotion = minimax_tts_config.get("emotion", "neutral")
            
            # 加载虚拟试衣工具配置
            tryon_config = config.get("tryon", {})
            self.enable_tryon = tryon_config.get("enable", True)
            
            # Load custom prompt configuration
            prompts_config = config.get("prompts", {})
            self.enable_custom_prompt = prompts_config.get("enable_custom_prompt", False)
            self.custom_system_prompt = prompts_config.get("system_prompt", "")
            self.custom_greeting = prompts_config.get("greeting", "")
            
            return config
            
        except FileNotFoundError:
            logger.error(f"配置文件未找到: {config_path}")
            return {}
        except Exception as e:
            logger.exception(f"加载配置失败: {e}")
            return {}
            
    def _init_clients(self) -> None: # Renamed
        """初始化 API 客户端 (Gemini and TTS)"""
        # Init Gemini Client
        if self.gemini_api_key:
            try:
                self.gemini_client = GeminiClient(api_key=self.gemini_api_key, base_url=self.gemini_base_url)
                logger.info(f"Gemini客户端初始化完成，目标URL: {self.gemini_base_url}")
                
                # 设置记忆相关参数
                if self.enable_memory:
                    self.gemini_client.set_max_history(self.max_history)
                    self.gemini_client.set_memory_expire_hours(self.memory_expire_hours)
                    logger.info(f"记忆功能已启用，最大历史记录数: {self.max_history}, 记忆保留时间: {self.memory_expire_hours}小时")
                
            except ValueError as ve:
                 logger.error(f"初始化Gemini客户端失败: {ve}")
                 self.enabled = False
            except Exception as e:
                logger.exception("初始化Gemini客户端时发生意外错误")
                self.enabled = False
        else:
             logger.warning("未提供Gemini API密钥，插件核心功能将受限")
             self.enabled = False # Disable if Gemini is essential

        # Init Fish Audio TTS Client
        if self.tts_enabled and self.tts_api_key and self.tts_reference_id:
             try:
                 self.tts_client = TTSClient(
                     api_key=self.tts_api_key,
                     default_reference_id=self.tts_reference_id # <-- Pass reference_id
                 )
                 logger.info(f"Fish Audio TTS客户端初始化完成 (Reference ID: {self.tts_reference_id})") # Log ref id
             except ValueError as ve:
                 logger.error(f"初始化TTS客户端失败: {ve}")
                 self.tts_enabled = False 
             except Exception as e:
                 logger.exception("初始化TTS客户端时发生意外错误")
                 self.tts_enabled = False 
        elif self.tts_enabled:
            logger.warning("TTS已启用但未完全配置 (缺少API Key或Reference ID)，将禁用TTS功能。") # Updated warning
            self.tts_enabled = False
        else:
            logger.info("Fish Audio TTS功能未启用。")
            
        # Init MiniMax TTS Client
        if self.minimax_tts_enabled and self.minimax_tts_api_key and self.minimax_tts_group_id:
            try:
                self.minimax_tts_client = MinimaxTTSClient(
                    api_key=self.minimax_tts_api_key,
                    group_id=self.minimax_tts_group_id,
                    base_url=self.minimax_tts_base_url
                )
                logger.info(f"MiniMax TTS客户端初始化完成 (API Key: ...{self.minimax_tts_api_key[-4:]}, Group ID: {self.minimax_tts_group_id})")
            except ValueError as ve:
                logger.error(f"初始化MiniMax TTS客户端失败: {ve}")
                self.minimax_tts_enabled = False
            except Exception as e:
                logger.exception("初始化MiniMax TTS客户端时发生意外错误")
                self.minimax_tts_enabled = False
        elif self.minimax_tts_enabled:
            logger.warning("MiniMax TTS已启用但未完全配置 (缺少API Key或Group ID)，将禁用MiniMax TTS功能。")
            self.minimax_tts_enabled = False
        else:
            logger.info("MiniMax TTS功能未启用。")

    def _create_and_register_agent(self) -> Optional[MCPAgent]:
        """Creates a new MCPAgent instance and registers tools."""
        if not self.gemini_client:
             logger.error("Gemini客户端未初始化，无法创建代理")
             return None
             
        try:
            # 准备系统提示词
            system_prompt = None
            if self.enable_custom_prompt and self.custom_system_prompt:
                system_prompt = self.custom_system_prompt
                logger.info("使用自定义系统提示词")
            
            # 检查是否启用MCP（多步骤思考）
            force_thinking = self.force_thinking
            thinking_steps = self.thinking_steps
            if not self.enable_mcp:
                # 如果禁用MCP，则设置为不强制思考，步骤为0
                force_thinking = False
                thinking_steps = 0
                logger.info("MCP功能已禁用，将跳过思考步骤")
            
            agent = MCPAgent(
                client=self.gemini_client,
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                max_steps=self.max_steps,
                thinking_steps=thinking_steps,  # 使用根据配置调整后的值
                force_thinking=force_thinking,  # 使用根据配置调整后的值
                thinking_prompt=self.thinking_prompt,
                system_prompt=system_prompt  # 传递自定义系统提示词
            )
            
            # Register tools for this new agent instance
            tools = []
            if self.enable_calculator:
                tools.append(CalculatorTool())
            if self.enable_datetime:
                tools.append(DateTimeTool())
            if self.enable_search:
                search_config = self.config.get("search", {})
                search_api_key = self.serper_api_key if self.search_engine == "serper" else self.bing_api_key
                search_url = search_config.get("serper_url", "https://google.serper.dev/search") if self.search_engine == "serper" else search_config.get("bing_url", "https://api.bing.microsoft.com/v7.0/search")
                tools.append(SearchTool(api_key=search_api_key, search_url=search_url, search_engine=self.search_engine))
            if self.enable_weather:
                weather_config = self.config.get("weather", {})
                tools.append(WeatherTool(
                    api_key=weather_config.get("api_key", ""), 
                    forecast_url=weather_config.get("forecast_url", "https://v3.alapi.cn/api/tianqi/seven"),
                    index_url=weather_config.get("index_url", "https://v3.alapi.cn/api/tianqi/index")
                    ))
            if self.enable_code:
                code_config = self.config.get("code", {})
                tools.append(CodeTool(
                    timeout=code_config.get("timeout", 10),
                    max_output_length=code_config.get("max_output_length", 2000),
                    enable_exec=code_config.get("enable_exec", True)
                ))
            if self.enable_stock:
                tools.append(StockTool(data_cache_days=self.stock_data_cache_days))
            if self.enable_drawing:
                # 获取绘图工具配置
                drawing_config = self.config.get("drawing", {})
                tools.append(ModelScopeDrawingTool(
                    api_base=drawing_config.get("api_base", "https://www.modelscope.cn/api/v1/muse/predict"),
                    cookies=drawing_config.get("modelscope_cookies", ""),
                    csrf_token=drawing_config.get("modelscope_csrf_token", ""),
                    max_wait_time=drawing_config.get("max_wait_time", 120)
                ))
            # 添加虚拟试衣工具
            if self.enable_tryon:
                # 获取虚拟试衣工具配置
                tryon_config = self.config.get("tryon", {})
                tools.append(VirtualTryOnTool(
                    api_base=tryon_config.get("api_base", "https://kwai-kolors-kolors-virtual-try-on.ms.show"),
                    modelscope_cookies=tryon_config.get("modelscope_cookies", ""),
                    modelscope_csrf_token=tryon_config.get("modelscope_csrf_token", ""),
                    max_wait_time=tryon_config.get("max_wait_time", 120)
                ))
            agent.register_tools(tools)
            logger.debug(f"为新请求创建并注册了 {len(tools)} 个工具的MCPAgent")
            return agent
        except Exception as e:
             logger.exception("创建和注册新代理实例时出错")
             return None

    # --- Core Request Handler ---
    async def _handle_request(self, bot: WechatAPIClient, message: dict, query: str):
        """Handles the core logic for processing a request after validation."""
        # Use the correct keys based on the message dictionary structure
        is_group = message.get("IsGroup", False) 
        user_id = message.get("SenderWxid") # ID of the user who sent the message
        group_id = message.get("FromWxid") if is_group else None # ID of the group (if any)

        # Determine the target ID for the reply
        if is_group:
             target_id = group_id
        else:
             target_id = user_id # Reply to sender in private chat

        # --- Add Validation for target_id and user_id --- 
        if not target_id:
             # This should theoretically not happen now if message structure is consistent
             logger.error(f"无法确定消息的目标ID (target_id is None)，无法处理请求: {message}")
             return False # Cannot proceed without a target
        if not user_id:
             logger.warning(f"无法确定消息的发送者ID (SenderWxid 缺失)，但将尝试处理请求 (目标: {target_id}): {message}")
             # If user_id is strictly needed later, more checks might be required

        at_list = [user_id] if is_group and user_id else [] # Ensure user_id exists for at_list in groups
        session_id = target_id # Use target_id for locking
        
        if session_id in self.responding_to and self.responding_to[session_id]:
            await bot.send_at_message(target_id, "我正在思考上一个问题，请稍候...", at_list)
            return False # Block other plugins, already handling
            
        logger.info(f"OpenManus(Gemini+TTS)处理来自 {user_id or '未知用户'} 的请求 (目标: {target_id}): {query}")
        self.responding_to[session_id] = True
        # Keep track of all temp files created for cleanup
        temp_files_to_clean = []
        
        try:
            # 1. Create Agent and get text response
            agent = self._create_and_register_agent()
            if not agent or not self.gemini_client:
                logger.error("代理或Gemini客户端未初始化，无法处理请求")
                await bot.send_at_message(target_id, "抱歉，内部服务未准备好，请稍后再试或联系管理员。", at_list)
                return False # Handled (error)
                
            # 获取历史对话记录（如果启用记忆功能）
            history = None
            if self.enable_memory and self.gemini_client:
                history = self.gemini_client.get_chat_history(session_id)
                if history:
                    logger.info(f"获取到会话 {session_id} 的历史记录，共 {len(history)} 条")
                else:
                    logger.debug(f"会话 {session_id} 没有历史记录或已过期")
            
            # 执行代理，带上历史记录（如果有）
            result = await agent.run(query, history=history)
            final_answer = result.get("answer", "")  # 使用.get避免None错误
            
            # 如果成功获取回答且启用了记忆功能，保存对话记录
            if final_answer and self.enable_memory and self.gemini_client:
                # 保存用户问题
                self.gemini_client.add_to_chat_history(session_id, "user", query)
                # 保存AI回答
                self.gemini_client.add_to_chat_history(session_id, "assistant", final_answer)
                logger.info(f"已保存对话到会话 {session_id} 的历史记录中")
            
            if not final_answer:
                logger.warning("Gemini未生成有效文本回复 (result was None or missing 'answer')。")
                await bot.send_at_message(target_id, "抱歉，处理时遇到问题，无法生成回复。", at_list)
                return False # Handled (error)
                
            logger.debug(f"从Gemini获取最终文本回复，长度:{len(final_answer)}")
            
            # 2. 直接使用语义分段TTS
            tts_available = (self.minimax_tts_enabled and self.minimax_tts_client) or (self.tts_enabled and self.tts_client)
            
            # 如果TTS服务可用
            if tts_available:
                # --- 使用自然分段方式发送语音 ---
                try:
                    # 不再使用旧的基于时长分割方法，而是先发送一个通知消息
                    if len(final_answer) > 500:  # 如果回复较长，发送提示
                        await bot.send_at_message(
                            target_id, 
                            "回复内容较长，正在生成语音消息，请稍候...", 
                            at_list
                        )
                    
                    # 记录完整的文本内容，便于调试
                    logger.debug(f"准备发送到TTS的完整文本内容: '{final_answer}'")
                    
                    # 使用新的基于语义分段的方法处理并发送语音
                    await self.send_tts_with_natural_breaks(bot, target_id, final_answer, at_list)
                    return False  # 请求已处理
                    
                except Exception as e:
                    # 记录错误并回退到文本模式
                    logger.exception(f"使用语义分段处理或发送语音时出错: {e}")
                    # 回退到文本
                    await bot.send_at_message(target_id, f"(语音处理或发送失败): {final_answer}", at_list)
                    return False  # 请求已处理(处理出错)
            else: # 没有TTS服务可用
                if self.tts_enabled or self.minimax_tts_enabled:
                    logger.warning("所有TTS服务配置不正确，将发送原始文本。")
                else:
                    logger.debug("未启用任何TTS服务，发送文本回复。")
                    
                # 检查回复中是否包含ModelScope图片链接
                urls = []
                if self.enable_drawing and "modelscope-studios.oss-cn-zhangjiakou.aliyuncs.com" in final_answer and (".png" in final_answer or ".jpg" in final_answer):
                    urls = re.findall(r'https?://modelscope-studios\.oss-cn-zhangjiakou\.aliyuncs\.com/[^\s\]]+?(?:\.png|\.jpg)', final_answer)
                    # 创建后台任务下载图片，但不等待其完成
                    if urls:
                        logger.info(f"检测到回复中包含ModelScope图片链接: {urls[0]}")
                        asyncio.create_task(self._download_and_send_image(bot, target_id, urls[0]))
                
                # 发送文本回复
                await bot.send_at_message(target_id, final_answer, at_list)
                return False # 请求已处理
                
        except Exception as e:
            logger.exception(f"处理来自 {user_id or '未知'} 的请求时发生意外异常") 
            # Ensure target_id is valid before sending error message
            if target_id:
                 await bot.send_at_message(target_id, f"处理您的请求时出错，请稍后再试。", at_list) 
            return False 
        finally:
            self.responding_to[session_id] = False
            # Clean up ALL temporary files created
            for temp_file in temp_files_to_clean:
                 if temp_file and os.path.exists(temp_file):
                      try:
                           if hasattr(aiofiles, 'os') and hasattr(aiofiles.os, 'remove'):
                                await aiofiles.os.remove(temp_file)
                           else:
                                os.remove(temp_file) 
                           logger.debug(f"已清理临时语音文件: {temp_file}")
                      except OSError as oe:
                           logger.error(f"清理临时语音文件失败: {oe}")

    # --- Trigger/Blocking Decorators ---
    @on_text_message(priority=90)
    async def detect_trigger_keyword(self, bot: WechatAPIClient, message: dict):
        if not self.enabled: return True
        content = message.get("content", message.get("Content", "")).strip() # Use strip here
        if content.lower().startswith(f"{self.trigger_word} ") or content.lower() == self.trigger_word:
            logger.info(f"OpenManus检测到唤醒词: {content}, 让 handle_text 处理")
            return True # Let handle_text execute
        return True # Not triggered, allow other plugins

    @on_text_message(priority=50)
    async def handle_blocking(self, bot: WechatAPIClient, message: dict):
        if not self.enabled or not self.config.get("blocking", {}).get("enable", False):
             return True
             
        content = message.get("content", message.get("Content", "")).strip()
        from_user_id = message.get("sender_id", message.get("SenderWxid", ""))
        room_id = message.get("room_id", message.get("FromWxid", ""))
        is_at_msg = message.get("is_at_msg", False) # Check flag from detect_at_trigger
        is_trigger_msg = content.lower().startswith(f"{self.trigger_word} ") or content.lower() == self.trigger_word
        
        # Only check blocking if the message is directed at the bot (@ or trigger word)
        if not is_at_msg and not is_trigger_msg:
             return True # Not for us, don't block

        # Extract query for checking sensitive words
        query = content # If it's an @ message, the content is the query
        if is_trigger_msg and content.lower() != self.trigger_word:
            query = content[len(self.trigger_word):].strip()
        elif is_trigger_msg: # Only trigger word sent
             query = "" 

        sensitive_words = self.config.get("blocking", {}).get("sensitive_words", [])
        for word in sensitive_words:
            # Check if the sensitive word exists in the extracted query
            if word and word in query: # Ensure word is not empty
                logger.warning(f"检测到敏感词: {word}, 消息来自 {from_user_id} in {room_id or 'private'}")
                await bot.send_at_message(
                    room_id or from_user_id, 
                    f"抱歉，您的消息包含不当内容，已被拦截。", # Simplified message
                    [from_user_id] if room_id else [] # Only use at_list in groups
                )
                return False # Blocked

        return True # Not blocked

    @on_at_message(priority=90)
    async def detect_at_trigger(self, bot: WechatAPIClient, message: dict):
        if not self.enabled or not self.group_at_enabled:
             return True
        room_id = message.get("room_id", message.get("FromWxid", ""))
        if not room_id:
            return True # Should be a group message if decorator triggered
            
        logger.info(f"OpenManus检测到@消息，让 handle_at 处理")
        # Add flag for blocking check and potentially other logic
        message['is_at_msg'] = True 
        return True # Let handle_at execute

    # --- Main Handlers (Call _handle_request) ---
    @on_at_message(priority=70)
    async def handle_at(self, bot: WechatAPIClient, message: dict):
        """处理@消息 (Gemini+TTS版) - Calls _handle_request"""
        if not self.enabled or not self.group_at_enabled:
            return True # Already checked by detect_at_trigger, but safe fallback
            
        content = message.get("content", message.get("Content", "")).strip()
        from_user_id = message.get("sender_id", message.get("SenderWxid", ""))
        room_id = message.get("room_id", message.get("FromWxid", "")) # Should exist
        
        # Handle case where user just @'s the bot with no further text
        if not content: 
             await bot.send_at_message(room_id, "请问有什么可以帮助您的？请@我并输入问题。", [from_user_id])
             return False # Handled (sent prompt)
             
        # 检查是否是命令（如清除记忆等）
        command_handled = await self._handle_commands(bot, message, content)
        if command_handled:
            return False  # 命令已处理，不需要继续
        
        # Call the core handler with the message content as the query
        logger.debug(f"handle_at 调用 _handle_request, query: {content}")
        return await self._handle_request(bot, message, content)

    @on_text_message(priority=70)
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        """处理私聊或群聊中的触发词消息 (Gemini+TTS版) - Calls _handle_request"""
        if not self.enabled:
            return True # Pass to others if disabled

        content = message.get("content", message.get("Content", "")).strip()
        room_id = message.get("room_id", None) # None indicates private chat
        sender_id = message.get("SenderWxid", message.get("sender_id", ""))
        
        # Check if private chat is allowed
        if not room_id and not self.private_chat_enabled:
            # No need to log here unless debugging, just pass silently
            return True # Private chat disabled, pass

        # Extract query (Assume detect_trigger_keyword ensured it starts with trigger)
        query = ""
        if content.lower().startswith(f"{self.trigger_word} "):
            query = content[len(self.trigger_word):].strip()
        # No need to check `content.lower() == self.trigger_word` here if query remains ""
        
        # Handle case where user sent only the trigger word
        if not query and content.lower() == self.trigger_word:
            await bot.send_at_message(
                room_id or sender_id, # Target correct chat
                f"我是OpenManus智能助手(Gemini+TTS版)，请在触发词 '{self.trigger_word}' 后面输入您的问题。", 
                [sender_id] if room_id else [] # Only use at_list in groups
            )
            return False # Handled (sent help prompt)
        elif not query and not content.lower() == self.trigger_word:
             # This case should ideally not be reached if detect_trigger_keyword is working
             logger.warning(f"handle_text 收到非预期消息: {content}")
             return True # Not a valid trigger format for this handler
        
        # 检查是否是命令（如清除记忆等）
        command_handled = await self._handle_commands(bot, message, query)
        if command_handled:
            return False  # 命令已处理，不需要继续

        # 检查是否是绘图命令
        if query.lower().startswith("绘制") and self.enable_drawing:
            draw_handled = await self._handle_drawing_command(bot, message, query[2:].strip())
            if draw_handled:
                return False  # 绘图命令已处理，不需要继续

        # Call the core handler with the extracted query
        logger.debug(f"handle_text 调用 _handle_request, query: {query}")
        return await self._handle_request(bot, message, query)

    # 检查和处理消息中的ModelScope图片链接
    @on_text_message(priority=50)
    async def process_modelscope_image_links(self, bot: WechatAPIClient, message: dict):
        """检测并处理消息中的ModelScope图片链接"""
        if not self.enabled or not self.enable_drawing:
            return True  # 如果插件或绘图功能被禁用，跳过处理
            
        content = message.get("content", message.get("Content", "")).strip()
        
        # 检查消息是否来自机器人自己（避免消息循环）
        sender_id = message.get("SenderWxid", message.get("sender_id", ""))
        self_id = message.get("ToWxid", "")  # 机器人自己的ID
        if sender_id == self_id:
            return True  # 如果是机器人自己发送的消息，跳过处理
        
        # 检查消息是否包含ModelScope图片链接
        if "modelscope-studios.oss-cn-zhangjiakou.aliyuncs.com" in content and (".png" in content or ".jpg" in content):
            # 提取所有ModelScope图片链接
            urls = re.findall(r'https?://modelscope-studios\.oss-cn-zhangjiakou\.aliyuncs\.com/[^\s\]]+?(?:\.png|\.jpg)', content)
            if not urls:
                return True  # 没有找到有效的链接，继续其他处理
                
            # 处理消息发送目标
            is_group = message.get("IsGroup", False)
            user_id = message.get("SenderWxid", message.get("sender_id", ""))
            group_id = message.get("FromWxid") if is_group else None
            target_id = group_id if is_group else user_id
            
            # 创建后台任务下载并发送图片，不阻塞当前消息处理
            asyncio.create_task(self._download_and_send_image(bot, target_id, urls[0]))
            
        return True  # 继续处理其他消息
            
    async def _download_and_send_image(self, bot: WechatAPIClient, target_id: str, image_url: str):
        """后台下载并发送ModelScope图片
        
        Args:
            bot: WechatAPIClient实例
            target_id: 目标ID（群ID或用户ID）
            image_url: 图片URL
        """
        try:
            logger.info(f"【图片处理】开始后台下载图片: {image_url} 发送到: {target_id}")
            
            # 创建绘图工具实例
            agent = self._create_and_register_agent()
            if not agent:
                logger.error("【图片处理】无法创建代理实例来处理图片下载")
                return
                
            # 获取ModelScopeDrawingTool实例
            drawing_tool = None
            # 直接创建一个新的绘图工具实例，避免使用agent.tools
            drawing_config = self.config.get("drawing", {})
            drawing_tool = ModelScopeDrawingTool(
                api_base=drawing_config.get("api_base", "https://www.modelscope.cn/api/v1/muse/predict"),
                cookies=drawing_config.get("modelscope_cookies", ""),
                csrf_token=drawing_config.get("modelscope_csrf_token", ""),
                max_wait_time=drawing_config.get("max_wait_time", 120)
            )
            
            logger.info(f"【图片处理】成功创建绘图工具，准备下载图片: {image_url}")
                
            # 下载图片 - 改为直接返回图片内容
            local_path = None
            image_data = None
            
            try:
                # 直接下载图片内容
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    }
                    async with session.get(image_url, headers=headers) as response:
                        if response.status != 200:
                            logger.error(f"【图片处理】下载图片失败，状态码: {response.status}")
                            return None
                        
                        # 读取图片内容
                        image_data = await response.read()
                        data_length = len(image_data)
                        logger.debug(f"【图片处理】成功读取图片数据，大小: {data_length} 字节")
                        
                        if data_length < 100:
                            logger.error(f"【图片处理】图片数据异常，太小: {data_length} 字节")
                            return None
                            
                        logger.info(f"【图片处理】图片已成功下载，大小: {data_length} 字节")
            except Exception as e:
                logger.exception(f"【图片处理】下载图片时出错: {e}")
                return
                
            if not image_data:
                logger.error("【图片处理】下载图片失败，未获取到图片数据")
                return
                
            # 延迟一段时间后再发送图片（避免与文本回复过于接近）
            await asyncio.sleep(1.5)
                
            # 发送图片 - 直接使用图片内容而非文件路径
            try:
                if hasattr(bot, 'send_image_message'):
                    logger.info(f"【图片处理】使用send_image_message方法发送图片")
                    await bot.send_image_message(target_id, image=image_data)  # 直接传递图片内容
                    logger.info(f"【图片处理】成功发送图片到: {target_id}")
                elif hasattr(bot, 'SendImageMessage'):
                    logger.info(f"【图片处理】使用SendImageMessage方法发送图片")
                    await bot.SendImageMessage(target_id, image=image_data)  # 直接传递图片内容
                    logger.info(f"【图片处理】成功发送图片到: {target_id}")
                else:
                    logger.error("【图片处理】API不支持发送图片消息")
                    return
            except Exception as e:
                logger.exception(f"【图片处理】发送图片异常: {e}")
                
        except Exception as e:
            logger.exception(f"【图片处理】后台处理图片时发生异常: {e}")
            return

    def get_help(self) -> str:
        """返回插件帮助信息"""
        if not self.enabled:
            return "OpenManus插件当前已禁用。请配置正确的API密钥后重新启用。"
            
        basic_help = (
            f"OpenManus Gemini智能助手 v{self.version}\n"
            f"触发关键词: {self.trigger_word}\n\n"
            "支持功能:\n"
            "- 智能对话和问答\n"
            "- 使用搜索引擎查询信息\n"
            "- 数学计算和日期时间查询\n"
            "- 查询天气信息\n"
        )
        
        # Add TTS info if available
        tts_info = []
        if self.tts_enabled:
            tts_info.append("- Fish Audio TTS语音合成")
        if self.minimax_tts_enabled:
            tts_info.append("- MiniMax T2A v2语音合成")
            
        if tts_info:
            basic_help += "\n".join(tts_info) + "\n"
            
        usage_help = (
            "\n使用方法:\n"
            f"1. 直接发送: {self.trigger_word} 你的问题\n"
            "2. 群聊中@我 并提问\n\n"
            "示例:\n"
            f"{self.trigger_word} 帮我写一首短诗\n"
            f"{self.trigger_word} 查询北京今天的天气\n"
            f"{self.trigger_word} 计算 (245 + 37) * 1.5"
        )
        
        return basic_help + usage_help

    async def _handle_commands(self, bot: WechatAPIClient, message: dict, content: str):
        """处理内置命令，如清除记忆等"""
        user_id = message.get("sender_id", message.get("SenderWxid", ""))
        room_id = message.get("room_id", message.get("FromWxid", ""))
        target_id = room_id or user_id
        at_list = [user_id] if room_id and user_id else []
        session_id = target_id  # 使用同样的会话ID规则
        
        # 处理清除记忆/对话命令
        if content.strip().lower() in ["清除记忆", "清除对话", "忘记对话", "清除上下文"]:
            if self.gemini_client:
                self.gemini_client.clear_chat_history(session_id)
                await bot.send_at_message(
                    target_id,
                    "已清除与您的对话记忆，开始新的对话。",
                    at_list
                )
                return True  # 命令已处理
                
        return False  # 不是已知命令
        
    def normalize_text_for_tts(self, text):
        """
        规范化处理文本以便于TTS服务处理
        
        Args:
            text: 原始文本
            
        Returns:
            规范化后的文本
        """
        if not text:
            return ""
            
        # 1. 将连续多个换行符替换为单个换行
        text = re.sub(r'\n{2,}', '\n', text)
        
        # 2. 处理数字列表格式（如"1."开头的行）
        text = re.sub(r'(\n|^)(\d+)\.\s*', r'\1\2. ', text)
        
        # 3. 将单个换行符替换为适当的停顿标记（逗号或句号）
        text = re.sub(r'([^，。？！.,:;?!])\n([^\n])', r'\1，\2', text)
        
        # 4. 删除不必要的空白字符
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text

    async def send_tts_with_natural_breaks(self, bot, target_id, text, at_list=None):
        """
        一次性生成语音，分段发送TTS语音
        
        Args:
            bot: WechatAPIClient实例
            target_id: 目标ID (群或用户)
            text: 要转换为语音的文本
            at_list: @用户列表 (可选)
        
        Returns:
            bool: 是否成功处理
        """
        # 文本规范化处理，优化换行符和格式
        text = self.normalize_text_for_tts(text)
        
        # 临时文件列表 (用于清理)
        temp_files_to_clean = []
        
        # 1. 分段获取语音 - 将长文本分成较短的段落单独请求TTS，避免一次性请求过长文本
        segments = split_text_at_natural_breaks(text, max_duration_seconds=30)
        segment_count = len(segments)
        logger.info(f"已将文本分为 {segment_count} 个语音段落进行处理")
        
        # 如果分段数大于1，先发送提示信息
        if segment_count > 1:
            await bot.send_at_message(
                target_id, 
                f"回复内容较长，将分{segment_count}段发送，请稍候...", 
                at_list
            )
        
        # 逐段处理和发送
        success_count = 0
        for i, segment_text in enumerate(segments):
            segment_number = i + 1
            
            # 合成语音，带重试机制
            audio_data = None
            tts_method_used = None
            audio_format = None
            
            # 尝试重试TTS合成，最多3次
            max_retries = 3
            for retry in range(max_retries):
                try:
                    # 使用MiniMax TTS
                    if self.minimax_tts_enabled and self.minimax_tts_client:
                        audio_data = await self.minimax_tts_client.text_to_speech(
                            text=segment_text,
                            voice_id=self.minimax_tts_voice_id,
                            model=self.minimax_tts_model,
                            format="mp3", # 固定使用mp3格式获取
                            speed=self.minimax_tts_speed,
                            vol=self.minimax_tts_vol,
                            pitch=self.minimax_tts_pitch,
                            sample_rate=self.minimax_tts_sample_rate,
                            bitrate=self.minimax_tts_bitrate,
                            language_boost=self.minimax_tts_language_boost,
                            emotion=self.minimax_tts_emotion
                        )
                        if audio_data:
                            tts_method_used = "MiniMax TTS"
                            audio_format = "mp3" # 强制指定mp3格式
                            break  # 成功获取音频数据，跳出重试循环
                            
                    # 如果MiniMax失败，使用Fish Audio TTS
                    if not audio_data and self.tts_enabled and self.tts_client:
                        audio_data = await self.tts_client.text_to_speech(
                            text=segment_text,
                            format="mp3" # 固定使用mp3格式获取
                        )
                        if audio_data:
                            tts_method_used = "Fish Audio TTS"
                            audio_format = "mp3" # 强制指定mp3格式
                            break  # 成功获取音频数据，跳出重试循环
                            
                    if not audio_data and retry < max_retries - 1:
                        await asyncio.sleep(1)  # 重试前等待一会
                        
                except Exception as e:
                    logger.error(f"语音合成出错: {e}")
                    if retry < max_retries - 1:
                        await asyncio.sleep(1)  # 重试前等待一会
            
            # 如果获取到语音数据，处理并发送
            if audio_data and len(audio_data) > 100:  # 确保音频长度合理
                if audio_format == 'pcm': 
                    audio_format = 'wav'
                    
                # 使用唯一文件名并确保目录存在
                unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
                audio_file = f"segment_{segment_number}_{unique_id}.{audio_format}"
                audio_path = os.path.join(self.temp_audio_dir, audio_file)
                temp_files_to_clean.append(audio_path)
                
                try:
                    # 确保临时目录存在
                    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
                    
                    # 保存音频数据
                    async with aiofiles.open(audio_path, 'wb') as f:
                        await f.write(audio_data)
                    
                    # 验证音频文件是否有效
                    try:
                        # 尝试使用pydub加载音频文件以验证其有效性
                        audio_segment = AudioSegment.from_file(audio_path, format=audio_format)
                        duration_ms = len(audio_segment)
                        
                        # 直接使用原格式发送
                        try:
                            # 读取MP3音频数据
                            async with aiofiles.open(audio_path, 'rb') as f:
                                audio_bytes = await f.read()
                            
                            format_to_send = audio_format  # 直接使用MP3格式
                            
                        except Exception as conv_err:
                            # 读取失败，使用原始音频
                            logger.warning(f"读取音频数据时出错: {conv_err}")
                            async with aiofiles.open(audio_path, 'rb') as f:
                                audio_bytes = await f.read()
                            format_to_send = audio_format
                        
                        # BASE64编码和音频检查
                        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                        
                        # 发送语音
                        success = await self._send_voice_message(bot, target_id, audio_base64, format_to_send, segment_number, segment_count)
                        
                        if success:
                            success_count += 1
                        else:
                            # 发送失败时尝试发送文本
                            await bot.send_at_message(target_id, f"(语音发送失败，文本内容): {segment_text}", at_list)
                            
                    except Exception as audio_err:
                        logger.error(f"处理音频文件时出错: {audio_err}")
                        # 音频处理出错，尝试直接发送原始数据
                        async with aiofiles.open(audio_path, 'rb') as f:
                            audio_bytes = await f.read()
                            
                        # BASE64编码和发送
                        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                        success = await self._send_voice_message(bot, target_id, audio_base64, audio_format, segment_number, segment_count)
                        
                        if success:
                            success_count += 1
                        else:
                            # 发送失败时发送文本
                            await bot.send_at_message(target_id, f"(语音处理出错，文本内容): {segment_text}", at_list)
                    
                    # 片段之间等待一小段时间
                    if i < segment_count - 1:
                        await asyncio.sleep(2)  # 避免发送太快
                        
                except Exception as e:
                    logger.error(f"处理和发送语音段落时出错: {e}")
                    # 出错时尝试发送文本
                    await bot.send_at_message(target_id, f"(语音处理出错): {segment_text}", at_list)
            else:
                # 语音合成失败时发送文本
                await bot.send_at_message(target_id, f"(语音合成失败): {segment_text}", at_list)
        
        # 总结发送情况
        logger.info(f"总共处理了 {segment_count} 个语音段落，成功发送: {success_count}个")
        
        # 清理临时文件
        for temp_file in temp_files_to_clean:
            if temp_file and os.path.exists(temp_file):
                try:
                    if hasattr(aiofiles, 'os') and hasattr(aiofiles.os, 'remove'):
                        await aiofiles.os.remove(temp_file)
                    else:
                        os.remove(temp_file)
                except OSError as oe:
                    logger.error(f"清理临时语音文件失败: {oe}")
        
        return True
        
    async def _send_voice_message(self, bot, target_id, audio_base64, audio_format, chunk_index=1, total_chunks=1):
        """封装发送语音消息的逻辑，包括重试
        
        Args:
            bot: WechatAPIClient实例
            target_id: 目标ID
            audio_base64: BASE64编码的音频数据
            audio_format: 音频格式
            chunk_index: 当前片段索引
            total_chunks: 总片段数
            
        Returns:
            bool: 是否发送成功
        """
        max_retries = 3
        success = False
        method_used = None
        
        # 尝试重试发送语音，最多3次
        for retry in range(max_retries):
            try:
                if hasattr(bot, 'send_voice_message'):
                    method_used = 'send_voice_message'
                    send_result = await bot.send_voice_message(
                        target_id, 
                        audio_base64, 
                        format=audio_format
                    )
                    # 检查发送结果
                    if isinstance(send_result, tuple) and len(send_result) >= 3:
                        success = True
                    elif send_result is not None and send_result is not False:
                        success = True
                elif hasattr(bot, 'SendVoiceMessage'):
                    method_used = 'SendVoiceMessage'
                    send_result = await bot.SendVoiceMessage(
                        target_id, 
                        audio_base64, 
                        format=audio_format
                    )
                    # 检查发送结果
                    if isinstance(send_result, tuple) and len(send_result) >= 3:
                        success = True
                    elif send_result is not None and send_result is not False:
                        success = True
                else:
                    logger.error(f"语音发送失败: API不支持发送语音消息")
                    break
                
                if success:
                    break  # 发送成功，跳出重试循环
                elif retry < max_retries - 1:
                    await asyncio.sleep(2)  # 重试前等待
            except Exception as e:
                logger.error(f"发送语音出错: {e}")
                if retry < max_retries - 1:
                    await asyncio.sleep(2)  # 重试前等待
        
        return success

    async def _handle_drawing_command(self, bot: WechatAPIClient, message: dict, prompt: str) -> bool:
        """专门处理绘图命令
        
        Args:
            bot: WechatAPIClient实例
            message: 消息字典
            prompt: 绘图提示词（已去除"绘制"前缀）
            
        Returns:
            bool: 是否成功处理
        """
        if not self.enable_drawing:
            return False
            
        # 提取发送目标
        from_user_id = message.get("sender_id", message.get("SenderWxid", ""))
        room_id = message.get("room_id", message.get("FromWxid", ""))
        target_id = room_id or from_user_id
        
        # 创建绘图工具
        drawing_config = self.config.get("drawing", {})
        drawing_tool = ModelScopeDrawingTool(
            api_base=drawing_config.get("api_base", "https://www.modelscope.cn/api/v1/muse/predict"),
            cookies=drawing_config.get("modelscope_cookies", ""),
            csrf_token=drawing_config.get("modelscope_csrf_token", ""),
            max_wait_time=drawing_config.get("max_wait_time", 120)
        )
        
        # 获取所有可用的模型名称（包括自定义LoRA）
        available_models = list(drawing_tool.model_config.keys()) + ["custom"]
        
        # 构建模型正则表达式模式
        models_pattern = "|".join([re.escape(model) + "风格" for model in available_models])
        # 添加默认格式
        models_pattern += "|默认风格|动漫风格|写实风格"
        
        # 提取模型和比例参数
        model_match = re.search(fr'({models_pattern})', prompt)
        ratio_match = re.search(r'比例为?(1:1|4:3|3:4|16:9|9:16)', prompt)
        
        # 默认使用配置文件中的默认模型
        model_name = drawing_config.get("default_model", "rioko")
        if model_match:
            style = model_match.group(1)
            if style == "默认风格":
                model_name = "default"
            elif style == "动漫风格":
                model_name = "anime"
            elif style == "写实风格":
                model_name = "realistic"
            elif style.endswith("风格"):
                # 提取自定义模型名（去掉"风格"后缀）
                custom_name = style[:-2]
                if custom_name in available_models:
                    model_name = custom_name
        
        ratio = drawing_config.get("default_ratio", "1:1")
        if ratio_match:
            ratio = ratio_match.group(1)
        
        # 提取自定义LoRA参数
        lora_model_match = re.search(r'使用LoRA[模型]?[:|：]?\s*(\S+)', prompt)
        lora_scale_match = re.search(r'LoRA权重[:|：]?\s*(\d+\.?\d*)', prompt)
        
        lora_model_id = ""
        lora_scale = drawing_config.get("default_lora_scale", 1.0)
        
        if lora_model_match:
            lora_model_id = lora_model_match.group(1)
            model_name = "custom"
        
        if lora_scale_match:
            try:
                lora_scale = float(lora_scale_match.group(1))
            except ValueError:
                pass
        
        # 移除风格、比例和LoRA相关参数，保留纯净的提示词
        clean_prompt = prompt
        clean_prompt = re.sub(fr'({models_pattern}|比例为?(?:1:1|4:3|3:4|16:9|9:16))', '', clean_prompt)
        clean_prompt = re.sub(r'使用LoRA[模型]?[:|：]?\s*\S+', '', clean_prompt)
        clean_prompt = re.sub(r'LoRA权重[:|：]?\s*\d+\.?\d*', '', clean_prompt)
        clean_prompt = clean_prompt.strip()
        
        # 发送等待消息
        await bot.send_text_message(target_id, f"正在生成图像，请稍候...")
        
        try:
            # 准备绘图参数
            drawing_params = {
                "prompt": clean_prompt,
                "model": model_name,
                "ratio": ratio
            }
            
            # 添加自定义LoRA参数
            if model_name == "custom":
                drawing_params["lora_model_id"] = lora_model_id
                drawing_params["lora_scale"] = lora_scale
            
            # 执行绘图
            logger.info(f"执行绘图: {drawing_params}")
            result = await drawing_tool.execute(**drawing_params)
            
            # 处理绘图结果
            if result and result.get("success"):
                # 获取图片URL
                image_url = result.get("image_url")
                if image_url:
                    # 发送图片URL和提示词信息
                    await bot.send_text_message(
                        target_id, 
                        f"✅ 图像已生成！\n使用模型: {result.get('model', model_name)}\n{result.get('lora_info', '')}\n图像链接: {image_url}"
                    )
                    
                    # 尝试发送实际图片
                    try:
                        await drawing_tool.send_generated_image(bot, target_id, image_url)
                    except Exception as img_err:
                        logger.error(f"发送生成图片时出错: {img_err}")
                        await bot.send_text_message(target_id, f"⚠️ 图片发送失败，请通过链接查看")
                else:
                    await bot.send_text_message(target_id, "⚠️ 图像已生成但URL为空，请稍后重试")
            else:
                # 处理错误情况
                error_msg = result.get("error", "未知错误") if result else "图像生成失败"
                await bot.send_text_message(target_id, f"❌ 生成图像失败: {error_msg}")
            
            return True  # 命令已处理
        except Exception as e:
            logger.exception(f"处理绘图命令时出错: {e}")
            await bot.send_text_message(target_id, f"❌ 处理绘图命令时出错: {str(e)}")
            return True  # 命令已处理但出错

# --- Plugin Registration and Exports ---
plugin_instance = OpenManus()

# Keep these simple exports pointing to the instance methods or basic info
async def handle_message(msg_data):
    """Main entry point, delegates to instance methods via decorators."""
    # The decorators @on_text_message and @on_at_message on the
    # OpenManus class methods handle the actual message processing.
    # This function might be called by the loader but doesn't need logic itself.
    pass 

def get_help():
    """Returns help string from the plugin instance."""
    return plugin_instance.get_help()

def get_info():
    """Returns basic info about the plugin."""
    return {
        "name": plugin_instance.name,
        "version": plugin_instance.version,
        "author": plugin_instance.author,
        "description": plugin_instance.description,
        "trigger_word": plugin_instance.trigger_word,
        "enabled": plugin_instance.enabled # Add enabled status from instance
    } 