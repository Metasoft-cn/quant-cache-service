# -*- coding: utf-8 -*-
"""文件读取路由 — 读取 JSON/CSV/Parquet/PKL/TXT 缓存内容"""
from fastapi import APIRouter, Query, HTTPException

from app.cache_manager import CacheManager

router = APIRouter()
_manager = CacheManager()


@router.get("/cache/file/{category}/{filename}")
async def read_file(
    category: str,
    filename: str,
    max_rows: int = Query(1000, ge=1, le=10000, description="最大返回行数（大文件预览）"),
):
    """
    读取缓存文件内容。
    自动识别格式: json / csv / parquet / pkl / txt / log / md
    大文件自动截断并标记 truncated=true
    """
    try:
        return _manager.read_file(category, filename, max_rows=max_rows)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cache/file/{category}/{filename}/meta")
async def get_file_meta(category: str, filename: str):
    """仅获取文件元信息（不读内容）"""
    try:
        from pathlib import Path
        file_path = _manager._safe_resolve(_manager.cache_root, f"{category}/{filename}")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"文件不存在: {category}/{filename}")
        stat = file_path.stat()
        return {
            "name": filename,
            "category": category,
            "path": str(file_path),
            "size_bytes": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 2),
            "extension": file_path.suffix.lower(),
            "created": _manager._fmt_time(stat.st_ctime),
            "last_modified": _manager._fmt_time(stat.st_mtime),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
