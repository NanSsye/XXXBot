# 🤖 XYBot V2

XYBot V2 是一个功能丰富的微信机器人框架,支持多种互动功能和游戏玩法。

# 免责声明

- 这个项目免费开源，不存在收费。
- 本工具仅供学习和技术研究使用，不得用于任何商业或非法行为。
- 本工具的作者不对本工具的安全性、完整性、可靠性、有效性、正确性或适用性做任何明示或暗示的保证，也不对本工具的使用或滥用造成的任何直接或间接的损失、责任、索赔、要求或诉讼承担任何责任。
- 本工具的作者保留随时修改、更新、删除或终止本工具的权利，无需事先通知或承担任何义务。
- 本工具的使用者应遵守相关法律法规，尊重微信的版权和隐私，不得侵犯微信或其他第三方的合法权益，不得从事任何违法或不道德的行为。
- 本工具的使用者在下载、安装、运行或使用本工具时，即表示已阅读并同意本免责声明。如有异议，请立即停止使用本工具，并删除所有相关文件。

# 公告

## 项目还在开发中，有些commit有bug，更新叠代会非常迅速。如果你部署好的能用，在正式发布前，可以不用更新了。

## 统一回复ISSUE内的问题：我敢承诺项目内不会有任何形式的后门程序、病毒程序、木马程序，最多只有一个防滥用倒卖的框架检测。

# 📄 文档

## https://henryxiaoyang.github.io/XYBotV2

# 💬 微信交流群

<div style="text-align: center" align="center">
    <img alt="微信交流群二维码" src="https://qrcode.yangres.com/get_image" style="width: 300px; height: auto;">
    <p>微信扫码加入交流群</p>
    <a href="https://qrcode.yangres.com/get_image">🔗图片会被缓存，点我查看最新二维码</a>
</div>

# ✨ 主要功能

## 🛠️ 基础功能

- 🤖 AI聊天 - 支持文字、图片、语音等多模态交互
- 📰 每日新闻 - 自动推送每日新闻
- 🎵 点歌系统 - 支持在线点歌
- 🌤️ 天气查询 - 查询全国各地天气
- 🎮 游戏功能 - 五子棋、战争雷霆玩家查询等

## 💎 积分系统

- 📝 每日签到 - 支持连续签到奖励
- 🎲 抽奖系统 - 多种抽奖玩法
- 🧧 红包系统 - 群内发积分红包
- 💰 积分交易 - 用户间积分转账
- 📊 积分排行 - 查看积分排名

## 👮 管理功能

- ⚙️ 插件管理 - 动态加载/卸载插件
- 👥 白名单管理 - 控制机器人使用权限
- 📊 积分管理 - 管理员可调整用户积分
- 🔄 签到重置 - 重置所有用户签到状态

# 🔌 插件系统

XYBot V2 采用插件化设计,所有功能都以插件形式实现。主要插件包括:

- 👨‍💼 AdminPoint - 积分管理
- 🔄 AdminSignInReset - 签到重置
- 🛡️ AdminWhitelist - 白名单管理
- 🤖 Ai - AI聊天
- 📊 BotStatus - 机器人状态
- 📱 GetContact - 获取通讯录
- 🌤️ GetWeather - 天气查询
- 🎮 Gomoku - 五子棋游戏
- 🌅 GoodMorning - 早安问候
- 📈 Leaderboard - 积分排行
- 🎲 LuckyDraw - 幸运抽奖
- 📋 Menu - 菜单系统
- 🎵 Music - 点歌系统
- 📰 News - 新闻推送
- 💱 PointTrade - 积分交易
- 💰 QueryPoint - 积分查询
- 🎯 RandomMember - 随机群成员
- 🖼️ RandomPicture - 随机图片
- 🧧 RedPacket - 红包系统
- ✍️ SignIn - 每日签到
- ✈️ Warthunder - 战争雷霆查询

# 🚀 部署说明

## 🐳 Docker 部署（推荐）

### 1. 🔧 准备环境

需要安装 Docker 和 Docker Compose:

