import tomllib

from WechatAPI import WechatAPIClient
from database.XYBotDB import XYBotDB
from utils.decorators import *
from utils.plugin_base import PluginBase


class AdminPoint(PluginBase):
    description = "管理积分"
    author = "HenryXiaoYang"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

        with open("plugins/AdminPoint/config.toml", "rb") as f:
            plugin_config = tomllib.load(f)

        with open("main_config.toml", "rb") as f:
            main_config = tomllib.load(f)

        config = plugin_config["AdminPoint"]
        main_config = main_config["XYBot"]

        self.enable = config["enable"]
        self.command_format = config["command-format"]

        self.admins = main_config["admins"]

        self.db = XYBotDB()

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = str(message["Content"]).strip()
        command = content.split(" ")

        if not len(command) or command[0] not in ["加积分", "减积分", "设置积分"]:
            return

        sender_wxid = message["SenderWxid"]

        if sender_wxid not in self.admins:
            await bot.send_text_message(message["FromWxid"], "-----XYBot-----\n❌你配用这个指令吗？😡")
            return
        elif len(command) < 3 or not command[1].isdigit():
            await bot.send_text_message(message["FromWxid"], f"-----XYBot-----\n{self.command_format}")
            return

        if command[0] == "加积分":
            if command[2].startswith("@") and len(message["Ats"]) == 1:  # 判断是@还是wxid
                change_wxid = message["Ats"][0]
            elif "@" not in " ".join(command[2:]):
                change_wxid = command[2]
            else:
                await bot.send_text_message(message["FromWxid"], "-----XYBot-----\n❌请不要手动@！")
                return

            change_point = int(command[1])
            self.db.add_points(change_wxid, change_point)

            nickname = await bot.get_nickname(change_wxid)
            new_point = self.db.get_points(change_wxid)

            output = (
                f"-----XYBot-----\n"
                f"成功功给 {change_wxid} {nickname if nickname else ''} 加了 {change_point} 点积分\n"
                f"他现在有 {new_point} 点积分"
            )

            await bot.send_text_message(message["FromWxid"], output)

        elif command[0] == "减积分":
            if command[2].startswith("@") and len(message["Ats"]) == 1:  # 判断是@还是wxid
                change_wxid = message["Ats"][0]
            elif "@" not in " ".join(command[2:]):
                change_wxid = command[2]
            else:
                await bot.send_text_message(message["FromWxid"], "-----XYBot-----\n❌请不要手动@！")
                return

            change_point = int(command[1])
            self.db.add_points(change_wxid, -change_point)

            nickname = await bot.get_nickname(change_wxid)
            new_point = self.db.get_points(change_wxid)

            output = (
                f"-----XYBot-----\n"
                f"成功功给 {nickname if nickname else ''} {change_wxid} 减了 {change_point} 点积分\n"
                f"他现在有 {new_point} 点积分"
            )

            await bot.send_text_message(message["FromWxid"], output)

        elif command[0] == "设置积分":
            if command[2].startswith("@") and len(message["Ats"]) == 1:  # 判断是@还是wxid
                change_wxid = message["Ats"][0]
            elif "@" not in " ".join(command[2:]):
                change_wxid = command[2]
            else:
                await bot.send_text_message(message["FromWxid"], "-----XYBot-----\n❌请不要手动@！")
                return

            change_point = int(command[1])
            self.db.set_points(change_wxid, change_point)

            nickname = await bot.get_nickname(change_wxid)

            output = (
                f"-----XYBot-----\n"
                f"成功功将 {nickname if nickname else ''} {change_wxid} 的积分设置为 {change_point}"
            )

            await bot.send_text_message(message["FromWxid"], output)
