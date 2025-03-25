import json
import random
import time
import tomllib

import aiohttp

from WechatAPI import WechatAPIClient
from utils.decorators import *
from utils.plugin_base import PluginBase


class TencentLke(PluginBase):
    description = "腾讯大模型知识引擎LKE"
    author = "ChenChongWu"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

        with open("main_config.toml", "rb") as f:
            config = tomllib.load(f)

        self.admins = config["XYBot"]["admins"]

        with open("plugins/TencentLke/config.toml", "rb") as f:
            config = tomllib.load(f)

        plugin_config = config["TencentLke"]
        self.enable = plugin_config["enable"]
        self.bot_app_key = plugin_config["bot_app_key"]
        self.other_plugin_cmd = plugin_config["other-plugin-cmd"]

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return
        command = str(message["Content"]).strip().split(" ")

        if command and command[0] in self.other_plugin_cmd:  # 指令来自其他插件
            return

        if message["SenderWxid"] in self.admins:  # 自己发送不进行AI回答
            return

        content = str(message["Content"]).strip()
        if (content == ""):
            return

        await self.TencentLke(bot, message, message["Content"])

    async def TencentLke(self, bot: WechatAPIClient, message: dict, query: str, files=None):
        headers = {"Content-Type": "application/json"}
        payload = json.dumps({
            'content': query,
            'request_id': str(int(time.time())) + str(random.randint(1, 999)),
            'bot_app_key': self.bot_app_key,
            'visitor_biz_id': message["FromWxid"],
            'session_id': message["FromWxid"]
        })
        url = f"https://wss.lke.cloud.tencent.com/v1/qbot/chat/sse"
        async with aiohttp.ClientSession(proxy="") as session:
            async with session.post(url=url, headers=headers, data=payload, timeout=10) as resp:
                last_line = None
                async for line in resp.content:  # 流式传输
                    line = line.decode("utf-8").strip()
                    if (line != ""):
                        last_line = line

                last_line = last_line.strip().replace("data:", "")
                resp_json = json.loads(last_line)

                if (resp_json['type'] == "reply"):
                    try:
                        AIResult = resp_json['payload']["content"]
                        if (AIResult != ""):
                            await bot.send_text_message(message.get("FromWxid"), AIResult)

                    except json.JSONDecodeError as e:
                        return

                return
