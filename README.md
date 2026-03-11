# 灾害监测与分析系统

> 分布式灾害监测与智能分析平台：RSOE 数据抓取 → 遥感影像下载 → AI 推理 → 智能日报生成

---

## 📁 项目结构

```
disaster-monitor/
├── us-public-server/     # 美国公网服务器（FastAPI）
│   ├── main.py           # 应用入口
│   ├── config/           # 配置管理
│   ├── database/         # 数据库 Schema + 初始化脚本
│   ├── models/           # SQLAlchemy ORM 模型
│   ├── schemas/          # Pydantic 请求/响应模型
│   ├── core/             # 核心业务逻辑
│   │   ├── rsoe_spider.py       # RSOE 数据抓取
│   │   ├── gee_manager.py       # GEE 影像下载
│   │   ├── quality_assessor.py  # GPT-4.1-mini 质量评估
│   │   ├── pool_manager.py      # 蓄水池状态机
│   │   ├── task_scheduler.py    # APScheduler 定时任务
│   │   └── report_generator.py  # Gemini 日报生成
│   ├── api/              # RESTful API 路由
│   │   ├── auth.py       # JWT 认证
│   │   ├── events.py     # 事件管理
│   │   ├── tasks.py      # GPU 任务队列
│   │   ├── products.py   # 成品池
│   │   ├── reports.py    # 日报管理
│   │   └── admin.py      # 系统管理
│   ├── utils/            # 工具模块
│   ├── frontend/         # Vue3 管理后台
│   └── storage/          # 数据存储（影像/HTML/JSON/报告）
│
└── gpu-server/           # 内网 GPU 服务器（Worker）
    ├── main.py           # Worker 入口
    ├── config/           # 配置管理
    ├── core/
    │   ├── api_client.py        # 公网 API 客户端
    │   ├── model_loader.py      # 模型加载器
    │   ├── inference_engine.py  # 推理引擎（7 任务）
    │   └── task_processor.py    # 任务处理协调器
    ├── utils/            # 日志 + 影像处理工具
    ├── models/           # 模型文件目录
    └── temp/             # 临时文件
```

---

## 🚀 快速开始

### 一、美国公网服务器

```bash
cd us-public-server

# 1. 创建虚拟环境
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Linux/Mac

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
copy .env.example .env
# 编辑 .env，填写 RSOE Cookie、GEE、OpenAI、Gemini 密钥

# 4. 初始化数据库
python database/init_db.py

# 5. 创建管理员账户
python database/create_admin.py

# 6. 创建 GPU 服务器 API Token（保存输出的 Token）
python database/create_token.py

# 7. 启动服务
python main.py
# 或开发模式：uvicorn main:app --reload --port 8000
```

访问：
- **管理后台**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

---

### 二、内网 GPU 服务器

```bash
cd gpu-server

# 1. 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 2. 安装 PyTorch（根据 CUDA 版本）
pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu118

# 3. 安装其他依赖
pip install -r requirements.txt

# 4. 配置环境变量
copy .env.example .env
# 设置 API_BASE_URL 和 API_TOKEN（从公网服务器获取）

# 5. 放置模型文件
# 将模型放到 models/disaster_model/ 目录
# 支持 HuggingFace 格式（含 config.json + model.safetensors）

# 6. 启动 Worker
python main.py
```

---

## 🔄 工作流程

```
1. 每日 02:00  抓取 RSOE 事件列表 → 写入 events 表（status=pending）
2. 每小时      蓄水池处理：
               pending → pool（获取坐标）
               pool → 提交 GEE 下载（灾前/灾后影像）
               pool(双影像) → GPT-4.1-mini 质量评估 → checked
               checked → 加入任务队列 → queued
3. GPU Worker  每小时轮询：
               拉取任务 → 下载影像 → 7 项 AI 推理 → 回传结果
               → 写入成品池（status=completed）
4. 每日 07:00  Gemini Flash 生成单事件摘要
               Gemini Pro 综合生成灾害日报 → 保存至 daily_reports
```

---

## 📊 事件状态流

```
pending → pool → checked → queued → processing → completed
                                                       ↑
                              GPU Worker 回传结果 ──────┘
```

---

## 🔐 认证方式

| 角色       | 方式             | 请求头                          |
|----------|----------------|-------------------------------|
| 管理员      | JWT Bearer     | `Authorization: Bearer <token>` |
| GPU Worker | API Token      | `X-API-Token: <token>`          |

---

## ⚙️ 必需配置项

**公网服务器 (.env)**：
```
RSOE_SESSION_EDIS_WEB=...   # 从浏览器 Cookie 获取
GEE_PROJECT_ID=...          # Google Earth Engine 项目 ID
GEE_SERVICE_ACCOUNT_EMAIL=...
GEE_SERVICE_ACCOUNT_PATH=config/service_account.json
OPENAI_API_KEY=...          # 影像质量评估
GEMINI_API_KEY=...          # 日报生成
SECRET_KEY=...              # 随机 32 字节 hex
JWT_SECRET_KEY=...          # 随机 32 字节 hex
```

**GPU 服务器 (.env)**：
```
API_BASE_URL=https://your-server.com  # 或 http://127.0.0.1:8000（开发）
API_TOKEN=...                         # 从公网服务器 create_token.py 获取
MODEL_PATH=models/disaster_model      # 本地模型路径
CUDA_VISIBLE_DEVICES=0
```

---

## 🛠️ 技术栈

| 层         | 技术                                              |
|-----------|--------------------------------------------------|
| Web 框架   | FastAPI + Uvicorn                                |
| 数据库     | SQLite（可迁移 PostgreSQL）                       |
| 定时任务   | APScheduler                                      |
| 数据抓取   | Requests + BeautifulSoup4                        |
| 遥感影像   | Google Earth Engine API + Rasterio               |
| 质量评估   | OpenAI GPT-4.1-mini Vision                       |
| 日报生成   | Google Gemini Flash + Pro                        |
| AI 推理    | PyTorch + HuggingFace Transformers               |
| 前端       | Vue 3 + TailwindCSS（CDN，无需构建）              |
| 认证       | JWT (python-jose) + bcrypt                       |

---

## 📝 开发规范

- 日志使用 **loguru**，关键操作必须记录
- 任务队列必须实现**锁机制**（`locked_by` + `locked_until`）
- 结果回传接口必须**幂等**（PUT + UPSERT）
- GEE 认证**仅在应用启动时初始化**，不在定时任务中裸跑
