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

> 如果是修改插件配置则可使用热加载、热卸载、热重载指令，不用重启机器人。

## ❓ 常见问题

1. 与网络相关的报错

- 检查网络连接，是否能ping通微信服务器
- 尝试关闭代理软件，尝试重启电脑
- 尝试重启XYBot和Redis
- 如是Docker部署，检查Docker容器网络是否能连接到微信服务器和Dragonfly数据库

2. `正在运行`相关的报错

- 将占用9000端口的进程强制结束