import os
import asyncio
import sys
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

# 从当前目录导入app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import app, check_auth

# API: 重启容器
@app.post("/api/system/restart", response_class=JSONResponse)
async def api_restart_container(request: Request):
    """重启容器API"""
    # 检查认证状态
    try:
        # 使用check_auth函数检查认证
        token = request.cookies.get('session')
        if not token:
            return JSONResponse(status_code=401, content={"success": False, "error": "未认证"})
    except Exception as e:
        logger.error(f"认证检查失败: {str(e)}")
        return JSONResponse(status_code=401, content={"success": False, "error": "认证失败"})
    
    try:
        logger.info(f"用户请求重启容器")
        
        # 创建一个后台任务来执行重启
        async def restart_task():
            # 等待1秒让响应先返回
            await asyncio.sleep(1)
            logger.warning("正在重启容器...")
            # 使用os.system执行重启命令
            os.system("pkill -f 'python /app/main.py' || true")
            # 如果在Docker中，可以尝试使用以下命令
            os.system("kill -1 1 || true")
        
        # 启动后台任务
        asyncio.create_task(restart_task())
        
        # 使用明确的JSONResponse返回
        return JSONResponse(content={
            "success": True,
            "message": "容器正在重启，页面将在几秒后自动刷新..."
        })
    except Exception as e:
        logger.error(f"重启容器失败: {str(e)}")
        return JSONResponse(content={
            "success": False,
            "error": f"重启容器失败: {str(e)}"
        }) 