# -*- coding: utf-8 -*-
"""
API 集成测试 — 使用临时目录构造模拟缓存，验证所有端点。
运行: pytest tests/test_api.py -v
"""
import os
import json
import csv
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def temp_cache(tmp_path):
    """构造模拟缓存目录结构"""
    # tushare 类别
    tushare_dir = tmp_path / "tushare"
    tushare_dir.mkdir()

    # JSON 文件
    cal_data = [{"cal_date": "20260101", "is_open": 0},
                 {"cal_date": "20260102", "is_open": 1}]
    (tushare_dir / "cal_test.json").write_text(
        json.dumps(cal_data, ensure_ascii=False), encoding="utf-8"
    )

    # CSV 文件
    with open(tushare_dir / "daily_test.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ts_code", "trade_date", "close", "vol"])
        writer.writeheader()
        for i in range(5):
            writer.writerow({"ts_code": "000001.SZ", "trade_date": f"2026010{i+1}",
                              "close": str(10 + i), "vol": str(1000 + i)})

    # daily 类别
    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    (daily_dir / "000001.SZ.json").write_text(
        json.dumps([{"date": "20260101", "close": 10.5}], ensure_ascii=False),
        encoding="utf-8",
    )

    # 临时可清理目录
    pytest_tmp = tmp_path / "pytest_tmp"
    pytest_tmp.mkdir()
    (pytest_tmp / "temp_file.txt").write_text("temp", encoding="utf-8")

    # 根目录散文件
    (tmp_path / "root_config.json").write_text('{"version": "1.0"}', encoding="utf-8")

    return tmp_path


@pytest.fixture
def client(temp_cache, monkeypatch):
    """创建测试客户端，注入临时缓存路径"""
    monkeypatch.setenv("CACHE_ROOT", str(temp_cache))
    monkeypatch.setenv("PARQUET_ROOT", str(temp_cache / "nonexistent"))
    monkeypatch.setenv("API_TOKEN", "")

    # 重新导入以获取新配置
    import importlib
    from app import config, cache_manager, main
    importlib.reload(config)
    importlib.reload(cache_manager)

    # 重新创建 manager 实例
    from app.routers import browse, files, health, manage
    browse._manager = cache_manager.CacheManager()
    files._manager = cache_manager.CacheManager()
    health._manager = cache_manager.CacheManager()
    manage._manager = cache_manager.CacheManager()

    with TestClient(main.app) as c:
        yield c


class TestRoot:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "quant-cache-service"
        assert "docs" in data


class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "quant-cache-service"
        assert data["cache_root_exists"] is True
        assert data["cache_root_writable"] is True
        assert data["total_files"] >= 4
        assert "uptime_seconds" in data


class TestStats:
    def test_stats(self, client):
        resp = client.get("/api/cache/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_files"] >= 4
        assert data["total_size_mb"] >= 0
        cat_names = [c["name"] for c in data["categories"]]
        assert "tushare" in cat_names
        assert "daily" in cat_names


