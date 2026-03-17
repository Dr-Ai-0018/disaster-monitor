# Disaster Monitor

> 分布式灾害监测与智能分析平台
>
> RSOE 数据抓取 → GEE 遥感影像下载 → GPT-4.1-mini 质量评估 → GPU AI 推理 → Gemini 日报生成

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        us-public-server                             │
│                      (公网 FastAPI 服务器)                           │
│                                                                     │
│  ┌───────────┐   ┌──────────────┐   ┌───────────┐  ┌────────────┐ │
│  │ RSOE      │   │ GEE          │   │ GPT-4.1   │  │ Gemini     │ │
│  │ Spider    │──▶│ Image DL     │──▶│ mini QA   │──▶│ Report Gen │ │
│  └───────────┘   └──────────────┘   └───────────┘  └────────────┘ │
│        │                                    │                       │
│  events table ──▶ event_pool ──▶ task_queue ──▶ products           │
│                                    │                                │
│                          REST API (X-API-Token)                     │
└────────────────────────────────────┼────────────────────────────────┘
                                     │ pull / push
                         ┌───────────▼────────────┐
                         │      gpu-server         │
                         │   (内网 GPU Worker)      │
                         │                         │
                         │  下载影像 → AI 推理(7项) │
                         │  → 回传成品              │
                         └─────────────────────────┘
```

---

## 目录结构

```
disaster-monitor/
├── us-public-server/                # 公网服务器
│   ├── main.py                      # FastAPI 应用入口
│   ├── config.json                  # 调度/存储/质量评估等可视化配置
│   ├── config/
│   │   ├── settings.py              # 全局配置（.env + config.json 合并）
│   │   └── service_account.json     # GEE 服务账号密钥（不入库）
│   ├── api/
│   │   ├── auth.py                  # JWT 登录/刷新/登出
│   │   ├── events.py                # 事件管理（CRUD + 触发处理）
│   │   ├── event_pool.py            # 全局事件池查询
│   │   ├── tasks.py                 # GPU 任务队列（拉取/心跳/回传）
│   │   ├── products.py              # AI 成品池（管理端）
│   │   ├── reports.py               # 日报管理（生成/发布）
│   │   ├── admin.py                 # 系统管理（用户/Token/Settings）
│   │   └── public.py                # 公开接口（无需认证）
│   ├── core/
│   │   ├── rsoe_spider.py           # RSOE-EDIS 数据抓取
│   │   ├── gee_manager.py           # Google Earth Engine 影像下载
│   │   ├── quality_assessor.py      # GPT-4.1-mini 卫星影像质量评估
│   │   ├── pool_manager.py          # 事件状态机（pending→pool→queued）
│   │   ├── event_pool_manager.py    # 全局事件池去重管理
│   │   ├── report_generator.py      # Gemini 日报 + 单事件摘要生成
│   │   └── task_scheduler.py        # APScheduler 定时任务注册
│   ├── models/models.py             # SQLAlchemy ORM 模型
│   ├── schemas/schemas.py           # Pydantic 请求/响应 Schema
│   ├── database/
│   │   ├── schema.sql               # 建表 DDL
│   │   ├── init_db.py               # 数据库初始化
│   │   ├── create_admin.py          # 默认管理员创建
│   │   └── create_token.py          # GPU Worker Token 创建
│   ├── utils/
│   │   ├── logger.py                # 日志初始化（loguru）
│   │   └── auth_utils.py            # JWT 工具函数
│   ├── frontend/
│   │   ├── public.html              # 公开展示页（3-Tab：事件池/日报/AI分析）
│   │   ├── admin.html               # 管理后台
│   │   ├── css/                     # 样式文件
│   │   └── js/
│   │       ├── public.js            # 公开页逻辑
│   │       └── admin.js             # 管理后台逻辑
│   ├── storage/                     # 运行时数据（不入库）
│   │   ├── html/                    # RSOE 原始 HTML 缓存
│   │   ├── json/                    # RSOE 事件 JSON 缓存
│   │   ├── images/                  # GEE 下载的 GeoTIFF 影像
│   │   └── reports/                 # 日报存档
│   ├── test/
│   │   └── end_to_end_full_flow.py  # 全链路端到端测试
│   ├── requirements.txt
│   └── .env.example
│
└── gpu-server/                      # 内网 GPU Worker
    ├── main.py                      # Worker 入口（定时轮询）
    ├── config/
    │   └── settings.py              # Worker 配置（.env）
    ├── core/
    │   ├── api_client.py            # 公网 API 客户端（拉取/心跳/回传）
    │   ├── model_loader.py          # 模型加载（HuggingFace / 本地）
    │   ├── inference_engine.py      # AI 推理引擎（7 项分析任务）
    │   └── task_processor.py        # 任务协调：下载→推理→回传
    ├── utils/
    │   ├── image_processor.py       # GeoTIFF 预处理（归一化/裁剪/增强）
    │   └── logger.py                # 日志初始化
    ├── models/                      # 模型权重目录（不入库）
    ├── requirements.txt
    └── .env.example
