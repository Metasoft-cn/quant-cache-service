# -*- coding: utf-8 -*-
"""
缓存管理器 — 核心业务逻辑。
负责目录扫描、统计、文件读取、格式解析、清理操作。
所有路径操作严格限制在 CACHE_ROOT / PARQUET_ROOT 内，防路径穿越。
"""
import os
import json
import csv
import io
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from app.config import settings


class CacheManager:
    """缓存管理核心"""

    def __init__(self, cache_root: Optional[Path] = None, parquet_root: Optional[Path] = None):
        self.cache_root = Path(cache_root) if cache_root else settings.CACHE_ROOT
        self.parquet_root = Path(parquet_root) if parquet_root else settings.PARQUET_ROOT

    # ---------- 路径安全 ----------

    def _safe_resolve(self, base: Path, relative: str) -> Path:
        """解析相对路径，确保结果在 base 内（防路径穿越）"""
        target = (base / relative).resolve()
        base_resolved = base.resolve()
        if not str(target).startswith(str(base_resolved)):
            raise ValueError(f"路径越界: {relative}")
        return target

    def _fmt_time(self, ts: float) -> str:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    def _dir_size(self, path: Path) -> Tuple[int, int]:
        """递归计算目录大小和文件数"""
        total_size = 0
        file_count = 0
        try:
            for f in path.rglob("*"):
                if f.is_file():
                    try:
                        total_size += f.stat().st_size
                        file_count += 1
                    except OSError:
                        pass
        except OSError:
            pass
        return total_size, file_count

    # ---------- 统计 ----------

    def get_stats(self) -> Dict[str, Any]:
        """缓存总统计 + 按类别（一级子目录）分组"""
        if not self.cache_root.exists():
            return {
                "cache_root": str(self.cache_root),
                "total_size_mb": 0,
                "total_files": 0,
                "total_dirs": 0,
                "categories": [],
                "error": "缓存根目录不存在",
            }

        total_size, total_files = self._dir_size(self.cache_root)
        total_dirs = sum(1 for _ in self.cache_root.rglob("*") if _.is_dir())

        categories = []
        for d in sorted(self.cache_root.iterdir()):
            if d.is_dir():
                size, count = self._dir_size(d)
                categories.append({
                    "name": d.name,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "file_count": count,
                    "is_cleanable": d.name in settings.CLEANABLE_DIRS,
                })

        # 根目录散文件
        root_files = [f for f in self.cache_root.iterdir() if f.is_file()]
        if root_files:
            root_size = sum(f.stat().st_size for f in root_files)
            categories.insert(0, {
                "name": "(root)",
                "size_mb": round(root_size / (1024 * 1024), 2),
                "file_count": len(root_files),
                "is_cleanable": False,
            })

        return {
            "cache_root": str(self.cache_root),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_files": total_files,
            "total_dirs": total_dirs,
            "categories": categories,
        }

    def list_categories(self) -> List[Dict[str, Any]]:
        """列出所有缓存类别（一级子目录）"""
        if not self.cache_root.exists():
            return []
        result = []
        for d in sorted(self.cache_root.iterdir()):
            if d.is_dir():
                size, count = self._dir_size(d)
                result.append({
                    "name": d.name,
                    "path": str(d),
                    "size_mb": round(size / (1024 * 1024), 2),
                    "file_count": count,
                    "last_modified": self._fmt_time(d.stat().st_mtime),
                    "is_cleanable": d.name in settings.CLEANABLE_DIRS,
                })
        return result

    def list_files(self, category: str, pattern: Optional[str] = None,
                   limit: int = 200, offset: int = 0) -> Dict[str, Any]:
        """列出某类别下的文件"""
        cat_path = self._safe_resolve(self.cache_root, category)
        if not cat_path.exists():
            raise FileNotFoundError(f"类别不存在: {category}")

        files = []
        for f in sorted(cat_path.rglob("*")):
            if f.is_file():
                if pattern and pattern.lower() not in f.name.lower():
                    continue
                ext = f.suffix.lower()
                files.append({
                    "name": f.name,
                    "path": str(f.relative_to(self.cache_root)),
                    "category": category,
                    "size_kb": round(f.stat().st_size / 1024, 2),
                    "extension": ext,
                    "last_modified": self._fmt_time(f.stat().st_mtime),
                    "readable": ext in settings.ALLOWED_EXTENSIONS,
                })

        total = len(files)
        paginated = files[offset:offset + limit]
        return {
            "category": category,
            "total": total,
            "limit": limit,
            "offset": offset,
            "files": paginated,
        }

    def search_files(self, pattern: str, category: Optional[str] = None,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """全局搜索缓存文件"""
        base = self.cache_root
        if category:
            base = self._safe_resolve(self.cache_root, category)
        if not base.exists():
            return []

        results = []
        for f in base.rglob("*"):
            if f.is_file() and pattern.lower() in f.name.lower():
                ext = f.suffix.lower()
                results.append({
                    "name": f.name,
                    "path": str(f.relative_to(self.cache_root)),
                    "category": f.relative_to(self.cache_root).parts[0] if f.relative_to(self.cache_root).parts else "(root)",
                    "size_kb": round(f.stat().st_size / 1024, 2),
                    "extension": ext,
                    "last_modified": self._fmt_time(f.stat().st_mtime),
                })
                if len(results) >= limit:
                    break
        return results

    # ---------- 文件读取 ----------

    def read_file(self, category: str, filename: str,
                  max_rows: int = 1000) -> Dict[str, Any]:
        """
        读取缓存文件内容，自动识别格式。
        支持: json, csv, parquet, pkl, txt
        大文件只返回预览（前 N 行 / 前 N 条）。
        """
        file_path = self._safe_resolve(self.cache_root, f"{category}/{filename}")
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {category}/{filename}")

        size = file_path.stat().st_size
        ext = file_path.suffix.lower()
        truncated = False
        content = None
        row_count = None
        columns = None

        # 大小检查
        if size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            return {
                "name": filename,
                "category": category,
                "extension": ext,
                "size_kb": round(size / 1024, 2),
                "content": None,
                "preview": True,
                "truncated": True,
                "error": f"文件超过 {settings.MAX_FILE_SIZE_MB}MB 读取上限，请下载或缩小范围",
            }

        try:
            if ext == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                if isinstance(content, list) and len(content) > max_rows:
                    content = content[:max_rows]
                    truncated = True
                    row_count = len(content)

            elif ext == ".csv":
                rows = []
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.DictReader(f)
                    columns = reader.fieldnames or []
                    for i, row in enumerate(reader):
                        if i >= max_rows:
                            truncated = True
                            break
                        rows.append(row)
                content = rows
                row_count = len(rows)

            elif ext == ".parquet":
                try:
                    import pandas as pd
                    df = pd.read_parquet(file_path)
                    row_count = len(df)
                    columns = list(df.columns)
                    if len(df) > max_rows:
                        df = df.head(max_rows)
                        truncated = True
                    content = json.loads(df.to_json(orient="records", force_ascii=False))
                except ImportError:
                    content = {"error": "pandas/pyarrow 未安装，无法读取 parquet"}

            elif ext == ".pkl":
                try:
                    import pickle
                    with open(file_path, "rb") as f:
                        obj = pickle.load(f)
                    # 尝试序列化为 JSON 友好格式
                    if hasattr(obj, "to_dict"):
                        content = obj.to_dict()
                    elif hasattr(obj, "head"):
                        content = {"type": str(type(obj)), "shape": getattr(obj, "shape", None),
                                   "preview": str(obj)[:500]}
                    else:
                        content = {"type": str(type(obj)), "repr": repr(obj)[:2000]}
                except Exception as e:
                    content = {"error": f"pkl 读取失败: {str(e)}"}

            elif ext in (".txt", ".md", ".log"):
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                row_count = len(lines)
                if len(lines) > max_rows:
                    lines = lines[:max_rows]
                    truncated = True
                content = "".join(lines)

            else:
                content = {"error": f"不支持的格式: {ext}"}

        except Exception as e:
            content = {"error": f"读取失败: {str(e)}"}

        return {
            "name": filename,
            "category": category,
            "extension": ext,
            "size_kb": round(size / 1024, 2),
            "row_count": row_count,
            "columns": columns,
            "content": content,
            "preview": max_rows is not None,
            "truncated": truncated,
        }

    # ---------- 健康检查 ----------

    def health_check(self, start_time: float) -> Dict[str, Any]:
        """服务 + 缓存健康检查"""
        import time
        checks = {}

        cache_exists = self.cache_root.exists()
        checks["cache_root_exists"] = "pass" if cache_exists else "fail"

        cache_writable = False
        if cache_exists:
            try:
                test_file = self.cache_root / ".cache_service_write_test"
                test_file.write_text("ok", encoding="utf-8")
                test_file.unlink()
                cache_writable = True
                checks["cache_root_writable"] = "pass"
            except OSError:
                checks["cache_root_writable"] = "fail"

        parquet_exists = self.parquet_root.exists()
        checks["parquet_root_exists"] = "pass" if parquet_exists else "warn"

        total_size, total_files = (0, 0)
        if cache_exists:
            total_size, total_files = self._dir_size(self.cache_root)

        return {
            "service": "quant-cache-service",
            "version": "1.0.0",
            "cache_root_exists": cache_exists,
            "cache_root_writable": cache_writable,
            "parquet_root_exists": parquet_exists,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_files": total_files,
            "uptime_seconds": round(time.time() - start_time, 2),
            "checks": checks,
        }

    # ---------- 清理 ----------

    def clean_temp(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        清理临时/可清理目录。
        只清理 settings.CLEANABLE_DIRS 中列出的目录，防止误删核心数据。
        dry_run=True 时只报告不删除。
        """
        cleaned = []
        skipped = []
        files_removed = 0
        space_freed = 0

        for dir_name in settings.CLEANABLE_DIRS:
            dir_path = self.cache_root / dir_name
            if not dir_path.exists():
                skipped.append(f"{dir_name} (不存在)")
                continue

            size, count = self._dir_size(dir_path)
            if not dry_run:
                try:
                    import shutil
                    shutil.rmtree(dir_path)
                    files_removed += count
                    space_freed += size
                    cleaned.append(f"{dir_name} (删除 {count} 文件, {round(size/1024/1024,2)} MB)")
                except OSError as e:
                    skipped.append(f"{dir_name} (删除失败: {e})")
            else:
                cleaned.append(f"{dir_name} (将删除 {count} 文件, {round(size/1024/1024,2)} MB)")

        return {
            "cleaned_dirs": cleaned,
            "skipped_dirs": skipped,
            "files_removed": files_removed,
            "space_freed_mb": round(space_freed / (1024 * 1024), 2),
            "dry_run": dry_run,
        }
