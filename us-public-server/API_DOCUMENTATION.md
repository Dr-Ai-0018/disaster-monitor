# 灾害监测系统 API 文档

## 基础信息

- **Base URL**: `http://your-server.com` 或 `http://localhost:8000`
- **API版本**: v1.0.0
- **认证方式**: JWT Bearer Token（管理员接口） / API Token（GPU Worker接口）

---

## 认证

### 管理员登录
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your_password"
}

Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin"
  }
}
```

### 使用JWT Token
```http
GET /api/events
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

---

## 全局事件池 API（公开访问，无需认证）

### 获取事件池列表
```http
GET /api/pool?page=1&limit=50&category=FL&severity=high

Query Parameters:
- page: int (default: 1) - 页码
- limit: int (default: 50, max: 200) - 每页数量
- category: string (optional) - 事件类型 (FL/TC/EQ/VO/WF/ST/DR/LS/TS/AV)
- country: string (optional) - 国家名称（模糊搜索）
- severity: string (optional) - 严重程度 (extreme/high/medium/low)
- active_only: bool (default: true) - 仅显示活跃事件

Response:
{
  "total": 1234,
  "page": 1,
  "limit": 50,
  "pages": 25,
  "data": [
    {
      "event_id": 12345,
      "sub_id": 0,
      "title": "Flooding in Bangladesh",
      "category": "FL",
      "category_name": "Flood",
      "country": "Bangladesh",
      "continent": "Asia",
      "severity": "high",
      "longitude": 90.4125,
      "latitude": 23.8103,
      "address": "Dhaka Division",
      "event_date": 1704067200000,
      "last_update": 1704153600000,
      "first_seen": 1704067200000,
      "last_seen": 1704153600000,
      "fetch_count": 5,
      "is_active": true
    }
  ]
}
```

### 获取事件池统计
```http
GET /api/pool/stats

Response:
{
  "total_events": 5432,
  "active_events": 234,
  "inactive_events": 5198,
  "by_category": {
    "FL": 89,
    "TC": 12,
    "EQ": 45,
    "WF": 67
  },
  "by_country": {
    "United States": 45,
    "China": 38,
    "India": 32
  },
  "by_severity": {
    "extreme": 5,
    "high": 34,
    "medium": 123,
    "low": 72
  }
}
```

### 获取单个事件详情
```http
GET /api/pool/{event_id}/{sub_id}

Response:
{
  "event_id": 12345,
  "sub_id": 0,
  "title": "...",
  // ... 完整事件信息
}
```

---

## 事件管理 API（需要JWT认证）

### 获取事件列表
```http
GET /api/events?page=1&limit=20&status=pool&severity=high
Authorization: Bearer {token}

Query Parameters:
- page, limit, status, category, country, severity
- start_date, end_date: int (timestamp in ms)

Response: 同事件池，但包含更多处理状态信息
```

### 获取事件统计
```http
GET /api/events/stats
Authorization: Bearer {token}

Response:
{
  "total_events": 1234,
  "by_status": {
    "pending": 45,
    "pool": 123,
    "checked": 67,
    "queued": 34,
    "processing": 12,
    "completed": 953
  },
  "by_category": {...},
  "by_severity": {...},
  "recent_24h": 23
}
```

### 获取单个事件详情
```http
GET /api/events/{uuid}
Authorization: Bearer {token}

Response: 包含完整的处理流程信息
```

### 手动推进事件处理
```http
POST /api/events/{uuid}/process
Authorization: Bearer {token}

Response:
{
  "message": "事件 {uuid} 处理已触发，当前状态: pool"
}
```

---

## GPU 任务队列 API（需要API Token认证）