class TestCategories:
    def test_list_categories(self, client):
        resp = client.get("/api/cache/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        names = [c["name"] for c in data]
        assert "tushare" in names
        assert "daily" in names
        # 检查字段
        tushare = next(c for c in data if c["name"] == "tushare")
        assert "size_mb" in tushare
        assert "file_count" in tushare
        assert "is_cleanable" in tushare


class TestFiles:
    def test_list_files(self, client):
        resp = client.get("/api/cache/files/tushare")
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "tushare"
        assert data["total"] >= 2
        assert len(data["files"]) >= 2

    def test_list_files_with_pattern(self, client):
        resp = client.get("/api/cache/files/tushare?pattern=cal")
        assert resp.status_code == 200
        data = resp.json()
        assert all("cal" in f["name"].lower() for f in data["files"])

    def test_list_files_pagination(self, client):
        resp = client.get("/api/cache/files/tushare?limit=1&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["files"]) == 1

    def test_list_files_not_found(self, client):
        resp = client.get("/api/cache/files/nonexistent")
        assert resp.status_code == 404


class TestReadFile:
    def test_read_json(self, client):
        resp = client.get("/api/cache/file/tushare/cal_test.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["extension"] == ".json"
        assert data["truncated"] is False
        assert isinstance(data["content"], list)
        assert len(data["content"]) == 2

    def test_read_csv(self, client):
        resp = client.get("/api/cache/file/tushare/daily_test.csv")
        assert resp.status_code == 200
        data = resp.json()
        assert data["extension"] == ".csv"
        assert data["row_count"] == 5
        assert data["columns"] == ["ts_code", "trade_date", "close", "vol"]
        assert len(data["content"]) == 5
        assert data["content"][0]["ts_code"] == "000001.SZ"

    def test_read_csv_max_rows(self, client):
        resp = client.get("/api/cache/file/tushare/daily_test.csv?max_rows=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["truncated"] is True
        assert len(data["content"]) == 2

    def test_read_file_not_found(self, client):
        resp = client.get("/api/cache/file/tushare/nonexistent.json")
        assert resp.status_code == 404

    def test_file_meta(self, client):
        resp = client.get("/api/cache/file/tushare/cal_test.json/meta")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "cal_test.json"
        assert data["category"] == "tushare"
        assert data["extension"] == ".json"
        assert "size_bytes" in data


class TestSearch:
    def test_search(self, client):
        resp = client.get("/api/cache/search?q=cal")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any("cal" in f["name"].lower() for f in data)

    def test_search_in_category(self, client):
        resp = client.get("/api/cache/search?q=daily&category=tushare")
        assert resp.status_code == 200
        data = resp.json()
        assert all(f["category"] == "tushare" for f in data)


class TestAudit:
    def test_audit(self, client):
        resp = client.get("/api/cache/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "items" in data
        assert data["total_files"] >= 4
        # tushare 和 daily 应该 present
        item_map = {i["category"]: i for i in data["items"]}
        assert item_map["tushare"]["status"] == "present"
        assert item_map["daily"]["status"] == "present"


class TestClean:
    def test_cleanable(self, client):
        resp = client.get("/api/cache/cleanable")
        assert resp.status_code == 200
        data = resp.json()
        assert "cleanable_dirs" in data
        assert "total_cleanable_mb" in data
        # pytest_tmp 应该在列表中且存在
        pytest_tmp = next(d for d in data["cleanable_dirs"] if d["name"] == "pytest_tmp")
        assert pytest_tmp["exists"] is True
        assert pytest_tmp["file_count"] == 1

    def test_clean_dry_run(self, client, temp_cache):
        resp = client.post("/api/cache/clean?dry_run=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True
        assert data["files_removed"] == 0  # dry_run 不删除
        # 验证文件还在
        assert (temp_cache / "pytest_tmp" / "temp_file.txt").exists()

    def test_clean_execute(self, client, temp_cache):
        resp = client.post("/api/cache/clean?dry_run=false")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is False
        assert data["files_removed"] >= 1
        assert data["space_freed_mb"] >= 0
        # 验证临时目录已删除
        assert not (temp_cache / "pytest_tmp").exists()
        # 核心数据目录不动
        assert (temp_cache / "tushare").exists()
        assert (temp_cache / "daily").exists()


class TestPathSecurity:
    def test_sibling_prefix_escape_blocked(self, temp_cache):
        """相邻目录即使名称以前缀匹配，也绝不能被视为缓存根目录内部。"""
        from app.cache_manager import CacheManager

        sibling = temp_cache.parent / f"{temp_cache.name}_evil"
        sibling.mkdir()
        (sibling / "secret.txt").write_text("secret", encoding="utf-8")

        manager = CacheManager(cache_root=temp_cache, parquet_root=temp_cache)
        with pytest.raises(ValueError, match="路径越界"):
            manager._safe_resolve(temp_cache, f"../{sibling.name}/secret.txt")

    def test_path_traversal_blocked(self, client):
        """路径穿越攻击应被拒绝"""
        resp = client.get("/api/cache/files/..%2F..%2Fetc")
        # 要么 404（目录不存在），要么 400（路径越界），都不能返回系统文件
        assert resp.status_code in (400, 404)

    def test_read_path_traversal_blocked(self, client):
        resp = client.get("/api/cache/file/tushare/..%2F..%2F..%2FWindows%2Fwin.ini")
        assert resp.status_code in (400, 404)
