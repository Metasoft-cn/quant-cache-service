# -*- coding: utf-8 -*-
"""浏览统计路由 — 总览、类别列表、文件列表、搜索"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Depends

from app.cache_manager import CacheManager
from app.main import verify_api_key

router = APIRouter()
_manager = CacheManager()


@router.get("/cache/stats")
async def get_stats():
    """缓存总统计 — 总大小、文件数、按类别分组"""
    return _manager.get_stats()


@router.get("/cache/categories")
async def list_categories():
    """列出所有缓存类别（一级子目录）"""
    return _manager.list_categories()


@router.get("/cache/files/{category}")
async def list_files(
    category: str,
    pattern: Optional[str] = Query(None, description="文件名过滤关键词"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """列出某类别下的文件（支持分页和过滤）"""
    try:
        return _manager.list_files(category, pattern=pattern, limit=limit, offset=offset)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cache/search")
async def search_files(
    q: str = Query(..., description="搜索关键词（文件名匹配）"),
    category: Optional[str] = Query(None, description="限定类别"),
    limit: int = Query(100, ge=1, le=500),
):
    """全局搜索缓存文件"""
    return _manager.search_files(q, category=category, limit=limit)
