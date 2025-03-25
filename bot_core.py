import asyncio
import json
import os
import sys
import time
import tomllib
from pathlib import Path

from loguru import logger

import WechatAPI
from database.XYBotDB import XYBotDB
from database.keyvalDB import KeyvalDB
from database.messsagDB import MessageDB
from utils.decorators import scheduler
from utils.plugin_manager import plugin_manager
from utils.xybot import XYBot

# 导入管理后台模块
try:
    # 正确设置导入路径
    admin_path = str(Path(__file__).resolve().parent)
    if admin_path not in sys.path:
        sys.path.append(admin_path)
    
    # 导入管理后台服务器模块
    try:
        from admin.server import set_bot_instance as admin_set_bot_instance
        logger.debug("成功导入admin.server.set_bot_instance")
    except ImportError as e:
        logger.error(f"导入admin.server.set_bot_instance失败: {e}")
        # 创建一个空函数
        def admin_set_bot_instance(bot):
            logger.warning("admin.server.set_bot_instance未导入，调用被忽略")
            return None
    
    # 直接定义状态更新函数，不依赖导入
    def update_bot_status(status, details=None, extra_data=None):
        """更新bot状态，供管理后台读取"""
        try:
            # 使用统一的路径写入状态文件 - 修复路径问题
            status_file = Path(admin_path) / "admin" / "bot_status.json"
            root_status_file = Path(admin_path) / "bot_status.json"
            
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
            
            # 添加额外数据
            if extra_data and isinstance(extra_data, dict):
                for key, value in extra_data.items():
                    current_status[key] = value
            
            # 确保目录存在
            status_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入status_file
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(current_status, f)
            
            # 写入root_status_file
            with open(root_status_file, "w", encoding="utf-8") as f:
                json.dump(current_status, f)
                
            logger.debug(f"成功更新bot状态: {status}, 路径: {status_file} 和 {root_status_file}")
            
            # 输出更多调试信息
            if "nickname" in current_status:
                logger.debug(f"状态文件包含昵称: {current_status['nickname']}")
            if "wxid" in current_status:
                logger.debug(f"状态文件包含微信ID: {current_status['wxid']}")
            if "alias" in current_status:
                logger.debug(f"状态文件包含微信号: {current_status['alias']}")
                
        except Exception as e:
            logger.error(f"更新bot状态失败: {e}")
    
    # 定义设置bot实例的函数
    def set_bot_instance(bot):
        """设置bot实例到管理后台"""
        # 先调用admin模块的设置函数
        admin_set_bot_instance(bot)
        
        # 更新状态
        update_bot_status("initialized", "机器人实例已设置")
        logger.success("成功设置bot实例并更新状态")
        
        return bot
        
except ImportError as e:
    logger.error(f"导入管理后台模块失败: {e}")
    # 创建空函数，防止程序崩溃
    def set_bot_instance(bot):
        logger.warning("管理后台模块未正确导入，set_bot_instance调用被忽略")
        return None
    
    # 创建一个空的状态更新函数
    def update_bot_status(status, details=None):
        logger.debug(f"管理后台模块未正确导入，状态更新被忽略: {status}")


