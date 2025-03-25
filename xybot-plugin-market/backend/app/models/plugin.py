from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base

# 插件标签关联表
plugin_tag = Table(
    "plugin_tag",
    Base.metadata,
    Column("plugin_id", String(36), ForeignKey("plugins.id")),
    Column("tag_id", Integer, ForeignKey("tags.id"))
)

class Plugin(Base):
    """插件数据库模型"""
    __tablename__ = "plugins"
    
    # 基本信息
    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), index=True, nullable=False)
    description = Column(Text, nullable=False)
    author = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    github_url = Column(String(255), nullable=False)
    icon = Column(Text, nullable=True)  # Base64编码的图标
    
    # 状态信息
    status = Column(String(20), default="pending")  # pending/approved/rejected
    submit_time = Column(DateTime, default=datetime.utcnow)
    review_time = Column(DateTime, nullable=True)
    
    # 统计信息
    downloads = Column(Integer, default=0)
    
    # 提交者信息
    submitter_id = Column(String(100), nullable=True)  # 可能是Bot ID或null
    
    # 关系
    tags = relationship("Tag", secondary=plugin_tag, back_populates="plugins")
    requirements = relationship("Requirement", back_populates="plugin", cascade="all, delete-orphan")
    
    # 审核信息
    review_comment = Column(Text, nullable=True)  # 审核评论


class Tag(Base):
    """标签数据库模型"""
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True)
    
    # 关系
    plugins = relationship("Plugin", secondary=plugin_tag, back_populates="tags")


class Requirement(Base):
    """插件依赖数据库模型"""
    __tablename__ = "requirements"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=True)
    plugin_id = Column(String(36), ForeignKey("plugins.id"))
    
    # 关系
    plugin = relationship("Plugin", back_populates="requirements") 