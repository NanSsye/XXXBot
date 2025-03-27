import os
import sys
import json
import time
import asyncio
import threading
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any, Union, Set

import uvicorn
from fastapi import FastAPI, Request, Response, Depends, HTTPException, WebSocket, WebSocketDisconnect, Body, File, Form, UploadFile
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from itsdangerous import URLSafeSerializer
from functools import wraps

from loguru import logger
import psutil
import platform
import socket
import re
import glob
import subprocess
import shutil
import inspect
import aiohttp
import base64
import httpx
import requests
import zipfile
import io
# 使用try-except导入rarfile和py7zr
try:
    import rarfile
    # 配置rarfile使用的工具路径，尝试多个可能的位置
    rarfile.UNRAR_TOOL = "unrar"  # 默认命令
    # 如果是Windows，尝试常见的安装位置
    if os.name == 'nt':
        possible_paths = [
            r"C:\Program Files\WinRAR\UnRAR.exe",
            r"C:\Program Files\WinRAR\unrar.exe",
            r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
            r"C:\Program Files (x86)\WinRAR\unrar.exe"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                rarfile.UNRAR_TOOL = path
                logger.info(f"设置rarfile使用的unrar路径: {path}")
                break
    logger.info(f"rarfile配置完成，使用的unrar工具路径: {rarfile.UNRAR_TOOL}")
except ImportError:
    rarfile = None
    logger.warning("rarfile库不可用，无法使用Python处理RAR文件")

try:
    import py7zr
except ImportError:
    py7zr = None
# import patoolib  # 删除此行，因为patoolib不可用

# 确保当前目录在sys.path中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# 全局变量
app = FastAPI(title="XYBotV2管理后台")
security = HTTPBasic()
templates = None
bot_instance = None
config = {
    "host": "0.0.0.0",
    "port": 8080,
    "username": "admin",
    "password": "admin123",
    "debug": False,
    "secret_key": "xybotv2_admin_secret_key",
    "max_history": 1000
}

# WebSocket连接
active_connections: List[WebSocket] = []

# 加载配置
def load_config():
    global config
    try:
        config_path = os.path.join(current_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                loaded_config = json.load(f)
                config.update(loaded_config)
                logger.info(f"管理后台配置已加载: {config_path}")
    except Exception as e:
        logger.error(f"加载管理后台配置失败: {str(e)}")

# 安全验证
def verify_credentials(credentials: HTTPBasicCredentials):
    """验证用户凭据"""
    correct_username = config["username"]
    correct_password = config["password"]
    
    if (credentials.username != correct_username or 
        credentials.password != correct_password):
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# WebSocket连接管理
async def connect_websocket(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
async def disconnect_websocket(websocket: WebSocket):
    if websocket in active_connections:
        active_connections.remove(websocket)
        
async def broadcast_message(message: str):
    """向所有WebSocket连接广播消息"""
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except Exception as e:
            logger.error(f"广播消息失败: {str(e)}")
            await disconnect_websocket(connection)

# 系统信息
def get_system_info():
    """获取系统信息"""
    try:
        # 获取基本系统信息
        import platform
        import psutil
        import socket
        
        hostname = socket.gethostname()
        platform_info = platform.platform()
        python_version = platform.python_version()
        
        # 获取CPU信息
        try:
            cpu_count = psutil.cpu_count(logical=True)
            cpu_percent = psutil.cpu_percent(interval=0.1)
            if cpu_count is None:
                cpu_count = psutil.cpu_count(logical=False)
        except Exception as e:
            logger.error(f"获取CPU信息失败: {str(e)}")
            cpu_count = 0
            cpu_percent = 0
        
        # 获取内存信息
        try:
            memory = psutil.virtual_memory()
            memory_total = memory.total
            memory_available = memory.available
            memory_used = memory.used
            memory_percent = memory.percent
        except Exception as e:
            logger.error(f"获取内存信息失败: {str(e)}")
            memory_total = 0
            memory_available = 0
            memory_used = 0
            memory_percent = 0
        
        # 获取磁盘信息
        try:
            disk = psutil.disk_usage('/')
            disk_total = disk.total
            disk_free = disk.free
            disk_used = disk.used
            disk_percent = disk.percent
        except Exception as e:
            logger.error(f"获取磁盘信息失败: {str(e)}")
            disk_total = 0
            disk_free = 0
            disk_used = 0
            disk_percent = 0
        
        # 获取系统启动时间
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            uptime_str = str(timedelta(seconds=int(uptime.total_seconds())))
        except Exception as e:
            logger.error(f"获取系统启动时间失败: {str(e)}")
            boot_time = datetime.now()
            uptime_str = "未知"

        return {
            "hostname": hostname,
            "platform": platform_info,
            "python_version": python_version,
            "cpu_count": cpu_count,
            "cpu_percent": cpu_percent,
            "memory_total": memory_total,
            "memory_available": memory_available,
            "memory_used": memory_used,
            "memory_percent": memory_percent,
            "disk_total": disk_total,
            "disk_free": disk_free,
            "disk_used": disk_used,
            "disk_percent": disk_percent,
            "boot_time": boot_time.strftime("%Y-%m-%d %H:%M:%S"),
            "uptime": uptime_str,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "os": platform.system(),
            "version": platform.version(),
            "processor": platform.processor()
        }
    except Exception as e:
        logger.error(f"获取系统信息失败: {str(e)}")
        # 返回基本信息
        import platform
        return {
            "hostname": "unknown",
            "platform": "unknown",
            "python_version": platform.python_version(),
            "cpu_count": 0,
            "cpu_percent": 0,
            "memory_total": 0,
            "memory_available": 0,
            "memory_used": 0,
            "memory_percent": 0,
            "disk_total": 0,
            "disk_free": 0,
            "disk_used": 0,
            "disk_percent": 0,
            "boot_time": "unknown",
            "uptime": "unknown",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "os": platform.system(),
            "version": platform.version(),
            "processor": platform.processor()
        }

def get_system_status():
    """获取系统运行状态信息"""
    try:
        import psutil
        from datetime import datetime, timedelta
        
        # 获取CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.5)
        
        # 获取内存使用情况
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used = memory.used
        memory_total = memory.total
        
        # 获取磁盘使用情况
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used = disk.used
        disk_total = disk.total
        
        # 获取网络信息
        net_io_counters = psutil.net_io_counters()
        bytes_sent = net_io_counters.bytes_sent
        bytes_recv = net_io_counters.bytes_recv
        
        # 获取系统启动时间和运行时间
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        uptime_str = str(timedelta(seconds=int(uptime.total_seconds())))
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'memory_used': memory_used,
            'memory_total': memory_total,
            'disk_percent': disk_percent,
            'disk_used': disk_used,
            'disk_total': disk_total,
            'bytes_sent': bytes_sent,
            'bytes_recv': bytes_recv,
            'uptime': uptime_str,
            'start_time': boot_time.strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        logger.error(f"获取系统状态信息失败: {str(e)}")
        return {
            'cpu_percent': 0,
            'memory_percent': 0,
            'memory_used': 0,
            'memory_total': 0,
            'disk_percent': 0,
            'disk_used': 0,
            'disk_total': 0,
            'bytes_sent': 0,
            'bytes_recv': 0,
            'uptime': "未知",
            'start_time': "未知"
        }

# 设置bot实例
def set_bot_instance(bot):
    """设置bot实例，用于后台管理界面访问"""
    global bot_instance
    bot_instance = bot
    logger.info("管理后台已设置bot实例")
    
    # 不再需要添加get_contacts方法，因为我们直接使用wxapi.get_contract_list
    
    # 保存到临时文件，确保子进程能够访问
    try:
        with open(os.path.join(current_dir, "bot_instance_status.txt"), "w", encoding="utf-8") as f:
            f.write(f"bot_instance_set: {datetime.now().isoformat()}")
    except Exception as e:
        logger.error(f"保存bot实例状态失败: {e}")
    
    return bot_instance

# 联系人获取辅助方法
def get_contacts_from_bot(bot):
    """从机器人实例获取联系人列表"""
    contacts = []
    try:
        # 尝试从wxapi获取联系人 - 仅使用同步方法
        if hasattr(bot, 'wxapi'):
            try:
                logger.debug("尝试直接获取wxapi相关属性而不调用异步方法")
                # 查看wxapi有哪些可用属性，可能有已缓存的联系人列表
                wxapi_attrs = [attr for attr in dir(bot.wxapi) if not attr.startswith('_')]
                logger.debug(f"wxapi可用属性: {wxapi_attrs}")
                
                # 检查是否有contacts或contact_list属性
                if hasattr(bot.wxapi, 'contacts') and bot.wxapi.contacts:
                    contacts = bot.wxapi.contacts
                    logger.info(f"从wxapi.contacts属性获取到{len(contacts)}个联系人")
                    return contacts
                elif hasattr(bot.wxapi, 'contact_list') and bot.wxapi.contact_list:
                    contacts = bot.wxapi.contact_list
                    logger.info(f"从wxapi.contact_list属性获取到{len(contacts)}个联系人")
                    return contacts
            except Exception as e:
                logger.error(f"访问wxapi属性失败: {e}")

        # 尝试调用直接获取实时联系人的其他方法
        logger.warning("无法从wxapi获取联系人，可能需要实现更多方法")
        
        # 如果无法获取联系人，返回空列表
        return []
    except Exception as e:
        logger.error(f"获取联系人失败: {e}")
        return []

# 直接定义状态更新函数，不依赖导入
def update_bot_status(status, details=None, extra_data=None):
    """更新bot状态，供管理后台读取"""
    try:
        # 直接使用绝对路径写入状态文件
        status_file = Path(current_dir) / "bot_status.json"
        
        # 读取当前状态
        current_status = {}
        if status_file.exists():
            with open(status_file, "r", encoding="utf-8") as f:
                current_status = json.load(f)
        
        # 更新状态
        current_status["status"] = status
        current_status["timestamp"] = time.time()
        if details:
            current_status["details"] = details
            
            # 检查详情中是否包含二维码URL
            qrcode_pattern = re.compile(r'获取到登录二维码: (https?://[^\s]+)')
            match = qrcode_pattern.search(str(details))
            if match:
                qrcode_url = match.group(1)
                logger.debug(f"从状态详情中提取到二维码URL: {qrcode_url}")
                current_status["qrcode_url"] = qrcode_url
            
            # 检查详情中是否包含UUID
            uuid_pattern = re.compile(r'获取到登录uuid: ([^\s]+)')
            match = uuid_pattern.search(str(details))
            if match:
                uuid = match.group(1)
                logger.debug(f"从状态详情中提取到UUID: {uuid}")
                current_status["uuid"] = uuid
                
                # 如果有uuid但没有qrcode_url，尝试构建
                if "qrcode_url" not in current_status:
                    current_status["qrcode_url"] = f"https://api.pwmqr.com/qrcode/create/?url=http://weixin.qq.com/x/{uuid}"
                    logger.debug(f"根据UUID构建二维码URL: {current_status['qrcode_url']}")
            
        # 添加额外数据
        if extra_data and isinstance(extra_data, dict):
            for key, value in extra_data.items():
                current_status[key] = value
                
            # 特别处理extra_data中的二维码信息
            if "qrcode_url" in extra_data:
                logger.debug(f"从extra_data中获取二维码URL: {extra_data['qrcode_url']}")
                
            if "uuid" in extra_data and "qrcode_url" not in current_status:
                current_status["qrcode_url"] = f"https://api.pwmqr.com/qrcode/create/?url=http://weixin.qq.com/x/{extra_data['uuid']}"
                logger.debug(f"根据extra_data中的UUID构建二维码URL: {current_status['qrcode_url']}")
        
        # 确保目录存在
        status_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(current_status, f)
            
        logger.debug(f"成功更新bot状态: {status}")
        logger.debug(f"状态文件内容: qrcode_url={current_status.get('qrcode_url', None)}, uuid={current_status.get('uuid', None)}")
        
        # 复制一份到根目录供其他模块使用
        try:
            root_status_file = Path(current_dir).parent / "bot_status.json"
            with open(root_status_file, "w", encoding="utf-8") as f:
                json.dump(current_status, f)
            logger.debug(f"已复制状态文件到根目录: {root_status_file}")
        except Exception as e:
            logger.error(f"复制状态文件到根目录失败: {e}")
    except Exception as e:
        logger.error(f"更新bot状态失败: {e}")

# 从状态文件获取bot状态
def get_bot_status():
    """从状态文件获取bot的最新状态"""
    try:
        # 使用统一的状态文件路径
        status_file = Path(current_dir) / "bot_status.json"
        root_status_file = Path(current_dir).parent / "bot_status.json"
        
        logger.debug(f"尝试读取状态文件: {status_file}, 备选: {root_status_file}")
        
        # 优先读取管理后台目录中的状态文件
        if os.path.exists(status_file):
            with open(status_file, "r", encoding="utf-8") as f:
                status_data = json.load(f)
                # 添加调试日志
                logger.debug(f"读取状态文件成功: {status_file}")
                # 特别检查个人信息
                if "nickname" in status_data:
                    logger.debug(f"状态文件中包含昵称: {status_data['nickname']}")
                if "wxid" in status_data:
                    logger.debug(f"状态文件中包含微信ID: {status_data['wxid']}")
                if "alias" in status_data:
                    logger.debug(f"状态文件中包含微信号: {status_data['alias']}")
                # 特别检查二维码URL
                if "qrcode_url" in status_data:
                    logger.debug(f"状态文件中包含二维码URL: {status_data['qrcode_url']}")
                else:
                    logger.debug("状态文件中不包含二维码URL")
                    
                # 检查日志信息中是否包含二维码URL
                if "details" in status_data:
                    qrcode_pattern = re.compile(r'获取到登录二维码: (https?://[^\s]+)')
                    match = qrcode_pattern.search(str(status_data['details']))
                    if match:
                        qrcode_url = match.group(1)
                        logger.debug(f"从状态详情中提取到二维码URL: {qrcode_url}")
                        status_data["qrcode_url"] = qrcode_url
                
                # 检查是否包含uuid，用于构建二维码
                if "uuid" in status_data:
                    logger.debug(f"状态文件中包含UUID: {status_data['uuid']}")
                    # 如果有uuid但没有qrcode_url，尝试构建
                    if "qrcode_url" not in status_data:
                        status_data["qrcode_url"] = f"https://api.pwmqr.com/qrcode/create/?url=http://weixin.qq.com/x/{status_data['uuid']}"
                        logger.debug(f"根据UUID构建二维码URL: {status_data['qrcode_url']}")
                
                return status_data
        
        # 如果管理后台目录中的状态文件不存在，尝试读取根目录中的状态文件
        if os.path.exists(root_status_file):
            with open(root_status_file, "r", encoding="utf-8") as f:
                status_data = json.load(f)
                logger.debug(f"从根目录读取状态文件成功: {root_status_file}")
                
                # 特别检查个人信息
                if "nickname" in status_data:
                    logger.debug(f"状态文件中包含昵称: {status_data['nickname']}")
                if "wxid" in status_data:
                    logger.debug(f"状态文件中包含微信ID: {status_data['wxid']}")
                if "alias" in status_data:
                    logger.debug(f"状态文件中包含微信号: {status_data['alias']}")
                
                # 特别检查二维码URL
                if "qrcode_url" in status_data:
                    logger.debug(f"状态文件中包含二维码URL: {status_data['qrcode_url']}")
                else:
                    logger.debug("状态文件中不包含二维码URL")
                    
                # 检查日志信息中是否包含二维码URL
                if "details" in status_data:
                    qrcode_pattern = re.compile(r'获取到登录二维码: (https?://[^\s]+)')
                    match = qrcode_pattern.search(str(status_data['details']))
                    if match:
                        qrcode_url = match.group(1)
                        logger.debug(f"从状态详情中提取到二维码URL: {qrcode_url}")
                        status_data["qrcode_url"] = qrcode_url
                
                # 检查是否包含uuid，用于构建二维码
                if "uuid" in status_data:
                    logger.debug(f"状态文件中包含UUID: {status_data['uuid']}")
                    # 如果有uuid但没有qrcode_url，尝试构建
                    if "qrcode_url" not in status_data:
                        status_data["qrcode_url"] = f"https://api.pwmqr.com/qrcode/create/?url=http://weixin.qq.com/x/{status_data['uuid']}"
                        logger.debug(f"根据UUID构建二维码URL: {status_data['qrcode_url']}")
                
                # 同时将数据复制到管理后台目录中
                try:
                    with open(status_file, "w", encoding="utf-8") as fw:
                        json.dump(status_data, fw)
                    logger.debug("已将根目录状态文件同步到管理后台目录")
                except Exception as e:
                    logger.error(f"同步状态文件失败: {e}")
                
                return status_data
        
        # 尝试从用户提供的日志中提取二维码信息
        logger.debug("状态文件不存在，尝试从日志中提取二维码信息")
        # 读取最新的日志文件
        log_dir = Path(__file__).parent.parent / "logs"
        if log_dir.exists():
            log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
            if log_files:
                latest_log = log_files[0]
                try:
                    with open(latest_log, "r", encoding="utf-8", errors="ignore") as f:
                        log_content = f.read()
                        
                        # 提取uuid和二维码URL
                        uuid_pattern = re.compile(r'获取到登录uuid: ([^\s]+)')
                        qrcode_pattern = re.compile(r'获取到登录二维码: (https?://[^\s]+)')
                        
                        uuid_match = uuid_pattern.search(log_content)
                        qrcode_match = qrcode_pattern.search(log_content)
                        
                        if uuid_match and qrcode_match:
                            uuid = uuid_match.group(1)
                            qrcode_url = qrcode_match.group(1)
                            logger.debug(f"从日志中提取到UUID: {uuid} 和二维码URL: {qrcode_url}")
                            
                            # 创建状态数据
                            status_data = {
                                "status": "waiting_login",
                                "timestamp": time.time(),
                                "uuid": uuid,
                                "qrcode_url": qrcode_url,
                                "details": f"等待微信扫码登录, 二维码: {qrcode_url}"
                            }
                            
                            # 保存状态数据到文件
                            try:
                                with open(status_file, "w", encoding="utf-8") as fw:
                                    json.dump(status_data, fw)
                                logger.debug("已将从日志提取的二维码信息保存到状态文件")
                            except Exception as e:
                                logger.error(f"保存状态文件失败: {e}")
                            
                            return status_data
                except Exception as e:
                    logger.error(f"读取日志文件失败: {e}")
        
        # 状态文件不存在时返回默认状态
        logger.debug("状态文件不存在，返回默认状态")
        return {
            "status": "unknown",
            "timestamp": time.time(),
            "initialized": False,
            "details": "等待状态更新"
        }
    except Exception as e:
        logger.error(f"读取bot状态文件失败: {e}")
        return {"status": "error", "error": str(e), "timestamp": time.time()}

# 初始化FastAPI应用
def init_app():
    global templates
    # 配置模板目录
    templates_dir = os.path.join(current_dir, "templates")
    templates = Jinja2Templates(directory=templates_dir)
    
    # 配置静态文件目录
    static_dir = os.path.join(current_dir, "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="admin.static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # 添加中间件
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 加载路由
    setup_routes()
    
    logger.info(f"管理后台初始化完成，将在 {config['host']}:{config['port']} 上启动")

def setup_routes():
    # 登录页面
    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        return templates.TemplateResponse(
            "login.html", 
            {
                "request": request
            }
        )
    
    # API: 重启容器
    @app.post("/api/system/restart", response_class=JSONResponse)
    async def api_restart_container(request: Request):
        """重启容器API"""
        # 检查认证状态
        try:
            username = await check_auth(request)
            if not username:
                return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
        except Exception as e:
            logger.error(f"认证检查失败: {str(e)}")
            return JSONResponse(status_code=401, content={"success": False, "error": "认证失败"})
        
        try:
            logger.info(f"用户 {username} 请求重启容器")
            
            # 创建一个后台任务来执行重启
            async def restart_task():
                # 在函数内部导入所需模块，避免作用域问题
                import os
                import sys
                import asyncio
                import subprocess
                from pathlib import Path
                
                # 等待1秒让响应先返回
                await asyncio.sleep(1)
                logger.warning("正在重启容器...")
                
                # 检测是否在Docker容器中运行
                in_docker = os.path.exists('/.dockerenv') or os.path.exists('/app/.dockerenv')
                logger.info(f"是否在Docker环境中: {in_docker}")
                
                if in_docker:
                    # Docker环境下的重启策略
                    logger.info("在Docker环境中运行，使用Docker特定的重启方法")
                    
                    # 方法1: 尝试向自己发送SIGTERM信号，让Docker重启策略生效
                    try:
                        import signal
                        logger.info("尝试向PID 1发送SIGTERM信号")
                        os.kill(1, signal.SIGTERM)
                        # 等待信号生效
                        await asyncio.sleep(5)
                    except Exception as e:
                        logger.error(f"发送SIGTERM失败: {e}")
                    
                    # 方法2: 尝试使用docker命令重启当前容器
                    try:
                        # 获取当前容器ID
                        container_id = subprocess.check_output(["cat", "/proc/self/cgroup"]).decode('utf-8')
                        if 'docker' in container_id:
                            # 提取容器ID
                            for line in container_id.splitlines():
                                if 'docker' in line:
                                    parts = line.split('/')
                                    if len(parts) > 2:
                                        container_id = parts[-1]
                                        logger.info(f"检测到容器ID: {container_id}")
                                        # 尝试使用docker命令重启
                                        cmd = f"docker restart {container_id}"
                                        logger.info(f"执行命令: {cmd}")
                                        # 使用一个简单的Shell脚本来执行docker命令
                                        restart_cmd = f"sleep 2 && {cmd} &"
                                        subprocess.Popen(["sh", "-c", restart_cmd])
                                        break
                    except Exception as e:
                        logger.error(f"使用docker命令重启失败: {e}")
                    
                    # 方法3: 最后的方法，直接退出进程，依靠Docker的自动重启策略
                    logger.info("使用最后的方法: 直接退出进程")
                    os._exit(1)  # 使用非零退出码，通常会触发Docker的重启策略
                
                else:
                    # 非Docker环境下的重启策略
                    # 获取当前脚本的路径和执行命令
                    current_file = os.path.abspath(__file__)
                    parent_dir = os.path.dirname(current_file)
                    run_server_path = os.path.join(parent_dir, "run_server.py")
                    
                    # 确定Python解释器路径
                    python_executable = sys.executable or "python"
                    
                    # 获取当前工作目录
                    cwd = os.getcwd()
                    
                    # 创建一个重启脚本，保证在当前进程结束后仍能启动新进程
                    restart_script = os.path.join(parent_dir, "restart_helper.py")
                    
                    logger.info(f"创建重启辅助脚本: {restart_script}")
                    try:
                        with open(restart_script, 'w') as f:
                            f.write(f"""#!/usr/bin/env python
import os
import sys
import time
import subprocess

# 等待原进程结束
time.sleep(2)

# 重启服务器
cmd = ["{python_executable}", "{run_server_path}"]
print("执行重启命令:", " ".join(cmd))
subprocess.Popen(cmd, cwd="{cwd}", shell=False)

# 删除自身
try:
    os.remove(__file__)
except:
    pass
""")
                    except Exception as e:
                        logger.error(f"创建重启脚本失败: {e}")
                        return
                    
                    # 使脚本可执行
                    try:
                        os.chmod(restart_script, 0o755)
                    except Exception as e:
                        logger.warning(f"设置重启脚本权限失败: {e}")
                    
                    # 启动重启脚本
                    logger.info(f"启动重启脚本: {restart_script}")
                    try:
                        if sys.platform.startswith('win'):
                            # Windows
                            subprocess.Popen([python_executable, restart_script], 
                                            creationflags=subprocess.DETACHED_PROCESS)
                        else:
                            # Linux/Unix
                            subprocess.Popen([python_executable, restart_script], 
                                            start_new_session=True)
                    except Exception as e:
                        logger.error(f"启动重启脚本失败: {e}")
                        return
                
                # 等待一点时间让重启脚本启动
                await asyncio.sleep(1)
                
                # 结束当前进程
                logger.info("正在关闭当前进程...")
                try:
                    os._exit(0)
                except Exception as e:
                    logger.error(f"关闭进程失败: {e}")
                    sys.exit(0)
            
            # 启动后台任务
            asyncio.create_task(restart_task())
            
            # 使用明确的JSONResponse返回
            return JSONResponse(content={
                "success": True,
                "message": "容器正在重启，页面将在几秒后自动刷新..."
            })
        except Exception as e:
            logger.error(f"重启容器失败: {str(e)}")
            return JSONResponse(content={
                "success": False,
                "error": f"重启容器失败: {str(e)}"
            })
    
    # 用户登录API
    @app.post("/api/auth/login", response_class=JSONResponse)
    async def login_api(request: Request, response: Response):
        try:
            data = await request.json()
            username = data.get("username")
            password = data.get("password")
            remember = data.get("remember", False)
            
            # 验证用户名和密码
            if username == config["username"] and password == config["password"]:
                # 创建会话数据
                session_data = {
                    "authenticated": True,
                    "username": username,
                    "expires": time.time() + (30 * 24 * 60 * 60 if remember else 24 * 60 * 60)  # 30天或1天
                }
                
                # 序列化会话数据
                serializer = URLSafeSerializer(config["secret_key"], "session")
                session_str = serializer.dumps(session_data)
                
                # 直接设置Cookie
                response.set_cookie(
                    key="session", 
                    value=session_str,
                    max_age=30 * 24 * 60 * 60 if remember else None,  # 30天或浏览器关闭时
                    path="/",
                    httponly=True,
                    samesite="lax"
                )
                
                # 调试日志
                logger.debug(f"用户 {username} 登录成功，已设置会话Cookie，有效期：{'30天' if remember else '浏览器会话'}")
                
                return {"success": True, "message": "登录成功"}
            else:
                return {"success": False, "error": "用户名或密码错误"}
        except Exception as e:
            logger.error(f"登录处理出错: {str(e)}")
            return {"success": False, "error": f"登录处理出错: {str(e)}"}
    
    # 检查会话认证
    async def check_auth(request: Request):
        """检查用户是否已认证"""
        try:
            # 从Cookie中获取会话数据
            session_cookie = request.cookies.get("session")
            if not session_cookie:
                logger.debug("未找到会话Cookie")
                return None
            
            # 调试日志
            logger.debug(f"获取到会话Cookie: {session_cookie[:15]}...")
            
            # 解码会话数据
            try:
                serializer = URLSafeSerializer(config["secret_key"], "session")
                session_data = serializer.loads(session_cookie)
                
                # 输出会话数据，辅助调试
                logger.debug(f"解析会话数据成功: {session_data}")
                
                # 检查会话是否已过期
                expires = session_data.get("expires", 0)
                if expires < time.time():
                    logger.debug(f"会话已过期: 当前时间 {time.time()}, 过期时间 {expires}")
                    return None
                
                # 会话有效
                logger.debug(f"会话有效，用户: {session_data.get('username')}")
                return session_data.get("username")
            except Exception as e:
                logger.error(f"解析会话数据失败: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"检查认证失败: {str(e)}")
            return None

    def require_auth(func):
        """认证装饰器"""
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            check_auth(request)
            return await func(request, *args, **kwargs)
        return wrapper

    # 主页
    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            # 未认证，重定向到登录页面
            return RedirectResponse(url="/login")
        
        # 获取系统状态信息
        system_info = get_system_info()
        system_status = get_system_status()
        
        return templates.TemplateResponse(
            "index.html", 
            {
                "request": request, 
                "bot": bot_instance,
                "active_page": "index",
                "system_info": system_info,
                "uptime": system_status["uptime"],
                "start_time": system_status["start_time"],
                "memory_usage": f"{system_status['memory_percent']}%",
                "memory_percent": system_status["memory_percent"],
                "cpu_percent": system_status["cpu_percent"],
                "current_time": datetime.now().strftime("%H:%M:%S")
            }
        )
    
    @app.get("/index", response_class=HTMLResponse)
    async def index(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            # 未认证，重定向到登录页面
            return RedirectResponse(url="/login")
        
        # 获取系统状态信息
        system_info = get_system_info()
        system_status = get_system_status()
        
        return templates.TemplateResponse(
            "index.html", 
            {
                "request": request, 
                "bot": bot_instance,
                "active_page": "index",
                "system_info": system_info,
                "uptime": system_status["uptime"],
                "start_time": system_status["start_time"],
                "memory_usage": f"{system_status['memory_percent']}%",
                "memory_percent": system_status["memory_percent"],
                "cpu_percent": system_status["cpu_percent"],
                "current_time": datetime.now().strftime("%H:%M:%S")
            }
        )
    
    # 插件管理页面
    @app.get("/plugins", response_class=HTMLResponse)
    async def plugins_page(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            # 未认证，重定向到登录页面
            return RedirectResponse(url="/login")
        
        return templates.TemplateResponse(
            "plugins.html", 
            {
                "request": request, 
                "bot": bot_instance,
                "active_page": "plugins"
            }
        )
    
    # 联系人页面
    @app.get("/contacts", response_class=HTMLResponse)
    async def contacts_page(request: Request):
        # 检查认证状态
        try:
            username = await check_auth(request)
            if not username:
                # 未认证，重定向到登录页面
                return RedirectResponse(url="/login?next=/contacts", status_code=303)
                
            logger.debug(f"用户 {username} 访问联系人页面")
            # 认证成功，显示联系人页面
            return templates.TemplateResponse("contacts.html", {
                "request": request,
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            logger.error(f"访问联系人页面失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
    
    # 系统状态页面
    @app.get("/system", response_class=HTMLResponse)
    async def system_page(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            # 未认证，重定向到登录页面
            return RedirectResponse(url="/login")
        
        try:
            # 获取系统状态信息
            system_info = get_system_info()
            system_status = get_system_status()
            
            # 获取联系人信息
            contact_stats = {'total': 0, 'friends': 0, 'groups': 0, 'official': 0}
            
            logger.debug(f"系统信息: {system_info}")
            logger.debug(f"系统状态: {system_status}")
            
            return templates.TemplateResponse(
                "system.html", 
                {
                    "request": request, 
                    "bot": bot_instance,
                    "active_page": "system",
                    "system_info": system_info,
                    "system_status": system_status,
                    "contact_stats": contact_stats
                }
            )
        except Exception as e:
            logger.error(f"系统页面渲染失败: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # API: 系统状态 (需要认证)
    @app.get("/api/system/status", response_class=JSONResponse)
    async def api_system_status(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
            
        return {
            "success": True,
            "data": get_system_status()
        }
    
    # API: 系统信息 (需要认证)
    @app.get("/api/system/info", response_class=JSONResponse)
    async def api_system_info(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
            
        try:
            # 获取系统信息
            info = get_system_info()
            return {
                "success": True,
                "data": info,
                "error": None
            }
        except Exception as e:
            logger.error(f"获取系统信息API失败: {str(e)}")
            # 返回默认值但标记为成功，避免前端显示错误
            return JSONResponse(content={
                "success": True,  # 改为True，即使获取失败也不显示错误
                "data": {
                    "hostname": socket.gethostname() if hasattr(socket, 'gethostname') else "unknown",
                    "platform": platform.platform() if hasattr(platform, 'platform') else "unknown",
                    "python_version": platform.python_version() if hasattr(platform, 'python_version') else "unknown",
                    "cpu_count": 0,
                    "memory_total": 0,
                    "memory_available": 0,
                    "disk_total": 0,
                    "disk_free": 0,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "error": str(e)
            })
    
    # API: 机器人状态 (需要认证)
    @app.get("/api/bot/status", response_class=JSONResponse)
    async def api_bot_status(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        # 不需要认证也可以查看状态
        #if not username:
        #    return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
            
        try:
            # 获取状态数据
            status_data = get_bot_status()
            logger.debug(f"API获取bot状态: {status_data}")
            
            # 添加bot实例的一些信息（如果可用）
            if bot_instance and hasattr(bot_instance, 'wxid') and status_data.get("status") in ["online", "ready"]:
                try:
                    # 避免覆盖状态文件中已有的信息
                    if not status_data.get("nickname"):
                        status_data["nickname"] = bot_instance.nickname
                    if not status_data.get("wxid"):    
                        status_data["wxid"] = bot_instance.wxid
                    if not status_data.get("alias"):
                        status_data["alias"] = bot_instance.alias
                    
                    logger.debug(f"从bot_instance添加的信息: nickname={bot_instance.nickname}, wxid={bot_instance.wxid}, alias={bot_instance.alias}")
                except Exception as e:
                    logger.error(f"获取bot实例信息失败: {e}")
            else:
                # 直接从状态文件中获取信息
                logger.debug(f"bot_instance不可用或状态不是online/ready，使用状态文件中的信息")
                
                # 确保状态数据中有个人信息字段(即使是空值)
                for field in ["nickname", "wxid", "alias"]:
                    if field not in status_data:
                        status_data[field] = None
            
            # 再次确认返回的字段
            logger.debug(f"最终返回的状态数据: nickname={status_data.get('nickname')}, wxid={status_data.get('wxid')}, alias={status_data.get('alias')}")
            
            return {"success": True, "data": status_data}
        except Exception as e:
            logger.error(f"获取bot状态失败: {e}")
            return {"success": False, "error": str(e)}
    
    # API: 获取插件列表
    @app.get("/api/plugins", response_class=JSONResponse)
    async def api_plugins_list(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
            
        try:
            # 使用try-except语句导入插件管理器
            try:
                from utils.plugin_manager import plugin_manager
                
                # 获取插件信息列表
                plugins_info = plugin_manager.get_plugin_info()
                
                # 确保返回的数据是可序列化的
                if not isinstance(plugins_info, list):
                    plugins_info = []
                    logger.error("plugin_manager.get_plugin_info()返回了非列表类型")
                
                # 记录调试信息
                logger.debug(f"获取到{len(plugins_info)}个插件信息")
                
                return {
                    "success": True,
                    "data": {
                        "plugins": plugins_info
                    }
                }
            except ImportError as e:
                logger.error(f"导入plugin_manager失败: {str(e)}")
                return {"success": False, "error": f"导入plugin_manager失败: {str(e)}"}
        except Exception as e:
            logger.error(f"获取插件信息失败: {str(e)}")
            return {"success": False, "error": f"获取插件信息失败: {str(e)}"}
    
    # API: 启用插件
    @app.post("/api/plugins/{plugin_name}/enable", response_class=JSONResponse)
    async def api_enable_plugin(plugin_name: str, request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
            
        try:
            from utils.plugin_manager import plugin_manager
            
            success = await plugin_manager.load_plugin_from_directory(bot_instance, plugin_name)
            return {"success": success}
        except Exception as e:
            logger.error(f"启用插件失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # API: 禁用插件
    @app.post("/api/plugins/{plugin_name}/disable", response_class=JSONResponse)
    async def api_disable_plugin(plugin_name: str, request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
            
        try:
            from utils.plugin_manager import plugin_manager
            
            success = await plugin_manager.unload_plugin(plugin_name)
            return {"success": success}
        except Exception as e:
            logger.error(f"禁用插件失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # 辅助函数: 查找插件配置路径
    def find_plugin_config_path(plugin_id: str):
        """查找插件配置文件路径，尝试多个可能的位置"""
        possible_paths = [
            os.path.join("plugins", plugin_id, "config.toml"),  # 原始路径
            os.path.join("_data", "plugins", plugin_id, "config.toml"),  # _data目录下的路径
            os.path.join("..", "plugins", plugin_id, "config.toml"),  # 相对上级目录
            os.path.abspath(os.path.join("plugins", plugin_id, "config.toml")),  # 绝对路径
            os.path.join(os.path.dirname(os.path.dirname(current_dir)), "plugins", plugin_id, "config.toml")  # 项目根目录
        ]
        
        # 检查环境变量定义的数据目录
        data_dir_env = os.environ.get('XYBOT_DATA_DIR')
        if data_dir_env:
            possible_paths.append(os.path.join(data_dir_env, "plugins", plugin_id, "config.toml"))
        
        # 检查Docker环境特定路径
        if os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv'):
            docker_paths = [
                os.path.join("/app/data/plugins", plugin_id, "config.toml"),
                os.path.join("/data/plugins", plugin_id, "config.toml"),
                os.path.join("/usr/local/xybot/plugins", plugin_id, "config.toml")
            ]
            possible_paths.extend(docker_paths)
        
        # 查找第一个存在的路径
        for path in possible_paths:
            if os.path.exists(path):
                logger.debug(f"找到插件配置文件: {path}")
                return path
        
        return None

    # API: 获取插件配置
    @app.get("/api/plugin_config", response_class=JSONResponse)
    async def api_get_plugin_config(plugin_id: str, request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
        
        try:
            import tomllib
            
            # 查找配置文件路径
            config_path = find_plugin_config_path(plugin_id)
            if not config_path:
                return {"success": False, "message": f"插件 {plugin_id} 的配置文件不存在"}
            
            # 读取配置
            with open(config_path, "rb") as f:
                config_content = tomllib.load(f)
            
            return {
                "success": True,
                "config": config_content
            }
        except Exception as e:
            logger.error(f"获取插件配置失败: {str(e)}")
            return {"success": False, "error": str(e)}

    # API: 保存插件配置
    @app.post("/api/save_plugin_config", response_class=JSONResponse)
    async def api_save_plugin_config(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
        
        try:
            # 获取请求数据
            data = await request.json()
            plugin_id = data.get('plugin_id')
            config = data.get('config')
            
            if not plugin_id or not config:
                return {"success": False, "message": "缺少必要参数"}
            
            # 找到配置文件路径
            config_path = find_plugin_config_path(plugin_id)
            if not config_path:
                # 如果配置文件不存在，创建默认位置
                config_path = os.path.join("plugins", plugin_id, "config.toml")
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            # 生成TOML内容
            toml_content = ""
            for section, values in config.items():
                toml_content += f"[{section}]\n"
                for key, value in values.items():
                    if isinstance(value, str):
                        toml_content += f'{key} = "{value}"\n'
                    elif isinstance(value, bool):
                        toml_content += f"{key} = {str(value).lower()}\n"
                    else:
                        toml_content += f"{key} = {value}\n"
                toml_content += "\n"
            
            # 保存配置
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(toml_content)
            
            return {"success": True, "message": "配置已保存"}
        except Exception as e:
            logger.error(f"保存插件配置失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # 插件市场API配置
    PLUGIN_MARKET_API = {
        "BASE_URL": "https://xianan.xin:1562/api",  # 修改这一行
        "LIST": "/plugins?status=approved",
        "SUBMIT": "/plugins",
        "INSTALL": "/plugins/install/",
        "CACHE_FILE": os.path.join(current_dir, "_cache", "plugin_market.json"),
        "CACHE_DIR": os.path.join(current_dir, "_cache"),
        "TEMP_DIR": os.path.join(current_dir, "_temp"),
        "SYNC_INTERVAL": 3600  # 1小时
    }
    
    # 确保缓存和临时目录存在
    os.makedirs(PLUGIN_MARKET_API["CACHE_DIR"], exist_ok=True)
    os.makedirs(PLUGIN_MARKET_API["TEMP_DIR"], exist_ok=True)
    
    # 获取客户端唯一标识
    def get_client_id():
        client_id_file = os.path.join(PLUGIN_MARKET_API["CACHE_DIR"], "client_id")
        
        # 如果文件存在，读取ID
        if os.path.exists(client_id_file):
            with open(client_id_file, "r") as f:
                return f.read().strip()
        
        # 生成新ID
        import uuid
        client_id = str(uuid.uuid4())
        
        # 保存到文件
        with open(client_id_file, "w") as f:
            f.write(client_id)
        
        return client_id
    
    # 获取Bot版本信息
    def get_bot_version():
        """获取Bot版本信息"""
        try:
            from .config import VERSION
            return VERSION
        except ImportError:
            return "1.0.0"
    
    # 获取系统信息
    def get_system_info():
        import platform
        return {
            "os": platform.system(),
            "version": platform.version(),
            "processor": platform.processor(),
            "python": platform.python_version()
        }
    
    # API: 获取插件市场列表
    @app.get("/api/plugin_market", response_class=JSONResponse)
    async def api_get_plugin_market(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
            
        try:
            # 实例化httpx客户端
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 构建请求头
                headers = {
                    "X-Client-ID": get_client_id(),
                    "X-Bot-Version": get_bot_version(),
                    "User-Agent": f"XYBot/{get_bot_version()}"
                }
                
                try:
                    # 请求远程API
                    response = await client.get(
                        f"{PLUGIN_MARKET_API['BASE_URL']}{PLUGIN_MARKET_API['LIST']}",
                        headers=headers
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    # 缓存结果
                    with open(PLUGIN_MARKET_API["CACHE_FILE"], "w", encoding="utf-8") as f:
                        json.dump({
                            "timestamp": int(time.time()),
                            "data": data
                        }, f, ensure_ascii=False, indent=2)
                    
                    return data
                    
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    logger.error(f"从远程获取插件市场数据失败: {str(e)}")
                    # 尝试从缓存加载
                    return await load_plugin_market_from_cache()
                    
        except Exception as e:
            logger.error(f"获取插件市场失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # 从缓存加载插件市场数据
    async def load_plugin_market_from_cache():
        try:
            if not os.path.exists(PLUGIN_MARKET_API["CACHE_FILE"]):
                return {"success": False, "error": "无法连接到插件市场服务器，且无本地缓存"}
            
            with open(PLUGIN_MARKET_API["CACHE_FILE"], "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            
            # 检查缓存是否过期（7天）
            if int(time.time()) - cache_data.get("timestamp", 0) > 7 * 24 * 3600:
                return {
                    "success": True,
                    "plugins": cache_data.get("data", {}).get("plugins", []),
                    "message": "显示的是缓存数据，可能已过期"
                }
            
            return {
                "success": True,
                "plugins": cache_data.get("data", {}).get("plugins", []),
                "message": "显示的是缓存数据"
            }
            
        except Exception as e:
            logger.error(f"从缓存加载插件市场数据失败: {str(e)}")
            return {"success": False, "error": f"加载缓存数据失败: {str(e)}"}
    
    # API: 提交插件到市场
    @app.post("/api/plugin_market/submit", response_class=JSONResponse)
    async def api_submit_plugin(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
            
        try:
            # 获取表单数据
            data = await request.json()
            
            # 验证必要字段
            required_fields = ["name", "description", "author", "version", "github_url"]
            for field in required_fields:
                if not data.get(field):
                    return {"success": False, "error": f"缺少必要字段: {field}"}
            
            # 添加客户端信息
            if "client_info" not in data:
                data["client_info"] = {
                    "id": get_client_id(),
                    "version": get_bot_version(),
                    "system": get_system_info()
                }
            
            # 添加状态和时间戳
            data["status"] = "pending"
            data["submitted_at"] = int(time.time())
            
            # 如果有图标，处理Base64
            if "icon" in data and data["icon"]:
                try:
                    # 处理图标上传，转为Base64
                    icon_file = data["icon"]
                    import base64
                    icon_data = base64.b64encode(icon_file).decode('utf-8')
                    data["icon"] = icon_data
                except Exception as e:
                    logger.error(f"处理图标失败: {str(e)}")
                    # 移除有问题的图标
                    data.pop("icon", None)
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                # 构建请求头
                headers = {
                    "X-Client-ID": get_client_id(),
                    "X-Bot-Version": get_bot_version(),
                    "Content-Type": "application/json",
                    "User-Agent": f"XYBot/{get_bot_version()}"
                }
                
                try:
                    # 发送到远程API
                    response = await client.post(
                        f"{PLUGIN_MARKET_API['BASE_URL']}{PLUGIN_MARKET_API['SUBMIT']}",
                        headers=headers,
                        json=data
                    )
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    return result
                    
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    logger.error(f"提交插件到远程服务器失败: {str(e)}")
                    
                    # 保存到本地临时文件，稍后同步
                    temp_file = os.path.join(
                        PLUGIN_MARKET_API["TEMP_DIR"], 
                        f"plugin_submit_{int(time.time())}_{data['name'].replace(' ', '_')}.json"
                    )
                    
                    with open(temp_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    
            return {
                "success": False,
                        "error": f"无法连接到服务器: {str(e)}",
                        "message": "提交已保存到本地，将在网络恢复后自动同步"
                    }
                    
        except Exception as e:
            logger.error(f"提交插件失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # API: 安装插件
    @app.post("/api/plugin_market/install", response_class=JSONResponse)
    async def api_install_plugin(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
            
        try:
            # 获取请求数据
            data = await request.json()
            plugin_name = data.get("plugin_id")
            plugin_data = data.get("plugin_data")
            
            if not plugin_name:
                return {"success": False, "error": "缺少插件ID"}
            
            if not plugin_data:
                # 如果没有传递插件数据，则从远程获取
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # 构建请求头
                    headers = {
                        "X-Client-ID": get_client_id(),
                        "X-Bot-Version": get_bot_version(),
                        "User-Agent": f"XYBot/{get_bot_version()}"
                    }
                    
                    try:
                        # 请求远程API
                        response = await client.get(
                            f"{PLUGIN_MARKET_API['BASE_URL']}/plugins/{plugin_name}",
                            headers=headers
                        )
                        
                        response.raise_for_status()
                        result = response.json()
                        
                        if not result.get("success"):
                            return result
                        
                        plugin_data = result.get("plugin")
                        
                    except (httpx.HTTPError, httpx.TimeoutException) as e:
                        logger.error(f"从远程获取插件详情失败: {str(e)}")
                        return {"success": False, "error": f"无法连接到服务器: {str(e)}"}
            
            # 获取插件名称（用于创建目录）
            plugin_name = plugin_data.get("name", "").replace(" ", "_")  # 保留原始大小写
            if not plugin_name:
                return {"success": False, "error": "无法获取插件名称"}
            
            # 创建临时目录
            import tempfile
            import shutil
            from pathlib import Path
            import zipfile
            import io
            import requests
            import sys
            import subprocess
            
            temp_dir = tempfile.mkdtemp()
            plugin_dir = os.path.join("plugins", plugin_name)
            
            try:
                # 下载插件代码
                github_url = plugin_data.get("github_url")
                if not github_url:
                    return {"success": False, "error": "缺少GitHub链接"}
                
                # 构建GitHub仓库ZIP下载链接
                if github_url.endswith('.git'):
                    github_url = github_url[:-4]
                
                # 尝试下载main分支
                zip_url = f"{github_url}/archive/refs/heads/main.zip"
                logger.info(f"正在从 {zip_url} 下载插件...")
                
                try:
                    response = requests.get(zip_url, timeout=30)
                    if response.status_code != 200:
                        # 尝试使用master分支
                        zip_url = f"{github_url}/archive/refs/heads/master.zip"
                        logger.info(f"尝试从master分支下载: {zip_url}")
                        response = requests.get(zip_url, timeout=30)
                        
                    if response.status_code != 200:
                        return {"success": False, "error": f"下载插件失败: HTTP {response.status_code}"}
                    
                    # 解压ZIP文件到临时目录
                    z = zipfile.ZipFile(io.BytesIO(response.content))
                    z.extractall(temp_dir)
                    
                    # 检查插件是否已存在
                    if os.path.exists(plugin_dir):
                        # 如果存在，先备份配置文件
                        config_path = os.path.join(plugin_dir, "config.toml")
                        config_backup = None
                        if os.path.exists(config_path):
                            with open(config_path, "rb") as f:
                                config_backup = f.read()
                        
                        # 删除旧目录
                        shutil.rmtree(plugin_dir)
                    
                    # 创建插件目录
                    os.makedirs(plugin_dir, exist_ok=True)
                    
                    # ZIP文件解压后通常会有一个包含所有文件的顶级目录
                    extracted_dirs = os.listdir(temp_dir)
                    if len(extracted_dirs) == 1:
                        extract_subdir = os.path.join(temp_dir, extracted_dirs[0])
                        
                        # 将文件从解压的子目录复制到目标目录
                        for item in os.listdir(extract_subdir):
                            s = os.path.join(extract_subdir, item)
                            d = os.path.join(plugin_dir, item)
                            if os.path.isdir(s):
                                shutil.copytree(s, d, dirs_exist_ok=True)
                            else:
                                shutil.copy2(s, d)
                    else:
                        # 直接从临时目录复制文件
                        for item in os.listdir(temp_dir):
                            s = os.path.join(temp_dir, item)
                            d = os.path.join(plugin_dir, item)
                            if os.path.isdir(s):
                                shutil.copytree(s, d, dirs_exist_ok=True)
                            else:
                                shutil.copy2(s, d)
                    
                    # 恢复配置文件（如果有）
                    if config_backup:
                        with open(config_path, "wb") as f:
                            f.write(config_backup)
                    else:
                        # 确保创建一个空的配置文件（防止加载插件时出错）
                        config_path = os.path.join(plugin_dir, "config.toml")
                        if not os.path.exists(config_path):
                            with open(config_path, "w", encoding="utf-8") as f:
                                f.write("# 插件配置文件\n")
                    
                    # 安装依赖
                    requirements_file = os.path.join(plugin_dir, "requirements.txt")
                    if os.path.exists(requirements_file):
                        logger.info(f"正在安装插件依赖...")
                        process = subprocess.Popen(
                            [sys.executable, "-m", "pip", "install", "-r", requirements_file],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        stdout, stderr = process.communicate()
                        
                        if process.returncode != 0:
                            logger.warning(f"安装依赖可能失败: {stderr.decode('utf-8', errors='ignore')}")
                    
                    # 安装完成后，立即加载插件
                    try:
                        from utils.plugin_manager import plugin_manager
                        await plugin_manager.load_plugin_from_directory(bot_instance, plugin_name)
                    except Exception as e:
                        logger.warning(f"自动加载插件失败，用户需要手动启用: {str(e)}")
                    
                    return {"success": True, "message": "插件安装成功"}
                    
                except Exception as e:
                    logger.error(f"下载和安装插件失败: {str(e)}")
                    return {"success": False, "error": f"安装失败: {str(e)}"}
                
            finally:
                # 清理临时目录
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                
        except Exception as e:
            logger.error(f"安装插件失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # 周期性任务：同步本地待处理的插件提交到服务器
    async def sync_pending_plugins():
        while True:
            try:
                # 等待一段时间
                await asyncio.sleep(PLUGIN_MARKET_API["SYNC_INTERVAL"])
                
                # 检查临时目录中的提交文件
                temp_files = glob.glob(os.path.join(PLUGIN_MARKET_API["TEMP_DIR"], "plugin_submit_*.json"))
                
                if not temp_files:
                    continue
                
                logger.info(f"开始同步 {len(temp_files)} 个待处理的插件提交")
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    # 构建请求头
                    headers = {
                        "X-Client-ID": get_client_id(),
                        "X-Bot-Version": get_bot_version(),
                        "Content-Type": "application/json",
                        "User-Agent": f"XYBot/{get_bot_version()}"
                    }
                    
                    for temp_file in temp_files:
                        try:
                            # 读取提交数据
                            with open(temp_file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            
                            # 发送到远程API
                            response = await client.post(
                                f"{PLUGIN_MARKET_API['BASE_URL']}{PLUGIN_MARKET_API['SUBMIT']}",
                                headers=headers,
                                json=data
                            )
                            
                            if response.status_code == 200:
                                # 提交成功，删除临时文件
                                os.remove(temp_file)
                                logger.info(f"成功同步插件提交: {os.path.basename(temp_file)}")
                            else:
                                logger.warning(f"同步插件提交失败: {response.status_code} - {response.text}")
                                
                        except Exception as e:
                            logger.error(f"同步插件提交失败: {str(e)}")
                
            except Exception as e:
                logger.error(f"执行同步待处理插件任务失败: {str(e)}")
    
    # 周期性任务：缓存插件市场数据
    async def cache_plugin_market_data():
        while True:
            try:
                # 等待一段时间
                await asyncio.sleep(PLUGIN_MARKET_API["SYNC_INTERVAL"])
                
                logger.info("开始缓存插件市场数据")
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # 构建请求头
                    headers = {
                        "X-Client-ID": get_client_id(),
                        "X-Bot-Version": get_bot_version(),
                        "User-Agent": f"XYBot/{get_bot_version()}"
                    }
                    
                    try:
                        # 请求远程API
                        response = await client.get(
                            f"{PLUGIN_MARKET_API['BASE_URL']}{PLUGIN_MARKET_API['LIST']}",
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            # 缓存结果
                            with open(PLUGIN_MARKET_API["CACHE_FILE"], "w", encoding="utf-8") as f:
                                json.dump({
                                    "timestamp": int(time.time()),
                                    "data": data
                                }, f, ensure_ascii=False, indent=2)
                                
                            logger.info("成功缓存插件市场数据")
                        else:
                            logger.warning(f"缓存插件市场数据失败: {response.status_code} - {response.text}")
                            
                    except Exception as e:
                        logger.error(f"获取插件市场数据失败: {str(e)}")
                
            except Exception as e:
                logger.error(f"执行缓存插件市场数据任务失败: {str(e)}")
    
    # 启动周期性任务
    @app.on_event("startup")
    async def start_periodic_tasks():
        # 启动同步待处理插件任务
        asyncio.create_task(sync_pending_plugins())
        # 启动缓存插件市场数据任务
        asyncio.create_task(cache_plugin_market_data())
    
    # API: 获取LoginQR接口
    @app.get('/api/bot/login_qrcode')
    async def api_login_qrcode(request: Request):
        """获取登录二维码URL"""
        try:
            # 读取bot状态 - 修复：get_bot_status是同步函数，不需要await
            status_data = get_bot_status()
            
            logger.debug(f"获取二维码API被调用，状态数据: {status_data}")
            
            # 先检查状态数据中是否有二维码URL
            if status_data and "qrcode_url" in status_data:
                logger.info(f"从状态文件获取到二维码URL: {status_data['qrcode_url']}")
                # 添加或更新时间戳和有效期
                if "timestamp" not in status_data:
                    status_data["timestamp"] = time.time()
                if "expires_in" not in status_data:
                    status_data["expires_in"] = 240
                    
                # 当状态文件中的二维码URL是最新的
                return {
                    "success": True,
                    "data": {
                        "qrcode_url": status_data["qrcode_url"],
                        "expires_in": status_data["expires_in"],
                        "timestamp": status_data["timestamp"],
                        "uuid": status_data.get("uuid", "")
                    }
                }
                
            # 检查状态日志中是否有二维码信息
            if status_data and "details" in status_data:
                logger.debug(f"检查状态详情中的二维码信息: {status_data['details']}")
                qrcode_pattern = re.compile(r'(https?://[^\s]+)')
                match = qrcode_pattern.search(str(status_data['details']))
                if match:
                    qrcode_url = match.group(1)
                    logger.info(f"从状态详情中提取二维码URL: {qrcode_url}")
                    return {
                        "success": True,
                        "data": {
                            "qrcode_url": qrcode_url,
                            "expires_in": 240,
                            "timestamp": time.time(),
                            "uuid": status_data.get("uuid", "")
                        }
                    }
            
            # 如果状态文件中没有二维码URL，则尝试从日志中获取
            logger.warning("状态文件中没有二维码URL，尝试从日志获取")
            qrcode_data = await get_qrcode_from_logs()
            if qrcode_data and "qrcode_url" in qrcode_data:
                # 发现了二维码URL，更新状态
                logger.info(f"从日志中获取到二维码URL: {qrcode_data['qrcode_url']}")
                
                # 同时更新状态文件，确保下次能直接从状态文件获取
                status_path = Path(__file__).parent / "bot_status.json"
                if status_data:
                    status_data.update(qrcode_data)
                else:
                    status_data = {
                        "status": "waiting_login",
                        "details": "等待微信扫码登录",
                        "timestamp": time.time(),
                        **qrcode_data
                    }
                    
                with open(status_path, "w", encoding="utf-8") as f:
                    json.dump(status_data, f)
                    logger.info("已更新二维码URL到状态文件")
                
                return {
                    "success": True,
                    "data": {
                        "qrcode_url": qrcode_data["qrcode_url"],
                        "expires_in": qrcode_data.get("expires_in", 240),
                        "timestamp": qrcode_data.get("timestamp", time.time()),
                        "uuid": qrcode_data.get("uuid", "")
                    }
                }
            
            # 直接从提供的uuid构建二维码URL
            if status_data and "uuid" in status_data:
                logger.info(f"尝试从uuid构建二维码URL: {status_data['uuid']}")
                qrcode_url = f"https://api.pwmqr.com/qrcode/create/?url=http://weixin.qq.com/x/{status_data['uuid']}"
                return {
                    "success": True,
                    "data": {
                        "qrcode_url": qrcode_url,
                        "expires_in": 240,
                        "timestamp": time.time(),
                        "uuid": status_data["uuid"]
                    }
                }
            
            # 如果都没有找到二维码URL，则返回错误
            logger.error("无法获取二维码URL")
            return {
                "success": False,
                "error": "未找到二维码URL，请在终端查看并手动输入",
                "debug_info": status_data
            }
        except Exception as e:
            logger.exception(f"获取登录二维码URL失败: {e}")
            return {
                "success": False,
                "error": f"获取登录二维码失败: {str(e)}"
            }
    
    # 路由别名 - 为兼容性提供相同功能的别名路由
    @app.get('/api/login/qrcode')
    async def api_login_qrcode_alias(request: Request):
        """获取登录二维码URL（路由别名）"""
        logger.info("通过别名路由/api/login/qrcode请求二维码")
        return await api_login_qrcode(request)

    async def get_qrcode_from_logs():
        """从日志文件中获取二维码URL"""
        try:
            # 获取最新的日志文件
            log_dir = Path(__file__).parent.parent / "logs"
            if not log_dir.exists():
                logger.warning("日志目录不存在")
                return None
            
            # 查找最新的日志文件
            log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
            if not log_files:
                logger.warning("未找到日志文件")
                return None
            
            # 读取最新的日志文件，最后100行
            latest_log = log_files[0]
            logger.debug(f"读取最新日志文件: {latest_log}")
            
            # 使用系统命令获取最后100行
            if os.name == "nt":  # Windows
                cmd = f'powershell -command "Get-Content -Tail 100 \"{latest_log}\""'
            else:  # Linux/Unix
                cmd = f'tail -n 100 "{latest_log}"'
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            log_content = result.stdout
            
            # 正则表达式匹配二维码URL
            qrcode_pattern = re.compile(r'获取到登录二维码: (https?://[^\s]+)')
            match = qrcode_pattern.search(log_content)
            
            if match:
                qrcode_url = match.group(1)
                logger.success(f"从日志中获取到二维码URL: {qrcode_url}")
                
                # 检查URL有效性
                if not qrcode_url.startswith("http"):
                    logger.warning(f"获取到的二维码URL格式不正确: {qrcode_url}")
                    return None
                
                return {
                    "qrcode_url": qrcode_url,
                    "expires_in": 240,  # 默认240秒过期
                    "timestamp": time.time()
                }
            
            logger.warning("在日志中未找到二维码URL")
            return None
        except Exception as e:
            logger.exception(f"从日志获取二维码URL失败: {e}")
            return None
    
    # WebSocket连接
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await connect_websocket(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                # 这里可以处理从客户端接收的数据
                await websocket.send_text(f"已收到: {data}")
        except WebSocketDisconnect:
            await disconnect_websocket(websocket)

    @app.route('/qrcode')
    async def page_qrcode(request):
        """二维码页面，不需要认证"""
        return templates.TemplateResponse("qrcode.html", {"request": request})

    @app.route('/qrcode_redirect')
    async def qrcode_redirect(request):
        """二维码重定向API，用于将用户从主页重定向到二维码页面"""
        return RedirectResponse(url='/qrcode')

    # 添加文件管理集成页面路由
    @app.get("/files", response_class=HTMLResponse)
    async def files_integrated(request: Request):
        """集成到主界面的文件管理页面"""
        try:
            # 检查认证状态
            username = await check_auth(request)
            if not username:
                # 未认证，重定向到登录页面
                return RedirectResponse(url="/login", status_code=303)
                
            logger.debug(f"用户 {username} 访问集成文件管理器页面")
            # 认证成功，显示集成了文件管理器的界面
            return templates.TemplateResponse("files_integrated.html", {"request": request})
        except Exception as e:
            logger.error(f"访问文件管理器集成页面失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"服务器错误: {str(e)}"}
            )

    # 添加文件管理API
    @app.get("/file-manager", response_class=HTMLResponse)
    async def file_manager(request: Request):
        """文件管理页面"""
        # 使用会话验证
        try:
            # 检查认证状态
            username = await check_auth(request)
            if not username:
                # 记录调试信息
                logger.debug("文件管理器页面访问失败：未认证")
                # 未认证，重定向到登录页面
                return RedirectResponse(url="/login", status_code=303)
                
            logger.debug(f"用户 {username} 访问文件管理器页面")
            # 认证成功，显示文件管理器页面
            return templates.TemplateResponse("file-manager.html", {"request": request})
        except Exception as e:
            logger.error(f"访问文件管理器页面失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"服务器错误: {str(e)}"}
            )
    
    @app.get("/api/files/list")
    async def api_files_list(request: Request, path: str = "/", page: int = 1, limit: int = 100):
        """获取文件列表，支持分页加载"""
        # 使用会话验证
        try:
            # 记录调试日志
            logger.debug(f"请求获取文件列表：路径 {path}，页码 {page}，每页数量 {limit}")
            
            # 检查认证状态
            username = await check_auth(request)
            if not username:
                # 记录调试信息
                logger.debug("文件列表API访问失败：未认证")
                return JSONResponse(status_code=401, content={
                    'success': False, 
                    'message': '未认证，请先登录'
                })
            
            # 处理相对路径
            if not path.startswith('/'):
                path = '/' + path
            
            # 获取完整路径 - 从项目根目录开始
            root_dir = Path(current_dir).parent
            full_path = root_dir / path.lstrip('/')
            
            logger.debug(f"处理文件列表路径: {path} -> {full_path}")
            
            # 安全检查：确保路径在项目目录内
            if not os.path.abspath(full_path).startswith(os.path.abspath(root_dir)):
                logger.warning(f"尝试访问不安全的路径: {full_path}")
                return JSONResponse(status_code=403, content={
                    'success': False, 
                    'message': '无法访问项目目录外的文件'
                })
            
            # 检查路径是否存在
            if not os.path.exists(full_path):
                logger.warning(f"路径不存在: {full_path}")
                return JSONResponse(status_code=404, content={
                    'success': False, 
                    'message': '路径不存在'
                })
            
            # 检查路径是否是目录
            if not os.path.isdir(full_path):
                logger.warning(f"路径不是目录: {full_path}")
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': '路径不是一个目录'
                })
            
            # 获取目录内容
            items = []
            total_items = 0
            
            try:
                # 设置超时控制
                start_time = time.time()
                MAX_TIME = 3  # 最多允许3秒处理时间
                
                # 首先计算总数
                dir_items = []
                for item in os.listdir(full_path):
                    # 检查是否超时
                    if time.time() - start_time > MAX_TIME:
                        logger.warning(f"获取文件列表超时：路径 {path}")
                        break
                    
                    item_path = os.path.join(full_path, item)
                    try:
                        is_dir = os.path.isdir(item_path)
                        dir_items.append((item, item_path, is_dir))
                    except (PermissionError, OSError) as e:
                        logger.warning(f"无法访问文件: {item_path}, 错误: {str(e)}")
                        continue
                
                # 按类型和名称排序（文件夹在前）
                dir_items.sort(key=lambda x: (0 if x[2] else 1, x[0].lower()))
                
                # 计算总数和分页
                total_items = len(dir_items)
                total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1
                
                # 验证页码有效性
                if page < 1:
                    page = 1
                if page > total_pages:
                    page = total_pages
                
                # 计算分页索引
                start_idx = (page - 1) * limit
                end_idx = min(start_idx + limit, total_items)
                
                # 提取当前页的项目
                page_items = dir_items[start_idx:end_idx]
                
                # 转换为应答格式
                for item, item_path, is_dir in page_items:
                    try:
                        item_stat = os.stat(item_path)
                        
                        # 构建相对路径
                        item_rel_path = os.path.join(path, item).replace('\\', '/')
                        if not item_rel_path.startswith('/'):
                            item_rel_path = '/' + item_rel_path
                        
                        # 添加项目信息
                        items.append({
                            'name': item,
                            'path': item_rel_path,
                            'type': 'directory' if is_dir else 'file',
                            'size': item_stat.st_size,
                            'modified': int(item_stat.st_mtime)
                        })
                    except (PermissionError, OSError) as e:
                        logger.warning(f"无法获取文件信息: {item_path}, 错误: {str(e)}")
                        continue
                
            except Exception as e:
                logger.error(f"列出目录内容时出错: {str(e)}")
                return JSONResponse(status_code=500, content={
                    'success': False, 
                    'message': f'列出目录内容时出错: {str(e)}'
                })
            
            logger.debug(f"成功获取路径 {path} 的文件列表，共 {total_items} 项，当前页 {page}/{(total_items + limit - 1) // limit if total_items > 0 else 1}，返回 {len(items)} 项")
            
            # 返回结果包含分页信息
            return JSONResponse(content={
                'success': True, 
                'items': items,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total_items': total_items,
                    'total_pages': (total_items + limit - 1) // limit if total_items > 0 else 1
                }
            })
            
        except Exception as e:
            logger.error(f"获取文件列表失败: {str(e)}")
            return JSONResponse(status_code=500, content={
                'success': False, 
                'message': f'获取文件列表失败: {str(e)}'
            })
    
    @app.get("/api/files/tree")
    async def api_files_tree(request: Request):
        """获取文件夹树结构"""
        # 使用会话验证
        try:
            # 检查认证状态
            username = await check_auth(request)
            if not username:
                # 记录调试信息
                logger.debug("文件树API访问失败：未认证")
                return JSONResponse(status_code=401, content={
                    'success': False, 
                    'message': '未认证，请先登录'
                })
            
            # 获取项目根目录
            root_dir = Path(current_dir).parent
            
            # 递归构建文件夹树
            def build_tree(dir_path, rel_path='/'):
                tree = {
                    'name': os.path.basename(dir_path) or 'root',
                    'path': rel_path,
                    'type': 'directory',
                    'children': []
                }
                
                try:
                    for item in os.listdir(dir_path):
                        item_path = os.path.join(dir_path, item)
                        item_rel_path = os.path.join(rel_path, item).replace('\\', '/')
                        if not item_rel_path.startswith('/'):
                            item_rel_path = '/' + item_rel_path
                        
                        # 只包含文件夹
                        if os.path.isdir(item_path):
                            # 排除某些目录
                            if item not in ['.git', '__pycache__', 'node_modules', 'venv', 'env', '.venv', '.env']:
                                tree['children'].append(build_tree(item_path, item_rel_path))
                except Exception as e:
                    logger.error(f"读取目录 {dir_path} 失败: {str(e)}")
                
                # 按名称排序子文件夹
                tree['children'].sort(key=lambda x: x['name'].lower())
                
                return tree
            
            # 构建树结构
            tree = build_tree(root_dir)
            
            return JSONResponse(content={'success': True, 'tree': tree})
            
        except Exception as e:
            logger.error(f"获取文件夹树失败: {str(e)}")
            return JSONResponse(status_code=500, content={
                'success': False, 
                'message': f'获取文件夹树失败: {str(e)}'
            })
    
    @app.get("/api/files/read")
    async def api_files_read(request: Request, path: str = None):
        """读取文件内容"""
        # 使用会话验证
        try:
            # 检查认证状态
            username = await check_auth(request)
            if not username:
                # 记录调试信息
                logger.debug("文件读取API访问失败：未认证")
                return JSONResponse(status_code=401, content={
                    'success': False, 
                    'message': '未认证，请先登录'
                })
            
            if not path:
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': '未提供文件路径'
                })
            
            # 处理相对路径
            if not path.startswith('/'):
                path = '/' + path
            
            # 获取完整路径
            root_dir = Path(current_dir).parent
            full_path = root_dir / path.lstrip('/')
            
            # 安全检查：确保路径在项目目录内
            if not os.path.abspath(full_path).startswith(os.path.abspath(root_dir)):
                return JSONResponse(status_code=403, content={
                    'success': False, 
                    'message': '无法访问项目目录外的文件'
                })
            
            # 检查文件是否存在
            if not os.path.exists(full_path):
                return JSONResponse(status_code=404, content={
                    'success': False, 
                    'message': '文件不存在'
                })
            
            # 检查是否是文件
            if not os.path.isfile(full_path):
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': '路径不是一个文件'
                })
            
            # 读取文件内容
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return JSONResponse(content={'success': True, 'content': content})
            
        except Exception as e:
            logger.error(f"读取文件失败: {str(e)}")
            return JSONResponse(status_code=500, content={
                'success': False, 
                'message': f'读取文件失败: {str(e)}'
            })
    
    @app.post("/api/files/write")
    async def api_files_write(request: Request):
        """写入文件内容"""
        # 使用会话验证
        try:
            # 检查认证状态
            username = await check_auth(request)
            if not username:
                # 记录调试信息
                logger.debug("文件写入API访问失败：未认证")
                return JSONResponse(status_code=401, content={
                    'success': False, 
                    'message': '未认证，请先登录'
                })
            
            # 加强错误捕获和日志记录
            try:
                data = await request.json()
            except Exception as e:
                logger.error(f"解析请求体失败: {str(e)}")
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': f'无法解析请求体: {str(e)}'
                })
            
            # 记录请求信息以便调试    
            logger.debug(f"接收到写入文件请求: {data}")
            
            path = data.get('path')
            content = data.get('content')
            
            if not path:
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': '未提供文件路径'
                })
            
            # 处理相对路径
            if not path.startswith('/'):
                path = '/' + path
            
            # 获取完整路径
            root_dir = Path(current_dir).parent
            full_path = root_dir / path.lstrip('/')
            
            # 安全检查：确保路径在项目目录内
            if not os.path.abspath(full_path).startswith(os.path.abspath(root_dir)):
                return JSONResponse(status_code=403, content={
                    'success': False, 
                    'message': '无法访问项目目录外的文件'
                })
            
            # 确保父目录存在
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # 写入文件内容
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"成功写入文件: {path}")
            return JSONResponse(content={'success': True})
            
        except Exception as e:
            logger.error(f"写入文件失败: {str(e)}")
            return JSONResponse(status_code=500, content={
                'success': False, 
                'message': f'写入文件失败: {str(e)}'
            })
    
    @app.post("/api/files/create")
    async def api_files_create(request: Request):
        """创建文件或文件夹"""
        # 使用会话验证
        try:
            # 检查认证状态
            username = await check_auth(request)
            if not username:
                # 记录调试信息
                logger.debug("文件创建API访问失败：未认证")
                return JSONResponse(status_code=401, content={
                    'success': False, 
                    'message': '未认证，请先登录'
                })
            
            # 加强错误捕获和日志记录
            try:
                data = await request.json()
            except Exception as e:
                logger.error(f"解析请求体失败: {str(e)}")
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': f'无法解析请求体: {str(e)}'
                })
                
            # 记录请求信息以便调试
            logger.debug(f"接收到创建文件/文件夹请求: {data}")
            
            path = data.get('path')
            content = data.get('content', '')
            type = data.get('type', 'file')
            
            if not path:
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': '未提供路径'
                })
            
            # 处理相对路径
            if not path.startswith('/'):
                path = '/' + path
            
            # 获取完整路径
            root_dir = Path(current_dir).parent
            full_path = root_dir / path.lstrip('/')
            
            # 安全检查：确保路径在项目目录内
            if not os.path.abspath(full_path).startswith(os.path.abspath(root_dir)):
                return JSONResponse(status_code=403, content={
                    'success': False, 
                    'message': '无法在项目目录外创建文件'
                })
            
            # 检查文件是否已存在
            if os.path.exists(full_path):
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': '文件或文件夹已存在'
                })
            
            # 创建文件夹或文件
            if type == 'directory':
                os.makedirs(full_path, exist_ok=True)
                logger.info(f"成功创建文件夹: {path}")
            else:
                # 确保父文件夹存在
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # 创建文件并写入内容
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"成功创建文件: {path}")
            
            return JSONResponse(content={'success': True})
            
        except Exception as e:
            logger.error(f"创建文件或文件夹失败: {str(e)}")
            return JSONResponse(status_code=500, content={
                'success': False, 
                'message': f'创建文件或文件夹失败: {str(e)}'
            })
    
    @app.post("/api/files/delete")
    async def api_files_delete(request: Request):
        """删除文件或文件夹"""
        # 使用会话验证
        try:
            # 检查认证状态
            username = await check_auth(request)
            if not username:
                # 记录调试信息
                logger.debug("文件删除API访问失败：未认证")
                return JSONResponse(status_code=401, content={
                    'success': False, 
                    'message': '未认证，请先登录'
                })
            
            # 加强错误捕获和日志记录
            try:
                data = await request.json()
            except Exception as e:
                logger.error(f"解析请求体失败: {str(e)}")
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': f'无法解析请求体: {str(e)}'
                })
            
            # 记录请求信息以便调试
            logger.debug(f"接收到删除文件/文件夹请求: {data}")
            
            path = data.get('path')
            
            if not path:
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': '未提供路径'
                })
            
            # 处理相对路径
            if not path.startswith('/'):
                path = '/' + path
            
            # 获取完整路径
            root_dir = Path(current_dir).parent
            full_path = root_dir / path.lstrip('/')
            
            # 安全检查：确保路径在项目目录内
            if not os.path.abspath(full_path).startswith(os.path.abspath(root_dir)):
                return JSONResponse(status_code=403, content={
                    'success': False, 
                    'message': '无法删除项目目录外的文件'
                })
            
            # 检查文件或文件夹是否存在
            if not os.path.exists(full_path):
                return JSONResponse(status_code=404, content={
                    'success': False, 
                    'message': '文件或文件夹不存在'
                })
            
            # 删除文件或文件夹
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
                logger.info(f"成功删除文件夹: {path}")
            else:
                os.remove(full_path)
                logger.info(f"成功删除文件: {path}")
            
            return JSONResponse(content={'success': True})
            
        except Exception as e:
            logger.error(f"删除文件或文件夹失败: {str(e)}")
            return JSONResponse(status_code=500, content={
                'success': False, 
                'message': f'删除文件或文件夹失败: {str(e)}'
            })
    
    @app.post("/api/files/rename")
    async def api_files_rename(request: Request):
        """重命名文件或文件夹"""
        # 使用会话验证
        try:
            # 检查认证状态
            username = await check_auth(request)
            if not username:
                # 记录调试信息
                logger.debug("文件重命名API访问失败：未认证")
                return JSONResponse(status_code=401, content={
                    'success': False, 
                    'message': '未认证，请先登录'
                })
            
            # 加强错误捕获和日志记录
            try:
                data = await request.json()
            except Exception as e:
                logger.error(f"解析请求体失败: {str(e)}")
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': f'无法解析请求体: {str(e)}'
                })
                
            # 记录请求信息以便调试
            logger.debug(f"接收到重命名文件/文件夹请求: {data}")
            
            old_path = data.get('old_path')
            new_path = data.get('new_path')
            
            if not old_path or not new_path:
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': '未提供旧路径或新路径'
                })
            
            # 处理相对路径
            if not old_path.startswith('/'):
                old_path = '/' + old_path
            if not new_path.startswith('/'):
                new_path = '/' + new_path
            
            # 获取完整路径
            root_dir = Path(current_dir).parent
            old_full_path = root_dir / old_path.lstrip('/')
            new_full_path = root_dir / new_path.lstrip('/')
            
            # 安全检查：确保路径在项目目录内
            if (not os.path.abspath(old_full_path).startswith(os.path.abspath(root_dir)) or 
                not os.path.abspath(new_full_path).startswith(os.path.abspath(root_dir))):
                return JSONResponse(status_code=403, content={
                    'success': False, 
                    'message': '无法操作项目目录外的文件'
                })
            
            # 检查旧文件是否存在
            if not os.path.exists(old_full_path):
                return JSONResponse(status_code=404, content={
                    'success': False, 
                    'message': '原文件或文件夹不存在'
                })
            
            # 检查新文件是否已存在
            if os.path.exists(new_full_path):
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': '目标文件或文件夹已存在'
                })
                
            # 确保父文件夹存在
            os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
            
            # 重命名文件或文件夹
            shutil.move(old_full_path, new_full_path)
            
            logger.info(f"成功将 {old_path} 重命名为 {new_path}")
            return JSONResponse(content={'success': True})
            
        except Exception as e:
            logger.error(f"重命名文件或文件夹失败: {str(e)}")
            return JSONResponse(status_code=500, content={
                'success': False, 
                'message': f'重命名文件或文件夹失败: {str(e)}'
            })

    @app.post("/api/files/upload")
    async def api_files_upload(request: Request, path: str = Form(...), files: List[UploadFile] = File(...)):
        """上传文件到指定路径"""
        # 使用会话验证
        try:
            # 检查认证状态
            username = await check_auth(request)
            if not username:
                # 记录调试信息
                logger.warning("文件上传API访问失败：未认证")
                return JSONResponse(status_code=401, content={
                    'success': False, 
                    'message': '未认证，请先登录'
                })
            
            # 处理相对路径
            if not path.startswith('/'):
                path = '/' + path
            
            # 获取完整路径 - 从项目根目录开始
            root_dir = Path(current_dir).parent
            full_path = root_dir / path.lstrip('/')
            
            logger.debug(f"用户 {username} 请求上传文件到路径: {path} -> {full_path}")
            
            # 安全检查：确保路径在项目目录内
            if not os.path.abspath(full_path).startswith(os.path.abspath(root_dir)):
                logger.warning(f"尝试上传到不安全的路径: {full_path}")
                return JSONResponse(status_code=403, content={
                    'success': False, 
                    'message': '无法上传到项目目录外的位置'
                })
            
            # 检查路径是否存在且是目录
            if not os.path.exists(full_path):
                logger.warning(f"上传目标路径不存在: {full_path}")
                return JSONResponse(status_code=404, content={
                    'success': False, 
                    'message': '上传目标路径不存在'
                })
            
            if not os.path.isdir(full_path):
                logger.warning(f"上传目标路径不是目录: {full_path}")
                return JSONResponse(status_code=400, content={
                    'success': False, 
                    'message': '上传目标路径不是一个目录'
                })
            
            # 获取表单数据中的上传类型
            form = await request.form()
            upload_type = "files"  # 默认为普通文件上传
            
            # 检查是否是文件夹上传请求
            if "upload_type" in form:
                upload_type = form["upload_type"]
                logger.debug(f"上传类型: {upload_type}")
            
            # 处理上传的文件
            uploaded_files = []
            errors = []
            
            # 处理文件夹上传
            is_folder_upload = False
            for file in files:
                if '/' in file.filename or '\\' in file.filename:
                    is_folder_upload = True
                    break
            
            if is_folder_upload or upload_type == "folder":
                logger.info(f"检测到文件夹上传请求 ({len(files)} 个文件)")
                
                # 按文件路径分组文件
                folder_files = {}
                for file in files:
                    # 处理文件路径，统一分隔符
                    file_path = file.filename.replace('\\', '/')
                    folder_files[file_path] = file
                
                # 创建必要的目录结构并保存文件
                for file_path, file in folder_files.items():
                    try:
                        # 如果是隐藏文件或临时文件，跳过
                        if file_path.startswith('.') or file_path.endswith('~'):
                            logger.debug(f"跳过隐藏或临时文件: {file_path}")
                            continue
                        
                        # 获取目录部分
                        dir_part = os.path.dirname(file_path)
                        
                        # 构建目标路径
                        target_dir = full_path
                        if dir_part:
                            target_dir = os.path.join(full_path, dir_part)
                            # 确保目录存在
                            os.makedirs(target_dir, exist_ok=True)
                        
                        # 构建完整的文件路径
                        target_file_path = os.path.join(full_path, file_path)
                        
                        # 检查文件是否已存在
                        if os.path.exists(target_file_path):
                            logger.warning(f"文件已存在: {target_file_path}")
                            errors.append({
                                'filename': file_path,
                                'error': '文件已存在'
                            })
                            continue
                        
                        # 保存文件
                        logger.debug(f"保存上传的文件: {target_file_path}")
                        content = await file.read()
                        with open(target_file_path, "wb") as f:
                            f.write(content)
                        
                        # 记录成功上传的文件
                        file_stats = os.stat(target_file_path)
                        uploaded_files.append({
                            'filename': file_path,
                            'size': file_stats.st_size,
                            'modified': file_stats.st_mtime
                        })
                        
                        logger.info(f"成功上传文件: {file_path} 到 {target_file_path}")
                        
                    except Exception as e:
                        logger.error(f"上传文件 {file_path} 失败: {str(e)}")
                        errors.append({
                            'filename': file_path,
                            'error': str(e)
                        })
                
                # 返回上传结果
                return JSONResponse(content={
                    'success': True if uploaded_files else False,
                    'message': f'成功上传文件夹中的 {len(uploaded_files)} 个文件，失败 {len(errors)} 个',
                    'uploaded_files': uploaded_files,
                    'errors': errors
                })
            else:
                # 普通文件上传处理（原有代码）
                for file in files:
                    try:
                        # 构建目标文件路径
                        target_file_path = full_path / file.filename
                        
                        # 检查文件是否已存在
                        if os.path.exists(target_file_path):
                            logger.warning(f"文件已存在: {target_file_path}")
                            errors.append({
                                'filename': file.filename,
                                'error': '文件已存在'
                            })
                            continue
                        
                        # 保存文件
                        logger.debug(f"保存上传的文件: {target_file_path}")
                        content = await file.read()
                        with open(target_file_path, "wb") as f:
                            f.write(content)
                        
                        # 记录成功上传的文件
                        file_stats = os.stat(target_file_path)
                        uploaded_files.append({
                            'filename': file.filename,
                            'size': file_stats.st_size,
                            'modified': file_stats.st_mtime
                        })
                        
                        logger.info(f"用户 {username} 成功上传文件: {file.filename} 到 {path}")
                        
                        # 检查是否需要自动解压
                        if "auto_extract" in form and form["auto_extract"] == "true":
                            if file.filename.lower().endswith(('.zip', '.rar', '.7z', '.tar', '.gz', '.tar.gz')):
                                logger.info(f"请求自动解压文件: {file.filename}")
                                # 调用解压函数
                                extract_result = await extract_archive(
                                    archive_path=str(target_file_path),
                                    destination=str(full_path),
                                    overwrite=False
                                )
                                # 合并解压结果
                                if extract_result.get('success', False):
                                    logger.info(f"自动解压成功: {file.filename}")
                                else:
                                    logger.warning(f"自动解压失败: {file.filename}, {extract_result.get('message', '')}")
                        
                    except Exception as e:
                        logger.error(f"上传文件 {file.filename} 失败: {str(e)}")
                        errors.append({
                            'filename': file.filename,
                            'error': str(e)
                        })
                
                # 返回上传结果
                return JSONResponse(content={
                    'success': True if uploaded_files else False,
                    'message': f'成功上传 {len(uploaded_files)} 个文件，失败 {len(errors)} 个' if uploaded_files else '上传失败',
                    'uploaded_files': uploaded_files,
                    'errors': errors
                })
            
        except Exception as e:
            logger.error(f"文件上传过程中发生错误: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"服务器错误: {str(e)}"}
            )

    # 添加压缩包解压API
    @app.post("/api/files/extract")
    async def api_files_extract(
        request: Request, 
        file_path: str = Form(...), 
        destination: str = Form(...),
        overwrite: bool = Form(False)
    ):
        """解压压缩文件到指定目录"""
        try:
            # 检查认证状态
            username = await check_auth(request)
            if not username:
                logger.warning("文件解压API访问失败：未认证")
                return JSONResponse(status_code=401, content={
                    'success': False, 
                    'message': '未认证，请先登录'
                })
            
            # 处理相对路径
            if not file_path.startswith('/'):
                file_path = '/' + file_path
                
            if not destination.startswith('/'):
                destination = '/' + destination
            
            # 获取完整路径 - 从项目根目录开始
            root_dir = Path(current_dir).parent
            full_file_path = root_dir / file_path.lstrip('/')
            full_destination = root_dir / destination.lstrip('/')
            
            logger.debug(f"用户 {username} 请求解压文件: {file_path} -> {destination}")
            
            # 安全检查：确保路径在项目目录内
            if not os.path.abspath(full_file_path).startswith(os.path.abspath(root_dir)):
                logger.warning(f"尝试访问不安全的文件路径: {full_file_path}")
                return JSONResponse(status_code=403, content={
                    'success': False, 
                    'message': '无法访问项目目录外的文件'
                })
                
            if not os.path.abspath(full_destination).startswith(os.path.abspath(root_dir)):
                logger.warning(f"尝试解压到不安全的路径: {full_destination}")
                return JSONResponse(status_code=403, content={
                    'success': False, 
                    'message': '无法解压到项目目录外的位置'
                })
            
            # 确保目标目录存在
            os.makedirs(full_destination, exist_ok=True)
            
            # 调用解压函数
            return await extract_archive(
                archive_path=str(full_file_path),
                destination=str(full_destination),
                overwrite=overwrite
            )
            
        except Exception as e:
            logger.error(f"解压文件过程中发生错误: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"服务器错误: {str(e)}"}
            )
            
    # 解压缩文件的辅助函数
    async def extract_archive(archive_path: str, destination: str, overwrite: bool = False) -> dict:
        """解压缩文件

        Args:
            archive_path: 压缩文件路径
            destination: 解压目标路径
            overwrite: 是否覆盖已存在的文件

        Returns:
            dict: 解压结果
        """
        logger.info(f"开始解压文件: {archive_path} -> {destination}")
        
        # 确保目标路径存在
        os.makedirs(destination, exist_ok=True)
        
        # 提取文件扩展名
        file_ext = os.path.splitext(archive_path.lower())[1]
        if file_ext == '.gz' and archive_path.lower().endswith('.tar.gz'):
            file_ext = '.tar.gz'
        
        # 记录已解压的文件
        extracted_files = []
        
        try:
            # 检查文件是否存在
            if not os.path.exists(archive_path):
                logger.error(f"压缩文件不存在: {archive_path}")
                return {
                    'success': False,
                    'message': '文件不存在'
                }
            
            # 根据不同压缩格式处理
            if file_ext in ['.zip', '.rar', '.7z']:
                # 使用shutil解压zip文件
                if file_ext == '.zip':
                    try:
                        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                            # 获取文件列表
                            file_list = zip_ref.namelist()
                            
                            # 确保安全：检查是否包含绝对路径或父目录引用
                            for file_name in file_list:
                                if file_name.startswith('/') or '..' in file_name:
                                    return {
                                        'success': False,
                                        'message': f'压缩包含不安全的路径: {file_name}'
                                    }
                            
                            # 执行解压
                            for file_name in file_list:
                                target_path = os.path.join(destination, file_name)
                                
                                # 如果是目录，创建它
                                if file_name.endswith('/') or file_name.endswith('\\'):
                                    os.makedirs(target_path, exist_ok=True)
                                    continue
                                    
                                # 确保父目录存在
                                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                
                                # 检查文件是否已存在且不覆盖
                                if os.path.exists(target_path) and not overwrite:
                                    logger.warning(f"文件已存在且不覆盖: {target_path}")
                                    continue
                                
                                # 解压文件
                                with zip_ref.open(file_name) as source, open(target_path, 'wb') as target:
                                    shutil.copyfileobj(source, target)
                                
                                extracted_files.append(file_name)
                                
                    except zipfile.BadZipFile as e:
                        return {
                            'success': False,
                            'message': f'无效的ZIP文件: {str(e)}'
                        }
                else:
                    # 对于非ZIP的归档文件，优先使用Python库解压
                    try:
                        if file_ext == '.rar' and rarfile is not None:
                            logger.info("使用rarfile库解压RAR文件")
                            with rarfile.RarFile(archive_path) as rf:
                                # 获取文件列表
                                file_list = rf.namelist()
                                
                                # 确保安全：检查是否包含绝对路径或父目录引用
                                for file_name in file_list:
                                    if file_name.startswith('/') or '..' in file_name:
                                        return {
                                            'success': False,
                                            'message': f'压缩包含不安全的路径: {file_name}'
                                        }
                                
                                # 执行解压
                                for file_name in file_list:
                                    # 构建目标路径
                                    target_path = os.path.join(destination, file_name)
                                    
                                    # 如果是目录，创建它
                                    if file_name.endswith('/') or file_name.endswith('\\'):
                                        os.makedirs(target_path, exist_ok=True)
                                        continue
                                        
                                    # 确保父目录存在
                                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                    
                                    # 检查文件是否已存在且不覆盖
                                    if os.path.exists(target_path) and not overwrite:
                                        logger.warning(f"文件已存在且不覆盖: {target_path}")
                                        continue
                                    
                                    # 提取文件
                                    with rf.open(file_name) as source, open(target_path, 'wb') as target:
                                        shutil.copyfileobj(source, target)
                                    
                                    extracted_files.append(file_name)
                                
                                logger.info(f"成功解压RAR文件: {archive_path}，共 {len(extracted_files)} 个文件")
                                return {
                                    'success': True,
                                    'message': f'成功解压 {len(extracted_files)} 个文件',
                                    'extracted_files': extracted_files[:100],  # 限制返回的文件数量
                                    'total_files': len(extracted_files)
                                }
                        elif file_ext == '.7z' and py7zr is not None:
                            logger.info("使用py7zr库解压7Z文件")
                            with py7zr.SevenZipFile(archive_path, mode='r') as z:
                                # 解压文件
                                z.extractall(path=destination)
                                # 获取解压的文件列表
                                extracted_files = z.getnames()
                                
                                logger.info(f"成功解压7Z文件: {archive_path}，共 {len(extracted_files)} 个文件")
                                return {
                                    'success': True,
                                    'message': f'成功解压 {len(extracted_files)} 个文件',
                                    'extracted_files': extracted_files[:100],  # 限制返回的文件数量
                                    'total_files': len(extracted_files)
                                }
                    except ImportError as e:
                        logger.warning(f"缺少库 {str(e)}，尝试使用外部命令")
                    except Exception as e:
                        logger.error(f"使用Python库解压失败: {str(e)}")
                        
                    # 如果Python库解压失败，尝试使用外部命令
                    try:
                        logger.info("尝试使用外部命令解压")
                        # 检查系统可用命令
                        commands_to_try = []
                        
                        if file_ext == '.rar':
                            # 先尝试unrar，这是专门处理RAR的工具
                            commands_to_try.append({
                                'name': 'unrar',
                                'cmd': ['unrar', 'x', '-y' if overwrite else '-n', archive_path, destination]
                            })
                            # 然后尝试7z系列命令
                            for cmd_name in ['7z', '7za', '7zr', '/usr/bin/7z', '/usr/bin/7za', '/usr/bin/7zr']:
                                commands_to_try.append({
                                    'name': cmd_name,
                                    'cmd': [cmd_name, 'x', '-y' if overwrite else '-n', '-o' + destination, archive_path]
                                })
                        elif file_ext == '.7z':
                            # 先尝试7z系列命令
                            for cmd_name in ['7z', '7za', '7zr', '/usr/bin/7z', '/usr/bin/7za', '/usr/bin/7zr']:
                                commands_to_try.append({
                                    'name': cmd_name,
                                    'cmd': [cmd_name, 'x', '-y' if overwrite else '-n', '-o' + destination, archive_path]
                                })
                        
                        # 尝试每个命令
                        command_success = False
                        for command in commands_to_try:
                            try:
                                logger.info(f"尝试使用 {command['name']} 解压")
                                # 先测试命令是否可用
                                subprocess.run([command['name'], '--help'], capture_output=True, text=True, timeout=2)
                                
                                # 执行解压命令
                                logger.info(f"执行解压命令: {' '.join(command['cmd'])}")
                                result = subprocess.run(command['cmd'], capture_output=True, text=True, timeout=60)
                                
                                if result.returncode == 0:
                                    logger.info(f"命令 {command['name']} 执行成功")
                                    command_success = True
                                    # 解析输出以获取解压的文件列表
                                    output_lines = result.stdout.splitlines()
                                    for line in output_lines:
                                        # 根据不同工具的输出格式查找提取的文件
                                        if 'Extracting' in line or 'Extraindo' in line or '提取' in line:
                                            parts = line.split()
                                            if len(parts) > 0:
                                                file_info = parts[-1].strip()
                                                extracted_files.append(file_info)
                                
                                    if not extracted_files:
                                        # 如果没有从输出中解析到文件列表，扫描目录
                                        for root, dirs, files in os.walk(destination):
                                            for file in files:
                                                file_path = os.path.join(root, file)
                                                rel_path = os.path.relpath(file_path, destination)
                                                extracted_files.append(rel_path)
                                
                                    logger.info(f"解压成功，共解压 {len(extracted_files)} 个文件")
                                    return {
                                        'success': True,
                                        'message': f'成功解压 {len(extracted_files)} 个文件',
                                        'extracted_files': extracted_files[:100],  # 限制返回的文件数量
                                        'total_files': len(extracted_files)
                                    }
                                else:
                                    logger.warning(f"命令 {command['name']} 执行失败，返回码: {result.returncode}")
                                    logger.warning(f"错误输出: {result.stderr}")
                            except FileNotFoundError:
                                logger.warning(f"命令 {command['name']} 不可用")
                            except subprocess.TimeoutExpired:
                                logger.warning(f"命令 {command['name']} 执行超时")
                        
                        # 检查所有命令是否都已尝试且全部失败
                        if not command_success:
                            logger.error(f"所有解压命令尝试均失败，无法解压 {archive_path}")
                            return {
                                'success': False,
                                'message': f'无法解压 {file_ext} 文件: 所有解压工具尝试均失败。请在服务器上安装unrar或7z工具。'
                            }
                            
                    except Exception as e:
                        logger.error(f"使用外部命令解压过程中发生错误: {str(e)}")
                        return {
                            'success': False,
                            'message': f'解压失败: {str(e)}'
                        }
            elif file_ext in ['.tar', '.gz', '.tar.gz', '.tgz']:
                # 使用tarfile模块解压tar文件
                try:
                    import tarfile
                    
                    # 确定打开模式
                    mode = 'r:gz' if file_ext in ['.gz', '.tar.gz', '.tgz'] else 'r'
                    
                    with tarfile.open(archive_path, mode) as tar:
                        # 获取成员列表
                        members = tar.getmembers()
                        
                        # 安全检查
                        for member in members:
                            if member.name.startswith('/') or '..' in member.name:
                                return {
                                    'success': False,
                                    'message': f'压缩包含不安全的路径: {member.name}'
                                }
                        
                        # 解压文件
                        for member in members:
                            target_path = os.path.join(destination, member.name)
                            
                            # 跳过已存在且不覆盖的文件
                            if os.path.exists(target_path) and not overwrite:
                                if member.isreg():  # 只记录常规文件
                                    logger.warning(f"文件已存在且不覆盖: {target_path}")
                                continue
                            
                            tar.extract(member, destination)
                            
                            if member.isreg():  # 只记录常规文件
                                extracted_files.append(member.name)
                        
                except tarfile.ReadError as e:
                    return {
                        'success': False,
                        'message': f'无效的TAR文件: {str(e)}'
                    }
            else:
                return {
                    'success': False,
                    'message': f'不支持的压缩格式: {file_ext}'
                }
            
            # 检查是否有任何文件被成功解压
            if not extracted_files:
                logger.warning(f"没有文件被解压: {archive_path}")
                return {
                    'success': False,
                    'message': '解压过程完成，但没有文件被解压。请检查压缩文件是否有效或安装必要的解压工具。'
                }
            
            # 记录解压完成
            logger.info(f"成功解压文件: {archive_path}，共 {len(extracted_files)} 个文件")
            
            return {
                'success': True,
                'message': f'成功解压 {len(extracted_files)} 个文件',
                'extracted_files': extracted_files[:100],  # 限制返回的文件数量
                'total_files': len(extracted_files)
            }
            
        except Exception as e:
            logger.error(f"解压文件失败: {str(e)}")
            return {
                'success': False,
                'message': f'解压失败: {str(e)}'
            }

    # 添加登出API
    @app.post("/api/auth/logout", response_class=JSONResponse)
    async def logout_api(request: Request, response: Response):
        """用户登出接口"""
        try:
            # 清除会话Cookie
            response.delete_cookie(key="session", path="/")
            return {"success": True, "message": "已成功退出登录"}
        except Exception as e:
            logger.error(f"退出登录失败: {str(e)}")
            return {"success": False, "error": f"退出登录失败: {str(e)}"}

    @app.get("/files", response_class=HTMLResponse)
    async def files_page(request: Request):
        # 检查认证状态
        try:
            username = await check_auth(request)
            if not username:
                # 未认证，重定向到登录页面
                return RedirectResponse(url="/login?next=/files", status_code=303)
                
            logger.debug(f"用户 {username} 访问文件管理页面")
            # 认证成功，显示文件管理页面
            return templates.TemplateResponse("files.html", {
                "request": request,
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            logger.error(f"访问文件管理页面失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

    # API: 系统日志 (需要认证)
    @app.get("/api/system/logs", response_class=JSONResponse)
    async def api_system_logs(request: Request, log_level: str = None, limit: int = 100):
        """获取系统日志"""
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
        
        try:
            # 可能的日志文件位置
            log_paths = [
                "logs/latest.log",
                "logs/xybot.log",
                "logs/XYBot_*.log",
                "_data/logs/XYBot_*.log",
                "../logs/XYBot_*.log",
                "./logs/XYBot_*.log",
                # 相对于当前目录的位置
                os.path.join(current_dir, "../logs/latest.log"),
                os.path.join(current_dir, "../logs/xybot.log"),
                os.path.join(current_dir, "../logs/XYBot_*.log"),
                os.path.join(current_dir, "./logs/latest.log"),
            ]
            
            # 查找存在的日志文件
            found_logs = []
            for path_pattern in log_paths:
                for log_file in glob.glob(path_pattern):
                    if os.path.exists(log_file) and os.path.isfile(log_file):
                        found_logs.append(log_file)
            
            # 如果没找到日志文件
            if not found_logs:
                logger.warning("未找到任何日志文件")
                return {
                    "success": True,
                    "logs": [],
                    "log_files": [],
                    "message": "未找到任何日志文件"
                }
            
            # 选择最新的日志文件
            latest_log = max(found_logs, key=os.path.getmtime)
            logger.info(f"读取日志文件: {latest_log}")
            
            # 读取日志文件并按行返回最新的limit行
            log_entries = []
            log_files = [os.path.basename(log) for log in found_logs]
            
            with open(latest_log, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                # 获取最后的limit行
                lines = lines[-limit:] if len(lines) > limit else lines
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 解析日志行
                    log_entry = {"raw": line}
                    
                    # 尝试解析日志级别
                    level_match = re.search(r'\|\s*(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*\|', line)
                    if level_match:
                        log_entry["level"] = level_match.group(1).lower()
                    else:
                        log_entry["level"] = "info"  # 默认级别
                    
                    # 如果指定了级别过滤，且不匹配，则跳过
                    if log_level and log_entry["level"] != log_level.lower():
                        continue
                    
                    # 尝试解析时间戳
                    time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
                    if time_match:
                        log_entry["timestamp"] = time_match.group(1)
                    
                    # 尝试解析消息内容
                    content_match = re.search(r'\|\s*(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*\|\s*(.*)', line)
                    if content_match:
                        log_entry["message"] = content_match.group(2).strip()
                    else:
                        log_entry["message"] = line
                    
                    log_entries.append(log_entry)
            
            return {
                "success": True,
                "logs": log_entries,
                "log_files": log_files,
                "current_log": os.path.basename(latest_log)
            }
            
        except Exception as e:
            logger.error(f"获取系统日志时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"获取系统日志失败: {str(e)}"}
            )
            
    # API: 联系人管理 (需要认证)
    @app.get("/api/contacts", response_class=JSONResponse)
    async def api_contacts(request: Request, refresh: bool = False):
        """获取联系人列表"""
        # 检查用户是否已登录
        username = await check_auth(request)
        if not username:
            return JSONResponse(content={
                "success": False,
                "error": "未授权访问"
            })
        
        # 缓存文件路径
        cache_dir = os.path.join("data", "cache")
        os.makedirs(cache_dir, exist_ok=True)
        contacts_cache_file = os.path.join(cache_dir, "contacts_cache.json")
        
        # 如果不是强制刷新，尝试从缓存读取
        if not refresh and os.path.exists(contacts_cache_file):
            try:
                # 检查缓存是否在24小时内
                cache_time = os.path.getmtime(contacts_cache_file)
                current_time = time.time()
                cache_age = current_time - cache_time
                
                # 如果缓存不超过24小时，直接返回缓存数据
                if cache_age < 24 * 3600:  # 24小时 = 86400秒
                    logger.info(f"从缓存加载联系人列表（缓存时间：{datetime.fromtimestamp(cache_time).strftime('%Y-%m-%d %H:%M:%S')}）")
                    with open(contacts_cache_file, 'r', encoding='utf-8') as f:
                        cached_data = json.load(f)
                        return JSONResponse(content=cached_data)
                else:
                    logger.info("联系人缓存已过期（超过24小时），将重新获取")
            except Exception as e:
                logger.error(f"读取联系人缓存失败: {e}")
        
        logger.info("请求联系人列表API")
        
        # 使用固定wxid调用微信API获取联系人列表
        try:
            # 确保bot_instance可用
            if not bot_instance or not hasattr(bot_instance, 'bot'):
                logger.error("bot_instance未设置或不可用")
                return JSONResponse(content={
                    "success": False,
                    "error": "机器人实例未初始化，请确保机器人已启动",
                    "data": []
                })
            
            # 检查get_contract_list方法
            if not hasattr(bot_instance.bot, 'get_contract_list'):
                logger.error("bot.get_contract_list方法不存在")
                return JSONResponse(content={
                    "success": False,
                    "error": "微信API不支持获取联系人列表",
                    "data": []
                })
            
            # 获取API请求的URL
            if hasattr(bot_instance.bot, 'ip') and hasattr(bot_instance.bot, 'port'):
                api_url = f"http://{bot_instance.bot.ip}:{bot_instance.bot.port}/GetContractList"
                logger.info(f"请求URL: {api_url}")
            
            # 从bot状态中获取微信ID
            bot_status = get_bot_status()
            wxid = None
            
            # 检查bot_status中是否包含wxid
            if bot_status and "wxid" in bot_status:
                wxid = bot_status["wxid"]
                logger.info(f"从系统状态获取到wxid: {wxid}")
            else:
                # 尝试从bot实例中获取wxid
                if hasattr(bot_instance.bot, 'wxid') and bot_instance.bot.wxid:
                    wxid = bot_instance.bot.wxid
                    logger.info(f"从bot实例获取到wxid: {wxid}")
                else:
                    # 回退到原来的固定wxid
                    wxid = "wxid_uz9za1pqr3ea22"
                    logger.warning(f"无法获取动态wxid，使用固定wxid: {wxid}")
            
            request_params = {
                "Wxid": wxid,
                "CurrentWxcontactSeq": 0,
                "CurrentChatroomContactSeq": 0
            }
            logger.info(f"请求方式: POST")
            logger.info(f"请求参数: {request_params}")
            
            # 保存原始wxid
            original_wxid = None
            if hasattr(bot_instance.bot, 'wxid'):
                original_wxid = bot_instance.bot.wxid
            
            # 设置wxid并调用API
            bot_instance.bot.wxid = wxid
            
            # 调用API获取联系人
            import asyncio
            if asyncio.get_event_loop().is_running():
                contacts_data = await bot_instance.bot.get_contract_list(wx_seq=0, chatroom_seq=0)
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    contacts_data = loop.run_until_complete(bot_instance.bot.get_contract_list(wx_seq=0, chatroom_seq=0))
                finally:
                    loop.close()
            
            # 恢复原始wxid
            if original_wxid is not None:
                bot_instance.bot.wxid = original_wxid
            
            # 打印返回数据的完整结构，帮助调试
            logger.debug(f"API返回数据结构: {contacts_data}")
            
            # 检查返回数据
            if not contacts_data or not isinstance(contacts_data, dict):
                logger.error(f"API返回数据无效: {contacts_data}")
                return JSONResponse(content={
                    "success": False,
                    "error": "获取联系人列表失败，返回数据无效",
                    "data": []
                })
            
            # 检查ContactUsernameList字段 - 直接在顶层
            if 'ContactUsernameList' not in contacts_data or not isinstance(contacts_data['ContactUsernameList'], list):
                logger.error(f"返回数据中没有ContactUsernameList字段或格式不正确: {contacts_data}")
                return JSONResponse(content={
                    "success": False,
                    "error": "获取联系人列表失败，返回数据格式不正确",
                    "data": []
                })
            
            # 提取联系人列表
            contact_usernames = contacts_data['ContactUsernameList']
            logger.info(f"找到{len(contact_usernames)}个联系人ID")
            
            # 构建联系人对象
            contact_list = []
            
            # 检查是否支持获取联系人详情
            has_contract_detail_method = hasattr(bot_instance.bot, 'get_contract_detail')
            
            if has_contract_detail_method:
                logger.info("使用get_contract_detail方法获取联系人详细信息")
                
                # 分批获取联系人详情 (每批最多20个)
                batch_size = 20
                all_contact_details = {}
                
                for i in range(0, len(contact_usernames), batch_size):
                    batch = contact_usernames[i:i+batch_size]
                    logger.debug(f"获取联系人详情批次 {i//batch_size+1}/{(len(contact_usernames)+batch_size-1)//batch_size}: {batch}")
                    
                    try:
                        # 调用API获取联系人详情
                        if asyncio.get_event_loop().is_running():
                            contact_details = await bot_instance.bot.get_contract_detail(batch)
                        else:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                contact_details = loop.run_until_complete(bot_instance.bot.get_contract_detail(batch))
                            finally:
                                loop.close()
                        
                        # 改为INFO级别确保输出
                        logger.info(f"批次{i//batch_size+1}获取到联系人详情: {len(contact_details)}个")
                        
                        # 强制打印每个批次的第一个联系人信息作为样本
                        if contact_details and len(contact_details) > 0:
                            logger.info(f"联系人详情样本结构: {json.dumps(contact_details[0], ensure_ascii=False)}")
                        
                        # 显式记录关键字段是否存在
                        if contact_details and len(contact_details) > 0:
                            first_contact = contact_details[0]
                            logger.info(f"联系人[{first_contact.get('Username', 'unknown')}]有以下字段: {sorted(first_contact.keys())}")
                            
                            # 检查并记录关键字段
                            for field in ['Username', 'NickName', 'Remark', 'SmallHeadImgUrl', 'BigHeadImgUrl']:
                                if field in first_contact:
                                    logger.info(f"字段[{field}]存在，值为: {first_contact[field]}")
                                else:
                                    logger.info(f"字段[{field}]不存在")
                        
                        # 将联系人详情与wxid关联
                        for contact_detail in contact_details:
                            # 修正UserName字段名大小写问题
                            if 'UserName' in contact_detail and contact_detail['UserName']:
                                # 处理嵌套结构，UserName可能是{"string": "wxid"}格式
                                if isinstance(contact_detail['UserName'], dict) and 'string' in contact_detail['UserName']:
                                    wxid = contact_detail['UserName']['string']
                                else:
                                    wxid = str(contact_detail['UserName'])
                                
                                all_contact_details[wxid] = contact_detail
                                if wxid in batch[:3]:  # 只记录前3个，避免日志过多
                                    logger.info(f"联系人[{wxid}]头像信息: " + 
                                              f"SmallHeadImgUrl={contact_detail.get('SmallHeadImgUrl', 'None')}, " +
                                              f"BigHeadImgUrl={contact_detail.get('BigHeadImgUrl', 'None')}")
                    except Exception as e:
                        logger.error(f"获取联系人详情批次失败 ({i}~{i+batch_size-1}): {e}")
                        logger.error(traceback.format_exc())
                
                # 根据获取的详细信息创建联系人对象
                for username in contact_usernames:
                    # 根据wxid格式确定联系人类型
                    contact_type = "friend"
                    if username.endswith("@chatroom"):
                        contact_type = "group"
                    elif username.startswith("gh_"):
                        contact_type = "official"
                    
                    # 获取联系人详情
                    contact_detail = all_contact_details.get(username, {})
                    
                    # 提取字段
                    nickname = ""
                    remark = ""
                    avatar = "/static/img/favicon.ico"
                    
                    # 提取昵称 - 处理嵌套结构
                    if contact_detail and 'NickName' in contact_detail:
                        if isinstance(contact_detail['NickName'], dict) and 'string' in contact_detail['NickName']:
                            nickname = contact_detail['NickName']['string'] or username
                        else:
                            nickname = str(contact_detail['NickName']) or username
                    
                    # 提取备注 - 处理嵌套结构
                    if contact_detail and 'Remark' in contact_detail:
                        if isinstance(contact_detail['Remark'], dict) and 'string' in contact_detail['Remark']:
                            remark = contact_detail['Remark']['string'] or ""
                        elif isinstance(contact_detail['Remark'], str):
                            remark = contact_detail['Remark']
                    
                    # 提取头像URL - 直接使用URL，无需处理嵌套结构
                    if contact_detail and 'SmallHeadImgUrl' in contact_detail and contact_detail['SmallHeadImgUrl']:
                        avatar = contact_detail['SmallHeadImgUrl']
                    elif contact_detail and 'BigHeadImgUrl' in contact_detail and contact_detail['BigHeadImgUrl']:
                        avatar = contact_detail['BigHeadImgUrl']
                    
                    # 确定显示名称（优先使用备注，其次昵称，最后是wxid）
                    display_name = remark or nickname or username
                    
                    # 创建联系人对象
                    contact = {
                        "wxid": username,
                        "name": display_name,
                        "nickname": nickname,
                        "remark": remark,
                        "avatar": avatar,
                        "type": contact_type,
                        "online": True,
                        "starred": False
                    }
                    contact_list.append(contact)
            else:
                # 回退到使用昵称API
                has_nickname_method = hasattr(bot_instance.bot, 'get_nickname')
                if has_nickname_method:
                    logger.info("使用get_nickname方法获取联系人昵称")
                    
                    # 分批获取联系人昵称 (每批最多20个)
                    batch_size = 20
                    all_nicknames = {}
                    
                    # 分批处理联系人
                    for i in range(0, len(contact_usernames), batch_size):
                        batch = contact_usernames[i:i+batch_size]
                        try:
                            # 调用API获取昵称
                            if asyncio.get_event_loop().is_running():
                                nicknames = await bot_instance.bot.get_nickname(batch)
                            else:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    nicknames = loop.run_until_complete(bot_instance.bot.get_nickname(batch))
                                finally:
                                    loop.close()
                            
                            # 将昵称与wxid关联
                            for j, wxid in enumerate(batch):
                                if j < len(nicknames) and nicknames[j]:
                                    all_nicknames[wxid] = nicknames[j]
                                else:
                                    all_nicknames[wxid] = wxid
                        except Exception as e:
                            logger.error(f"获取昵称批次失败 ({i}~{i+batch_size-1}): {e}")
                            # 对失败批次使用wxid作为昵称
                            for wxid in batch:
                                all_nicknames[wxid] = wxid
                else:
                    logger.warning("bot既没有get_contract_detail也没有get_nickname方法，将使用wxid作为昵称")
                    all_nicknames = {username: username for username in contact_usernames}
                
                # 根据获取的昵称创建联系人对象
                for username in contact_usernames:
                    # 根据wxid格式确定联系人类型
                    contact_type = "friend"
                    if username.endswith("@chatroom"):
                        contact_type = "group"
                    elif username.startswith("gh_"):
                        contact_type = "official"
                    
                    # 获取昵称（如果有）
                    nickname = all_nicknames.get(username, username)
                    display_name = nickname if nickname else username
                    
                    # 创建联系人对象
                    contact = {
                        "wxid": username,
                        "name": display_name,
                        "nickname": nickname,
                        "remark": "",
                        "avatar": "/static/img/favicon.ico",
                        "type": contact_type,
                        "online": True,
                        "starred": False
                    }
                    contact_list.append(contact)
            
            # 创建响应数据
            response_data = {
                "success": True,
                "data": contact_list,
                "timestamp": int(time.time())
            }
            
            # 将结果缓存到文件
            try:
                with open(contacts_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(response_data, f, ensure_ascii=False, indent=2)
                logger.info(f"联系人列表已缓存至 {contacts_cache_file}")
            except Exception as e:
                logger.error(f"缓存联系人列表失败: {e}")
            
            # 返回联系人列表
            logger.success(f"成功获取到{len(contact_list)}个联系人")
            return JSONResponse(content=response_data)
        
        except Exception as e:
            logger.error(f"获取联系人列表失败: {e}")
            logger.error(traceback.format_exc())
            
            # 返回空列表和错误信息
            return JSONResponse(content={
                "success": False,
                "error": f"获取联系人列表失败: {str(e)}",
                "data": []
            })

    # 添加一个请求限制和计数器
    request_counters = {}
    request_timestamps = {}
    REQUEST_RATE_LIMIT = 5  # 每10秒最多5次请求

    @app.post('/api/contacts/details', response_class=JSONResponse)
    async def api_contacts_details(request: Request):
        logger.info("收到联系人详情批量请求")
        # 获取客户端IP
        client_ip = request.client.host
        current_time = time.time()
        
        # 检查请求频率
        if client_ip in request_counters:
            # 清除10秒前的请求记录
            request_timestamps[client_ip] = [t for t in request_timestamps[client_ip] if current_time - t < 10]
            
            # 检查10秒内的请求次数
            if len(request_timestamps[client_ip]) >= REQUEST_RATE_LIMIT:
                logger.warning(f"客户端 {client_ip} 请求频率过高，已限制")
                return JSONResponse(
                    content={
                        'success': False,
                        'error': '请求过于频繁，请稍后再试',
                        'rate_limited': True
                    }
                )
        else:
            request_counters[client_ip] = 0
            request_timestamps[client_ip] = []
        
        # 更新请求计数和时间戳
        request_counters[client_ip] += 1
        request_timestamps[client_ip].append(current_time)
        
        logger.info(f"客户端 {client_ip} 联系人详情请求计数: {request_counters[client_ip]}")

        try:
            # 验证用户是否登录
            username = await check_auth(request)
            if not username:
                logger.warning("未登录用户尝试获取联系人详情")
                return JSONResponse(
                    content={
                        'success': False,
                        'error': '用户未登录'
                    }
                )
                
            # 获取请求的联系人ID列表
            data = await request.json()
            if not data or 'wxids' not in data:
                logger.warning("请求缺少wxids参数")
                return JSONResponse(
                    content={
                        'success': False,
                        'error': '缺少wxids参数'
                    }
                )

            wxids = data['wxids']
            # 验证wxids是否为列表且不为空
            if not isinstance(wxids, list) or len(wxids) == 0:
                logger.warning(f"wxids参数格式错误: {wxids}")
                return JSONResponse(
                    content={
                        'success': False,
                        'error': 'wxids必须是非空列表'
                    }
                )
                
            # 限制每次请求最多20个
            if len(wxids) > 20:
                logger.warning(f"请求的wxids数量超过限制: {len(wxids)}")
                wxids = wxids[:20]
                
            logger.info(f"正在获取 {len(wxids)} 个联系人的详情")
            
            # 尝试首先从缓存中获取联系人信息
            cache_dir = os.path.join("data", "cache")
            os.makedirs(cache_dir, exist_ok=True)
            contacts_cache_file = os.path.join(cache_dir, "contacts_cache.json")
            
            # 从缓存中加载现有联系人数据
            cached_contacts = {}
            if os.path.exists(contacts_cache_file):
                try:
                    with open(contacts_cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                        if isinstance(cache_data, dict) and 'data' in cache_data:
                            for contact in cache_data['data']:
                                if 'wxid' in contact:
                                    cached_contacts[contact['wxid']] = contact
                            logger.info(f"从缓存加载了 {len(cached_contacts)} 个联系人")
                except Exception as e:
                    logger.error(f"读取联系人缓存失败: {str(e)}")
            
            # 获取机器人实例
            # 从会话数据中获取wxid
            session_cookie = request.cookies.get("session")
            wxid_from_session = None
            if session_cookie:
                try:
                    serializer = URLSafeSerializer(config["secret_key"], "session")
                    session_data = serializer.loads(session_cookie)
                    wxid_from_session = session_data.get("wxid")
                except Exception as e:
                    logger.error(f"解析会话数据失败: {str(e)}")
            
            # 获取机器人实例
            wxapi = get_bot(wxid_from_session)
            if not wxapi:
                logger.error("无法获取机器人实例")
                # 如果有缓存数据，尝试从缓存返回
                if cached_contacts:
                    results = []
                    missing_wxids = []
                    for wxid in wxids:
                        if wxid in cached_contacts:
                            contact = cached_contacts[wxid]
                            results.append({
                                'wxid': wxid,
                                'nickname': contact.get('nickname', wxid),
                                'avatar': contact.get('avatar', ''),
                                'remark': contact.get('remark', ''),
                                'alias': contact.get('alias', ''),
                                'from_cache': True
                            })
                        else:
                            missing_wxids.append(wxid)
                            results.append({'wxid': wxid, 'nickname': wxid, 'error': '详情未找到', 'from_cache': True})
                    
                    if missing_wxids:
                        logger.warning(f"以下 {len(missing_wxids)} 个wxid在缓存中未找到: {missing_wxids}")
                    
                    logger.info(f"从缓存返回 {len(results)} 个联系人详情")
                    return JSONResponse(
                        content={
                            'success': True,
                            'data': results,
                            'from_cache': True
                        }
                    )
                else:
                    return JSONResponse(
                        content={
                            'success': False,
                            'error': '无法获取微信机器人实例，且没有缓存数据'
                        }
                    )
            
            # 获取联系人详情
            results = []
            success_count = 0
            cached_count = 0
            api_count = 0
            
            for wxid in wxids:
                logger.debug(f"正在获取联系人详情: {wxid}")
                # 首先检查缓存
                if wxid in cached_contacts:
                    cached_contact = cached_contacts[wxid]
                    contact_info = {
                        'wxid': wxid,
                        'nickname': cached_contact.get('nickname', wxid),
                        'avatar': cached_contact.get('avatar', ''),
                        'remark': cached_contact.get('remark', ''),
                        'alias': cached_contact.get('alias', ''),
                        'from_cache': True
                    }
                    results.append(contact_info)
                    success_count += 1
                    cached_count += 1
                    continue
                
                # 缓存中没有，尝试从API获取
                try:
                    # 调用API获取联系人详情
                    detail = await wxapi.get_contract_detail(wxid)
                    
                    # 处理返回结果
                    if detail:
                        # 检查detail是否为列表
                        if isinstance(detail, list) and len(detail) > 0:
                            # 如果是列表，获取第一个元素
                            detail_item = detail[0]
                            if isinstance(detail_item, dict):
                                # 提取信息并添加到结果中
                                contact_info = {
                                    'wxid': wxid,
                                    'nickname': detail_item.get('nickname', wxid),
                                    'avatar': detail_item.get('avatar', ''),
                                    'remark': detail_item.get('remark', ''),
                                    'alias': detail_item.get('alias', '')
                                }
                                results.append(contact_info)
                                success_count += 1
                                api_count += 1
                            else:
                                logger.warning(f"联系人 {wxid} 详情项不是字典: {detail_item}")
                                # 尝试从缓存获取备用数据
                                if wxid in cached_contacts:
                                    cached_contact = cached_contacts[wxid]
                                    contact_info = {
                                        'wxid': wxid,
                                        'nickname': cached_contact.get('nickname', wxid),
                                        'avatar': cached_contact.get('avatar', ''),
                                        'remark': cached_contact.get('remark', ''),
                                        'alias': cached_contact.get('alias', ''),
                                        'from_cache': True
                                    }
                                    results.append(contact_info)
                                    success_count += 1
                                    cached_count += 1
                                else:
                                    results.append({'wxid': wxid, 'nickname': wxid, 'error': '详情格式错误'})
                        elif isinstance(detail, dict):
                            # 如果是字典，直接使用
                            contact_info = {
                                'wxid': wxid,
                                'nickname': detail.get('nickname', wxid),
                                'avatar': detail.get('avatar', ''),
                                'remark': detail.get('remark', ''),
                                'alias': detail.get('alias', '')
                            }
                            results.append(contact_info)
                            success_count += 1
                            api_count += 1
                        else:
                            logger.warning(f"联系人 {wxid} 详情格式不支持: {type(detail)}")
                            # 尝试从缓存获取备用数据
                            if wxid in cached_contacts:
                                cached_contact = cached_contacts[wxid]
                                contact_info = {
                                    'wxid': wxid,
                                    'nickname': cached_contact.get('nickname', wxid),
                                    'avatar': cached_contact.get('avatar', ''),
                                    'remark': cached_contact.get('remark', ''),
                                    'alias': cached_contact.get('alias', ''),
                                    'from_cache': True
                                }
                                results.append(contact_info)
                                success_count += 1
                                cached_count += 1
                            else:
                                results.append({'wxid': wxid, 'nickname': wxid, 'error': '详情格式不支持'})
                    else:
                        logger.warning(f"联系人 {wxid} 详情为空")
                        # 尝试从缓存获取备用数据
                        if wxid in cached_contacts:
                            cached_contact = cached_contacts[wxid]
                            contact_info = {
                                'wxid': wxid,
                                'nickname': cached_contact.get('nickname', wxid),
                                'avatar': cached_contact.get('avatar', ''),
                                'remark': cached_contact.get('remark', ''),
                                'alias': cached_contact.get('alias', ''),
                                'from_cache': True
                            }
                            results.append(contact_info)
                            success_count += 1
                            cached_count += 1
                        else:
                            results.append({'wxid': wxid, 'nickname': wxid, 'error': '详情为空'})
                except Exception as e:
                    logger.error(f"获取联系人 {wxid} 详情时出错: {str(e)}")
                    # 尝试从缓存获取备用数据
                    if wxid in cached_contacts:
                        cached_contact = cached_contacts[wxid]
                        contact_info = {
                            'wxid': wxid,
                            'nickname': cached_contact.get('nickname', wxid),
                            'avatar': cached_contact.get('avatar', ''),
                            'remark': cached_contact.get('remark', ''),
                            'alias': cached_contact.get('alias', ''),
                            'from_cache': True
                        }
                        results.append(contact_info)
                        success_count += 1
                        cached_count += 1
                    else:
                        results.append({'wxid': wxid, 'nickname': wxid, 'error': str(e)})
            
            logger.info(f"成功获取 {success_count}/{len(wxids)} 个联系人详情 (缓存: {cached_count}, API: {api_count})")
            return JSONResponse(
                content={
                    'success': True,
                    'data': results
                }
            )
            
        except Exception as e:
            logger.error(f"处理联系人详情批量请求时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return JSONResponse(
                content={
                    'success': False,
                    'error': f'服务器错误: {str(e)}'
                }
            )

    # 在setup_routes()函数内部添加群聊API
    @app.post("/api/group/members", response_class=JSONResponse)
    async def api_group_members(request: Request):
        """获取群聊成员列表 - 已禁用"""
        # 检查用户是否已登录
        username = await check_auth(request)
        if not username:
            return JSONResponse(
                status_code=401,
                content={"code": 401, "msg": "未登录"}
            )

        # 该功能已禁用，直接返回空结果
        logger.info(f"群成员获取功能已被禁用，返回空数据")
        return JSONResponse(
            content={"code": 0, "data": [], "message": "群成员获取功能已禁用"}
        )

    # 添加获取群公告的API端点
    @app.post("/api/group/announcement", response_class=JSONResponse)
    async def api_group_announcement(request: Request):
        """获取群聊公告"""
        # 检查用户是否已登录
        username = await check_auth(request)
        if not username:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "未登录，请先登录"}
            )
            
        try:
            # 解析请求数据
            data = await request.json()
            wxid = data.get("wxid")
            
            if not wxid:
                return JSONResponse(
                    content={"success": False, "error": "缺少群聊ID(wxid)参数"}
                )
            
            # 只有群才有公告
            if not wxid.endswith("@chatroom"):
                return JSONResponse(
                    content={"success": False, "error": "无效的群ID，只有群聊才有公告"}
                )
            
            # 由于微信API限制，公告功能已禁用
            logger.info(f"群公告功能已被禁用，返回空公告")
            return JSONResponse(
                content={"success": True, "announcement": ""}
            )
            
        except Exception as e:
            logger.error(f"获取群公告时出错: {str(e)}")
            return JSONResponse(
                content={"success": False, "error": f"服务器错误: {str(e)}"}
            )
    
    # 添加发送消息的API端点
    @app.post("/api/send_message", response_class=JSONResponse)
    async def api_send_message(request: Request):
        """发送消息到指定联系人"""
        # 检查用户是否已登录
        username = await check_auth(request)
        if not username:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "未登录，请先登录"}
            )
            
        try:
            # 解析请求数据
            data = await request.json()
            to_wxid = data.get("to_wxid")
            content = data.get("content")
            at_users = data.get("at", "")
            
            if not to_wxid or not content:
                return JSONResponse(
                    content={"success": False, "error": "缺少必要参数，需要to_wxid和content"}
                )
            
            # 确保机器人实例可用
            if not bot_instance or not hasattr(bot_instance, 'bot'):
                logger.error("bot_instance未设置或不可用")
                return JSONResponse(
                    content={"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
                )
            
            # 检查方法是否存在
            if not hasattr(bot_instance.bot, 'send_text_message'):
                logger.error("bot.send_text_message方法不存在")
                return JSONResponse(
                    content={"success": False, "error": "微信API不支持发送文本消息"}
                )
            
            # 发送消息
            try:
                logger.info(f"正在向 {to_wxid} 发送消息: {content[:20]}...")
                result = await bot_instance.bot.send_text_message(to_wxid, content, at_users)
                logger.success(f"消息发送成功，结果: {result}")
                
                return JSONResponse(
                    content={
                        "success": True, 
                        "message": "消息发送成功",
                        "data": {
                            "client_msg_id": result[0],
                            "create_time": result[1],
                            "new_msg_id": result[2]
                        }
                    }
                )
            except Exception as e:
                logger.error(f"发送消息时出错: {e}")
                return JSONResponse(
                    content={"success": False, "error": f"发送消息失败: {str(e)}"}
                )
                
        except Exception as e:
            logger.error(f"处理发送消息请求时出错: {str(e)}")
            return JSONResponse(
                content={"success": False, "error": f"服务器错误: {str(e)}"}
            )

    # 添加获取聊天记录的API
    @app.post("/api/chat/history", response_class=JSONResponse)
    async def api_chat_history(request: Request):
        """获取与特定联系人的聊天记录"""
        # 检查用户是否已登录
        username = await check_auth(request)
        if not username:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "未登录，请先登录"}
            )
        
        # 返回功能已禁用的消息
        return JSONResponse(
            content={
                "success": False,
                "error": "聊天记录和消息同步功能已被禁用",
                "message": "该功能已被管理员移除，不再提供聊天历史记录检索服务"
            }
        )

# 添加一个简化的文件上传API - 直接在模块顶层定义，确保路由被正确注册
@app.post("/upload")
async def simple_upload(request: Request, files: List[UploadFile] = File(...)):
    """简化的文件上传API，直接保存到项目的files目录"""
    try:
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            logger.warning("简化上传API访问失败：未认证")
            return JSONResponse(status_code=401, content={
                'success': False, 
                'message': '未认证，请先登录'
            })
        
        # 使用固定的上传目录 - 项目根目录下的files文件夹
        upload_dir = os.path.join(Path(current_dir).parent, "files")
        os.makedirs(upload_dir, exist_ok=True)
        
        logger.debug(f"用户 {username} 请求上传文件到路径: {upload_dir}")
        
        # 处理上传的文件
        uploaded_files = []
        errors = []
        
        for file in files:
            try:
                # 构建目标文件路径
                target_file_path = os.path.join(upload_dir, file.filename)
                
                # 检查文件是否已存在
                if os.path.exists(target_file_path):
                    logger.warning(f"文件已存在: {target_file_path}")
                    # 添加时间戳后缀，避免覆盖
                    filename_parts = os.path.splitext(file.filename)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    new_filename = f"{filename_parts[0]}_{timestamp}{filename_parts[1]}"
                    target_file_path = os.path.join(upload_dir, new_filename)
                    logger.debug(f"自动重命名为: {new_filename}")
                
                # 保存文件
                logger.debug(f"保存上传的文件: {target_file_path}")
                content = await file.read()
                with open(target_file_path, "wb") as f:
                    f.write(content)
                
                # 记录成功上传的文件
                file_stats = os.stat(target_file_path)
                uploaded_files.append({
                    'filename': os.path.basename(target_file_path),
                    'size': file_stats.st_size,
                    'modified': file_stats.st_mtime
                })
                
                logger.info(f"用户 {username} 成功上传文件: {os.path.basename(target_file_path)}")
                
            except Exception as e:
                logger.error(f"上传文件 {file.filename} 失败: {str(e)}")
                errors.append({
                    'filename': file.filename,
                    'error': str(e)
                })
        
        # 返回上传结果
        return JSONResponse(content={
            'success': True if uploaded_files else False,
            'message': f'成功上传 {len(uploaded_files)} 个文件，失败 {len(errors)} 个' if uploaded_files else '上传失败',
            'uploaded_files': uploaded_files,
            'errors': errors
        })
        
    except Exception as e:
        logger.error(f"简化上传API处理文件时出错: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"服务器错误: {str(e)}"}
        )

# 添加另一个备用上传API路径，确保多种路径都能正常工作
@app.post("/api/upload")
async def api_upload(request: Request, files: List[UploadFile] = File(...)):
    """备用上传API路径 - 转发到简化上传API"""
    return await simple_upload(request, files)

# 启动服务器
def start_server(host_arg=None, port_arg=None, username_arg=None, password_arg=None, debug_arg=None, bot=None):
    """启动管理后台服务器"""
    global config
    
    # 加载配置
    load_config()
    
    # 更新配置
    if host_arg is not None:
        config["host"] = host_arg
    if port_arg is not None:
        config["port"] = port_arg
    if username_arg is not None:
        config["username"] = username_arg
    if password_arg is not None:
        config["password"] = password_arg
    if debug_arg is not None:
        config["debug"] = debug_arg
    
    # 设置bot实例
    if bot is not None:
        set_bot_instance(bot)
    
    # 初始化FastAPI应用
    init_app()
    
    # 在新线程中启动服务器
    server_thread = threading.Thread(
        target=lambda: uvicorn.run(
            app,
            host=config["host"],
            port=config["port"]
        ),
        daemon=True
    )
    server_thread.start()
    
    return server_thread

# 获取机器人实例
def get_bot(wxid):
    """根据wxid获取机器人实例"""
    logger.info(f"尝试获取机器人实例, 请求wxid: {wxid}")
    
    if not bot_instance:
        logger.error("bot_instance不存在，机器人可能未初始化")
        return None
    
    if not wxid:
        # 尝试从系统状态获取wxid
        bot_status = get_bot_status()
        if bot_status and "wxid" in bot_status:
            wxid = bot_status["wxid"]
            logger.info(f"从系统状态获取到wxid: {wxid}")
        else:
            logger.warning("无法从系统状态获取wxid，尝试使用默认实例")
            # 尝试使用默认的bot_instance
            bot = getattr(bot_instance, 'bot', None)
            if not bot:
                logger.warning("默认bot_instance没有bot属性，尝试使用wxapi属性")
                bot = getattr(bot_instance, 'wxapi', None)
                if not bot:
                    logger.error("默认实例没有bot或wxapi属性，无法获取机器人")
                else:
                    logger.info("成功从默认实例获取wxapi属性")
            else:
                logger.info("成功从默认实例获取bot属性")
            return bot
    
    # 如果提供了wxid或从系统状态获取到了wxid
    try:
        # 尝试获取bot属性
        logger.debug(f"尝试从bot_instance获取bot属性")
        bot = getattr(bot_instance, 'bot', None)
        
        if not bot:
            logger.warning("bot_instance没有bot属性，尝试获取wxapi属性")
            # 尝试获取wxapi属性
            bot = getattr(bot_instance, 'wxapi', None)
            if not bot:
                logger.error("bot_instance既没有bot属性也没有wxapi属性")
                return None
            else:
                logger.info("成功获取wxapi属性")
        else:
            logger.info("成功获取bot属性")
        
        # 检查获取到的bot实例是否有效
        if hasattr(bot, 'wxid'):
            logger.info(f"获取到的bot实例wxid: {bot.wxid}")
        else:
            logger.warning("获取到的bot实例没有wxid属性")
        
        return bot
    except Exception as e:
        logger.exception(f"获取机器人实例时发生异常: {str(e)}")
        return None

    # 插件市场相关API ===========================================
    
    # API: 获取插件市场列表
    @app.get("/api/plugin_market", response_class=JSONResponse)
    async def api_get_plugin_market(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
        
        try:
            # 从远程服务器获取插件市场数据
            async with aiohttp.ClientSession() as session:
                try:
                    # 设置超时时间防止长时间等待
                    async with session.get('https://api.xybot.icu/plugin_market', timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            plugins = data.get('plugins', [])
                            return {"success": True, "plugins": plugins}
                        else:
                            error_text = await response.text()
                            return {"success": False, "error": f"远程服务器返回错误: {response.status} - {error_text}"}
                except aiohttp.ClientError as e:
                    logger.error(f"连接远程插件市场失败: {e}")
                    # 尝试从本地缓存获取
                    cache_path = os.path.join(current_dir, 'plugin_market_cache.json')
                    if os.path.exists(cache_path):
                        with open(cache_path, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                            return {"success": True, "plugins": cache_data.get('plugins', []), "cached": True}
                    else:
                        return {"success": False, "error": f"无法连接到远程服务器: {str(e)}"}
        except Exception as e:
            logger.error(f"获取插件市场失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # API: 提交插件到市场
    @app.post("/api/plugin_market/submit", response_class=JSONResponse)
    async def api_submit_plugin(
        request: Request,
        name: str = Form(...),
        description: str = Form(...),
        author: str = Form(...),
        version: str = Form(...),
        github_url: str = Form(...),
        tags: str = Form(None),
        requirements: str = Form(None),
        icon: UploadFile = File(None)
    ):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
        
        try:
            # 准备提交数据
            plugin_data = {
                "name": name,
                "description": description,
                "author": author,
                "version": version,
                "github_url": github_url,
                "tags": tags or "",
                "requirements": requirements or "",
                "submitted_by": username,  # 记录提交者
                "submitted_at": datetime.now().isoformat(),  # 记录提交时间
                "status": "pending"  # 状态：pending, approved, rejected
            }
            
            # 处理图标上传
            if icon and icon.filename:
                # 读取图标内容并转为base64
                icon_content = await icon.read()
                base64_icon = base64.b64encode(icon_content).decode('utf-8')
                plugin_data["icon_base64"] = base64_icon
            
            # 发送到远程服务器
            async with aiohttp.ClientSession() as session:
                try:
                    # 将数据发送到远程服务器进行审核
                    async with session.post(
                        'https://api.xybot.icu/plugin_market/submit',
                        json=plugin_data,
                        timeout=30
                    ) as response:
                        if response.status == 200:
                            resp_data = await response.json()
                            return {"success": True, "message": "插件提交成功，等待审核", "id": resp_data.get("id")}
                        else:
                            error_text = await response.text()
                            return {"success": False, "error": f"远程服务器返回错误: {response.status} - {error_text}"}
                except aiohttp.ClientError as e:
                    logger.error(f"提交插件到远程服务器失败: {e}")
                    
                    # 保存到本地临时文件，稍后重试
                    temp_dir = os.path.join(current_dir, 'pending_plugins')
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_file = os.path.join(temp_dir, f"{int(time.time())}_{name.replace(' ', '_')}.json")
                    
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(plugin_data, f, ensure_ascii=False, indent=2)
                    
                    return {
                        "success": True, 
                        "message": "由于网络问题，插件已暂存在本地，将在网络恢复后自动提交",
                        "local_only": True
                    }
        except Exception as e:
            logger.error(f"提交插件失败: {str(e)}\n{traceback.format_exc()}")
            return {"success": False, "error": str(e)}
    
    # API: 安装插件
    @app.post("/api/plugin_market/install", response_class=JSONResponse)
    async def api_install_plugin(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
        
        try:
            # 获取请求数据
            data = await request.json()
            plugin_name = data.get('name')
            github_url = data.get('github_url')
            
            if not plugin_name or not github_url:
                return {"success": False, "error": "缺少必要参数"}
            
            # 获取DependencyManager插件实例
            dependency_manager = None
            from utils.plugin_manager import plugin_manager
            for plugin in plugin_manager.plugins:
                if plugin.__class__.__name__ == "DependencyManager":
                    dependency_manager = plugin
                    break
            
            if not dependency_manager:
                return {"success": False, "error": "DependencyManager插件未安装"}
            
            # 使用DependencyManager的安装方法
            await dependency_manager._handle_github_install(
                bot_instance,
                "admin",  # 使用admin作为chat_id
                github_url
            )
            
            return {"success": True, "message": f"插件 {plugin_name} 安装成功"}
            
        except Exception as e:
            logger.error(f"安装插件失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # 周期性任务：同步本地待审核插件到服务器
    async def sync_pending_plugins():
        """检查本地待审核插件并尝试同步到服务器"""
        try:
            temp_dir = os.path.join(current_dir, 'pending_plugins')
            if not os.path.exists(temp_dir):
                return
            
            for filename in os.listdir(temp_dir):
                if not filename.endswith('.json'):
                    continue
                
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    plugin_data = json.load(f)
                
                # 尝试发送到服务器
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(
                            'https://api.xybot.icu/plugin_market/submit',
                            json=plugin_data,
                            timeout=10
                        ) as response:
                            if response.status == 200:
                                # 删除本地文件
                                os.remove(file_path)
                                logger.info(f"成功同步插件到服务器: {plugin_data.get('name')}")
                    except Exception as e:
                        logger.error(f"同步插件到服务器失败: {e}")
                        continue  # 跳过当前文件，稍后重试
        except Exception as e:
            logger.error(f"同步待审核插件失败: {str(e)}")
    
    # 周期性任务：缓存插件市场数据
    async def cache_plugin_market():
        """从远程服务器缓存插件市场数据到本地"""
        try:
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get('https://api.xybot.icu/plugin_market', timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # 保存到本地缓存
                            cache_path = os.path.join(current_dir, 'plugin_market_cache.json')
                            with open(cache_path, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                            
                            logger.info(f"成功缓存插件市场数据，共{len(data.get('plugins', []))}个插件")
                except Exception as e:
                    logger.error(f"缓存插件市场数据失败: {e}")
        except Exception as e:
            logger.error(f"缓存插件市场任务失败: {str(e)}")
    
    # 缓存插件市场数据
    @app.on_event("startup")
    async def startup_cache_plugin_market():
        # 应用启动时缓存一次插件市场数据
        asyncio.create_task(cache_plugin_market())
        
        # 设置定时任务每小时更新一次缓存
        async def periodic_cache():
            while True:
                await asyncio.sleep(3600)  # 每小时执行一次
                await cache_plugin_market()
        
        # 设置定时任务每10分钟同步一次待审核插件
        async def periodic_sync():
            while True:
                await asyncio.sleep(600)  # 每10分钟执行一次
                await sync_pending_plugins()
        
        # 启动定时任务
        asyncio.create_task(periodic_cache())
        asyncio.create_task(periodic_sync())

    # 插件市场API配置
    PLUGIN_MARKET_API = {
        "BASE_URL": "https://xianan.xin:1562/api",  # 修改这一行
        "LIST": "/plugins?status=approved",
        "DETAIL": "/plugins/",
        "INSTALL": "/plugins/install/",
    }
    
    # API: 安装插件
    @app.post("/api/plugins/install", response_class=JSONResponse)
    async def api_install_plugin(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
        
        try:
            # 获取请求数据
            data = await request.json()
            plugin_name = data.get('name')
            plugin_description = data.get('description')
            plugin_author = data.get('author')
            plugin_version = data.get('version')
            github_url = data.get('github_url')
            
            if not plugin_name or not github_url:
                return {"success": False, "error": "缺少必要参数"}
            
            # 创建临时目录
            import tempfile
            import shutil
            import requests
            import zipfile
            import io
            import sys
            import subprocess
            from pathlib import Path
            
            temp_dir = tempfile.mkdtemp()
            plugin_dir = os.path.join("plugins", plugin_name)
            
            try:
                # 构建 ZIP 下载链接
                if github_url.endswith('.git'):
                    zip_url = github_url[:-4] + '/archive/refs/heads/main.zip'
                else:
                    zip_url = github_url + '/archive/refs/heads/main.zip'
                
                # 下载 ZIP 文件
                logger.info(f"正在从 {zip_url} 下载插件...")
                try:
                    response = requests.get(zip_url, timeout=30)
                    if response.status_code != 200:
                        # 尝试使用 master 分支
                        zip_url = zip_url.replace('/main.zip', '/master.zip')
                        logger.info(f"尝试从 master 分支下载: {zip_url}")
                        response = requests.get(zip_url, timeout=30)
                except Exception as e:
                    logger.error(f"下载插件失败: {str(e)}")
                    return {"success": False, "error": f"下载插件失败: {str(e)}"}
                
                if response.status_code != 200:
                    return {"success": False, "error": f"下载插件失败: HTTP {response.status_code}"}
                
                # 解压 ZIP 文件
                logger.info(f"下载完成，文件大小: {len(response.content)} 字节")
                logger.info(f"解压 ZIP 文件到: {temp_dir}")
                
                z = zipfile.ZipFile(io.BytesIO(response.content))
                z.extractall(temp_dir)
                
                # 检查插件是否已存在
                if os.path.exists(plugin_dir):
                    # 如果存在，先备份配置文件
                    config_path = os.path.join(plugin_dir, "config.toml")
                    config_backup = None
                    if os.path.exists(config_path):
                        with open(config_path, "rb") as f:
                            config_backup = f.read()
                    
                    # 删除旧目录
                    shutil.rmtree(plugin_dir)
                
                # 创建插件目录
                os.makedirs(plugin_dir, exist_ok=True)
                
                # ZIP 文件解压后通常会有一个包含所有文件的顶级目录
                extracted_dirs = os.listdir(temp_dir)
                if len(extracted_dirs) == 1:
                    extract_subdir = os.path.join(temp_dir, extracted_dirs[0])
                    
                    # 将文件从解压的子目录复制到目标目录
                    for item in os.listdir(extract_subdir):
                        s = os.path.join(extract_subdir, item)
                        d = os.path.join(plugin_dir, item)
                        if os.path.isdir(s):
                            shutil.copytree(s, d, dirs_exist_ok=True)
                        else:
                            shutil.copy2(s, d)
                else:
                    # 直接解压到目标目录
                    for item in os.listdir(temp_dir):
                        s = os.path.join(temp_dir, item)
                        d = os.path.join(plugin_dir, item)
                        if os.path.isdir(s):
                            shutil.copytree(s, d, dirs_exist_ok=True)
                        else:
                            shutil.copy2(s, d)
                
                # 恢复配置文件（如果有）
                if config_backup:
                    with open(config_path, "wb") as f:
                        f.write(config_backup)
                else:
                    # 确保创建一个空的配置文件（防止加载插件时出错）
                    config_path = os.path.join(plugin_dir, "config.toml")
                    if not os.path.exists(config_path):
                        with open(config_path, "w", encoding="utf-8") as f:
                            f.write("# 插件配置文件\n")
                
                # 安装依赖
                requirements_file = os.path.join(plugin_dir, "requirements.txt")
                if os.path.exists(requirements_file):
                    logger.info(f"正在安装插件依赖...")
                    process = subprocess.Popen(
                        [sys.executable, "-m", "pip", "install", "-r", requirements_file],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        logger.warning(f"安装依赖可能失败: {stderr}")
                
                # 添加到已安装插件列表
                from utils.plugin_manager import plugin_manager
                success = await plugin_manager.load_plugin_from_directory(bot_instance, plugin_name)
                
                if success:
                    return {"success": True, "message": f"插件 {plugin_name} 安装成功"}
                else:
                    return {"success": False, "error": f"插件加载失败"}
                
            except Exception as e:
                logger.error(f"安装插件过程出错: {str(e)}")
                return {"success": False, "error": str(e)}
            finally:
                # 清理临时目录
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            
        except Exception as e:
            logger.error(f"安装插件失败: {str(e)}")
            return {"success": False, "error": str(e)}

    # 注释掉重复的API端点定义
    #@app.get('/api/system/info')
    #async def system_info_api(request: Request):
    #    """系统信息API"""
    #    try:
    #        info = get_system_info()
    #        return JSONResponse(content={
    #            "success": True,
    #            "data": info,
    #            "error": None
    #        })
    #    except Exception as e:
    #        logger.error(f"获取系统信息API失败: {str(e)}")
    #        return JSONResponse(content={
    #            "success": False,
    #            "data": {
    #                "hostname": "unknown",
    #                "platform": "unknown",
    #                "python_version": "unknown",
    #                "cpu_count": 0,
    #                "memory_total": 0,
    #                "memory_available": 0,
    #                "disk_total": 0,
    #                "disk_free": 0,
    #                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #            },
    #            "error": str(e)
    #        })

    def check_auth(request: Request):
        """检查用户认证状态"""
        try:
            token = request.headers.get('Authorization')
            if not token:
                # 尝试从cookie中获取token
                token = request.cookies.get('token')
                
            if not token:
                raise HTTPException(status_code=401, detail="未登录或登录已过期")
                
            # 这里可以添加token验证的逻辑
            # 例如验证token的有效性，检查是否过期等
            # 如果验证失败，抛出HTTPException(status_code=401)
            
            return True
        except Exception as e:
            logger.error(f"认证检查失败: {str(e)}")
            raise HTTPException(status_code=401, detail="认证失败")

    from fastapi import WebSocket
    from utils.plugin_manager import plugin_manager

    # WebSocket连接管理
    class ConnectionManager:
        def __init__(self):
            self.active_connections: List[WebSocket] = []

        async def connect(self, websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)

        def disconnect(self, websocket: WebSocket):
            self.active_connections.remove(websocket)

        async def send_message(self, message: str, websocket: WebSocket):
            await websocket.send_text(message)

    manager = ConnectionManager()

    @app.websocket("/ws/plugins")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                if data["action"] == "install_plugin":
                    plugin_data = data["data"]
                    try:
                        # 获取DependencyManager插件实例
                        dependency_manager = None
                        for plugin in plugin_manager.plugins:
                            if plugin.__class__.__name__ == "DependencyManager":
                                dependency_manager = plugin
                                break
                        
                        if not dependency_manager:
                            await websocket.send_json({
                                "type": "install_complete",
                                "success": False,
                                "error": "DependencyManager插件未安装"
                            })
                            continue
                        
                        # 发送进度消息
                        await websocket.send_json({
                            "type": "install_progress",
                            "message": "开始安装插件..."
                        })
                        
                        # 使用DependencyManager的安装方法
                        await dependency_manager._handle_github_install(
                            bot_instance,
                            "admin",  # 使用admin作为chat_id
                            plugin_data["github_url"]
                        )
                        
                        # 发送完成消息
                        await websocket.send_json({
                            "type": "install_complete",
                            "success": True
                        })
                        
                    except Exception as e:
                        logger.error(f"安装插件失败: {str(e)}")
                        await websocket.send_json({
                            "type": "install_complete",
                            "success": False,
                            "error": str(e)
                        })
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    @app.post("/api/dependency_manager/install", response_class=JSONResponse)
    async def api_dependency_manager_install(request: Request):
        # 检查认证状态
        username = await check_auth(request)
        if not username:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
        
        try:
            # 获取请求数据
            data = await request.json()
            plugin_name = data.get('name')
            github_url = data.get('github_url')
            
            if not plugin_name or not github_url:
                return {"success": False, "error": "缺少必要参数"}
            
            # 获取DependencyManager插件实例
            dependency_manager = None
            from utils.plugin_manager import plugin_manager
            for plugin in plugin_manager.plugins:
                if plugin.__class__.__name__ == "DependencyManager":
                    dependency_manager = plugin
                    break
            
            if not dependency_manager:
                return {"success": False, "error": "DependencyManager插件未安装"}
            
            # 使用DependencyManager的安装方法
            await dependency_manager._handle_github_install(
                bot_instance,
                "admin",  # 使用admin作为chat_id
                github_url
            )
            
            return {"success": True, "message": f"插件 {plugin_name} 安装成功"}
            
        except Exception as e:
            logger.error(f"安装插件失败: {str(e)}")
            return {"success": False, "error": str(e)}