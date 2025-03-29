# XXXBot 机器人项目

## 项目概述

XXXBot 是一个基于微信的智能机器人系统，通过整合多种 API 和功能，提供了丰富的交互体验。本系统包含管理后台界面，支持插件扩展，具备联系人管理、文件管理、系统状态监控等功能，同时与人工智能服务集成，提供智能对话能力。
![5a30bc98a824825d0d08c287ba5afe4](https://github.com/user-attachments/assets/1cca88ca-fbab-4fad-a07d-410a477c3cb6)

## 主要特性

### 1. 管理后台

- **控制面板**：系统概览、机器人状态监控
- **插件管理**：安装、配置、启用/禁用各类功能插件
- **文件管理**：上传、查看和管理机器人使用的文件
- **联系人管理**：微信好友和群组联系人管理
- **系统状态**：查看系统资源占用和运行状态

### 2. 聊天功能

- **私聊互动**：与单个用户的一对一对话
- **群聊响应**：在群组中通过@或特定命令触发
- **聊天室模式**：支持多人持续对话，带有用户状态管理
- **积分系统**：对话消耗积分，支持不同模型不同积分定价

### 3. 智能对话

- **多模型支持**：可配置多种 AI 模型，支持通过关键词切换
- **图文结合**：支持图片理解和多媒体输出
- **语音交互**：支持语音输入识别和语音回复

### 4. 插件系统

- **插件市场**：支持从插件市场下载和安装插件
- **自定义插件**：可开发和加载自定义功能插件
- **Dify 插件**：集成 Dify API，提供高级 AI 对话能力

## 安装指南

### 系统要求

- Python 3.11+
- 微信客户端（需配合特定接口使用）
- FFmpeg（用于语音处理）

### 安装步骤

1. **克隆代码库**

   ```bash
   git clone https://github.com/NanSsye/XXXBot.git
   cd XXXBot
   ```

2. **安装依赖**

   ```bash
   pip install -r requirements.txt
   ```

3. **安装 FFmpeg**

   - Windows: 下载安装包并添加到系统 PATH
   - Linux: `sudo apt-get install ffmpeg`
   - macOS: `brew install ffmpeg`

4. **配置**

   - 复制`main_config.toml.example`为`main_config.toml`并填写配置
   - 设置管理员 ID 和其他基本参数

5. **启动服务**

   ```bash
   python app.py
   ```

6. **访问后台**
   - 打开浏览器访问 `http://localhost:9090` 进入管理界面
   - 默认用户名：`admin`
   - 默认密码：`admin123`

## 配置详解

### 主配置文件

```toml
[XYBot]
admins = ["admin_wxid"]  # 管理员微信ID列表
enable_plugin_market = true  # 是否启用插件市场
```

### Dify 插件配置

```toml
[Dify]
enable = true
default-model = "model1"
command-tip = true
commands = ["ai", "机器人", "gpt"]
admin_ignore = true
whitelist_ignore = true
http-proxy = ""
voice_reply_all = false
robot-names = ["机器人", "小助手"]
remember_user_model = true
chatroom_enable = true

[Dify.models.model1]
api-key = "your_api_key"
base-url = "https://api.dify.ai/v1"
trigger-words = ["dify", "小d"]
price = 10
wakeup-words = ["你好小d", "嘿小d"]
```

## 使用指南

### 管理员命令

- 登录管理后台查看各项功能
- 通过微信直接向机器人发送命令管理

### 用户交互

- **私聊模式**：直接向机器人发送消息
- **群聊模式**：
  - @机器人 + 问题
  - 使用特定命令如 `ai 问题`
  - 使用唤醒词如 `你好小d 问题`

### 聊天室功能

- **加入聊天**：@机器人或使用命令
- **查看状态**：发送"查看状态"
- **暂时离开**：发送"暂时离开"
- **回来**：发送"回来了"
- **退出聊天**：发送"退出聊天"
- **查看统计**：发送"我的统计"
- **聊天排行**：发送"聊天室排行"

### 图片和语音

- 发送图片和文字组合进行图像相关提问
- 发送语音自动识别并回复
- 语音回复可根据配置自动开启

## 插件开发

### 插件目录结构

```
plugins/
  ├── YourPlugin/
  │   ├── __init__.py
  │   ├── main.py
  │   ├── config.toml
  │   └── README.md
```

### 基本插件模板

```python
from utils.plugin_base import PluginBase
from WechatAPI import WechatAPIClient
from utils.decorators import *

class YourPlugin(PluginBase):
    description = "插件描述"
    author = "作者名称"
    version = "1.0.0"

    def __init__(self):
        super().__init__()
        # 初始化代码

    @on_text_message(priority=10)
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        # 处理文本消息
        pass
```

## 常见问题

1. **安装依赖失败**

   - 尝试使用 `pip install --upgrade pip` 更新 pip
   - 可能需要安装开发工具: `apt-get install python3-dev`

2. **语音识别失败**

   - 确认 FFmpeg 已正确安装并添加到 PATH
   - 检查 SpeechRecognition 依赖是否正确安装

3. **无法连接微信**

   - 确认微信客户端和接口版本是否匹配
   - 检查网络连接和端口设置

4. **Dify API 错误**

   - 验证 API 密钥是否正确
   - 确认 API URL 格式和访问权限

5. **无法访问管理后台**
   - 确认服务器正常运行在 9090 端口
   - 尝试使用默认账号密码: admin/admin123
   - 检查防火墙设置是否阻止了端口访问

## 技术架构

- **后端**：Python FastAPI
- **前端**：Bootstrap, Chart.js, AOS
- **数据库**：SQLite (aiosqlite)
- **外部服务**：Dify API，Google Speech-to-Text
- **Web 服务**：默认端口 9090，默认账号 admin/admin123

## 项目结构

```
XXXBot/
  ├── admin/                  # 管理后台
  │   ├── static/             # 静态资源
  │   ├── templates/          # HTML模板
  │   └── contacts.json       # 联系人配置
  ├── plugins/                # 插件目录
  │   └── Dify/               # Dify插件
  ├── database/               # 数据库相关
  ├── utils/                  # 工具函数
  ├── WechatAPI/              # 微信API接口
  ├── app.py                  # 主应用入口
  ├── requirements.txt        # 依赖列表
  └── main_config.toml        # 主配置文件
```

## 协议和许可

本项目仅供学习和研究使用，使用前请确保符合微信和相关服务的使用条款。

## 鸣谢

特别感谢所有贡献者和使用的开源项目。

## 联系方式

GitHub: [https://github.com/NanSsye](https://github.com/NanSsye)
