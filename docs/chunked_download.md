# 分块下载大文件功能使用说明

本文档介绍如何使用分块下载功能，解决微信API的64KB文件大小限制问题。

## 背景

微信API的`download_attach`方法有64KB的文件大小限制，无法直接下载大文件。为了解决这个问题，我们实现了分块下载功能，可以下载任意大小的文件。

## 实现原理

1. **客户端扩展**：添加了`ChunkedDownloadMixin`类，提供分块下载功能
2. **代理服务器**：实现了一个代理服务器，拦截微信API请求，添加对分块下载的支持
3. **CDN插件修改**：修改了`CDNFileDownloader`插件，使用分块下载功能

## 使用方法

### 1. 启动代理服务器

首先，需要启动代理服务器：

```bash
python start_proxy.py
```

默认情况下，代理服务器会监听9001端口，并将请求转发到127.0.0.1:9000（原始微信API服务器）。

可以通过命令行参数修改配置：

```bash
python start_proxy.py --target-host 127.0.0.1 --target-port 9000 --proxy-port 9001
```

### 2. 修改配置文件

修改`main_config.toml`文件，将微信API客户端的端口改为代理服务器的端口：

```toml
[WechatAPIServer]
port = 9000                # 原始微信API服务器端口，保持不变

# 其他配置...

[XYBot]
api_port = 9001            # 添加此行，指定API客户端使用的端口（代理服务器端口）
```

### 3. 使用分块下载功能

现在，当您收到大文件时，`CDNFileDownloader`插件会自动使用分块下载功能下载文件。

您也可以在自己的代码中使用分块下载功能：

```python
from WechatAPI.Client import WechatAPIClient

# 创建客户端实例
bot = WechatAPIClient("127.0.0.1", 9001)  # 使用代理服务器端口

# 使用分块下载功能
success = await bot.download_attach_chunked(
    attach_id="文件ID",
    output_file="保存路径.zip",
    chunk_size=60000,  # 每块大小约60KB
    max_retries=3
)

if success:
    print("文件下载成功")
else:
    print("文件下载失败")
```

## 注意事项

1. **代理服务器必须运行**：使用分块下载功能前，必须先启动代理服务器
2. **内存占用**：代理服务器会将完整文件缓存在内存中，下载大文件时可能占用较多内存
3. **首次下载较慢**：首次下载文件时，代理服务器需要从原始API下载完整文件，可能较慢
4. **缓存机制**：代理服务器会缓存已下载的文件，再次下载同一文件时会更快

## 故障排除

如果遇到问题，请检查：

1. 代理服务器是否正常运行
2. 配置文件中的端口设置是否正确
3. 日志文件`logs/proxy_server.log`中是否有错误信息

## 高级配置

### 调整分块大小

可以调整分块大小以优化下载性能：

```python
# 使用较大的分块大小
success = await bot.download_attach_chunked(
    attach_id="文件ID",
    output_file="保存路径.zip",
    chunk_size=120000,  # 增加到120KB
    max_retries=3
)
```

### 显示下载进度

可以使用进度回调函数显示下载进度：

```python
async def show_progress(current_size, total_size):
    progress = (current_size / total_size) * 100
    print(f"下载进度: {progress:.2f}%, {current_size}/{total_size} 字节")

success = await bot.download_attach_chunked(
    attach_id="文件ID",
    output_file="保存路径.zip",
    progress_callback=show_progress
)
```