```

---

## 数据流水线

```
每日 02:00  RSOE Spider
            └─▶ 抓取灾害事件列表（HTML + JSON）
                └─▶ 写入 events 表 (status=pending)
                    写入 event_pool 表（全局去重）

每小时      Pool Manager（蓄水池状态机）
            ├─▶ pending → pool
            │     补充坐标/详情，提交 GEE 影像下载任务
            │
            ├─▶ GEE 任务监控
            │     COMPLETED → 影像落盘到 storage/images/
            │     全部 FAILED → fail_open 直通，标记 no_imagery
            │
            ├─▶ pool(有影像) → Quality Assessor
            │     GPT-4.1-mini Vision 评估影像可用性（score/pass）
            │
            └─▶ checked → queued
                  质量通过 → 写入 task_queue，等待 GPU 拉取

每小时      GPU Worker（内网轮询）
            └─▶ GET /api/tasks/pull
                └─▶ 下载 GeoTIFF 到本地 temp/
                    └─▶ AI 推理（7 项任务）
                        └─▶ PUT /api/tasks/result 回传
                            └─▶ 写入 products 表 (status=completed)

每日 07:00  Report Generator
            ├─▶ Gemini Flash：为每个新成品生成单事件 AI 摘要
            └─▶ Gemini Pro：综合生成灾害日报 → daily_reports 表
                            管理员审核后手动发布
```

---

## 事件状态流

```
pending ──▶ pool ──▶ checked ──▶ queued ──▶ processing ──▶ completed
                        │
                    (质量不通过)
                        └──▶ failed
```

---

## 公开前端页面

访问 `/`（无需登录），提供三个标签页：

| Tab | 内容 |
|-----|------|
| **EVENT_POOL** | 全局事件池实时列表，支持按灾害类型/国家/严重程度过滤和分页 |
| **AI_REPORTS** | 已发布的 AI 灾害日报，点击查看全文（Markdown 渲染）及分类/国家/严重性统计 |
| **AI_ANALYSIS** | AI 分析成品列表，含灾前/灾后卫星影像对比、AI 推理结果、AI 摘要、原始事件来源链接 |

卫星影像由 `/api/public/image/{uuid}/pre|post` 按需转换 GeoTIFF → PNG 提供。

---

## API 认证

| 调用方 | 认证方式 | 请求头 |
|--------|----------|--------|
| 管理后台 | JWT Bearer Token | `Authorization: Bearer <token>` |
| GPU Worker | 静态 API Token | `X-API-Token: <token>` |
| 公开前端 | 无需认证 | — |

---

## 快速开始

### 公网服务器

```bash
cd us-public-server

python -m venv venv && source venv/bin/activate   # Linux/Mac
# python -m venv venv && venv\Scripts\activate    # Windows

pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填写 RSOE Cookie / GEE / OpenAI / Gemini 密钥

python main.py
# 开发模式：uvicorn main:app --reload --port 8000
```

首次启动会自动完成：
- SQLite 数据库初始化（`database/disaster.db`）
- 创建默认管理员账户（`SEED_ADMIN_*` 环境变量控制）
- 创建默认 GPU Worker API Token（`SEED_GPU_TOKEN_*` 控制）

| 页面 | 地址 |
|------|------|
| 公开展示页 | `http://localhost:8000/` |
| 管理后台 | `http://localhost:8000/admin` |
| API 文档 | `http://localhost:8000/docs` |
| 健康检查 | `http://localhost:8000/health` |

