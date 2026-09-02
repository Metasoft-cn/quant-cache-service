# -*- coding: utf-8 -*-
"""
配置管理 — 从环境变量 / .env 读取，零硬编码路径。
缓存根目录通过 CACHE_ROOT 环境变量指向原项目的缓存位置。
"""
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# 加载项目根 .env（如果存在）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# 服务启动时间（健康检查 uptime 用；放在 config 避免循环导入）
START_TIME = time.time()


class Settings:
    """运行时配置，全部可通过环境变量覆盖"""

    # 缓存根目录 — 默认指向原量化项目 v2 的 cache 目录
    # 示例: D:\03_Others\Desktop\quant_system_研究原型_20260828\modules\股市预测机_v2\cache
    CACHE_ROOT: Path = Path(
        os.getenv(
            "CACHE_ROOT",
            r"D:\03_Others\Desktop\quant_system_研究原型_20260828\modules\股市预测机_v2\cache",
        )
    )

    # Parquet 缓存根目录（可选，独立路径）
    PARQUET_ROOT: Path = Path(
        os.getenv(
            "PARQUET_ROOT",
            r"D:\03_Others\Desktop\quant_system_研究原型_20260828\modules\股市预测机_v2\cache_parquet",
        )
    )

    # 服务配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8100"))
    API_TOKEN: str = os.getenv("API_TOKEN", "")  # 空 = 不鉴权

    # 安全限制
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))  # 单文件读取上限
    ALLOWED_EXTENSIONS: set = {
        ".json", ".csv", ".parquet", ".pkl", ".txt", ".md", ".log",
    }

    # 临时/可清理目录名（清理操作只动这些，防止误删核心数据）
    CLEANABLE_DIRS: set = {
        "pytest_tmp", "auto_fix_reports", "logs", "queue_runner_0453",
        "verify_0443_tmp", "_t1", "_t2", "cli_e2e_0549",
    }


settings = Settings()
