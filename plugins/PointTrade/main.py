import tomllib
from datetime import datetime

from WechatAPI import WechatAPIClient
from database.XYBotDB import XYBotDB
from utils.decorators import *
from utils.plugin_base import PluginBase


class PointTrade(PluginBase):
    description = "积分交易"
    author = "HenryXiaoYang"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

        with open("plugins/PointTrade/config.toml", "rb") as f:
            plugin_config = tomllib.load(f)

        config = plugin_config["PointTrade"]

        self.enable = config["enable"]
        self.command = config["command"]
        self.command_format = config["command-format"]

        self.db = XYBotDB()

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = str(message["Content"]).strip()
        command = content.split(" ")

        if command[0] not in self.command:
            return

        if len(command) < 3:
            await bot.send_at_message(message["FromWxid"], self.command_format, [message["SenderWxid"]])
            return
        elif not command[1].isdigit():
            await bot.send_at_message(message["FromWxid"], "\n-----XYBot-----\n🈚️转账积分无效(必须为正整数!)",
                                      [message["SenderWxid"]])
            return
        elif len(message["Ats"]) != 1:
            await bot.send_at_message(message["FromWxid"], "-----XYBot-----\n转账失败❌\n🈚️转账人无效！",
                                      [message["SenderWxid"]])
            return

        points = int(command[1])

        target_wxid = message["Ats"][0]
        trader_wxid = message["SenderWxid"]

        # check points
        trader_points = self.db.get_points(trader_wxid)

        if trader_points < points:
            await bot.send_at_message(message["FromWxid"], "\n-----XYBot-----\n转账失败❌\n积分不足！😭",
                                      [message["SenderWxid"]])
            return

        self.db.safe_trade_points(trader_wxid, target_wxid, points)

        trader_nick, target_nick = await bot.get_nickname([trader_wxid, target_wxid])

        trader_points = self.db.get_points(trader_wxid)
        target_points = self.db.get_points(target_wxid)

        output = (
            f"\n-----XYBot-----\n"
            f"✅积分转账成功！✨\n"
            f"🤝{trader_nick} 现在有 {trader_points} 点积分➖\n"
            f"🤝{target_nick} 现在有 {target_points} 点积分➕\n"
            f"⌚️时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await bot.send_at_message(message["FromWxid"], output, [trader_wxid, target_wxid])