- 🐋 Docker 安装: https://docs.docker.com/get-started/get-docker/
- 🔄 Docker Compose 安装: https://docs.docker.com/compose/install/

2. ⬇️ 拉取最新镜像

```bash
# 克隆项目
git clone https://github.com/HenryXiaoYang/XYBotV2.git
cd XYBotV2

# 拉取镜像
docker-compose pull
```

3. 🚀 启动容器

```bash
# 首次启动
docker-compose up -d

# 查看容器状态
docker-compose ps
```

4. 📱 查看日志然后登录微信

```bash
# 查看日志获取登录二维码
docker-compose logs -f xybotv2
```

扫描终端显示的二维码完成登录。（如果扫不出来,可以打开链接扫码）。首次登录成功后,需要挂机4小时。之后机器人就会自动开始正常运行。

5. ⚙️ 配置文件修改

```bash
# 查看数据卷位置
docker volume inspect xybotv2

# 编辑对应目录下的配置文件
xybotv2-volumes-dir/_data/main_config.toml
xybotv2-volumes-dir/_data/plugins/all_in_one_config.toml
```

修改配置后需要重启容器使配置生效:

```bash
docker-compose restart xybotv2
```

> [!TIP]
> 如果是修改插件配置则可使用热加载、热卸载、热重载指令，不用重启机器人。

### ❓ 常见问题

1. 🔌 Redis 连接失败

- 检查 DragonFly 服务是否正常运行
- 确认 main_config.toml 中的 redis-host 配置是否正确

2. ⚠️ 配置文件修改未生效

- 重启容器: `docker-compose restart xybotv2`
- 检查配置文件权限是否正确

3. 📝 日志查看

```bash
# 查看实时日志
docker-compose logs -f xybotv2

# 查看最近100行日志
docker-compose logs --tail=100 xybotv2
```

## 💻 直接部署

### 🪟 Windows 部署步骤

#### 1. 🔧 环境准备

- 安装 Python 3.11 (必须是3.11版本): https://www.python.org/downloads/release/python-3119/
    - 在安装过程中勾选 "Add Python to PATH" 选项
    - 或者手动添加：
        1. 右键点击 "此电脑" -> "属性" -> "高级系统设置" -> "环境变量"
        2. 在 "系统变量" 中找到 Path,点击 "编辑"
        3. 添加 Python 安装目录（如 `C:\Python311`）和 Scripts 目录（如 `C:\Python311\Scripts`）

