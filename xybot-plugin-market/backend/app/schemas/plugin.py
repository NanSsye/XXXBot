from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field


class TagBase(BaseModel):
    name: str


class TagCreate(TagBase):
    pass


class Tag(TagBase):
    id: int

    class Config:
        from_attributes = True


class RequirementBase(BaseModel):
    name: str
    version: Optional[str] = None


class RequirementCreate(RequirementBase):
    pass


class Requirement(RequirementBase):
    id: int
    plugin_id: str

    class Config:
        from_attributes = True


class PluginBase(BaseModel):
    name: str
    description: str
    author: str
    version: str
    github_url: str = Field(..., description="GitHub仓库URL或直接下载链接")
    icon: Optional[str] = None


class PluginCreate(PluginBase):
    tags: List[str] = []
    requirements: List[RequirementCreate] = []


class PluginReview(BaseModel):
    plugin_id: str
    action: str = Field(..., description="审核动作: approve/reject")
    comment: Optional[str] = None


class Plugin(PluginBase):
    id: str
    status: str
    submit_time: datetime
    review_time: Optional[datetime] = None
    downloads: int
    submitter_id: Optional[str] = None
    tags: List[Tag] = []
    requirements: List[Requirement] = []
    review_comment: Optional[str] = None

    class Config:
        from_attributes = True


class PluginResponse(BaseModel):
    success: bool
    plugin: Optional[Plugin] = None
    error: Optional[str] = None


class PluginsListResponse(BaseModel):
    success: bool
    plugins: List[Plugin] = []
    error: Optional[str] = None 