import tomllib
import xml.etree.ElementTree as ET
from typing import Dict, Any

from loguru import logger

from WechatAPI import WechatAPIClient
from WechatAPI.Client.protect import protector
from database.messsagDB import MessageDB
from utils.event_manager import EventManager


class XYBot:
    def __init__(self, bot_client: WechatAPIClient):
        self.bot = bot_client
        self.wxid = None
        self.nickname = None
        self.alias = None
        self.phone = None

        with open("main_config.toml", "rb") as f:
            main_config = tomllib.load(f)

        self.ignore_protection = main_config.get("XYBot", {}).get("ignore-protection", False)

        self.ignore_mode = main_config.get("XYBot", {}).get("ignore-mode", "")
        self.whitelist = main_config.get("XYBot", {}).get("whitelist", [])
        self.blacklist = main_config.get("XYBot", {}).get("blacklist", [])

        self.msg_db = MessageDB()

    def update_profile(self, wxid: str, nickname: str, alias: str, phone: str):
        """更新机器人信息"""
        self.wxid = wxid
        self.nickname = nickname
        self.alias = alias
        self.phone = phone

    async def process_message(self, message: Dict[str, Any]):
        """处理接收到的消息"""

        msg_type = message.get("MsgType")

        # 预处理消息
        message["FromWxid"] = message.get("FromUserName", {}).get("string")
        message.pop("FromUserName", None)
        message["ToWxid"] = message.get("ToWxid", {}).get("string")

        # 处理一下自己发的消息
        if message.get("FromWxid") == self.wxid and message.get("ToWxid", "").endswith("@chatroom"):
            message["FromWxid"], message["ToWxid"] = message["ToWxid"], message["FromWxid"]

        # 根据消息类型触发不同的事件
        if msg_type == 1:  # 文本消息
            await self.process_text_message(message)
        elif msg_type == 3:  # 图片消息
            await self.process_image_message(message)
        elif msg_type == 34:  # 语音消息
            await self.process_voice_message(message)
        elif msg_type == 43:  # 视频消息
            await self.process_video_message(message)
        elif msg_type == 49:  # xml消息
            await self.process_xml_message(message)
        elif msg_type == 10002:  # 系统消息
            await self.process_system_message(message)
        elif msg_type == 37:  # 好友请求
            if self.ignore_protection or not protector.check(14400):
                await EventManager.emit("friend_request", self.bot, message)
            else:
                logger.warning("风控保护: 新设备登录后4小时内请挂机")
        elif msg_type == 51:
            pass
        else:
            logger.info("未知的消息类型: {}", message)

    async def process_text_message(self, message: Dict[str, Any]):
        """处理文本消息"""
        message["Content"] = message.get("Content", {}).get("string", "")

        if message["FromWxid"].endswith("@chatroom"):  # 群聊消息
            message["IsGroup"] = True
            split_content = message["Content"].split(":\n", 1)
            if len(split_content) > 1:
                message["Content"] = split_content[1]
                message["SenderWxid"] = split_content[0]
            else:
                message["Content"] = split_content[0]
                message["SenderWxid"] = self.wxid
        else:
            message["SenderWxid"] = message["FromWxid"]
            if message["FromWxid"] == self.wxid:
                message["FromWxid"] = message["ToWxid"]
            message["IsGroup"] = False

        try:
            root = ET.fromstring(message.get("MsgSource", ""))
            ats = root.find("atuserlist").text if root.find("atuserlist") is not None else ""
        except Exception as e:
            logger.error("解析文本消息失败: {}", e)
            ats = ""

        if ats:
            ats = ats.strip(",").split(",")
        else:
            ats = []
        message["Ats"] = ats if ats and ats[0] != "" else []

        await self.msg_db.save_message(
            msg_id=int(message.get("MsgId", 0)),
            sender_wxid=message["SenderWxid"],
            from_wxid=message["FromWxid"],
            msg_type=int(message.get("MsgType", 0)),
            content=message["Content"],
            is_group=message["IsGroup"]
        )

        if self.wxid in message.get("Ats", []):
            logger.info("收到被@消息: 消息ID:{} 来自:{} 发送人:{} @:{} 内容:{}", 
                        message.get("MsgId", ""), message["FromWxid"], 
                        message["SenderWxid"], message["Ats"], message["Content"])
            if self.ignore_check(message["FromWxid"], message["SenderWxid"]):
                if self.ignore_protection or not protector.check(14400):
                    await EventManager.emit("at_message", self.bot, message)
                else:
                    logger.warning("风控保护: 新设备登录后4小时内请挂机")
            return

        logger.info("收到文本消息: 消息ID:{} 来自:{} 发送人:{} @:{} 内容:{}", 
                    message.get("MsgId", ""), message["FromWxid"], 
                    message["SenderWxid"], message["Ats"], message["Content"])

        if self.ignore_check(message["FromWxid"], message["SenderWxid"]):
            if self.ignore_protection or not protector.check(14400):
                await EventManager.emit("text_message", self.bot, message)
            else:
                logger.warning("风控保护: 新设备登录后4小时内请挂机")

    async def process_image_message(self, message: Dict[str, Any]):
        """处理图片消息"""
        message["Content"] = message.get("Content", {}).get("string", "").replace("\n", "").replace("\t", "")

        if message["FromWxid"].endswith("@chatroom"):
            message["IsGroup"] = True
            split_content = message["Content"].split(":", 1)
            if len(split_content) > 1:
                message["Content"] = split_content[1]
                message["SenderWxid"] = split_content[0]
            else:
                message["Content"] = split_content[0]
                message["SenderWxid"] = self.wxid
        else:
            message["SenderWxid"] = message["FromWxid"]
            if message["FromWxid"] == self.wxid:
                message["FromWxid"] = message["ToWxid"]
            message["IsGroup"] = False

        logger.info("收到图片消息: 消息ID:{} 来自:{} 发送人:{} XML:{}", 
                    message.get("MsgId", ""), message["FromWxid"], 
                    message["SenderWxid"], message["Content"])

        await self.msg_db.save_message(
            msg_id=int(message.get("MsgId", 0)),
            sender_wxid=message["SenderWxid"],
            from_wxid=message["FromWxid"],
            msg_type=int(message.get("MsgType", 0)),
            content=message.get("MsgSource", ""),
            is_group=message["IsGroup"]
        )

        aeskey, cdnmidimgurl = None, None
        try:
            root = ET.fromstring(message["Content"])
            img_element = root.find('img')
            if img_element is not None:
                aeskey = img_element.get('aeskey')
                cdnmidimgurl = img_element.get('cdnmidimgurl')
        except Exception as e:
            logger.error("解析图片消息失败: {}, 内容: {}", e, message["Content"])
            return

        if aeskey and cdnmidimgurl:
            message["Content"] = await self.bot.download_image(aeskey, cdnmidimgurl)

        if self.ignore_check(message["FromWxid"], message["SenderWxid"]):
            if self.ignore_protection or not protector.check(14400):
                await EventManager.emit("image_message", self.bot, message)
            else:
                logger.warning("风控保护: 新设备登录后4小时内请挂机")

    async def process_voice_message(self, message: Dict[str, Any]):
        """处理语音消息"""
        message["Content"] = message.get("Content", {}).get("string", "").replace("\n", "").replace("\t", "")

        if message["FromWxid"].endswith("@chatroom"):
            message["IsGroup"] = True
            split_content = message["Content"].split(":", 1)
            if len(split_content) > 1:
                message["Content"] = split_content[1]
                message["SenderWxid"] = split_content[0]
            else:
                message["Content"] = split_content[0]
                message["SenderWxid"] = self.wxid
        else:
            message["SenderWxid"] = message["FromWxid"]
            if message["FromWxid"] == self.wxid:
                message["FromWxid"] = message["ToWxid"]
            message["IsGroup"] = False

        logger.info("收到语音消息: 消息ID:{} 来自:{} 发送人:{} XML:{}", 
                    message.get("MsgId", ""), message["FromWxid"], 
                    message["SenderWxid"], message["Content"])

        await self.msg_db.save_message(
            msg_id=int(message.get("MsgId", 0)),
            sender_wxid=message["SenderWxid"],
            from_wxid=message["FromWxid"],
            msg_type=int(message.get("MsgType", 0)),
            content=message["Content"],
            is_group=message["IsGroup"]
        )

        if message["IsGroup"] or not message.get("ImgBuf", {}).get("buffer", ""):
            voiceurl, length = None, None
            try:
                root = ET.fromstring(message["Content"])
                voicemsg_element = root.find('voicemsg')
                if voicemsg_element is not None:
                    voiceurl = voicemsg_element.get('voiceurl')
                    length = int(voicemsg_element.get('length'))
            except Exception as e:
                logger.error("解析语音消息失败: {}, 内容: {}", e, message["Content"])
                return

            if voiceurl and length:
                silk_base64 = await self.bot.download_voice(message["MsgId"], voiceurl, length)
                message["Content"] = await self.bot.silk_base64_to_wav_byte(silk_base64)
        else:
            silk_base64 = message.get("ImgBuf", {}).get("buffer", "")
            message["Content"] = await self.bot.silk_base64_to_wav_byte(silk_base64)

        if self.ignore_check(message["FromWxid"], message["SenderWxid"]):
            if self.ignore_protection or not protector.check(14400):
                await EventManager.emit("voice_message", self.bot, message)
            else:
                logger.warning("风控保护: 新设备登录后4小时内请挂机")

    async def process_xml_message(self, message: Dict[str, Any]):
        """处理xml消息"""
        message["Content"] = message.get("Content", {}).get("string", "").replace("\n", "").replace("\t", "")

        if message["FromWxid"].endswith("@chatroom"):
            message["IsGroup"] = True
            split_content = message["Content"].split(":", 1)
            if len(split_content) > 1:
                message["Content"] = split_content[1]
                message["SenderWxid"] = split_content[0]
            else:
                message["Content"] = split_content[0]
                message["SenderWxid"] = self.wxid
        else:
            message["SenderWxid"] = message["FromWxid"]
            if message["FromWxid"] == self.wxid:
                message["FromWxid"] = message["ToWxid"]
            message["IsGroup"] = False

        # 保存消息到数据库（即使解析失败也保存）
        await self.msg_db.save_message(
            msg_id=int(message.get("MsgId", 0)),
            sender_wxid=message["SenderWxid"],
            from_wxid=message["FromWxid"],
            msg_type=int(message.get("MsgType", 0)),
            content=message["Content"],
            is_group=message["IsGroup"]
        )

        try:
            root = ET.fromstring(message["Content"])
            appmsg = root.find("appmsg")
            if appmsg is None:
                logger.warning("XML 中未找到 appmsg 节点，内容: {}", message["Content"])
                return
            type_element = appmsg.find("type")
            if type_element is None:
                logger.warning("XML 中未找到 type 节点，内容: {}", message["Content"])
                return
            type_value = int(type_element.text)
            logger.debug("解析到的 XML 类型: {}, 完整内容: {}", type_value, message["Content"])
        except ET.ParseError as e:
            logger.error("解析 XML 失败: {}, 完整内容: {}", e, message["Content"])
            return
        except Exception as e:
            logger.error("处理 XML 时发生异常: {}, 完整内容: {}", e, message["Content"])
            return

        if type_value == 57:  # 引用消息
            await self.process_quote_message(message)
        elif type_value == 6:  # 文件消息
            await self.process_file_message(message)
        elif type_value == 5:  # 公众号文章或链接分享消息
            logger.info("收到链接分享消息: 消息ID:{} 来自:{} 发送人:{} XML:{}", 
                        message.get("MsgId", ""), message["FromWxid"], 
                        message["SenderWxid"], message["Content"])
            logger.debug("完整 XML 内容: {}", message["Content"])
            if self.ignore_check(message["FromWxid"], message["SenderWxid"]):
                if self.ignore_protection or not protector.check(14400):
                    logger.debug("触发 article_message 事件: 消息ID: {}", message.get("MsgId", ""))
                    await EventManager.emit("article_message", self.bot, message)
                else:
                    logger.warning("风控保护: 新设备登录后4小时内请挂机")
        elif type_value == 74:  # 文件消息，但还在上传，不用管
            logger.debug("收到上传中文件消息: 消息ID:{} 来自:{}", message.get("MsgId", ""), message["FromWxid"])
        else:
            logger.info("未知的 XML 消息类型: {}, 完整内容: {}", type_value, message["Content"])

    async def process_quote_message(self, message: Dict[str, Any]):
        """处理引用消息"""
        quote_message = {}
        try:
            root = ET.fromstring(message["Content"])
            appmsg = root.find("appmsg")
            text = appmsg.find("title").text
            refermsg = appmsg.find("refermsg")

            quote_message["MsgType"] = int(refermsg.find("type").text)

            if quote_message["MsgType"] == 1:  # 文本消息
                quote_message["NewMsgId"] = refermsg.find("svrid").text
                quote_message["ToWxid"] = refermsg.find("fromusr").text
                quote_message["FromWxid"] = refermsg.find("chatusr").text
                quote_message["Nickname"] = refermsg.find("displayname").text
                quote_message["MsgSource"] = refermsg.find("msgsource").text
                quote_message["Content"] = refermsg.find("content").text
                quote_message["Createtime"] = refermsg.find("createtime").text

            elif quote_message["MsgType"] == 49:  # 引用消息
                quote_message["NewMsgId"] = refermsg.find("svrid").text
                quote_message["ToWxid"] = refermsg.find("fromusr").text
                quote_message["FromWxid"] = refermsg.find("chatusr").text
                quote_message["Nickname"] = refermsg.find("displayname").text
                quote_message["MsgSource"] = refermsg.find("msgsource").text
                quote_message["Createtime"] = refermsg.find("createtime").text

                quote_message["Content"] = refermsg.find("content").text

                quote_root = ET.fromstring(quote_message["Content"])
                quote_appmsg = quote_root.find("appmsg")

                quote_message["Content"] = quote_appmsg.find("title").text if isinstance(quote_appmsg.find("title"), ET.Element) else ""
                quote_message["destination"] = quote_appmsg.find("des").text if isinstance(quote_appmsg.find("des"), ET.Element) else ""
                quote_message["action"] = quote_appmsg.find("action").text if isinstance(quote_appmsg.find("action"), ET.Element) else ""
                quote_message["XmlType"] = int(quote_appmsg.find("type").text) if isinstance(quote_appmsg.find("type"), ET.Element) else 0
                quote_message["showtype"] = int(quote_appmsg.find("showtype").text) if isinstance(quote_appmsg.find("showtype"), ET.Element) else 0
                quote_message["soundtype"] = int(quote_appmsg.find("soundtype").text) if isinstance(quote_appmsg.find("soundtype"), ET.Element) else 0
                quote_message["url"] = quote_appmsg.find("url").text if isinstance(quote_appmsg.find("url"), ET.Element) else ""
                quote_message["lowurl"] = quote_appmsg.find("lowurl").text if isinstance(quote_appmsg.find("lowurl"), ET.Element) else ""
                quote_message["dataurl"] = quote_appmsg.find("dataurl").text if isinstance(quote_appmsg.find("dataurl"), ET.Element) else ""
                quote_message["lowdataurl"] = quote_appmsg.find("lowdataurl").text if isinstance(quote_appmsg.find("lowdataurl"), ET.Element) else ""
                quote_message["songlyric"] = quote_appmsg.find("songlyric").text if isinstance(quote_appmsg.find("songlyric"), ET.Element) else ""
                quote_message["appattach"] = {}
                quote_message["appattach"]["totallen"] = int(quote_appmsg.find("appattach").find("totallen").text) if isinstance(quote_appmsg.find("appattach").find("totallen"), ET.Element) else 0
                quote_message["appattach"]["attachid"] = quote_appmsg.find("appattach").find("attachid").text if isinstance(quote_appmsg.find("appattach").find("attachid"), ET.Element) else ""
                quote_message["appattach"]["emoticonmd5"] = quote_appmsg.find("appattach").find("emoticonmd5").text if isinstance(quote_appmsg.find("appattach").find("emoticonmd5"), ET.Element) else ""
                quote_message["appattach"]["fileext"] = quote_appmsg.find("appattach").find("fileext").text if isinstance(quote_appmsg.find("appattach").find("fileext"), ET.Element) else ""
                quote_message["appattach"]["cdnthumbaeskey"] = quote_appmsg.find("appattach").find("cdnthumbaeskey").text if isinstance(quote_appmsg.find("appattach").find("cdnthumbaeskey"), ET.Element) else ""
                quote_message["appattach"]["aeskey"] = quote_appmsg.find("appattach").find("aeskey").text if isinstance(quote_appmsg.find("appattach").find("aeskey"), ET.Element) else ""
                quote_message["extinfo"] = quote_appmsg.find("extinfo").text if isinstance(quote_appmsg.find("extinfo"), ET.Element) else ""
                quote_message["sourceusername"] = quote_appmsg.find("sourceusername").text if isinstance(quote_appmsg.find("sourceusername"), ET.Element) else ""
                quote_message["sourcedisplayname"] = quote_appmsg.find("sourcedisplayname").text if isinstance(quote_appmsg.find("sourcedisplayname"), ET.Element) else ""
                quote_message["thumburl"] = quote_appmsg.find("thumburl").text if isinstance(quote_appmsg.find("thumburl"), ET.Element) else ""
                quote_message["md5"] = quote_appmsg.find("md5").text if isinstance(quote_appmsg.find("md5"), ET.Element) else ""
                quote_message["statextstr"] = quote_appmsg.find("statextstr").text if isinstance(quote_appmsg.find("statextstr"), ET.Element) else ""
                quote_message["directshare"] = int(quote_appmsg.find("directshare").text) if isinstance(quote_appmsg.find("directshare"), ET.Element) else 0

        except Exception as e:
            logger.error("解析引用消息失败: {}, 完整内容: {}", e, message["Content"])
            return

        message["Content"] = text
        message["Quote"] = quote_message

        logger.info("收到引用消息: 消息ID:{} 来自:{} 发送人:{} 内容:{} 引用:{}", 
                    message.get("MsgId", ""), message["FromWxid"], 
                    message["SenderWxid"], message["Content"], message["Quote"])

        if self.ignore_check(message["FromWxid"], message["SenderWxid"]):
            if self.ignore_protection or not protector.check(14400):
                await EventManager.emit("quote_message", self.bot, message)
            else:
                logger.warning("风控保护: 新设备登录后4小时内请挂机")

    async def process_video_message(self, message):
        message["Content"] = message.get("Content", {}).get("string", "")

        if message["FromWxid"].endswith("@chatroom"):
            message["IsGroup"] = True
            split_content = message["Content"].split(":", 1)
            if len(split_content) > 1:
                message["Content"] = split_content[1]
                message["SenderWxid"] = split_content[0]
            else:
                message["Content"] = split_content[0]
                message["SenderWxid"] = self.wxid
        else:
            message["SenderWxid"] = message["FromWxid"]
            if message["FromWxid"] == self.wxid:
                message["FromWxid"] = message["ToWxid"]
            message["IsGroup"] = False

        logger.info("收到视频消息: 消息ID:{} 来自:{} 发送人:{} XML:{}", 
                    message.get("MsgId", ""), message["FromWxid"], 
                    message["SenderWxid"], message["Content"])

        await self.msg_db.save_message(
            msg_id=int(message.get("MsgId", 0)),
            sender_wxid=message["SenderWxid"],
            from_wxid=message["FromWxid"],
            msg_type=int(message.get("MsgType", 0)),
            content=message["Content"],
            is_group=message["IsGroup"]
        )

        message["Video"] = await self.bot.download_video(message.get("MsgId", 0))

        if self.ignore_check(message["FromWxid"], message["SenderWxid"]):
            if self.ignore_protection or not protector.check(14400):
                await EventManager.emit("video_message", self.bot, message)
            else:
                logger.warning("风控保护: 新设备登录后4小时内请挂机")

    async def process_file_message(self, message: Dict[str, Any]):
        """处理文件消息"""
        try:
            root = ET.fromstring(message["Content"])
            filename = root.find("appmsg").find("title").text
            attach_id = root.find("appmsg").find("appattach").find("attachid").text
            file_extend = root.find("appmsg").find("appattach").find("fileext").text
        except Exception as e:
            logger.error("解析文件消息失败: {}, 内容: {}", e, message["Content"])
            return

        message["Filename"] = filename
        message["FileExtend"] = file_extend

        logger.info("收到文件消息: 消息ID:{} 来自:{} 发送人:{} XML:{}", 
                    message.get("MsgId", ""), message["FromWxid"], 
                    message["SenderWxid"], message["Content"])

        await self.msg_db.save_message(
            msg_id=int(message.get("MsgId", 0)),
            sender_wxid=message["SenderWxid"],
            from_wxid=message["FromWxid"],
            msg_type=int(message.get("MsgType", 0)),
            content=message["Content"],
            is_group=message["IsGroup"]
        )

        message["File"] = await self.bot.download_attach(attach_id)

        if self.ignore_check(message["FromWxid"], message["SenderWxid"]):
            if self.ignore_protection or not protector.check(14400):
                await EventManager.emit("file_message", self.bot, message)
            else:
                logger.warning("风控保护: 新设备登录后4小时内请挂机")

    async def process_system_message(self, message: Dict[str, Any]):
        """处理系统消息"""
        message["Content"] = message.get("Content", {}).get("string", "")

        if message["FromWxid"].endswith("@chatroom"):
            message["IsGroup"] = True
            split_content = message["Content"].split(":", 1)
            if len(split_content) > 1:
                message["Content"] = split_content[1]
                message["SenderWxid"] = split_content[0]
            else:
                message["Content"] = split_content[0]
                message["SenderWxid"] = self.wxid
        else:
            message["SenderWxid"] = message["FromWxid"]
            if message["FromWxid"] == self.wxid:
                message["FromWxid"] = message["ToWxid"]
            message["IsGroup"] = False

        try:
            root = ET.fromstring(message["Content"])
            msg_type = root.attrib["type"]
        except Exception as e:
            logger.error("解析系统消息失败: {}, 内容: {}", e, message["Content"])
            return

        if msg_type == "pat":
            await self.process_pat_message(message)
        elif msg_type == "ClientCheckGetExtInfo":
            pass
        else:
            logger.info("收到系统消息: {}, 完整内容: {}", message, message["Content"])
            if self.ignore_check(message["FromWxid"], message["SenderWxid"]):
                if self.ignore_protection or not protector.check(14400):
                    await EventManager.emit("system_message", self.bot, message)
                else:
                    logger.warning("风控保护: 新设备登录后4小时内请挂机")

    async def process_pat_message(self, message: Dict[str, Any]):
        """处理拍一拍请求消息"""
        try:
            root = ET.fromstring(message["Content"])
            pat = root.find("pat")
            patter = pat.find("fromusername").text
            patted = pat.find("pattedusername").text
            pat_suffix = pat.find("patsuffix").text
        except Exception as e:
            logger.error("解析拍一拍消息失败: {}, 内容: {}", e, message["Content"])
            return

        message["Patter"] = patter
        message["Patted"] = patted
        message["PatSuffix"] = pat_suffix

        logger.info("收到拍一拍消息: 消息ID:{} 来自:{} 发送人:{} 拍者:{} 被拍:{} 后缀:{}", 
                    message.get("MsgId", ""), message["FromWxid"], 
                    message["SenderWxid"], message["Patter"], 
                    message["Patted"], message["PatSuffix"])

        await self.msg_db.save_message(
            msg_id=int(message.get("MsgId", 0)),
            sender_wxid=message["SenderWxid"],
            from_wxid=message["FromWxid"],
            msg_type=int(message.get("MsgType", 0)),
            content=f"{message['Patter']} 拍了拍 {message['Patted']} {message['PatSuffix']}",
            is_group=message["IsGroup"]
        )

        if self.ignore_check(message["FromWxid"], message["SenderWxid"]):
            if self.ignore_protection or not protector.check(14400):
                await EventManager.emit("pat_message", self.bot, message)
            else:
                logger.warning("风控保护: 新设备登录后4小时内请挂机")

    def ignore_check(self, FromWxid: str, SenderWxid: str):
        if self.ignore_mode == "Whitelist":
            return (FromWxid in self.whitelist) or (SenderWxid in self.whitelist)
        elif self.ignore_mode == "blacklist":
            return (FromWxid not in self.blacklist) and (SenderWxid not in self.blacklist)
        else:
            return True