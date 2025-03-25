import tomllib

from WechatAPI import WechatAPIClient
from database.XYBotDB import XYBotDB
from utils.decorators import *
from utils.plugin_base import PluginBase


class QueryPoint(PluginBase):
    description = "查询积分"
    author = "HenryXiaoYang"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

        with open("plugins/QueryPoint/config.toml", "rb") as f:
            plugin_config = tomllib.load(f)

        config = plugin_config["QueryPoint"]

        self.enable = config["enable"]
        self.command = config["command"]

        self.db = XYBotDB()

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = str(message["Content"]).strip()
        command = content.split(" ")

        if not len(command) or command[0] not in self.command:
            return

        query_wxid = message["SenderWxid"]

        points = self.db.get_points(query_wxid)

        output = ("\n"
                  f"-----XYBot-----\n"
                  f"你有 {points} 点积分！😄")
        await bot.send_at_message(message["FromWxid"], output, [query_wxid])
