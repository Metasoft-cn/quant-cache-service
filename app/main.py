# -*- coding: utf-8 -*-
"""
quant-cache-service — 独立缓存 API 服务
启动: python -m app.main 或 uvicorn app.main:app --reload --port 8100
"""
import sys
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.config import settings, START_TIME

app = FastAPI(
    title="Quant Cache Service",
    description="独立量化数据缓存服务 — 浏览、检索、读取、审计本地缓存",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 鉴权依赖 ----------
def verify_api_key(x_api_key: str = Header(None)):
    """简单 API Key 鉴权；未配置 API_TOKEN 时跳过"""
    if settings.API_TOKEN and x_api_key != settings.API_TOKEN:
        raise HTTPException(status_code=401, detail="无效或缺失 API Key")
    return x_api_key


# ---------- 注册路由 ----------
from app.routers import browse, files, health, manage  # noqa: E402

app.include_router(browse.router, prefix="/api", tags=["浏览统计"])
app.include_router(files.router, prefix="/api", tags=["文件读取"])
app.include_router(health.router, prefix="/api", tags=["健康审计"])
app.include_router(manage.router, prefix="/api", tags=["缓存管理"])


@app.get("/")
async def root():
    """服务根路径 — 基本信息"""
    return {
        "service": "quant-cache-service",
        "version": "1.0.0",
        "docs": "/docs",
        "cache_root": str(settings.CACHE_ROOT),
        "endpoints": {
            "stats": "/api/cache/stats",
            "categories": "/api/cache/categories",
            "files": "/api/cache/files/{category}",
            "read": "/api/cache/file/{category}/{filename}",
            "search": "/api/cache/search",
            "health": "/api/health",
            "audit": "/api/cache/audit",
        },
    }


if __name__ == "__main__":
    import uvicorn
    print(f"[quant-cache-service] 启动于 http://{settings.HOST}:{settings.PORT}")
    print(f"[quant-cache-service] 缓存根目录: {settings.CACHE_ROOT}")
    if settings.API_TOKEN:
        print("[quant-cache-service] 鉴权已启用 (X-API-Key)")
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
