# 灾害监测系统 - 部署指南

## 📋 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端界面层                              │
├────────────────────┬────────────────────────────────────────┤
│   公开展示页面     │        管理后台                         │
│  (无需认证)        │      (JWT认证)                          │
│  - 实时事件展示    │  - Dashboard                            │
│  - 数据统计        │  - 事件管理                             │
│  - 过滤搜索        │  - 成品池                               │
│                    │  - 日报管理                             │
│                    │  - 系统管理                             │
└────────────────────┴────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    API 接口层 (FastAPI)                      │
├─────────────────────────────────────────────────────────────┤
│  /api/pool/*     - 全局事件池API (公开)                     │
│  /api/events/*   - 事件管理API (JWT)                        │
│  /api/products/* - 成品池API (JWT)                          │
│  /api/reports/*  - 日报API (JWT)                            │
│  /api/tasks/*    - GPU任务队列API (API Token)              │
│  /api/admin/*    - 系统管理API (JWT)                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    业务逻辑层                                │
├─────────────────────────────────────────────────────────────┤
│  EventPoolManager  - 全局事件池管理（去重）                 │
│  PoolManager       - 蓄水池状态机                           │
│  RsoeSpider        - RSOE数据抓取                           │
│  GeeManager        - Google Earth Engine影像下载            │
│  QualityAssessor   - GPT-4o影像质量评估                     │
│  ReportGenerator   - Gemini日报生成                         │
│  TaskScheduler     - APScheduler定时任务                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    数据存储层                                │
├─────────────────────────────────────────────────────────────┤
│  events          - 处理中的事件                             │
│  event_pool      - 全局去重事件池 ⭐ NEW                    │
│  gee_tasks       - GEE下载任务                              │
│  task_queue      - GPU推理队列                              │
│  products        - 完成的成品                               │
│  daily_reports   - 日报存档                                 │
│  admin_users     - 管理员账户                               │
│  api_tokens      - API令牌                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速部署

### 1. 环境准备

**系统要求**
- Python 3.9+
- SQLite 3.x
- 至少 2GB RAM
- 50GB+ 存储空间

**依赖安装**
```bash
cd us-public-server
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

---

### 2. 配置环境变量

复制配置模板：
```bash
cp .env.example .env
```

编辑 `.env` 文件，配置必需项：

```env
# 应用配置
APP_NAME=DisasterMonitoringSystem
APP_ENV=production
DEBUG=false

# 安全密钥（生成随机密钥）
SECRET_KEY=your-32-byte-random-hex-string
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 数据库
DATABASE_URL=sqlite:///database/disaster.db

# RSOE Cookie（从浏览器获取）
SESSION_EDIS_WEB=your_session_cookie
ARR_AFFINITY=your_arr_affinity
ARR_AFFINITY_SAME_SITE=your_arr_affinity_same_site
_GA=your_ga
__GADS=your_gads
__GPI=your_gpi
__EOI=your_eoi
_GA_KHD7YP5VHW=your_ga_khd

# Google Earth Engine
GEE_PROJECT_ID=your-gee-project-id
GEE_SERVICE_ACCOUNT_EMAIL=your-service-account@your-project.iam.gserviceaccount.com
GEE_SERVICE_ACCOUNT_PATH=config/service_account.json

# OpenAI (用于影像质量评估)
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Google Gemini (用于日报生成)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
GEMINI_FLASH_MODEL=gemini-2.0-flash-exp
GEMINI_PRO_MODEL=gemini-2.0-flash-thinking-exp

# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_WORKERS=4

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8000,https://your-domain.com
```

---

### 3. 初始化数据库

```bash
# 创建数据库表
python database/init_db.py

# 创建管理员账户
python database/create_admin.py
# 输入: 用户名、密码

# 创建GPU Worker的API Token
python database/create_token.py
# 输入: Token名称
# ⚠️ 保存输出的Token，仅显示一次！
```

---

### 4. 配置定时任务

编辑 `config.json` 中的 `scheduler` 部分：

```json
{
  "scheduler": {
    "fetch_rsoe_data": {
      "enabled": true,
      "cron": "0 2 * * *",
      "description": "每天凌晨2点抓取RSOE数据"
    },
    "process_pool": {
      "enabled": true,
      "interval_hours": 1,
      "description": "每小时处理蓄水池"
    },
    "release_timeout_locks": {
      "enabled": true,
      "interval_minutes": 10,
      "description": "每10分钟释放超时锁"
    },
    "generate_daily_report": {
      "enabled": true,
      "cron": "0 7 * * *",
      "description": "每天早上7点生成日报"
    }
  }
}
```

**定时任务说明**：
- `cron`: Cron表达式，格式为 `分 时 日 月 周`
- `interval_hours`: 每N小时执行一次
- `interval_minutes`: 每N分钟执行一次

---

### 5. 启动服务

**开发模式**（带热重载）：
```bash
python main.py
# 或
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**生产模式**（使用Supervisor）：

创建 `supervisor.conf`：
```ini
[program:disaster-monitor]
directory=/path/to/us-public-server
command=/path/to/venv/bin/python main.py
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/disaster-monitor/error.log
stdout_logfile=/var/log/disaster-monitor/access.log
environment=PATH="/path/to/venv/bin"
```

启动：
```bash
supervisorctl reread
supervisorctl update
supervisorctl start disaster-monitor
```

---

### 6. 访问系统

- **前台公开页面**: `http://your-server:8000/`
- **管理后台**: `http://your-server:8000/admin`
- **API文档**: `http://your-server:8000/docs`
- **健康检查**: `http://your-server:8000/health`

---

## 🔧 高级配置

### Nginx反向代理

```nginx
server {
    listen 80;
    server_name disaster-monitor.yourdomain.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /storage/images {
        alias /path/to/us-public-server/storage/images;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### HTTPS配置（Let's Encrypt）

```bash
sudo certbot --nginx -d disaster-monitor.yourdomain.com
```

---

## 📊 定时任务配置详解

### 可配置参数

编辑 `config.json` 调整各项参数：

```json
{
  "scheduler": {
    "fetch_rsoe_data": {
      "enabled": true,
      "cron": "0 */6 * * *",  // 改为每6小时一次
      "description": "抓取RSOE数据"
    }
  },
  "task_queue": {
    "default_lock_duration_seconds": 7200,  // GPU任务锁定时长
    "heartbeat_interval_seconds": 300,      // 心跳间隔
    "max_retries": 3                        // 最大重试次数
  },
  "gee": {
    "time_window_days_before": 30,  // 灾前影像搜索窗口
    "time_window_days_after": 30,   // 灾后影像搜索窗口
    "cloud_threshold": 20,           // 云覆盖阈值
    "max_concurrent_tasks": 100      // GEE最大并发任务
  }
}
```

---

## 🗄️ 数据库维护

### 备份

```bash
# 自动备份脚本
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/disaster-monitor"
DB_PATH="database/disaster.db"

