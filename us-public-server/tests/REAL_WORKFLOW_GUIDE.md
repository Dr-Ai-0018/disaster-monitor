# 🌍 真实完整工作流测试指南

本指南演示**真实调用所有 API**（RSOE、GEE、OpenAI、Gemini），只有 GPU 模型推理部分使用模拟。

---

## 📋 完整流程概览

```
✅ RSOE API 真实调用
    ↓ 抓取真实灾害数据
✅ RSOE 详情 API 真实调用
    ↓ 提取真实经纬度坐标
✅ Google Earth Engine 真实调用
    ↓ 下载真实遥感影像（Sentinel-2/Landsat）
✅ OpenAI API 真实调用
    ↓ GPT-4 Vision 质量评估
GPU 任务入队
    ↓
🔧 GPU 推理模拟（唯一模拟部分）
    ↓ 7 种 AI 分析任务
✅ Gemini Flash 真实调用
    ↓ 生成事件分析摘要
✅ Gemini Pro 真实调用
    ↓ 生成每日灾害报告
```

---

## ⚙️ 前置配置要求

### 1. RSOE Cookie 配置

编辑 `.env` 文件，添加 RSOE 网站 Cookie：

```bash
# 从浏览器开发者工具获取
RSOE_SESSION_EDIS_WEB=your_session_cookie
RSOE_ARR_AFFINITY=your_affinity_cookie
RSOE__GA=your_ga_cookie
# ... 其他 Cookie
```

**获取方法**：
1. 访问 https://rsoe-edis.org/eventList
2. 打开浏览器开发者工具（F12）→ Network → 刷新页面
3. 找到 `eventList` 请求 → Headers → Cookie
4. 复制所有 Cookie 值到 `.env`

---

### 2. Google Earth Engine 配置

**方式 1：服务账号（推荐生产环境）**

```bash
GEE_SERVICE_ACCOUNT_EMAIL=your-service-account@your-project.iam.gserviceaccount.com
GEE_SERVICE_ACCOUNT_PATH=/path/to/service-account-key.json
GEE_PROJECT_ID=your-gee-project-id
```

**方式 2：已认证用户（开发环境）**

```bash
# 先在本地运行
earthengine authenticate
# 然后只需配置
GEE_PROJECT_ID=your-gee-project-id
```

---

### 3. OpenAI API 配置

```bash
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选，自定义端点
```

**用途**：GPT-4 Vision 评估遥感影像质量（云量、清晰度、数据缺失等）

---

### 4. Google Gemini API 配置

```bash
GEMINI_API_KEY=your-gemini-api-key
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
```

**用途**：
- Gemini Flash：生成事件分析摘要
- Gemini Pro：生成每日灾害报告

---

## 🚀 快速开始（4 步）

### 步骤 1：启动服务器

```powershell
cd E:\Project\Rsoe-Gee-0example\disaster-monitor\us-public-server
E:/project/full/Scripts/python.exe main.py
```

等待看到：`✅ 系统启动完成，监听 http://0.0.0.0:2335`

---

### 步骤 2：运行真实工作流测试

**新开终端**，运行：

```powershell
cd E:\Project\Rsoe-Gee-0example\disaster-monitor\us-public-server
E:/project/full/Scripts/python.exe tests/real_workflow_test.py
```

**预期输出**：

```
步骤 1: 抓取 RSOE 真实灾害数据
✅ 成功抓取 15 个事件
选择测试事件:
   Event ID: 123456
   标题: Severe Flooding in Jakarta, Indonesia
   类别: Flood
   国家: Indonesia

步骤 2: 从 RSOE API 提取事件坐标
✅ 坐标提取成功:
   经度: 106.8456
   纬度: -6.2088
   地址: Jakarta, Indonesia

步骤 3: 提交 GEE 影像下载任务
✅ GEE 任务提交成功:
   灾前影像: 2026-01-07 ~ 2026-03-06 (Task ID: xxx...)
   灾后影像: 2026-03-07 ~ 2026-04-06 (Task ID: xxx...)
   ⏳ GEE 正在异步处理，请等待下载完成...

步骤 4: 等待 GEE 影像下载
⏳ 正在轮询 GEE 任务状态...
   [0s] 灾前: RUNNING | 灾后: RUNNING
   [10s] 灾前: RUNNING | 灾后: RUNNING
   [20s] 灾前: COMPLETED | 灾后: COMPLETED
✅ 影像下载完成！
   灾前影像: storage/images/xxx_pre.tif
   灾后影像: storage/images/xxx_post.tif

步骤 5: AI 质量评估（OpenAI）
✅ 质量评估完成:
   评分: 85
   通过: 是
   云量: 12%
   清晰度: clear
   建议: Approved for AI analysis

步骤 6: 创建 GPU 推理任务
✅ GPU 任务创建成功:
   UUID: xxx-xxx-xxx
   优先级: 120
   状态: pending

步骤 7: GPU 推理处理
⚠️  此步骤需要运行 GPU 模拟器:
   E:/project/full/Scripts/python.exe tests/test_gpu_simulator.py
```

