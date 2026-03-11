# 🌍 完整工作流测试指南

本指南演示从 RSOE 数据抓取到最终报告生成的**端到端完整流程**。

---

## 📋 完整流程概览

```
RSOE 数据抓取
    ↓
坐标提取（经纬度）
    ↓
GEE 影像下载任务提交
    ↓
遥感影像下载（灾前/灾后）
    ↓
OpenAI 质量评估
    ↓
GPU 任务入队
    ↓
GPU AI 推理（7 种分析任务）
    ↓
Gemini 事件摘要生成
    ↓
Gemini 每日报告生成
```

---

## 🚀 快速开始（3 步）

### 步骤 1：启动服务器

```powershell
cd E:\Project\Rsoe-Gee-0example\disaster-monitor\us-public-server
E:/project/full/Scripts/python.exe main.py
```

等待看到：`✅ 系统启动完成，监听 http://0.0.0.0:2335`

---

### 步骤 2：运行完整工作流模拟器

**新开终端**，运行：

```powershell
cd E:\Project\Rsoe-Gee-0example\disaster-monitor\us-public-server
E:/project/full/Scripts/python.exe tests/full_workflow_simulator.py
```

**预期输出**：

```
步骤 1: 模拟 RSOE 数据抓取
✅ 创建事件成功
   Event ID: 888888
   标题: Severe Flooding in Jakarta, Indonesia

步骤 2: 提取事件坐标
✅ 坐标提取成功
   经度: 106.8456
   纬度: -6.2088

步骤 3: 提交 GEE 影像下载任务
✅ GEE 任务创建成功
   灾前影像: 2026-01-07 ~ 2026-03-06
   灾后影像: 2026-03-07 ~ 2026-03-14

步骤 4: 模拟 GEE 影像下载
✅ 影像下载完成
   灾前影像: storage/images/xxx_pre.tif
   灾后影像: storage/images/xxx_post.tif

步骤 5: AI 质量评估（OpenAI）
✅ 质量评估完成
   评分: 0.85
   云量: Low (< 10%)
   结论: Approved for AI analysis

步骤 6: 创建 GPU 推理任务
✅ GPU 任务创建成功
   任务数: 7 个 AI 分析任务
   状态: queued (已入队，等待 GPU 处理)

步骤 7: GPU 推理处理
⚠️  此步骤需要运行 GPU 模拟器:
   E:/project/full/Scripts/python.exe tests/test_gpu_simulator.py
```

---

### 步骤 3：运行 GPU 模拟器

**再开一个终端**，运行：

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

### 步骤 4：恢复工作流（生成摘要和报告）

GPU 推理完成后，回到步骤 2 的终端，运行：

```powershell
E:/project/full/Scripts/python.exe tests/full_workflow_simulator.py --resume
```

**预期输出**：

```
步骤 8: 生成事件摘要（Gemini Flash）
✅ 事件摘要生成成功
   字数: 500+ 字符
   模型: Gemini Flash (模拟)

步骤 9: 生成每日灾害报告（Gemini Pro）
✅ 每日报告生成成功
   日期: 2026-03-07
   事件数: 1
   字数: 800+ 字符

✅ 完整工作流执行成功！
```

---

## 🌐 查看结果

### 方式 1：前端界面（推荐）

访问 **http://localhost:2335**

- **登录账号**：`user-707`
- **登录密码**：`srgYJKmvr953yj`

登录后可以查看：

1. **事件池** → 查看事件状态（应为 `completed`）
2. **成品池** → 查看 AI 推理结果（7 个任务的分析）
3. **日报管理** → 查看每日灾害报告

---

### 方式 2：命令行查询

#### 查看事件详情

```powershell
E:/project/full/Scripts/python.exe -c "from models.models import Event, get_session_factory; import json; db=get_session_factory()(); e=db.query(Event).filter(Event.event_id==888888).first(); print('事件:', e.title if e else 'None'); print('状态:', e.status if e else 'None'); print('坐标:', (e.latitude, e.longitude) if e else 'None'); db.close()"
```

#### 查看推理结果

```powershell
E:/project/full/Scripts/python.exe -c "from models.models import Product, get_session_factory; import json; db=get_session_factory()(); p=db.query(Product).filter(Product.event_title.like('%Jakarta%')).first(); print('成品 UUID:', p.uuid if p else 'None'); print('摘要:', p.summary[:200] if p and p.summary else 'None'); db.close()"
```

#### 查看每日报告

```powershell
E:/project/full/Scripts/python.exe -c "from models.models import DailyReport, get_session_factory; from datetime import datetime, timezone; db=get_session_factory()(); today=datetime.now(timezone.utc).strftime('%Y-%m-%d'); r=db.query(DailyReport).filter(DailyReport.report_date==today).first(); print('报告日期:', r.report_date if r else 'None'); print('事件数:', r.event_count if r else 0); print('内容预览:', r.report_content[:300] if r else 'None'); db.close()"
```

