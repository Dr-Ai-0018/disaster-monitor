# 本地测试指南

本指南以 `Latest Model Open API` 为正式推理主链路。

## 📋 测试前准备

### 1. 启动公网服务器（端口 2335）

```bash
cd disaster-monitor/us-public-server

# 确保已安装依赖
pip install -r requirements.txt

# 初始化数据库（首次运行）
python database/init_db.py

# 创建管理员账户（首次运行）
python database/create_admin.py
# 输入用户名: admin
# 输入密码: admin123

# 启动服务器（监听 2335 端口）
python main.py
```

服务器启动后访问：
- **管理后台**: http://localhost:2335
- **API 文档**: http://localhost:2335/docs
- **健康检查**: http://localhost:2335/health

---

## 🧪 测试方案 A：完整流程测试（推荐）

### 步骤 1: 创建测试任务

```bash
# 创建一个已入队的测试任务（可直接被 Latest Model API 链路消费）
python tests/create_test_event.py --ready
```

输出示例：
```
✅ 测试任务创建成功:
   UUID: 12345678-abcd-...
   Event ID: 999997
   标题: [TEST] Earthquake Damage Assessment - Ready for AI
   任务状态: pending
   优先级: 80
```

### 步骤 2: 运行 Latest Model Open API 测试器

然后运行：
```bash
python tests/test_gpu_simulator.py
```

### 步骤 3: 查看结果

**方式 1: 通过管理后台**
1. 访问 http://localhost:2335
2. 登录（admin / admin123）
3. 进入「成品池」页面查看 AI 分析结果

**方式 2: 通过 API**
```bash
# 查看成品列表
curl http://localhost:2335/api/products?limit=10

# 查看特定成品详情
curl http://localhost:2335/api/products/{uuid}
```

**方式 3: 直接查数据库**
```bash
python -c "from models.models import Product, get_session_factory; db=get_session_factory()(); p=db.query(Product).first(); print(p.inference_result if p else 'No products')"
```

---

## 🧪 测试方案 B：手动推进流程

### 步骤 1: 创建基础测试事件

```bash
python tests/create_test_event.py
```

### 步骤 2: 手动推进蓄水池（pending → pool → checked → queued）

```bash
# 方式 1: 通过管理后台
# 访问 http://localhost:2335 → 系统管理 → 手动触发任务 → "处理蓄水池"

# 方式 2: 通过 Python 脚本
python -c "
from core.pool_manager import PoolManager
from models.models import get_session_factory

db = get_session_factory()()
pm = PoolManager(db)

# 推进 pending → pool（获取坐标）
pm.process_pending_events(limit=10)

# 提交 GEE 任务（需要 GEE 配置，可跳过）
# pm.submit_gee_tasks_for_pool(limit=10)

# 质量评估（需要 OpenAI，可跳过）
# pm.assess_ready_events(limit=10)

# 入队（手动设置状态为 checked 后执行）
pm.enqueue_checked_events(limit=10)

db.close()
"
```

### 步骤 3: 手动创建任务队列（跳过 GEE/质量评估）

```bash
python -c "
import json
from datetime import datetime, timezone
from models.models import Event, TaskQueue, get_session_factory

db = get_session_factory()()
now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

# 找到测试事件
event = db.query(Event).filter(Event.event_id == 999999).first()
if not event:
    print('❌ 测试事件不存在')
    exit(1)

# 手动设置为已下载影像
event.status = 'checked'
event.pre_image_downloaded = 1
event.post_image_downloaded = 1
event.pre_image_path = '/storage/images/test_pre.tif'
event.post_image_path = '/storage/images/test_post.tif'
event.quality_pass = 1
event.updated_at = now_ms

# 创建任务队列
task_data = {
    'uuid': event.uuid,
    'image_path': event.post_image_path or event.pre_image_path,
    'image_kind': 'post_disaster' if event.post_image_path else 'pre_disaster',
    'tasks': [
        {'task_id': 1, 'type': 'IMG_CAP', 'prompt': 'Describe this disaster.'},
        {'task_id': 2, 'type': 'IMG_VQA', 'prompt': 'Is there damage?'},
        {'task_id': 3, 'type': 'IMG_CT', 'prompt': 'Assess the impact.'},
        {'task_id': 4, 'type': 'PIX_SEG', 'prompt': 'Segment damaged areas.'},
        {'task_id': 5, 'type': 'PIX_CHG', 'prompt': 'Detect changes.'},
        {'task_id': 6, 'type': 'REG_DET_HBB', 'prompt': 'Detect objects.'},
        {'task_id': 7, 'type': 'REG_VG', 'prompt': 'Locate damage.'},
    ],
    'event_details': {
        'title': event.title,
        'category': event.category,
        'category_name': event.category_name,
        'country': event.country,
        'severity': event.severity,
        'longitude': event.longitude,
        'latitude': event.latitude,
        'event_date': event.event_date,
        'details': {}
    }
}

task = TaskQueue(
    uuid=event.uuid,
    priority=70,
    status='pending',
    task_data=json.dumps(task_data),
    created_at=now_ms,
    updated_at=now_ms,
)

event.status = 'queued'
db.add(task)
db.commit()
print(f'✅ 任务队列创建成功: {task.uuid}')
db.close()
"
```

