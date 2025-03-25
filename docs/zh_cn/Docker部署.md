# 🐳 Docker 部署

## 1. 🔧 准备环境

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

> 如果是修改插件配置则可使用热加载、热卸载、热重载指令，不用重启机器人。

## ❓ 常见问题

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

4. 与网络相关的报错

- 检查网络连接，是否能ping通微信服务器
- 尝试关闭代理软件，尝试重启电脑
- 尝试重启XYBot和Redis
- 如是Docker部署，检查Docker容器网络是否能连接到微信服务器和Dragonfly数据库

5. `正在运行`相关的报错

- 将占用9000端口的进程强制结束