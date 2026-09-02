# -*- coding: utf-8 -*-
"""健康审计路由 — 服务健康、缓存完整性审计"""
from fastapi import APIRouter

from app.cache_manager import CacheManager
from app.config import START_TIME

router = APIRouter()
_manager = CacheManager()


@router.get("/health")
async def health_check():
    """服务健康检查 — 缓存目录存在性、可写性、总大小、运行时长"""
    return _manager.health_check(START_TIME)


@router.get("/cache/audit")
async def cache_audit():
    """
    缓存完整性审计 — 检查各数据类别的覆盖情况。
    包括: 交易日历、日线、daily_basic、因子缓存、退市数据等。
    """
    stats = _manager.get_stats()
    categories = {c["name"]: c for c in stats.get("categories", [])}

    audit_items = []

    # 核心数据类别检查
    expected = {
        "tushare": "Tushare 原始数据（日线/财务/指数等）",
        "daily": "日线行情缓存",
        "daily_basic": "每日基本面指标",
        "daily_delisted": "退市股票日线（幸存者偏差补充）",
        "factor_cache": "因子计算缓存",
        "tushare_data": "Tushare 批量数据（大文件）",
        "tdxgp": "通达信数据",
        "minute_1min": "1分钟K线",
        "advanced": "高级特征/因子",
        "walk_forward": "Walk-Forward 验证结果",
    }

    for name, desc in expected.items():
        cat = categories.get(name)
        if cat:
            audit_items.append({
                "category": name,
                "description": desc,
                "status": "present",
                "size_mb": cat["size_mb"],
                "file_count": cat["file_count"],
            })
        else:
            audit_items.append({
                "category": name,
                "description": desc,
                "status": "missing",
                "size_mb": 0,
                "file_count": 0,
            })

    # 额外存在的类别
    known = set(expected.keys()) | {"(root)"}
    extra = [c for c in stats.get("categories", []) if c["name"] not in known]
    if extra:
        audit_items.append({
            "category": "_extra",
            "description": f"额外 {len(extra)} 个类别",
            "status": "info",
            "extra_categories": [c["name"] for c in extra],
        })

    present = sum(1 for a in audit_items if a["status"] == "present")
    missing = sum(1 for a in audit_items if a["status"] == "missing")

    return {
        "summary": {
            "total_categories_checked": len(expected),
            "present": present,
            "missing": missing,
            "coverage_pct": round(present / len(expected) * 100, 1) if expected else 0,
        },
        "total_size_mb": stats.get("total_size_mb", 0),
        "total_files": stats.get("total_files", 0),
        "items": audit_items,
    }
