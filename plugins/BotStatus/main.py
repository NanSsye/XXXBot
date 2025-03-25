import re
import tomllib

from WechatAPI import WechatAPIClient
from utils.decorators import *
from utils.plugin_base import PluginBase


class BotStatus(PluginBase):
    description = "机器人状态"
    author = "HenryXiaoYang"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

        with open("plugins/BotStatus/config.toml", "rb") as f:
            plugin_config = tomllib.load(f)

        with open("main_config.toml", "rb") as f:
            main_config = tomllib.load(f)

        config = plugin_config["BotStatus"]
        main_config = main_config["XYBot"]

        self.enable = config["enable"]
        self.command = config["command"]
        self.version = main_config["version"]
        self.status_message = config["status-message"]

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = str(message["Content"]).strip()
        command = content.split(" ")

        if not len(command) or command[0] not in self.command:
            return

        out_message = (f"{self.status_message}\n"
                       f"当前版本: {self.version}\n"
                       "项目地址：https://github.com/HenryXiaoYang/XYBotV2\n")
        await bot.send_text_message(message.get("FromWxid"), out_message)

    @on_at_message
    async def handle_at(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = str(message["Content"]).strip()
        command = re.split(r'[\s\u2005]+', content)

        if len(command) < 2 or command[1] not in self.command:
            return

        out_message = (f"{self.status_message}\n"
                       f"当前版本: {self.version}\n"
                       "项目地址：https://github.com/HenryXiaoYang/XYBotV2\n")
        await bot.send_text_message(message.get("FromWxid"), out_message)