### 拉取任务
```http
POST /api/tasks/pull
X-API-Token: your_api_token
Content-Type: application/json

{
  "worker_id": "gpu-worker-01",
  "limit": 1
}

Response:
{
  "tasks": [
    {
      "id": 123,
      "uuid": "event-uuid-here",
      "priority": 150,
      "task_data": {
        "uuid": "...",
        "pre_image_url": "http://.../pre_disaster.tif",
        "post_image_url": "http://.../post_disaster.tif",
        "event_details": {...},
        "tasks": [...]
      },
      "locked_by": "gpu-worker-01",
      "locked_until": 1704160800000,
      "created_at": 1704153600000
    }
  ],
  "count": 1
}
```

### 提交任务结果
```http
PUT /api/tasks/{uuid}/result
X-API-Token: your_api_token
Content-Type: application/json

{
  "worker_id": "gpu-worker-01",
  "status": "success",
  "inference_result": {
    "IMG_CAP": {
      "type": "IMG_CAP",
      "result": "Satellite imagery shows...",
      "error": null
    },
    "IMG_VQA": {...},
    // ... 其他7个任务结果
  },
  "processing_time_seconds": 45.3,
  "model_info": {
    "model_name": "disaster-model-v1",
    "device": "cuda:0"
  }
}

Response:
{
  "message": "Result submitted successfully",
  "uuid": "...",
  "status": "completed",
  "created": true
}
```

### 心跳更新
```http
POST /api/tasks/{uuid}/heartbeat
X-API-Token: your_api_token
Content-Type: application/json

{
  "worker_id": "gpu-worker-01"
}

Response:
{
  "message": "Heartbeat updated",
  "uuid": "...",
  "heartbeat": 1704155400000,
  "locked_until": 1704160800000
}
```

### 任务失败报告
```http
POST /api/tasks/{uuid}/fail
X-API-Token: your_api_token
Content-Type: application/json

{
  "worker_id": "gpu-worker-01",
  "reason": "CUDA out of memory",
  "error_details": "RuntimeError: ...",
  "can_retry": true
}

Response:
{
  "message": "Task marked as failed",
  "uuid": "...",
  "retry_count": 1,
  "will_retry": true
}
```

---

## 成品池 API

### 获取成品列表
```http
GET /api/products?page=1&limit=20
Authorization: Bearer {token}

Response:
{
  "total": 953,
  "page": 1,
  "limit": 20,
  "pages": 48,
  "data": [
    {
      "uuid": "...",
      "event_title": "...",
      "event_category": "FL",
      "event_country": "Bangladesh",
      "inference_result": {...},
      "summary": "AI生成的摘要...",
      "summary_generated": true,
      "created_at": 1704153600000
    }
  ]
}
```

### 获取单个成品详情
```http
GET /api/products/{uuid}
Authorization: Bearer {token}

Response: 包含完整的推理结果和事件详情
```

---

## 日报管理 API

### 获取日报列表
```http
GET /api/reports?page=1&limit=30
Authorization: Bearer {token}

Response:
{
  "total": 90,
  "page": 1,
  "limit": 30,
  "pages": 3,
  "data": [
    {
      "id": 1,
      "report_date": "2024-01-01",
      "report_title": "2024年1月1日全球灾害日报",
      "event_count": 23,
      "generated_at": 1704067200000,
      "published": true
    }
  ]
}
```

### 获取单个日报详情
```http
GET /api/reports/{report_date}
Authorization: Bearer {token}

Response:
{
  "id": 1,
  "report_date": "2024-01-01",
  "report_title": "...",
  "report_content": "完整的日报内容...",
  "event_count": 23,
  "category_stats": {...},
  "severity_stats": {...},
  "country_stats": {...},
  "generated_at": 1704067200000,
  "generated_by": "gemini-2.5-pro",
  "generation_time_seconds": 12.5,
  "published": true,
  "published_at": 1704070800000
}
```

### 生成日报
```http
POST /api/reports/generate
Authorization: Bearer {token}
Content-Type: application/json

{
  "date": "2024-01-01"
}

Response:
{
  "message": "日报生成任务已启动",
  "report_date": "2024-01-01"
}
```

### 发布日报
```http
PUT /api/reports/{report_date}/publish
Authorization: Bearer {token}

Response:
{
  "message": "日报已发布"
}
```

