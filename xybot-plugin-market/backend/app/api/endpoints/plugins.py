from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
import base64
import os

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.user import User
from app.models.plugin import Plugin, Tag, Requirement
from app.schemas.plugin import (
    PluginCreate, Plugin as SchemaPlugin, PluginResponse, 
    PluginsListResponse, PluginReview
)

router = APIRouter()

@router.get("/", response_model=PluginsListResponse)
async def list_plugins(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取插件列表
    - status: 过滤状态（pending, approved, rejected）
    """
    try:
        query = db.query(Plugin)
        if status:
            query = query.filter(Plugin.status == status)
        
        plugins = query.all()
        schema_plugins = [SchemaPlugin.from_orm(plugin) for plugin in plugins]
        return PluginsListResponse(success=True, plugins=schema_plugins)
    except Exception as e:
        return PluginsListResponse(success=False, error=str(e))

@router.get("/pending", response_model=PluginsListResponse)
async def list_pending_plugins(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    获取待审核的插件列表（需要管理员权限）
    """
    try:
        plugins = db.query(Plugin).filter(Plugin.status == "pending").all()
        schema_plugins = [SchemaPlugin.from_orm(plugin) for plugin in plugins]
        return PluginsListResponse(success=True, plugins=schema_plugins)
    except Exception as e:
        return PluginsListResponse(success=False, error=str(e))

@router.get("/{plugin_id}", response_model=PluginResponse)
async def get_plugin(
    plugin_id: str,
    db: Session = Depends(get_db)
):
    """
    获取插件详情
    """
    try:
        plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()
        if not plugin:
            return PluginResponse(success=False, error="插件不存在")
        
        schema_plugin = SchemaPlugin.from_orm(plugin)
        return PluginResponse(success=True, plugin=schema_plugin)
    except Exception as e:
        return PluginResponse(success=False, error=str(e))

@router.post("/", response_model=PluginResponse)
async def create_plugin(
    plugin_data: PluginCreate,
    db: Session = Depends(get_db)
):
    """
    提交插件（来自Bot）
    """
    try:
        # 创建新插件
        new_plugin = Plugin(
            name=plugin_data.name,
            description=plugin_data.description,
            author=plugin_data.author,
            version=plugin_data.version,
            github_url=plugin_data.github_url,
            icon=plugin_data.icon,
            status="pending",
            submit_time=datetime.utcnow(),
            downloads=0
        )
        
        # 处理标签
        for tag_name in plugin_data.tags:
            tag = db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.add(tag)
                db.flush()
            new_plugin.tags.append(tag)
        
        # 处理依赖
        for req_data in plugin_data.requirements:
            req = Requirement(
                name=req_data.name,
                version=req_data.version
            )
            new_plugin.requirements.append(req)
        
        db.add(new_plugin)
        db.commit()
        db.refresh(new_plugin)
        
        return PluginResponse(success=True, plugin=new_plugin)
    except Exception as e:
        db.rollback()
        return PluginResponse(success=False, error=str(e))

@router.post("/review", response_model=PluginResponse)
async def review_plugin(
    review_data: PluginReview,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    审核插件（需要管理员权限）
    """
    print(f"接收到审核请求: plugin_id={review_data.plugin_id}, action={review_data.action}, comment={review_data.comment}")
    print(f"当前用户: {current_user.username}")
    
    try:
        plugin = db.query(Plugin).filter(Plugin.id == review_data.plugin_id).first()
        if not plugin:
            print(f"插件不存在: {review_data.plugin_id}")
            return PluginResponse(success=False, error="插件不存在")
        
        print(f"找到插件: {plugin.name}, 当前状态: {plugin.status}")
        
        # 修改验证逻辑，允许在已审核状态之间切换
        # 仅pending状态需要验证action，已审核状态可以切换
        if plugin.status == "pending" and review_data.action not in ["approve", "reject"]:
            print(f"无效的审核动作: {review_data.action}")
            return PluginResponse(success=False, error="无效的审核动作")
        
        # 验证操作合法性
        if review_data.action == "approve":
            # approve操作：允许从pending或rejected变为approved
            if plugin.status not in ["pending", "rejected"]:
                return PluginResponse(success=False, error=f"当前状态({plugin.status})不能执行approve操作")
            new_status = "approved"
        elif review_data.action == "reject":
            # reject操作：允许从pending或approved变为rejected
            if plugin.status not in ["pending", "approved"]:
                return PluginResponse(success=False, error=f"当前状态({plugin.status})不能执行reject操作")
            new_status = "rejected"
        else:
            return PluginResponse(success=False, error="无效的审核动作")
        
        # 执行状态切换
        plugin.status = new_status
        plugin.review_time = datetime.utcnow()
        plugin.review_comment = review_data.comment
        
        try:
            db.commit()
            db.refresh(plugin)
            print(f"插件审核成功: {plugin.name}, 新状态: {plugin.status}")
            return PluginResponse(success=True, plugin=SchemaPlugin.from_orm(plugin))
        except Exception as db_error:
            db.rollback()
            print(f"数据库操作失败: {str(db_error)}")
            return PluginResponse(success=False, error=f"数据库操作失败: {str(db_error)}")
    except Exception as e:
        db.rollback()
        print(f"审核插件过程中发生异常: {str(e)}")
        return PluginResponse(success=False, error=str(e))

@router.post("/install/{plugin_id}", response_model=PluginResponse)
async def install_plugin(
    plugin_id: str,
    db: Session = Depends(get_db)
):
    """
    安装插件（统计下载次数）
    """
    try:
        plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()
        if not plugin:
            return PluginResponse(success=False, error="插件不存在")
        
        if plugin.status != "approved":
            return PluginResponse(success=False, error="插件未获审核通过")
        
        # 增加下载计数
        plugin.downloads += 1
        db.commit()
        
        return PluginResponse(success=True, plugin=plugin)
    except Exception as e:
        db.rollback()
        return PluginResponse(success=False, error=str(e)) 