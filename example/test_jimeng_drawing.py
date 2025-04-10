#!/usr/bin/env python
"""
测试脚本，用于测试集成到OpenManus的即梦绘画功能
这个脚本连接到MCP服务器，初始化会话，并请求生成AI绘画
"""

import json
import sys
import asyncio
import httpx
from urllib.parse import urljoin

# 默认MCP服务器URL
MCP_URL = "http://localhost:8088/mcp"

# 添加认证token - 需要确保这个token在服务器配置的valid_tokens列表中
AUTH_TOKEN = "sk-zhouhui111111"

async def test_generate_image(url=MCP_URL):
    """连接到MCP服务器测试即梦AI绘画功能"""
    print(f"连接到MCP服务器: {url}...")

    # 连接到SSE端点建立连接
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        # 首先建立SSE连接
        endpoint_url = None
        base_url = url.rsplit("/", 1)[0] + "/"  # 提取基础URL(去掉最后一个路径组件前的所有内容)

        response_queue = asyncio.Queue()

        # 任务：发送请求并通过SSE通道接收响应
        async def send_request(request_data, request_id):
            # 发送请求
            await client.post(endpoint_url, json=request_data)
            print(f"发送请求，ID: {request_id}")

            # 等待匹配ID的响应
            while True:
                response = await response_queue.get()
                if "id" in response and response["id"] == request_id:
                    return response
                else:
                    # 不是我们的响应，放回队列给其他人
                    await response_queue.put(response)

        # 启动SSE连接
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            print("已连接到MCP服务器")

            # 处理SSE流
            current_event = None

            async def process_sse_stream():
                nonlocal current_event, endpoint_url

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith("event:"):
                        current_event = line[len("event:"):].strip()
                        print(f"收到事件: {current_event}")
                    elif line.startswith("data:"):
                        data = line[len("data:"):].strip()

                        if current_event == "endpoint":
                            endpoint_path = data
                            endpoint_url = urljoin(base_url, endpoint_path.lstrip("/"))
                            print(f"端点URL: {endpoint_url}")
                        elif current_event == "message":
                            try:
                                message = json.loads(data)
                                # 格式化打印JSON消息
                                print("收到消息:")
                                print(json.dumps(message, indent=2, ensure_ascii=False))

                                # 添加到队列供请求处理程序使用
                                await response_queue.put(message)
                            except json.JSONDecodeError:
                                print(f"解析消息失败: {data}")

            # 在后台启动处理SSE流
            background_task = asyncio.create_task(process_sse_stream())

            # 等待端点URL设置
            while endpoint_url is None:
                await asyncio.sleep(0.1)

            try:
                # 1. 初始化请求
                init_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"experimental": {}},
                        "clientInfo": {"name": "mcp-test-client", "version": "0.1.0"},
                    },
                }

                print("\n发送初始化请求...")
                init_result = await send_request(init_request, 1)
                print("\n初始化响应:")
                print(json.dumps(init_result, indent=2, ensure_ascii=False))

                # 2. 发送已初始化通知
                init_notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}

                await client.post(endpoint_url, json=init_notification)
                print("\n发送已初始化通知")

                # 3. 列出工具请求
                list_tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}

                print("\n发送tools/list请求...")
                tools_result = await send_request(list_tools_request, 2)
                print("\n工具列表响应:")
                print(json.dumps(tools_result, indent=2, ensure_ascii=False))

                # 检查是否得到有效响应
                if "result" in tools_result and "tools" in tools_result["result"]:
                    tools = tools_result["result"]["tools"]
                    if tools:
                        print(f"\n找到 {len(tools)} 个工具:")
                        for i, tool in enumerate(tools):
                            print(f"{i + 1}. {tool['name']}")
                            print(f"{tool.get('description', '无描述')}")

                        # 4. 查找并调用即梦绘画工具
                        drawing_tool = None
                        for tool in tools:
                            if tool["name"] == "generate_image":
                                drawing_tool = tool
                                break

                        if drawing_tool:
                            print(f"\n尝试调用工具: {drawing_tool['name']}")

                            call_tool_request = {
                                "jsonrpc": "2.0",
                                "id": 3,
                                "method": "tools/call",
                                "params": {
                                    "name": drawing_tool["name"],
                                    "arguments": {
                                        "prompt": "一只可爱的小猫在草地上玩耍",
                                        "model": "2.1",
                                        "ratio": "1:1"
                                    },
                                },
                            }

                            print("\n发送AI绘画请求...")
                            print("这可能需要30秒至1分钟，请耐心等待...")
                            
                            # 设置超时时间
                            client.timeout = httpx.Timeout(300.0)
                            
                            tool_result = await send_request(call_tool_request, 3)
                            print("\nAI绘画结果:")
                            print(json.dumps(tool_result, indent=2, ensure_ascii=False))
                            
                            if "result" in tool_result and "success" in tool_result["result"] and tool_result["result"]["success"]:
                                print("\n绘画成功!")
                                if "image_urls" in tool_result["result"]:
                                    image_urls = tool_result["result"]["image_urls"]
                                    print(f"\n共生成 {len(image_urls)} 张图片:")
                                    for i, url in enumerate(image_urls):
                                        print(f"图片 {i+1}: {url}")
                                if "message" in tool_result["result"]:
                                    print(f"\n信息: {tool_result['result']['message']}")
                            else:
                                error = tool_result.get("result", {}).get("error", "未知错误")
                                print(f"\n绘画失败: {error}")
                        else:
                            print("\n未找到generate_image工具")
                    else:
                        print("\n未找到工具")
                else:
                    print("\n无效的tools/list响应格式")

            except Exception as e:
                print(f"\n发生错误: {e}")
            finally:
                # 清理并取消后台任务
                background_task.cancel()
                try:
                    await background_task
                except asyncio.CancelledError:
                    pass


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else MCP_URL
    asyncio.run(test_generate_image(url)) 