mkdir -p $BACKUP_DIR
cp $DB_PATH $BACKUP_DIR/disaster_$DATE.db
gzip $BACKUP_DIR/disaster_$DATE.db

# 保留最近30天的备份
find $BACKUP_DIR -name "disaster_*.db.gz" -mtime +30 -delete
```

### 恢复

```bash
# 停止服务
supervisorctl stop disaster-monitor

# 恢复数据库
gunzip -c /backup/disaster-monitor/disaster_20240101_120000.db.gz > database/disaster.db

# 启动服务
supervisorctl start disaster-monitor
```

### 清理旧数据

```python
# 手动清理脚本
python -c "
from models.models import get_session_factory
from core.event_pool_manager import EventPoolManager

db = get_session_factory()()
epm = EventPoolManager(db)

# 标记90天未更新的事件为不活跃
deactivated = epm.deactivate_stale_events(days_threshold=90)
print(f'已标记 {deactivated} 个事件为不活跃')

db.close()
"
```

---

## 🔍 监控与日志

### 日志文件

- **应用日志**: `logs/disaster.log`
- **错误日志**: `logs/error.log`
- **访问日志**: Nginx访问日志

### 日志级别

在 `.env` 中设置：
```env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### 监控指标

访问 `/api/admin/status` 获取系统状态：
- 数据库大小
- 事件统计
- GEE配额
- 调度器状态
- 任务队列情况

---

## 🛡️ 安全最佳实践

1. **定期更新密钥**
   ```bash
   # 生成新的JWT密钥
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **限制API访问**
   - 配置防火墙仅开放必要端口
   - 使用Nginx限流
   - 定期审查API Token使用情况

3. **数据备份**
   - 每日自动备份数据库
   - 异地存储备份文件
   - 定期测试恢复流程

4. **日志审计**
   - 启用详细日志
   - 监控异常访问
   - 定期审查管理员操作

---

## ❓ 常见问题

### Q: 如何修改定时任务执行时间？
A: 编辑 `config.json` 中的 `scheduler` 部分，修改 `cron` 或 `interval_*` 参数，重启服务生效。

### Q: GEE下载失败怎么办？
A: 检查：
1. Service Account权限
2. GEE配额是否超限
3. 网络连接是否正常

### Q: 如何清空数据库重新开始？
A: 
```bash
rm database/disaster.db
python database/init_db.py
python database/create_admin.py
```

### Q: 前端页面无法加载？
A: 检查：
1. 静态文件是否存在于 `frontend/` 目录
2. Nginx配置是否正确
3. 浏览器控制台错误信息

---

## 📞 技术支持

- **文档**: 参考 `API_DOCUMENTATION.md`
- **Issues**: GitHub Issues
- **邮件**: support@example.com

---

## 📝 版本历史

### v1.0.0 (2024-03-11)
- ✨ 全新架构：前后端完全分离
- ⭐ 新增全局事件池（去重机制）
- 🎨 专业化UI设计
- 🔐 JWT认证 + API Token双重认证
- 📊 实时数据统计展示
- 🚀 性能优化和代码重构