### GPU Worker

```bash
cd gpu-server

python -m venv venv && source venv/bin/activate

# 按 CUDA 版本安装 PyTorch（示例：CUDA 11.8）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt

cp .env.example .env
# 设置 API_BASE_URL 和 API_TOKEN

# 将模型文件放入 models/disaster_model/（HuggingFace 格式）

python main.py
```

---

## 必需环境变量

### us-public-server `.env`

```ini
# 安全密钥（生产环境必须替换）
SECRET_KEY=<openssl rand -hex 32>
JWT_SECRET_KEY=<openssl rand -hex 32>

# RSOE 认证 Cookie（从浏览器开发者工具 Application > Cookies 复制）
SESSION_EDIS_WEB=...
ARR_AFFINITY=...
ARR_AFFINITY_SAME_SITE=...

# Google Earth Engine
GEE_PROJECT_ID=your-gee-project-id
GEE_SERVICE_ACCOUNT_EMAIL=your-sa@project.iam.gserviceaccount.com
GEE_SERVICE_ACCOUNT_PATH=config/service_account.json

# OpenAI（影像质量评估，支持中转 Base URL）
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini

# Google Gemini（日报生成）
GEMINI_API_KEY=...
GEMINI_FLASH_MODEL=gemini-2.0-flash
GEMINI_PRO_MODEL=gemini-2.5-pro-preview-03-25

# 默认管理员（首次启动写入数据库后，可从 .env 删除密码）
SEED_ADMIN_USERNAME=admin
SEED_ADMIN_PASSWORD=change-me
```

### gpu-server `.env`

```ini
API_BASE_URL=https://your-public-server.com
API_TOKEN=<从公网服务器 SEED_GPU_TOKEN_VALUE 获取>
MODEL_PATH=models/disaster_model
CUDA_VISIBLE_DEVICES=0
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| Web 框架 | FastAPI + Uvicorn |
| 数据库 | SQLite（WAL 模式，可迁移 PostgreSQL） |
| 定时任务 | APScheduler |
| 数据抓取 | Requests + BeautifulSoup4 |
| 遥感影像 | Google Earth Engine Python API + Rasterio + Pillow |
| 影像质量评估 | OpenAI GPT-4.1-mini Vision |
| 日报 / 摘要生成 | Google Gemini Flash + Gemini Pro |
| AI 推理 | PyTorch + HuggingFace Transformers |
| 认证 | JWT (python-jose) + bcrypt |
| 前端 | TailwindCSS + Lucide Icons（CDN，无构建步骤） |

---

## 可视化配置（config.json）

`config.json` 控制不需要重启服务的运行参数，可通过管理后台 Settings 页面在线修改：

| 配置块 | 关键参数 |
|--------|----------|
| `rsoe` | 抓取 URL、分页数、请求延迟 |
| `gee` | 影像搜索时间窗口、云量阈值、分辨率 |
| `scheduler` | 各定时任务的 cron 表达式 |
| `task_queue` | 锁超时、心跳间隔、单次最大拉取数 |
| `quality_assessment` | 评估模型、置信阈值、fail_open 开关 |
| `report_generation` | 报告语言、摘要长度、生成模型 |
| `storage` | 各类数据的本地存储路径 |

---

## 运行测试

```bash
cd us-public-server

# 确保服务已在 8000 端口运行
python test/end_to_end_full_flow.py
```

测试覆盖：公开接口、JWT 认证、管理员操作、Settings 读写验证、事件全流程、定时任务触发、GPU 任务队列（拉取/心跳/回传）、成品查询、日报生成与发布、完整 GPU Worker 模拟流程。

---

## 开发约定

- 任务队列锁机制：`locked_by` + `locked_until`，Worker 需定期心跳续租，超时自动释放
- GEE 认证仅在应用启动时初始化（`lifespan`），不在定时任务内重复认证
- 结果回传接口幂等：`PUT /api/tasks/result` 使用 UPSERT，支持 Worker 重试
- SQLite 开启 WAL 模式（`PRAGMA journal_mode=WAL`）+ `connect_args timeout=30`，减少写锁竞争
- 日志使用 loguru，关键状态变更必须记录
