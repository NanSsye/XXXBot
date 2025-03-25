import tomllib

from WechatAPI import WechatAPIClient
from database.XYBotDB import XYBotDB
from utils.decorators import *
from utils.plugin_base import PluginBase


class AdminSignInReset(PluginBase):
    description = "重置签到状态"
    author = "HenryXiaoYang"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

        with open("plugins/AdminSigninReset/config.toml", "rb") as f:
            plugin_config = tomllib.load(f)

        with open("main_config.toml", "rb") as f:
            main_config = tomllib.load(f)

        config = plugin_config["AdminSignInReset"]
        main_config = main_config["XYBot"]

        self.enable = config["enable"]
        self.command = config["command"]

        self.admins = main_config["admins"]

        self.db = XYBotDB()

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = str(message["Content"]).strip()
        command = content.split(" ")

        if not len(command) or command[0] not in self.command:
            return

        sender_wxid = message["SenderWxid"]

        if sender_wxid not in self.admins:
            await bot.send_text_message(message["FromWxid"], "-----XYBot-----\n❌你配用这个指令吗？😡")
            return

        self.db.reset_all_signin_stat()
        await bot.send_text_message(message["FromWxid"], "-----XYBot-----\n成功重置签到状态！")
