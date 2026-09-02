# -*- coding: utf-8 -*-
"""Pydantic 响应模型 — 统一 API 输出结构"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """统一响应包装"""
    success: bool = True
    message: str = "ok"
    data: Optional[Any] = None


class CacheStats(BaseModel):
    """缓存总统计"""
    cache_root: str
    total_size_mb: float
    total_files: int
    total_dirs: int
    categories: List[Dict[str, Any]] = Field(default_factory=list)


class CategoryInfo(BaseModel):
    """缓存类别（子目录）信息"""
    name: str
    path: str
    size_mb: float
    file_count: int
    last_modified: str
    is_cleanable: bool


class FileInfo(BaseModel):
    """文件元信息"""
    name: str
    path: str
    category: str
    size_kb: float
    extension: str
    last_modified: str
    readable: bool


class FileContent(BaseModel):
    """文件内容响应"""
    name: str
    category: str
    extension: str
    size_kb: float
    row_count: Optional[int] = None
    columns: Optional[List[str]] = None
    content: Any = None
    preview: bool = False
    truncated: bool = False


class HealthStatus(BaseModel):
    """健康检查状态"""
    service: str = "quant-cache-service"
    version: str
    cache_root_exists: bool
    cache_root_writable: bool
    parquet_root_exists: bool
    total_size_mb: float
    total_files: int
    uptime_seconds: float
    checks: Dict[str, str] = Field(default_factory=dict)


class CleanResult(BaseModel):
    """清理操作结果"""
    cleaned_dirs: List[str] = Field(default_factory=list)
    skipped_dirs: List[str] = Field(default_factory=list)
    files_removed: int = 0
    space_freed_mb: float = 0.0
    dry_run: bool = True