### 步骤 4: 运行 Latest Model Open API 测试器

```bash
python tests/test_gpu_simulator.py
```

---

## 🔍 常见问题排查

### 1. Latest Model Open API 测试器报配置错误

**原因**: `LATEST_MODEL_ENDPOINT` 或 `LATEST_MODEL_API_KEY` 未配置

**解决**:
```bash
# 检查 .env
grep LATEST_MODEL .env
```

### 2. 推理任务未被消费

**原因**: 数据库中没有 `status=pending` 的任务，或 `Latest Model Open API` 未配置

**解决**:
```bash
# 检查任务队列
python -c "from models.models import TaskQueue, get_session_factory; db=get_session_factory()(); tasks=db.query(TaskQueue).all(); print(f'共 {len(tasks)} 个任务'); [print(f'  {t.uuid[:16]}... | status={t.status}') for t in tasks]"

# 如果没有任务，运行:
python tests/create_test_event.py --ready
```

### 3. 服务器启动失败

**检查端口占用**:
```bash
# Windows
netstat -ano | findstr :2335

# 如果被占用，修改 .env 中的 SERVER_PORT
```

**检查数据库**:
```bash
# 确保数据库文件存在
ls database/disaster.db

# 如果不存在，重新初始化
python database/init_db.py
```

### 4. 测试器调用远端 API 失败

**查看服务器日志**:
```bash
# 日志文件位置
cat logs/disaster_*.log | tail -50
```

**检查任务状态**:
```bash
python -c "from models.models import TaskQueue, get_session_factory; db=get_session_factory()(); t=db.query(TaskQueue).first(); print(f'Status: {t.status}, Locked by: {t.locked_by}' if t else 'No tasks')"
```

---

## 📊 验证测试结果

### 检查事件状态

```bash
python -c "
from models.models import Event, get_session_factory
db = get_session_factory()()
events = db.query(Event).filter(Event.event_id >= 999990).all()
for e in events:
    print(f'{e.event_id} | {e.title[:40]} | status={e.status}')
db.close()
"
```

### 检查任务队列

```bash
python -c "
from models.models import TaskQueue, get_session_factory
db = get_session_factory()()
tasks = db.query(TaskQueue).all()
for t in tasks:
    print(f'{t.uuid[:16]}... | status={t.status} | locked_by={t.locked_by or \"None\"}')
db.close()
"
```

### 检查成品池

```bash
python -c "
from models.models import Product, get_session_factory
import json
db = get_session_factory()()
products = db.query(Product).all()
for p in products:
    result = json.loads(p.inference_result) if p.inference_result else {}
    print(f'{p.uuid[:16]}... | {len(result)} tasks | summary={bool(p.summary)}')
db.close()
"
```

---

## 🎯 完整测试流程总结

```bash
# 1. 启动服务器
python main.py

# 2. 创建测试任务（新终端）
python tests/create_test_event.py --ready

# 3. 运行 Latest Model Open API 测试器
python tests/test_gpu_simulator.py

# 4. 查看结果
# 访问 http://localhost:2335 → 成品池
```

---

## 🚀 进阶测试

### 测试定时任务

```bash
# 手动触发 RSOE 数据抓取
curl -X POST http://localhost:2335/api/admin/jobs/fetch_rsoe_data/trigger \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 手动触发蓄水池处理
curl -X POST http://localhost:2335/api/admin/jobs/process_pool/trigger \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 手动生成日报
curl -X POST http://localhost:2335/api/admin/jobs/generate_daily_report/trigger \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 压力测试

```bash
# 创建 10 个测试任务
for i in {1..10}; do
  python tests/create_test_event.py --ready
  sleep 1
done

# 运行模拟器处理
python tests/test_gpu_simulator.py
```

---

## 📝 测试检查清单

- [ ] 服务器成功启动在 2335 端口
- [ ] 管理后台可以访问并登录
- [ ] 测试事件创建成功
- [ ] Latest Model Open API 测试器运行成功
- [ ] 远端任务提交成功
- [ ] 轮询状态正常
- [ ] 推理结果回写成功
- [ ] 成品池中可以看到结果
- [ ] 事件状态正确更新为 `completed`

全部通过 ✅ = 系统运行正常！
