# -*- coding: utf-8 -*-
"""缓存管理路由 — 清理临时文件、空间回收"""
from fastapi import APIRouter, Query, Depends

from app.cache_manager import CacheManager
from app.main import verify_api_key

router = APIRouter()
_manager = CacheManager()


@router.post("/cache/clean")
async def clean_temp(
    dry_run: bool = Query(True, description="试运行（只报告不删除），设为 false 才真正删除"),
    api_key: str = Depends(verify_api_key),
):
    """
    清理临时/可清理目录。
    只清理白名单内的临时目录（pytest_tmp、auto_fix_reports、logs 等），
    不会触碰核心数据（tushare/daily/factor_cache 等）。
    默认 dry_run=true，确认无误后传 dry_run=false 执行。
    """
    return _manager.clean_temp(dry_run=dry_run)


@router.get("/cache/cleanable")
async def list_cleanable():
    """列出可清理的临时目录及其大小"""
    from app.config import settings
    result = []
    for dir_name in sorted(settings.CLEANABLE_DIRS):
        dir_path = _manager.cache_root / dir_name
        if dir_path.exists():
            size, count = _manager._dir_size(dir_path)
            result.append({
                "name": dir_name,
                "exists": True,
                "size_mb": round(size / (1024 * 1024), 2),
                "file_count": count,
            })
        else:
            result.append({
                "name": dir_name,
                "exists": False,
                "size_mb": 0,
                "file_count": 0,
            })
    total_mb = sum(r["size_mb"] for r in result)
    return {
        "cleanable_dirs": result,
        "total_cleanable_mb": round(total_mb, 2),
        "note": "这些目录为运行时临时产物，可安全清理；核心数据目录不在此列。",
    }
