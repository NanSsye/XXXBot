import tomllib

from WechatAPI import WechatAPIClient
from utils.decorators import *
from utils.plugin_base import PluginBase


class Menu(PluginBase):
    description = "菜单"
    author = "老夏的金库"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

        with open("plugins/Menu/config.toml", "rb") as f:
            plugin_config = tomllib.load(f)

        with open("main_config.toml", "rb") as f:
            main_config = tomllib.load(f)

        config = plugin_config["Menu"]
        main_config = main_config["XYBot"]

        self.enable = config["enable"]
        self.command = config["command"]
        self.menu = config["menu"]
        self.admin_menu = config["admin-menu"]

        self.version = main_config["version"]

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = str(message["Content"]).strip()
        command = content.split(" ")

        if command[0] in self.command:
            menu = (f"\n"
                    f"{self.menu}\n"
                    f"\n"
                    f"来自XYBotV2 {self.version}\n"
                    f"https://github.com/HenryXiaoYang/XYBotV2")
            await bot.send_at_message(message["FromWxid"], menu, [message["SenderWxid"]])
        elif command[0] == "管理员菜单":
            await bot.send_at_message(message["FromWxid"], self.admin_menu, [message["SenderWxid"]])
