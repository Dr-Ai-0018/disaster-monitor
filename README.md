# Disaster Monitor

> 灾害监测与智能分析平台
>
> RSOE 抓取 → GEE 遥感影像下载 → AI 质检 → Latest Model Open API 推理 → Gemini 摘要 / 日报

---

## 当前架构

项目当前的正式推理主链路已经统一为 `Latest Model Open API`。

- `us-public-server` 负责事件管理、影像下载、质量评估、任务编排、成品写入、摘要生成、日报生成
- 遥感推理通过 `LATEST_MODEL_ENDPOINT` 指向的远端 API 完成
- 历史上的“内网 GPU Worker 拉任务 / 心跳 / 回传结果”方案已废弃，不再作为正式主链路

---

## 架构概览

```text
RSOE Spider
  -> events / event_pool
  -> GEE imagery download
  -> OpenAI quality assessment
  -> task_queue
  -> Latest Model Open API
  -> products
  -> Gemini summaries / daily reports
```

---

## 目录结构

```text
disaster-monitor/
├── README.md
└── us-public-server/
    ├── main.py
    ├── config.json
    ├── requirements.txt
    ├── api/
    │   ├── admin.py
    │   ├── auth.py
    │   ├── event_pool.py
    │   ├── events.py
    │   ├── products.py
    │   ├── public.py
    │   └── reports.py
    ├── core/
    │   ├── event_pool_manager.py
    │   ├── gee_manager.py
    │   ├── latest_model_client.py
    │   ├── pool_manager.py
    │   ├── quality_assessor.py
    │   ├── report_generator.py
    │   ├── rsoe_spider.py
    │   └── task_scheduler.py
    ├── database/
    ├── frontend/
    ├── models/
    ├── schemas/
    ├── storage/
    ├── tests/
    └── utils/
```

---

## 核心流程

```text
pending
  -> pool
  -> checked
  -> queued
  -> processing
  -> completed

如果质量评估失败或远端推理失败：
  -> failed
```

详细说明：

1. `RSOE` 抓取事件并写入 `events`
2. 详情补抓器扫描 `details_json` 为空的新事件，并按 `source_url` 补抓完整详情
3. `GEE` 下载灾前 / 灾后影像
4. `QualityAssessor` 用 AI 对影像可用性做判断
5. `PoolManager` 把可推理事件写入 `task_queue`
6. `LatestModelClient` 调用远端推理 API 并轮询结果
7. 推理结果写入 `products`
8. `ReportGenerator` 生成单事件摘要和日报

---

## 工作流与测试台

管理后台 `/admin` 里提供：

- 工作流：选择事件、选择影像、触发推理、查看结果
- Workflow Lab：单独测试
  - AI 质检
  - 指定影像推理
  - 单事件摘要
  - 日报生成
  - 状态快照

---

## 快速开始

```bash
cd us-public-server
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
```

至少需要配置：

```ini
SECRET_KEY=...
JWT_SECRET_KEY=...

OPENAI_API_KEY=...
GEMINI_API_KEY=...

LATEST_MODEL_ENDPOINT=https://your-latest-model-api.example.com
LATEST_MODEL_API_KEY=...

GEE_PROJECT_ID=...
GEE_SERVICE_ACCOUNT_EMAIL=...
GEE_SERVICE_ACCOUNT_PATH=config/service_account.json
```

启动服务：

```bash
.venv/bin/python main.py
```

或：

```bash
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 2335
```

---

## 公开接口

公开页面 `/` 提供：

- 事件池
- 已发布日报
- AI 分析成品

公开影像接口：

- `/api/public/image/{uuid}/pre`
- `/api/public/image/{uuid}/post`
- `/api/public/image/{uuid}/pre/enhanced`
- `/api/public/image/{uuid}/post/enhanced`

---

## 技术栈

| 模块 | 技术 |
|------|------|
| Web | FastAPI + Uvicorn |
| 数据库 | SQLite + SQLAlchemy |
| 抓取 | Requests + BeautifulSoup4 |
| 遥感影像 | Google Earth Engine + Pillow + numpy |
| 影像质检 | OpenAI |
| 推理 | Latest Model Open API |
| 摘要 / 日报 | Gemini |
| 调度 | APScheduler |
| 前端 | TailwindCSS + 原生 JS |

---

## 说明

- 历史文档中如果仍出现 `/api/tasks/*`、`GPU Worker`、`heartbeat/pull/result` 等描述，它们属于旧方案，正在迁移清理。
- 当前应以 `core/latest_model_client.py` 和 `core/pool_manager.py` 的 API 直连推理链路为准。
