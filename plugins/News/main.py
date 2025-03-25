import asyncio
import tomllib
from random import choice

import aiohttp

from WechatAPI import WechatAPIClient
from utils.decorators import *
from utils.plugin_base import PluginBase


class News(PluginBase):
    description = "新闻插件"
    author = "HenryXiaoYang"
    version = "1.1.0"

    # Change Log
    # 1.1.0 2025/2/22 默认关闭定时新闻

    def __init__(self):
        super().__init__()

        with open("plugins/News/config.toml", "rb") as f:
            plugin_config = tomllib.load(f)

        config = plugin_config["News"]

        self.enable = config["enable"]
        self.enable_schedule_news = config["enable-schedule-news"]
        self.command = config["command"]

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = str(message["Content"]).strip()
        command = content.split(" ")

        if command[0] not in self.command:
            return

        if "随机" in command[0]:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get("https://cn.apihz.cn/api/xinwen/baidu.php?id=88888888&key=88888888") as resp:
                    data = await resp.json()

            if data["code"] != 200:
                await bot.send_text_message(message["FromWxid"], "-----XYBot-----\n新闻获取失败！")
                return

            result = data.get("data", [])

            if len(result) == 0:
                await bot.send_text_message(message["FromWxid"], "-----XYBot-----\n新闻获取失败！")
                return

            new = choice(result["data"])
            await bot.send_link_message(message["FromWxid"],
                                        title=new["word"],
                                        url=new["rawUrl"],
                                        description=new["desc"],
                                        thumb_url=new["img"])

        else:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://zj.v.api.aa1.cn/api/60s-v2/?cc=XYBot") as resp:
                    image_byte = await resp.read()
            await bot.send_image_message(message["FromWxid"], image_byte)

    @schedule('cron', hour=12)
    async def noon_news(self, bot: WechatAPIClient):
        if not self.enable_schedule_news:
            return
        id_list = []
        wx_seq, chatroom_seq = 0, 0
        while True:
            contact_list = await bot.get_contract_list(wx_seq, chatroom_seq)
            id_list.extend(contact_list["ContactUsernameList"])
            wx_seq = contact_list["CurrentWxcontactSeq"]
            chatroom_seq = contact_list["CurrentChatRoomContactSeq"]
            if contact_list["CountinueFlag"] != 1:
                break

        chatrooms = []
        for id in id_list:
            if id.endswith("@chatroom"):
                chatrooms.append(id)

        async with aiohttp.ClientSession() as session:
            async with session.get("http://zj.v.api.aa1.cn/api/60s-v2/?cc=XYBot") as resp:
                iamge_byte = await resp.read()

        for id in chatrooms:
            await bot.send_image_message(id, iamge_byte)
            await asyncio.sleep(2)

    @schedule('cron', hour=18)
    async def night_news(self, bot: WechatAPIClient):
        if not self.enable_schedule_news:
            return
        id_list = []
        wx_seq, chatroom_seq = 0, 0
        while True:
            contact_list = await bot.get_contract_list(wx_seq, chatroom_seq)
            id_list.extend(contact_list["ContactUsernameList"])
            wx_seq = contact_list["CurrentWxcontactSeq"]
            chatroom_seq = contact_list["CurrentChatRoomContactSeq"]
            if contact_list["CountinueFlag"] != 1:
                break

        chatrooms = []
        for id in id_list:
            if id.endswith("@chatroom"):
                chatrooms.append(id)

        async with aiohttp.ClientSession() as session:
            async with session.get("http://v.api.aa1.cn/api/60s-v3/?cc=XYBot") as resp:
                iamge_byte = await resp.read()

        for id in chatrooms:
            await bot.send_image_message(id, iamge_byte)
            await asyncio.sleep(2)
