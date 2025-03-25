# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
import sphinx_rtd_theme

sys.path.insert(0, os.path.abspath('..'))

html_theme = 'furo'

project = 'WechatAPI'
copyright = '2025, HenryXiaoYang'
author = 'HenryXiaoYang'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',  # 支持Google风格的文档字符串
    'sphinx.ext.viewcode'
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

language = 'zh_CN'

# Napoleon设置
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_type_aliases = None

html_title = "XYBotV2"
html_sidebars = {
    "**": [
        "sidebar/scroll-start.html",
        "sidebar/brand.html",
        "sidebar/search.html",
        "sidebar/navigation.html",
        "custom-toc.html",
        "sidebar/scroll-end.html"
    ]
}

# furo主题配置
html_theme_options = {
    "sidebar_hide_name": False,
    "light_css_variables": {
        "color-brand-primary": "#2962ff",
        "color-brand-content": "#2962ff",
    },
    "navigation_with_keys": True,
}

# 重要函数导航列表
important_functions = {
    "登录": [
        ("检查WechatAPI是否在运行", "index.html#WechatAPI.Client.login.LoginMixin.is_running"),
        ("获取登录二维码", "index.html#WechatAPI.Client.login.LoginMixin.get_qr_code"),
        ("二次登录(唤醒登录)", "index.html#WechatAPI.Client.login.LoginMixin.awaken_login"),
        ("检查登录的UUID状态", "index.html#WechatAPI.Client.login.LoginMixin.check_login_uuid"),
        ("获取登录缓存信息", "index.html#WechatAPI.Client.login.LoginMixin.get_cached_info"),
        ("登出当前账号", "index.html#WechatAPI.Client.login.LoginMixin.log_out"),
        ("发送心跳包", "index.html#WechatAPI.Client.login.LoginMixin.heartbeat"),
        ("开始自动心跳", "index.html#WechatAPI.Client.login.LoginMixin.start_auto_heartbeat"),
        ("停止自动心跳", "index.html#WechatAPI.Client.login.LoginMixin.stop_auto_heartbeat"),
        ("获取自动心跳状态", "index.html#WechatAPI.Client.login.LoginMixin.get_auto_heartbeat_status")
    ],
    "消息": [
        ("同步消息", "index.html#WechatAPI.Client.message.MessageMixin.sync_message"),
        ("发送文本消息", "index.html#WechatAPI.Client.message.MessageMixin.send_text_message"),
        ("发送图片消息", "index.html#WechatAPI.Client.message.MessageMixin.send_image_message"),
        ("发送语音消息", "index.html#WechatAPI.Client.message.MessageMixin.send_voice_message"),
        ("发送视频消息", "index.html#WechatAPI.Client.message.MessageMixin.send_video_message"),
        ("发送链接消息", "index.html#WechatAPI.Client.message.MessageMixin.send_link_message"),
        ("发送名片消息", "index.html#WechatAPI.Client.message.MessageMixin.send_card_message"),
        ("发送应用(xml)消息", "index.html#WechatAPI.Client.message.MessageMixin.send_app_message"),
        ("发送表情消息", "index.html#WechatAPI.Client.message.MessageMixin.send_emoji_message"),
        ("转发图片消息", "index.html#WechatAPI.Client.message.MessageMixin.send_cdn_img_msg"),
        ("转发视频消息", "index.html#WechatAPI.Client.message.MessageMixin.send_cdn_video_msg"),
        ("转发文件消息", "index.html#WechatAPI.Client.message.MessageMixin.send_cdn_file_msg"),
        ("撤回消息", "index.html#WechatAPI.Client.message.MessageMixin.revoke_message")
    ],
    "用户": [
        ("获取个人二维码", "index.html#WechatAPI.Client.user.UserMixin.get_my_qrcode"),
        ("获取用户信息", "index.html#WechatAPI.Client.user.UserMixin.get_profile"),
        ("检查是否登录", "index.html#WechatAPI.Client.user.UserMixin.is_logged_in")
    ],
    "群聊": [
        ("获取群聊信息", "index.html#WechatAPI.Client.chatroom.ChatroomMixin.get_chatroom_info"),
        ("获取群聊公告", "index.html#WechatAPI.Client.chatroom.ChatroomMixin.get_chatroom_announce"),
        ("获取群聊成员列表", "index.html#WechatAPI.Client.chatroom.ChatroomMixin.get_chatroom_member_list"),
        ("获取群聊二维码", "index.html#WechatAPI.Client.chatroom.ChatroomMixin.get_chatroom_qrcode"),
        ("添加群成员(群聊最多40人)", "index.html#WechatAPI.Client.chatroom.ChatroomMixin.add_chatroom_member"),
        ("邀请群聊成员(群聊大于40人)", "index.html#WechatAPI.Client.chatroom.ChatroomMixin.invite_chatroom_member")
    ],
    "好友": [
        ("获取联系人信息", "index.html#WechatAPI.Client.friend.FriendMixin.get_contact"),
        ("获取联系人详情", "index.html#WechatAPI.Client.friend.FriendMixin.get_contract_detail"),
        ("获取联系人列表", "index.html#WechatAPI.Client.friend.FriendMixin.get_contract_list"),
        ("获取用户昵称", "index.html#WechatAPI.Client.friend.FriendMixin.get_nickname"),
        ("接受好友请求", "index.html#WechatAPI.Client.friend.FriendMixin.accept_friend"),
    ],
    "红包": [
        ("获取红包详情", "index.html#WechatAPI.Client.hongbao.HongBaoMixin.get_hongbao_detail")
    ],
    "工具": [
        ("检查数据库状态", "index.html#WechatAPI.Client.tool.ToolMixin.check_database"),
        ("设置步数", "index.html#WechatAPI.Client.tool.ToolMixin.set_step"),
        ("下载高清图片", "index.html#WechatAPI.Client.tool.ToolMixin.download_image"),
        ("下载视频", "index.html#WechatAPI.Client.tool.ToolMixin.download_video"),
        ("下载语音文件", "index.html#WechatAPI.Client.tool.ToolMixin.download_voice"),
        ("下载附件", "index.html#WechatAPI.Client.tool.ToolMixin.download_attach"),
        ("base64转字节", "index.html#WechatAPI.Client.tool.ToolMixin.base64_to_byte"),
        ("base64转文件", "index.html#WechatAPI.Client.tool.ToolMixin.base64_to_file"),
        ("字节转base64", "index.html#WechatAPI.Client.tool.ToolMixin.byte_to_base64"),
        ("文件转base64", "index.html#WechatAPI.Client.tool.ToolMixin.file_to_base64"),
        ("silk的base64转wav字节", "index.html#WechatAPI.Client.tool.ToolMixin.silk_base64_to_wav_byte"),
        ("silk字节转wav字节", "index.html#WechatAPI.Client.tool.ToolMixin.silk_byte_to_byte_wav_byte"),
        ("WAV字节转AMR的base64", "index.html#WechatAPI.Client.tool.ToolMixin.wav_byte_to_amr_base64"),
        ("WAV字节转AMR字节", "index.html#WechatAPI.Client.tool.ToolMixin.wav_byte_to_amr_byte"),
        ("WAV字节转silk的base64", "index.html#WechatAPI.Client.tool.ToolMixin.wav_byte_to_silk_base64"),
        ("WAV字节转silk字节", "index.html#WechatAPI.Client.tool.ToolMixin.wav_byte_to_silk_byte"),
    ]
}

# 添加 HTML 上下文
html_context = {
    'important_functions': important_functions
}