---

### 步骤 3：运行 GPU 模拟器

**再开一个终端**：

```powershell
E:/project/full/Scripts/python.exe tests/test_gpu_simulator.py
```

**预期输出**：

```
✅ 拉取到 1 个任务
🤖 模拟推理...
✅ 结果提交成功
📊 测试完成: 1/1 成功
```

---

### 步骤 4：完成后续流程（生成摘要和报告）

回到步骤 2 的终端，运行：

```powershell
E:/project/full/Scripts/python.exe tests/real_workflow_test.py --resume <事件UUID>
```

**预期输出**：

```
步骤 8: 生成事件摘要（Gemini Flash）
✅ 事件摘要生成成功:
   字数: 800+ 字符

步骤 9: 生成每日灾害报告（Gemini Pro）
✅ 每日报告生成成功:
   日期: 2026-03-07
   事件数: 1

✅ 完整工作流执行成功！
```

---

## 🌐 查看结果

### 前端界面

访问 **http://localhost:2335**

- **登录账号**：`user-707`
- **登录密码**：`srgYJKmvr953yj`

查看内容：
1. **事件池** → 真实 RSOE 事件（含坐标、影像路径）
2. **成品池** → AI 推理结果 + Gemini 生成的摘要
3. **日报管理** → Gemini Pro 生成的每日报告

---

### 命令行查询

#### 查看事件详情

```powershell
E:/project/full/Scripts/python.exe -c "from models.models import Event, get_session_factory; import json; db=get_session_factory()(); e=db.query(Event).order_by(Event.created_at.desc()).first(); print('事件:', e.title if e else 'None'); print('坐标:', (e.latitude, e.longitude) if e else 'None'); print('状态:', e.status if e else 'None'); print('影像:', e.pre_image_path if e else 'None'); db.close()"
```

#### 查看 GEE 任务状态

```powershell
E:/project/full/Scripts/python.exe -c "from models.models import GeeTask, get_session_factory; db=get_session_factory()(); tasks=db.query(GeeTask).order_by(GeeTask.created_at.desc()).limit(2).all(); [print(f'{t.task_type}: {t.status} | {t.download_url}') for t in tasks]; db.close()"
```

#### 查看质量评估结果

```powershell
E:/project/full/Scripts/python.exe -c "from models.models import Event, get_session_factory; import json; db=get_session_factory()(); e=db.query(Event).filter(Event.quality_checked==1).order_by(Event.created_at.desc()).first(); print('评分:', e.quality_score if e else 'None'); print('通过:', e.quality_pass if e else 'None'); print('评估:', json.loads(e.quality_assessment)['recommendation'] if e and e.quality_assessment else 'None'); db.close()"
```

---

## 📊 完整流程验证清单

- [ ] **步骤 1**：RSOE 真实数据抓取成功（显示真实事件列表）
- [ ] **步骤 2**：坐标提取成功（显示真实经纬度）
- [ ] **步骤 3**：GEE 任务提交成功（返回 GEE Task ID）
- [ ] **步骤 4**：影像下载完成（生成真实 .tif 文件）
- [ ] **步骤 5**：OpenAI 质量评估成功（返回评分和建议）
- [ ] **步骤 6**：GPU 任务入队成功
- [ ] **步骤 7**：GPU 模拟器完成推理
- [ ] **步骤 8**：Gemini 生成事件摘要（真实 API 调用）
- [ ] **步骤 9**：Gemini 生成每日报告（真实 API 调用）
- [ ] **前端验证**：所有数据在前端可见

**全部通过 = 真实完整工作流运行正常！** ✅

---

## 🔧 测试工具脚本

| 脚本 | 用途 |
|------|------|
| `tests/real_workflow_test.py` | 真实完整工作流（步骤 1-9） |
| `tests/real_workflow_test.py --resume <UUID>` | 恢复工作流（步骤 8-9） |
| `tests/test_gpu_simulator.py` | GPU Worker 模拟器 |
| `tests/check_db.py` | 检查数据库状态 |
| `tests/clean_db.py` | 清理测试数据 |

---

## 🎯 真实 API 调用说明

### 1. RSOE 数据抓取（真实）

**调用**：`RsoeSpider.fetch_event_list()`

- 真实请求：`https://rsoe-edis.org/eventList`
- 使用配置的 Cookie 认证
- 解析 HTML 表格获取事件列表
- 返回：事件 ID、标题、类别、国家、严重程度等

**调用**：`RsoeSpider.fetch_event_detail(event_id, sub_id)`

- 真实请求：`https://rsoe-edis.org/gateway/webapi/events/get/{event_id}/{sub_id}`
- 提取：经纬度、大洲、地址、详情 JSON
- 返回：完整事件详情

