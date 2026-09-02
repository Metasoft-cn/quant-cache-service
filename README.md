# Quant Cache Service

独立的量化数据缓存 API 服务。将原量化系统中的缓存数据浏览、检索、读取、审计能力抽离为独立服务，通过 HTTP API 对外提供。

## 特性

- **缓存总览** — 总大小、文件数、按类别（tushare/daily/factor_cache 等）分组统计
- **文件浏览** — 按类别列出文件，支持分页、关键词过滤
- **全局搜索** — 跨类别搜索缓存文件
- **格式解析** — 自动识别并读取 JSON / CSV / Parquet / PKL / TXT / LOG
- **大文件预览** — 超过行数限制自动截断，标记 `truncated`
- **健康审计** — 缓存目录存在性、可写性、数据类别覆盖率检查
- **安全清理** — 只清理白名单临时目录，核心数据不动；默认 dry-run
- **路径安全** — 所有路径操作限制在缓存根目录内，防路径穿越
- **可选鉴权** — 通过 `API_TOKEN` 环境变量启用 API Key 鉴权

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置缓存路径

复制 `.env.example` 为 `.env`，修改 `CACHE_ROOT` 指向你的缓存目录：

```bash
cp .env.example .env
```

```env
CACHE_ROOT=D:\path\to\your\cache
```

### 3. 启动服务

```bash
# 方式一
python -m app.main

# 方式二
uvicorn app.main:app --reload --port 8100

# Windows 一键启动
start.bat
```

服务启动后访问 `http://localhost:8100/docs` 查看交互式 API 文档。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 服务基本信息 |
| GET | `/api/health` | 服务健康检查 |
| GET | `/api/cache/stats` | 缓存总统计 |
| GET | `/api/cache/categories` | 列出所有缓存类别 |
| GET | `/api/cache/files/{category}` | 列出某类别下的文件（支持分页/过滤） |
| GET | `/api/cache/file/{category}/{filename}` | 读取文件内容（自动格式解析） |
| GET | `/api/cache/file/{category}/{filename}/meta` | 获取文件元信息 |
| GET | `/api/cache/search?q=xxx` | 全局搜索缓存文件 |
| GET | `/api/cache/audit` | 缓存完整性审计（数据类别覆盖率） |
| GET | `/api/cache/cleanable` | 列出可清理的临时目录 |
| POST | `/api/cache/clean?dry_run=true` | 清理临时目录（默认试运行） |

### 示例

```bash
# 查看缓存总览
curl http://localhost:8100/api/cache/stats

# 列出 tushare 类别下的文件
curl "http://localhost:8100/api/cache/files/tushare?limit=50"

# 读取某个 JSON 缓存文件
curl http://localhost:8100/api/cache/file/tushare/cal_20200101_20260820.json

# 读取 CSV（自动解析为行对象数组）
curl "http://localhost:8100/api/cache/file/daily/000001.SZ.csv?max_rows=100"

# 搜索包含 "factor" 的文件
curl "http://localhost:8100/api/cache/search?q=factor"

# 试运行清理（不实际删除）
curl -X POST "http://localhost:8100/api/cache/clean?dry_run=true"

# 执行清理
curl -X POST "http://localhost:8100/api/cache/clean?dry_run=false"
```

## 项目结构

```
quant-cache-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口 + 路由装配
│   ├── config.py            # 配置管理（环境变量）
│   ├── models.py            # Pydantic 响应模型
│   ├── cache_manager.py     # 缓存管理核心逻辑
│   └── routers/
│       ├── __init__.py
│       ├── browse.py        # 浏览/统计/搜索
│       ├── files.py         # 文件读取
│       ├── health.py        # 健康检查/审计
│       └── manage.py        # 清理/管理
├── data/                    # 数据目录（可选，默认不入库）
├── tests/
│   └── test_api.py          # API 集成测试
├── .env.example             # 环境变量模板
├── .gitignore
├── requirements.txt
├── start.bat                # Windows 一键启动
└── README.md
```

## 设计原则

1. **数据与代码分离** — 缓存数据不入库，通过 `CACHE_ROOT` 环境变量指向外部存储
2. **只读优先** — 默认所有操作只读；写操作（清理）需显式 `dry_run=false`
3. **安全边界** — 路径穿越防护、可清理目录白名单、单文件大小限制
4. **零硬编码** — 所有路径和配置通过环境变量注入
5. **大文件友好** — 自动截断预览，不一次性加载超大文件到内存

## 与原量化系统的关系

本服务是从 `quant_system_研究原型` 中抽离的独立缓存访问层。原项目的 `api/routers/data_services.py` 提供了部分数据访问能力，本服务将其通用化为：
- 不依赖原项目的业务模块（tushare_provider、factor 计算等）
- 直接操作缓存文件系统，纯文件级访问
- 可独立部署，供多个消费方使用

## License

MIT