async def bot_core():
    # 设置工作目录
    script_dir = Path(__file__).resolve().parent
    os.chdir(script_dir)
    
    # 更新初始化状态
    update_bot_status("initializing", "系统初始化中")
    
    # 读取配置文件
    config_path = script_dir / "main_config.toml"
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        logger.success("读取主设置成功")
    except Exception as e:
        logger.error(f"读取主设置失败: {e}")
        return

    # 启动WechatAPI服务
    server = WechatAPI.WechatAPIServer()
    api_config = config.get("WechatAPIServer", {})
    redis_host = api_config.get("redis-host", "127.0.0.1")
    redis_port = api_config.get("redis-port", 6379)
    logger.debug("Redis 主机地址: {}:{}", redis_host, redis_port)
    server.start(port=api_config.get("port", 9000),
                 mode=api_config.get("mode", "release"),
                 redis_host=redis_host,
                 redis_port=redis_port,
                 redis_password=api_config.get("redis-password", ""),
                 redis_db=api_config.get("redis-db", 0))

    # 实例化WechatAPI客户端
    bot = WechatAPI.WechatAPIClient("127.0.0.1", api_config.get("port", 9000))
    bot.ignore_protect = config.get("XYBot", {}).get("ignore-protection", False)

    # 等待WechatAPI服务启动
    time_out = 30  # 增加超时时间
    while not await bot.is_running() and time_out > 0:
        logger.info("等待WechatAPI启动中")
        await asyncio.sleep(2)
        time_out -= 2

    if time_out <= 0:
        logger.error("WechatAPI服务启动超时")
        # 更新状态
        update_bot_status("error", "WechatAPI服务启动超时")
        return None

    if not await bot.check_database():
        logger.error("Redis连接失败，请检查Redis是否在运行中，Redis的配置")
        # 更新状态
        update_bot_status("error", "Redis连接失败")
        return None

    logger.success("WechatAPI服务已启动")
    
    # 更新状态
    update_bot_status("waiting_login", "等待微信登录")
    
    # 检查并创建robot_stat.json文件
    robot_stat_path = script_dir / "resource" / "robot_stat.json"
    if not os.path.exists(robot_stat_path):
        default_config = {
            "wxid": "",
            "device_name": "",
            "device_id": ""
        }
        os.makedirs(os.path.dirname(robot_stat_path), exist_ok=True)
        with open(robot_stat_path, "w") as f:
            json.dump(default_config, f)
        robot_stat = default_config
    else:
        with open(robot_stat_path, "r") as f:
            robot_stat = json.load(f)

    wxid = robot_stat.get("wxid", None)
    device_name = robot_stat.get("device_name", None)
    device_id = robot_stat.get("device_id", None)

    if not await bot.is_logged_in(wxid):
        while not await bot.is_logged_in(wxid):
            # 需要登录
            try:
                if await bot.get_cached_info(wxid):
                    # 尝试唤醒登录
                    uuid = await bot.awaken_login(wxid)
                    logger.success("获取到登录uuid: {}", uuid)
                    # 更新状态，记录UUID但没有二维码
                    update_bot_status("waiting_login", f"等待微信登录 (UUID: {uuid})")
                else:
                    # 二维码登录
                    if not device_name:
                        device_name = bot.create_device_name()
                    if not device_id:
                        device_id = bot.create_device_id()
                    uuid, url = await bot.get_qr_code(device_id=device_id, device_name=device_name, print_qr=True)
                    logger.success("获取到登录uuid: {}", uuid)
                    logger.success("获取到登录二维码: {}", url)
                    # 更新状态，记录二维码URL
                    update_bot_status("waiting_login", "等待微信扫码登录", {
                        "qrcode_url": url,
                        "uuid": uuid,
                        "expires_in": 240, # 默认240秒过期
                        "timestamp": time.time()
                    })
                    
                    # 检查状态文件是否正确更新
                    try:
                        status_file = script_dir / "admin" / "bot_status.json"
                        if status_file.exists():
                            with open(status_file, "r", encoding="utf-8") as f:
                                current_status = json.load(f)
                                if current_status.get("qrcode_url") != url:
                                    logger.warning("状态文件中的二维码URL与实际不符，尝试重新更新状态")
                                    # 再次更新状态
                                    update_bot_status("waiting_login", "等待微信扫码登录", {
                                        "qrcode_url": url,
                                        "uuid": uuid,
                                        "expires_in": 240,
                                        "timestamp": time.time()
                                    })
                    except Exception as e:
                        logger.error(f"检查状态文件失败: {e}")

                # 显示倒计时
                logger.info("等待登录中，过期倒计时：240")

            except Exception as e:
                logger.error("发生错误: {}", e)
                # 出错时重新尝试二维码登录
                if not device_name:
                    device_name = bot.create_device_name()
                if not device_id:
                    device_id = bot.create_device_id()
                uuid, url = await bot.get_qr_code(device_id=device_id, device_name=device_name, print_qr=True)
                logger.success("获取到登录uuid: {}", uuid)
                logger.success("获取到登录二维码: {}", url)
                # 更新状态，记录二维码URL
                update_bot_status("waiting_login", "等待微信扫码登录", {
                    "qrcode_url": url,
                    "uuid": uuid,
                    "expires_in": 240, # 默认240秒过期
                    "timestamp": time.time()
                })

            while True:
                stat, data = await bot.check_login_uuid(uuid, device_id=device_id)
                if stat:
                    break
                # 计算剩余时间
                expires_in = data
                logger.info("等待登录中，过期倒计时：{}", expires_in)
                # 更新状态，包含倒计时
                update_bot_status("waiting_login", f"等待微信扫码登录 (剩余{expires_in}秒)", {
                    "qrcode_url": url if 'url' in locals() else None,
                    "uuid": uuid,
                    "expires_in": expires_in,
                    "timestamp": time.time()
                })
                await asyncio.sleep(5)

        # 保存登录信息
        robot_stat["wxid"] = bot.wxid
        robot_stat["device_name"] = device_name
        robot_stat["device_id"] = device_id
        with open("resource/robot_stat.json", "w") as f:
            json.dump(robot_stat, f)

        # 获取登录账号信息
        bot.wxid = data.get("acctSectResp").get("userName")
        bot.nickname = data.get("acctSectResp").get("nickName")
        bot.alias = data.get("acctSectResp").get("alias")
        bot.phone = data.get("acctSectResp").get("bindMobile")

        logger.info("登录账号信息: wxid: {}  昵称: {}  微信号: {}  手机号: {}", bot.wxid, bot.nickname, bot.alias,
                    bot.phone)

        # 登录微信
        try:
            # 等待登录，获取个人信息
            # await bot.login() - 这个方法不存在
            # 直接使用之前获取的个人信息即可，因为在 check_login_uuid 成功后已经设置了 wxid
            # 登录成功后更新状态
            update_bot_status("online", f"已登录：{bot.nickname}", {
                "nickname": bot.nickname, 
                "wxid": bot.wxid,
                "alias": bot.alias
            })
        except Exception as e:
            logger.error(f"登录失败: {e}")
            update_bot_status("error", f"登录失败: {str(e)}")
            return None

    else:  # 已登录
        bot.wxid = wxid
        profile = await bot.get_profile()

        bot.nickname = profile.get("NickName").get("string")
        bot.alias = profile.get("Alias")
        bot.phone = profile.get("BindMobile").get("string")

        logger.info("登录账号信息: wxid: {}  昵称: {}  微信号: {}  手机号: {}", bot.wxid, bot.nickname, bot.alias,
                    bot.phone)

    logger.info("登录设备信息: device_name: {}  device_id: {}", device_name, device_id)

    logger.success("登录成功")
    
    # 更新状态为在线
    update_bot_status("online", f"已登录：{bot.nickname}", {
        "nickname": bot.nickname, 
        "wxid": bot.wxid,
        "alias": bot.alias
    })

    # ========== 登录完毕 开始初始化 ========== #

    # 开启自动心跳
    try:
        success = await bot.start_auto_heartbeat()
        if success:
            logger.success("已开启自动心跳")
        else:
            logger.warning("开启自动心跳失败")
    except ValueError:
        logger.warning("自动心跳已在运行")
    except Exception as e:
        if "在运行" not in e:
            logger.warning("自动心跳已在运行")

    # 初始化机器人
    xybot = XYBot(bot)
    xybot.update_profile(bot.wxid, bot.nickname, bot.alias, bot.phone)
    
    # 设置机器人实例到管理后台
    set_bot_instance(xybot)
    
    # 初始化数据库
    XYBotDB()

    message_db = MessageDB()
    await message_db.initialize()

    keyval_db = KeyvalDB()
    await keyval_db.initialize()

    # 启动调度器
    scheduler.start()
    logger.success("定时任务已启动")

    # 加载插件目录下的所有插件
    loaded_plugins = await plugin_manager.load_plugins_from_directory(bot, load_disabled_plugin=False)
    logger.success(f"已加载插件: {loaded_plugins}")

    # ========== 开始接受消息 ========== #

    # 先接受堆积消息
    logger.info("处理堆积消息中")
    count = 0
    while True:
        data = await bot.sync_message()
        data = data.get("AddMsgs")
        if not data:
            if count > 2:
                break
            else:
                count += 1
                continue

        logger.debug("接受到 {} 条消息", len(data))
        await asyncio.sleep(1)
    logger.success("处理堆积消息完毕")

    # 更新状态为就绪
    update_bot_status("ready", "机器人已准备就绪")

    logger.success("开始处理消息")
    while True:
        now = time.time()

        try:
            data = await bot.sync_message()
        except Exception as e:
            logger.warning("获取新消息失败 {}", e)
            await asyncio.sleep(5)
            continue

        data = data.get("AddMsgs")
        if data:
            for message in data:
                asyncio.create_task(xybot.process_message(message))
        # 使用异步睡眠替代忙等待循环
        await asyncio.sleep(0.5)
        
    # 返回机器人实例（此处不会执行到，因为上面的无限循环）
    return xybot