---

## 📊 完整流程验证清单

- [ ] **步骤 1**：事件创建成功（Event ID: 888888）
- [ ] **步骤 2**：坐标提取成功（雅加达经纬度）
- [ ] **步骤 3**：GEE 任务创建（2 个任务：灾前/灾后）
- [ ] **步骤 4**：影像下载完成（2 个 .tif 文件）
- [ ] **步骤 5**：质量评估通过（评分 0.85）
- [ ] **步骤 6**：GPU 任务入队（7 个 AI 任务）
- [ ] **步骤 7**：GPU 推理完成（模拟器返回成功）
- [ ] **步骤 8**：事件摘要生成（Gemini Flash）
- [ ] **步骤 9**：每日报告生成（Gemini Pro）
- [ ] **前端验证**：成品池中可见完整分析结果

**全部通过 = 完整工作流运行正常！** ✅

---

## 🔧 测试工具脚本

| 脚本 | 用途 |
|------|------|
| `tests/full_workflow_simulator.py` | 完整工作流模拟（步骤 1-9） |
| `tests/full_workflow_simulator.py --resume` | 恢复工作流（步骤 8-9） |
| `tests/test_gpu_simulator.py` | GPU Worker 模拟器 |
| `tests/check_db.py` | 检查数据库状态 |
| `tests/clean_db.py` | 清理测试数据 |

---

## 🎯 流程说明

### 1. RSOE 数据抓取（模拟）

- 创建一个真实的灾害事件（雅加达洪水）
- 包含标题、类别、国家、严重程度等信息
- 初始状态：`pending`

### 2. 坐标提取（模拟）

- 从事件详情中提取经纬度（-6.2088, 106.8456）
- 状态更新：`pending` → `pool`

### 3. GEE 影像下载任务提交（模拟）

- 创建 2 个 GEE 任务：灾前影像（事件前 60 天）、灾后影像（事件后 7 天）
- 任务状态：`PENDING`

### 4. GEE 影像下载（模拟）

- 模拟 Sentinel-2 卫星影像下载
- 创建 `.tif` 文件（空文件，仅用于测试）
- 任务状态：`PENDING` → `COMPLETED`
- 事件状态：`pool` → `ready`

### 5. OpenAI 质量评估（模拟）

- 模拟 GPT-4 评估影像质量
- 评分：0.85（通过）
- 评估内容：云量、影像质量、时间相关性、空间覆盖
- 事件状态：`ready` → `checked`

### 6. GPU 任务入队（自动）

- 创建 7 个 AI 分析任务：
  1. IMG_CAP - 影像描述
  2. IMG_VQA - 视觉问答
  3. IMG_CT - 综合评估
  4. PIX_SEG - 像素分割
  5. PIX_CHG - 变化检测
  6. REG_DET_HBB - 目标检测
  7. REG_VG - 视觉定位
- 事件状态：`checked` → `queued`

### 7. GPU 推理（需手动运行模拟器）

- GPU Worker 拉取任务
- 执行 7 个 AI 分析任务
- 提交推理结果到成品池
- 事件状态：`queued` → `processing` → `completed`

### 8. Gemini 事件摘要生成（模拟）

- 使用 Gemini Flash 模型
- 基于 AI 推理结果生成事件分析摘要
- 包含：灾害概况、AI 分析结果、建议措施

### 9. Gemini 每日报告生成（模拟）

- 使用 Gemini Pro 模型
- 汇总当日所有事件
- 生成每日灾害监测报告
- 包含：执行摘要、重点事件、统计分布

---

## 🚨 常见问题

### Q1: 工作流在步骤 7 暂停了？

**原因**：步骤 7 需要手动运行 GPU 模拟器。

**解决**：
```powershell
E:/project/full/Scripts/python.exe tests/test_gpu_simulator.py
```

然后运行：
```powershell
E:/project/full/Scripts/python.exe tests/full_workflow_simulator.py --resume
```

### Q2: 如何重新测试完整流程？

**清理旧数据**：
```powershell
E:/project/full/Scripts/python.exe tests/clean_db.py
```

**重新运行**：
```powershell
E:/project/full/Scripts/python.exe tests/full_workflow_simulator.py
```

### Q3: 前端看不到数据？

**检查数据库**：
```powershell
E:/project/full/Scripts/python.exe tests/check_db.py
```

**刷新浏览器**：按 `Ctrl + F5` 强制刷新

---

## 📚 下一步

完整流程测试通过后，可以：

1. **配置真实 RSOE Cookie** → 抓取真实灾害数据
2. **配置 GEE 服务账号** → 下载真实遥感影像
3. **配置 OpenAI API Key** → 启用真实质量评估
4. **配置 Gemini API Key** → 启用真实摘要和报告生成
5. **部署真实 GPU Server** → 运行真实 AI 模型推理

参考：`../README.md` 和 `Disater-Process/06-部署指南.md`

---

🎉 **完整工作流测试完成！**
