FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV TZ=Asia/Shanghai
ENV IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg

# 安装系统基础依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    redis-server \
    build-essential \
    python3-dev \
    p7zip-full \
    unrar-free \
    curl \
    netcat \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/7za /usr/bin/7z

# 安装 nodejs 和 npm - 按照您的安装流程
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# 安装 wetty - 使用您的安装命令
RUN npm install -g wetty

# 安装 procps 工具 - 按照您的安装流程
RUN apt-get update && apt-get install -y procps \
    && rm -rf /var/lib/apt/lists/*

# 复制 Redis 配置
COPY redis.conf /etc/redis/redis.conf

# 复制依赖文件
COPY requirements.txt .

# 升级pip并安装Python依赖 - 按照您的安装流程
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir websockets httpx

# 复制应用代码
COPY . .

# 设置权限
RUN chmod -R 755 /app \
    && find /app -name "XYWechatPad" -exec chmod +x {} \; \
    && find /app -type f -name "*.py" -exec chmod +x {} \; \
    && find /app -type f -name "*.sh" -exec chmod +x {} \;

# 创建日志目录
RUN mkdir -p /app/logs && chmod 777 /app/logs

# 启动脚本
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# 暴露端口
EXPOSE 9090 3000

CMD ["./entrypoint.sh"]