---

## 系统管理 API

### 系统状态
```http
GET /api/admin/status
Authorization: Bearer {token}

Response:
{
  "system": {
    "status": "healthy",
    "version": "1.0.0",
    "env": "production"
  },
  "database": {
    "size_mb": 2345.67,
    "events_count": 12345,
    "tasks_pending": 23,
    "tasks_locked": 5,
    "products_count": 953,
    "by_status": {...}
  },
  "gee": {
    "authenticated": true,
    "running_tasks": 12,
    "quota_warning": false
  },
  "scheduler": {
    "running": true,
    "next_jobs": [
      {
        "job_id": "fetch_rsoe_data",
        "next_run": 1704067200000
      }
    ]
  }
}
```

### Token管理

#### 列出所有Token
```http
GET /api/admin/tokens
Authorization: Bearer {token}

Response:
[
  {
    "token": "abc123...xyz",
    "name": "gpu-worker-token",
    "description": "GPU服务器访问令牌",
    "is_active": true,
    "usage_count": 1234,
    "last_used": 1704153600000,
    "created_at": 1704067200000
  }
]
```

#### 创建Token
```http
POST /api/admin/tokens
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "new-worker-token",
  "description": "新的Worker令牌",
  "scopes": ["tasks.read", "tasks.update"]
}

Response:
{
  "token": "完整的token字符串（仅显示一次）",
  "name": "new-worker-token",
  "created_at": 1704153600000
}
```

#### 禁用Token
```http
DELETE /api/admin/tokens/{token_name}
Authorization: Bearer {token}

Response:
{
  "message": "Token 'token_name' 已禁用"
}
```

### 手动触发定时任务
```http
POST /api/admin/jobs/{job_id}/trigger
Authorization: Bearer {token}

job_id 可选值:
- fetch_rsoe_data: 抓取RSOE数据
- process_pool: 处理蓄水池
- release_timeout_locks: 释放超时锁
- generate_daily_report: 生成日报

Response:
{
  "message": "任务 'fetch_rsoe_data' 已触发"
}
```

---

## 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "detail": "错误描述信息",
  "error_code": "ERROR_CODE",
  "timestamp": 1704153600000
}
```

### 常见状态码

- `200 OK` - 请求成功
- `201 Created` - 资源创建成功
- `400 Bad Request` - 请求参数错误
- `401 Unauthorized` - 未认证或认证失败
- `403 Forbidden` - 权限不足
- `404 Not Found` - 资源不存在
- `500 Internal Server Error` - 服务器内部错误

---

## 数据字典

### 事件状态 (status)
- `pending` - 待处理（刚抓取）
- `pool` - 蓄水池（已获取坐标）
- `checked` - 质检通过（影像质量合格）
- `queued` - 已入队（等待GPU处理）
- `processing` - 推理中（GPU正在处理）
- `completed` - 已完成（推理完成）
- `failed` - 失败

### 严重程度 (severity)
- `extreme` - 极高
- `high` - 高
- `medium` - 中
- `low` - 低

### 事件类型 (category)
- `FL` - 洪水 (Flood)
- `TC` - 热带气旋 (Tropical Cyclone)
- `EQ` - 地震 (Earthquake)
- `VO` - 火山 (Volcano)
- `WF` - 野火 (Wildfire)
- `ST` - 风暴 (Storm)
- `DR` - 干旱 (Drought)
- `LS` - 滑坡 (Landslide)
- `TS` - 海啸 (Tsunami)
- `AV` - 雪崩 (Avalanche)

---

## 速率限制

- 管理员接口: 1000 请求/小时
- GPU任务接口: 10000 请求/小时
- 公开接口（事件池）: 无限制

---

## WebSocket 支持

*计划中，暂未实现*

---

## 更新日志

### v1.0.0 (2024-01-01)
- 初始版本发布
- 实现全局事件池（去重机制）
- 前后端完全分离
- 支持JWT和API Token双认证