---

### 2. Google Earth Engine（真实）

**调用**：`GeeManager.submit_download_task()`

- 真实调用 GEE Python API
- 查询 Sentinel-2 或 Landsat 影像集合
- 根据坐标、时间范围、云量筛选最佳影像
- 提交导出任务到 Google Drive 或 Cloud Storage
- 返回：GEE Task ID

**调用**：`GeeManager.check_task_status(task_id)`

- 轮询 GEE 任务状态（RUNNING / COMPLETED / FAILED）
- 下载完成后获取影像 URL
- 保存到本地 `storage/images/` 目录

---

### 3. OpenAI 质量评估（真实）

**调用**：`QualityAssessor.assess_pair(pre_path, post_path)`

- 真实调用 OpenAI GPT-4 Vision API
- 将影像编码为 base64 发送
- AI 评估：云量、清晰度、数据缺失、适用性
- 返回：评分（0-100）、通过/不通过、建议

**Prompt 示例**：
```
Evaluate the quality of this remote sensing image for disaster analysis.
Score from 0-100 and assess cloud coverage, clarity, data gaps, and suitability.
```

---

### 4. Google Gemini（真实）

**调用**：`ReportGenerator.generate_event_summary(uuid)`

- 真实调用 Gemini Flash API
- 基于 AI 推理结果生成事件分析摘要
- 包含：灾害概况、AI 分析结果、建议措施
- 返回：Markdown 格式摘要文本

**调用**：`ReportGenerator.generate_daily_report(date)`

- 真实调用 Gemini Pro API
- 汇总当日所有事件
- 生成每日灾害监测报告
- 包含：执行摘要、重点事件、统计分布
- 返回：完整报告文本

---

## 🚨 常见问题

### Q1: RSOE 数据抓取失败？

**可能原因**：
- Cookie 过期或无效
- RSOE 网站结构变化
- 网络连接问题

**解决方法**：
1. 重新获取 Cookie（见前置配置）
2. 检查网络连接
3. 查看日志：`logs/app.log`

---

### Q2: GEE 影像下载失败？

**可能原因**：
- GEE 认证失败
- 坐标无影像覆盖
- 云量过高（所有影像都被过滤）

**解决方法**：
1. 检查 GEE 认证：`earthengine authenticate`
2. 调整时间窗口（`.env` 中 `GEE_TIME_WINDOW_DAYS_BEFORE`）
3. 放宽云量阈值（`GEE_CLOUD_THRESHOLD`）

---

### Q3: OpenAI 质量评估失败？

**可能原因**：
- API Key 无效或额度不足
- 影像格式不支持
- 网络超时

**解决方法**：
1. 检查 API Key 和余额
2. 确保影像为 `.tif` 或 `.png` 格式
3. 增加超时时间（`.env` 中 `REQUEST_TIMEOUT`）

---

### Q4: Gemini 报告生成失败？

**可能原因**：
- API Key 无效
- 请求频率过高（Rate Limit）
- 内容过长

**解决方法**：
1. 检查 Gemini API Key
2. 添加重试逻辑或延迟
3. 减少输入内容长度

---

### Q5: 如何跳过某些步骤？

**场景 1：跳过 GEE 下载（使用本地影像）**

手动设置事件影像路径：
```python
event.pre_image_path = "storage/images/test_pre.tif"
event.post_image_path = "storage/images/test_post.tif"
event.pre_image_downloaded = 1
event.post_image_downloaded = 1
event.status = "ready"
```

**场景 2：跳过质量评估**

在 `.env` 中禁用：
```bash
QUALITY_ENABLED=false
```

**场景 3：只测试报告生成**

直接运行步骤 8-9：
```powershell
E:/project/full/Scripts/python.exe tests/real_workflow_test.py --resume <UUID>
```

---

## 📚 下一步

完整流程测试通过后，可以：

1. **部署定时任务** → 自动抓取 RSOE 数据（每小时）
2. **部署 GPU 服务器** → 运行真实 AI 模型推理
3. **配置邮件通知** → 发送每日报告
4. **优化影像质量** → 调整 GEE 参数和 OpenAI Prompt
5. **扩展报告模板** → 自定义 Gemini 生成格式

参考：
- `../README.md` - 项目总览
- `Disater-Process/06-部署指南.md` - 生产部署
- `config/settings.py` - 配置说明

---

## 🎉 总结

本测试脚本实现了：

✅ **真实 RSOE 数据抓取** - 获取全球灾害事件  
✅ **真实 GEE 影像下载** - Sentinel-2/Landsat 卫星数据  
✅ **真实 OpenAI 质量评估** - GPT-4 Vision AI 审查  
✅ **真实 Gemini 报告生成** - Flash/Pro 智能撰写  
🔧 **GPU 推理模拟** - 唯一模拟部分（可替换为真实模型）

**完整的端到端真实工作流已打通！**