- 安装 ffmpeg:
    1. 从 [ffmpeg官网](https://www.ffmpeg.org/download.html) 下载 Windows 版本
    2. 解压到合适的目录（如 `C:\ffmpeg`）
    3. 添加环境变量：
        - 右键点击 "此电脑" -> "属性" -> "高级系统设置" -> "环境变量"
        - 在 "系统变量" 中找到 Path，点击 "编辑"
        - 添加 ffmpeg 的 bin 目录路径（如 `C:\ffmpeg\bin`）
    4. 设置 IMAGEIO_FFMPEG_EXE 环境变量：
        - 在 "系统变量" 中点击 "新建"
        - 变量名输入：`IMAGEIO_FFMPEG_EXE`
        - 变量值输入 ffmpeg.exe 的完整路径（如 `C:\ffmpeg\bin\ffmpeg.exe`）
    5. 重启命令提示符或 PowerShell 使环境变量生效
    6. 验证安装：
        ```bash
        ffmpeg -version
        ```

- 安装 Redis:
    - 从 [Redis](https://github.com/tporadowski/redis/releases/tag/v5.0.14.1) 下载最新版本 (目前是7.4.2)
    - 下载并解压 `Redis-x64-5.0.14.1.zip`
    - 在命令行执行:
      ```bash
      # 进入目录
      cd Redis-x64-5.0.14.1
      
      # 启动Redis服务
      start redis-server.exe
      ```

#### 2. ⬇️ 下载项目

```bash
# 克隆项目
git clone https://github.com/HenryXiaoYang/XYBotV2.git
# 小白：直接 Github Download ZIP

cd XYBotV2

# 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 使用镜像源安装
pip install -r requirements.txt -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

#### 3. 🚀 启动机器人

```bash
# 确保Redis服务已启动
redis-cli ping  # 如果返回PONG则表示Redis正常运行

# 启动机器人
python main.py
```

#### 4. 📱 登录微信

- 扫描终端显示的二维码完成登录。如果扫不出来,可以打开二维码下面的链接扫码。
- 首次登录成功后,需要挂机4小时。之后机器人就会开始正常运行。

#### 5. ⚙️ 配置文件修改

主配置: main_config.toml 主配置文件

插件配置: plugins/all_in_one_config.toml 插件配置文件

这几个插件需要配置API密钥才可正常工作:

- 🤖 Ai
- 🌤️ GetWeather


- 如果机器人正在运行，需要重启才能使主配置生效：
    ```bash
    # 按Ctrl+C停止机器人
    # 重新启动
    python main.py
    ```

> [!TIP]
> 如果是修改插件配置则可使用热加载、热卸载、热重载指令，不用重启机器人。

### 🐧 Linux 部署步骤

#### 1. 🔧 环境准备

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv redis-server ffmpeg

# CentOS/RHEL
sudo yum install epel-release  # 如果需要EPEL仓库
sudo yum install python3.11 redis ffmpeg
sudo systemctl start redis
sudo systemctl enable redis

# 设置 IMAGEIO_FFMPEG_EXE 环境变量
echo 'export IMAGEIO_FFMPEG_EXE=$(which ffmpeg)' >> ~/.bashrc
source ~/.bashrc

# 如果使用其他shell(如zsh)，则需要：
# echo 'export IMAGEIO_FFMPEG_EXE=$(which ffmpeg)' >> ~/.zshrc
# source ~/.zshrc
```

#### 2. ⬇️ 下载项目

```bash
# 克隆项目
git clone https://github.com/HenryXiaoYang/XYBotV2.git
# 小白：直接 Github Download ZIP

cd XYBotV2

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 使用镜像源安装
pip install -r requirements.txt -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

4. 🚀 启动机器人

```bash
# 确保在虚拟环境中
source venv/bin/activate

# 检查Redis服务状态
systemctl status redis

# 如果Redis未运行，启动服务
sudo systemctl start redis

# 设置Redis开机自启
sudo systemctl enable redis

# 验证Redis连接
redis-cli ping
# 如果返回PONG表示连接正常

# 启动机器人
python3 main.py
```

5. 📱 登录微信

- 扫描终端显示的二维码完成登录。如果扫不出来,可以打开二维码下面的链接扫码。
- 首次登录成功后,需要挂机4小时。之后机器人就会开始正常运行。

6. ⚙️ 配置文件修改

主配置: main_config.toml 主配置文件

插件配置: plugins/all_in_one_config.toml 插件配置文件

这几个插件需要配置API密钥才可正常工作:

- 🤖 Ai
- 🌤️ GetWeather

- 如果机器人正在运行，需要重启才能使主配置生效：
    ```bash
    # 按Ctrl+C停止机器人
    # 重新启动
    python main.py
    ```

> [!TIP]
> 如果是修改插件配置则可使用热加载、热卸载、热重载指令，不用重启机器人。

# 💻 代码提交

提交代码时请使用 `feat: something` 作为说明，支持的标识如下:

- `feat` 新功能(feature)
- `fix` 修复bug
- `docs` 文档(documentation)
- `style` 格式(不影响代码运行的变动)
- `ref` 重构(即不是新增功能，也不是修改bug的代码变动)
- `perf` 性能优化(performance)
- `test` 增加测试
- `chore` 构建过程或辅助工具的变动
- `revert` 撤销

## ❓ 常见问题

1. 与网络相关的报错

- 检查网络连接，是否能ping通微信服务器
- 尝试关闭代理软件，尝试重启电脑
- 尝试重启XYBot和Redis
- 如是Docker部署，检查Docker容器网络是否能连接到微信服务器和Dragonfly数据库

2. `正在运行`相关的报错

- 将占用9000端口的进程强制结束
