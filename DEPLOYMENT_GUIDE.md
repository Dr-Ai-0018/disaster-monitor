# Disaster Monitor — 部署指南

> 适用版本：v1.0.x
> 架构：us-public-server（FastAPI 公网服务） + gpu-server（内网 GPU 推理节点）

---

## 目录

1. [系统要求](#1-系统要求)
2. [快速启动（本地开发）](#2-快速启动本地开发)
3. [环境变量配置（.env）](#3-环境变量配置env)
4. [config.json 参数说明](#4-configjson-参数说明)
5. [Google Earth Engine 配置](#5-google-earth-engine-配置)
6. [RSOE Cookie 获取](#6-rsoe-cookie-获取)
7. [GPU Server 部署](#7-gpu-server-部署)
8. [生产环境部署（Linux + systemd）](#8-生产环境部署linux--systemd)
9. [数据库维护](#9-数据库维护)
10. [管理员后台使用](#10-管理员后台使用)
11. [常见问题排查](#11-常见问题排查)

---

## 1. 系统要求

### us-public-server（公网节点）

| 项目 | 最低要求 | 推荐 |
|------|---------|------|
| Python | 3.10+ | 3.11 |
| 内存 | 1 GB | 2 GB |
| 磁盘 | 20 GB（卫星图像存储） | 100 GB+ |
| 网络 | 公网 IP | 独立服务器 |
| 操作系统 | Windows 10 / Ubuntu 20.04+ | Ubuntu 22.04 |

### gpu-server（推理节点，内网）

| 项目 | 要求 |
|------|------|
| Python | 3.10+ |
| GPU | NVIDIA，≥ 8 GB VRAM |
| CUDA | 11.8 / 12.x |
| 网络 | 能访问 us-public-server |

---

## 2. 快速启动（本地开发）

### 克隆项目

```bash
git clone <repo-url>
cd disaster-monitor
```

### 配置虚拟环境

```bash
# 创建并激活虚拟环境（Windows）
python -m venv venv
venv\Scripts\activate

# Ubuntu/macOS
python3 -m venv venv
source venv/bin/activate
```

### 安装依赖

```bash
cd us-public-server
pip install -r requirements.txt
```

### 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写必要的 API Keys 和 Cookie（见第 3 节）
```

### 初始化并启动

```bash
# 开发模式（支持热重载，不建议用于 E2E 测试）
uvicorn main:app --host 0.0.0.0 --port 2335 --reload

# 稳定模式（推荐用于测试和生产）
uvicorn main:app --host 0.0.0.0 --port 2335
```

启动后访问：
- **管理后台**：`http://localhost:2335/admin`
- **公开展示页**：`http://localhost:2335/`
- **API 文档**：`http://localhost:2335/docs`

---

## 3. 环境变量配置（.env）

> 所有变量均可通过管理后台 **Settings** 页面在线修改，无需重启即可生效（端口/DB路径除外）。

### 3.1 应用基础

```env
APP_NAME=DisasterMonitoringSystem
APP_ENV=development          # development | production
DEBUG=false
SECRET_KEY=<随机32字节hex>    # openssl rand -hex 32
```

### 3.2 数据库

```env
DATABASE_URL=sqlite:///database/disaster.db
```

> 生产环境可改为 PostgreSQL：`postgresql://user:pass@host/db`

### 3.3 RSOE Cookie（必填）

从浏览器 DevTools 的 `Application → Cookies → https://rsoe-edis.org` 获取（见第 6 节）。

```env
SESSION_EDIS_WEB=<值>
ARR_AFFINITY=<值>
ARR_AFFINITY_SAME_SITE=<值>
_GA=<值>
__GADS=<值>
__GPI=<值>
__EOI=<值>
_GA_KHD7YP5VHW=<值>
```

### 3.4 Google Earth Engine（必填）

```env
GEE_PROJECT_ID=your-gcp-project-id
GEE_SERVICE_ACCOUNT_EMAIL=your-sa@project.iam.gserviceaccount.com
GEE_SERVICE_ACCOUNT_PATH=config/service_account.json
```

### 3.5 OpenAI（图像质量评估）

```env
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1    # 支持中转站
OPENAI_MODEL=gpt-4.1-mini
```

### 3.6 Google Gemini（日报生成）

```env
GEMINI_API_KEY=sk-...                        # 支持 sk- 前缀中转站
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
GEMINI_FLASH_MODEL=gemini-2.0-flash
GEMINI_PRO_MODEL=gemini-2.5-pro-preview-03-25
```

> **中转站说明**：API Key 以 `sk-` 开头时，系统自动使用 `Authorization: Bearer <key>` 鉴权方式。

### 3.7 JWT 认证

```env
JWT_SECRET_KEY=<随机32字节hex>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440         # 24小时
```

### 3.8 初始管理员 & GPU Token

```env
SEED_ADMIN_USERNAME=your-admin-name
SEED_ADMIN_PASSWORD=your-strong-password
SEED_ADMIN_EMAIL=admin@example.com
SEED_GPU_TOKEN_VALUE=<随机长字符串>           # GPU 节点的 API Token
```

> 首次启动自动创建，后续修改需要在 **Settings → API Tokens** 中操作。

### 3.9 服务器

```env
SERVER_HOST=0.0.0.0
SERVER_PORT=2335
CORS_ORIGINS=https://your-domain.com,http://localhost:3000
REQUEST_TIMEOUT=30
REQUEST_DELAY=1.5
LOG_LEVEL=INFO
LOG_FILE=logs/disaster.log
```

---

## 4. config.json 参数说明

> 也可在管理后台 **Settings** 页面直接修改。

### 4.1 GEE 卫星图像

```json
"gee": {
  "cloud_threshold": 20,          // 云量过滤阈值（%）
  "time_window_days_before": 30,  // 灾前时间窗口（天）
  "time_window_days_after": 30,   // 灾后时间窗口（天）
  "scale": 10,                    // 分辨率（米/像素），Sentinel-2 最优为 10
  "max_concurrent_tasks": 5       // 最大并发下载任务数
}
```

### 4.2 质量评估

```json
"quality_assessment": {
  "enabled": true,
  "cloud_coverage_threshold": 30,  // 超过此云量直接失败
  "pass_score_threshold": 60,      // GPT 评分低于此值失败
  "fail_open": true,               // true = 评分失败也强制放行（开发推荐 true）
  "max_retries": 2
}
```

> **生产环境**建议将 `fail_open` 设为 `false` 以保证图像质量。

### 4.3 任务调度

```json
"scheduler": {
  "fetch_rsoe_data":      { "enabled": true },  // 每日 02:00 抓取灾难数据
  "process_pool":         { "enabled": true },  // 每小时处理蓄水池
  "generate_daily_report":{ "enabled": true }   // 每日 07:00 生成日报
}
```

### 4.4 日报生成

```json
"report_generation": {
  "top_events_count": 5,
  "max_summary_length": 500
}
```

---

## 5. Google Earth Engine 配置

### 步骤一：创建 GCP 项目并启用 GEE API

1. 访问 [Google Cloud Console](https://console.cloud.google.com)
2. 创建或选择项目，记录 **Project ID**
3. 启用 **Earth Engine API**

### 步骤二：创建服务账号

```bash
# 创建服务账号
gcloud iam service-accounts create gee-worker \
  --display-name="GEE Worker"

# 导出密钥（JSON 格式）
gcloud iam service-accounts keys create config/service_account.json \
  --iam-account=gee-worker@YOUR_PROJECT.iam.gserviceaccount.com
```

### 步骤三：在 EE 注册服务账号

1. 访问 [Earth Engine Code Editor](https://code.earthengine.google.com/)
2. 注册服务账号邮箱并申请访问权限

### 步骤四：填写 .env

```env
GEE_PROJECT_ID=your-project-id
GEE_SERVICE_ACCOUNT_EMAIL=gee-worker@your-project.iam.gserviceaccount.com
GEE_SERVICE_ACCOUNT_PATH=config/service_account.json
```

---

## 6. RSOE Cookie 获取

RSOE 事件列表需要有效的浏览器 Cookie 才能抓取。Cookie **有效期约 7-30 天**，过期后需要更新。

### 获取步骤

1. 用浏览器访问 [https://rsoe-edis.org/eventList](https://rsoe-edis.org/eventList)
2. 按 `F12` 打开开发者工具 → `Application`（或 `Storage`）→ `Cookies`
3. 选择 `https://rsoe-edis.org`
4. 复制以下 Cookie 的值，粘贴到 `.env` 或管理后台 **Settings → RSOE_COOKIES**：
   - `session_edis_web`
   - `ARRAffinity` → 对应 `ARR_AFFINITY`
   - `ARRAffinitySameSite` → 对应 `ARR_AFFINITY_SAME_SITE`
   - `_ga`, `__gads`, `__gpi`, `__eoi`, `_ga_KHD7YP5VHW`

> **提示**：Cookie 更新不需要重启服务，在管理后台 Settings 页面修改后立即生效。

---

## 7. GPU Server 部署

GPU 节点是独立进程，通过 HTTP API 与 us-public-server 通信。

### 配置

```bash
cd gpu-server
cp .env.example .env
```

关键配置项：

```env
API_BASE_URL=http://your-public-server:2335    # us-public-server 地址
API_TOKEN=<与 SEED_GPU_TOKEN_VALUE 相同的值>
WORKER_ID=gpu-node-01
CUDA_DEVICE=cuda:0
MODEL_PATH=/path/to/model
POLL_INTERVAL_SECONDS=3600    # 每小时拉取一次任务
TASK_BATCH_SIZE=5
```

### 启动

```bash
pip install -r requirements.txt
python main.py
```

---

## 8. 生产环境部署（Linux + systemd）

### 8.1 安装依赖

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv nginx
```

### 8.2 创建系统用户

```bash
sudo useradd -m -s /bin/bash disaster
sudo su - disaster
```

### 8.3 部署代码

```bash
git clone <repo-url> /home/disaster/disaster-monitor
cd /home/disaster/disaster-monitor/us-public-server
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填写生产配置
nano .env
```

### 8.4 systemd 服务文件

```ini
# /etc/systemd/system/disaster-monitor.service
[Unit]
Description=Disaster Monitor Public Server
After=network.target

[Service]
User=disaster
WorkingDirectory=/home/disaster/disaster-monitor/us-public-server
ExecStart=/home/disaster/disaster-monitor/us-public-server/venv/bin/uvicorn \
    main:app --host 127.0.0.1 --port 2335 --workers 2
Restart=on-failure
RestartSec=5
Environment="APP_ENV=production"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable disaster-monitor
sudo systemctl start disaster-monitor
sudo systemctl status disaster-monitor
```

### 8.5 Nginx 反向代理

```nginx
# /etc/nginx/sites-available/disaster-monitor
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # 卫星图像文件较大，增加超时
    proxy_read_timeout 300s;
    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:2335;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/disaster-monitor /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 8.6 SSL 证书（Let's Encrypt）

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 9. 数据库维护

### 备份

```bash
# SQLite 备份
cp database/disaster.db database/disaster.db.$(date +%Y%m%d)

# 或使用 sqlite3
sqlite3 database/disaster.db ".backup 'backup/disaster_$(date +%Y%m%d).db'"
```

### 清理旧数据

系统每日自动清理 90 天前的卫星图像（可在 config.json `storage.cleanup_enabled` 控制）。

手动清理：

```bash
# 清理 storage/images 下 30 天前的目录
find storage/images -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
```

### 重置数据库（开发用）

```bash
rm database/disaster.db
# 重启服务，自动重新初始化
```

---

## 10. 管理员后台使用

### 访问地址

`http://your-server:2335/admin`

### 功能说明

| 页面 | 功能 |
|------|------|
| **Dashboard** | 系统状态总览（GEE连接状态、调度器状态、事件/任务/产品数量） |
| **Quick Actions** | 手动触发：RSOE抓取、蓄水池处理、生成日报、释放锁 |
| **Events** | 查看事件池，手动推进单个事件 |
| **Products** | 查看 GPU 推理完成的产品 |
| **Reports** | 查看/生成每日灾害报告 |
| **Tokens** | 管理 GPU Worker API Token |
| **Settings** | **在线修改所有配置**（API Key、Cookie、GEE 参数等） |

### Settings 页面字段说明

- 🔒 **密码型字段**（API Key、Cookie）：显示脱敏值，修改时直接输入新值，留空表示不修改
- 📝 **普通字段**：直接显示原始值，修改后点击对应分组的 `SAVE` 按钮
- ⚡ **热更新**：所有修改立即写入 `.env` / `config.json` 并更新内存，无需重启（除端口/DB路径）

---

## 11. 常见问题排查

### Q: GEE 初始化失败

```
❌ GEE 初始化失败: ...credentials...
```

**检查：**
1. `config/service_account.json` 文件是否存在且格式正确
2. 服务账号邮箱是否已在 Earth Engine 注册
3. `GEE_PROJECT_ID` 是否与服务账号所属项目一致

### Q: RSOE 抓取返回 0 事件

**检查：**
1. Cookie 是否过期（从浏览器重新获取）
2. 服务器 IP 是否被 RSOE 封禁（尝试更换 IP 或使用代理）
3. 查看日志：`logs/disaster.log`

### Q: GPU Worker 401 Unauthorized

**检查：**
1. `gpu-server/.env` 中 `API_TOKEN` 是否与 `us-public-server/.env` 中 `SEED_GPU_TOKEN_VALUE` 一致
2. Token 是否在管理后台被禁用

### Q: SQLite database is locked

**原因：** 多个并发写操作冲突（常见于 `--reload` 热重载期间）

**解决：**
- 不使用 `--reload` 模式，改用 `uvicorn main:app --port 2335`
- 或升级为 PostgreSQL

### Q: Gemini API 调用失败

```
Gemini API 错误 401: ...
```

**检查：**
1. `GEMINI_API_KEY` 是否正确
2. 中转站 URL 格式：`https://your-relay.com/v1beta`（末尾不带 `/`）
3. 中转站是否支持 `sk-` 前缀的 Bearer 认证

### Q: 日报生成但内容为 fallback（无 Gemini 内容）

**检查：**
1. `GEMINI_API_KEY` 是否配置
2. 模型名称是否正确（`GEMINI_FLASH_MODEL`、`GEMINI_PRO_MODEL`）
3. 查看日志中 `Gemini Pro 调用失败` 的具体错误

### 查看实时日志

```bash
# Linux
tail -f logs/disaster.log

# systemd journal
journalctl -u disaster-monitor -f
```

---

## 附录：目录结构

```
us-public-server/
├── api/                # FastAPI 路由
│   ├── admin.py        # 管理接口（含 Settings GET/PUT）
│   ├── tasks.py        # GPU Worker 任务接口
│   ├── events.py       # 事件接口
│   ├── products.py     # 产品接口
│   └── reports.py      # 日报接口
├── config/
│   ├── settings.py     # 配置加载
│   └── service_account.json  # GEE 服务账号密钥（自行创建）
├── core/
│   ├── rsoe_spider.py  # RSOE 数据抓取
│   ├── gee_manager.py  # 卫星图像下载
│   ├── quality_assessor.py   # 图像质量评估（GPT）
│   ├── pool_manager.py # 事件状态流转
│   └── report_generator.py   # 日报生成（Gemini）
├── database/
│   ├── schema.sql      # 数据库表结构
│   └── disaster.db     # SQLite 数据库（运行时生成）
├── frontend/
│   ├── admin.html      # 管理后台
│   ├── public.html     # 公开展示页
│   ├── js/admin.js     # 管理后台逻辑
│   └── css/            # 样式文件
├── storage/            # 卫星图像存储（运行时生成）
├── logs/               # 日志文件（运行时生成）
├── utils/
│   ├── auth.py         # JWT + API Token 认证
│   └── config_manager.py     # .env / config.json 读写工具
├── .env                # 环境变量（不提交 git）
├── config.json         # 运行参数配置
└── main.py             # 应用入口
```

---

*文档版本：v1.0 · 2026-03-14*
