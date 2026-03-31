"""
完整工作流模拟器
模拟从 RSOE 数据抓取到最终报告生成的全流程
"""
import sys
import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.models import Event, GeeTask, TaskQueue, Product, DailyReport, get_session_factory
from core.pool_manager import PoolManager
from core.report_generator import ReportGenerator
from utils.logger import get_logger

logger = get_logger(__name__)


class FullWorkflowSimulator:
    """完整工作流模拟器"""
    
    def __init__(self):
        self.db = get_session_factory()()
        self.pool_manager = PoolManager(self.db)
        self.report_generator = ReportGenerator(self.db)
        
    def _now_ms(self):
        return int(datetime.now(timezone.utc).timestamp() * 1000)
    
    def step1_create_rsoe_event(self):
        """步骤 1: 模拟 RSOE 数据抓取，创建灾害事件"""
        print("\n" + "=" * 70)
        print("步骤 1: 模拟 RSOE 数据抓取")
        print("=" * 70)
        
        now_ms = self._now_ms()
        event_uuid = str(uuid.uuid4())
        
        # 模拟真实的 RSOE 事件数据
        event = Event(
            uuid=event_uuid,
            event_id=888888,  # 模拟事件 ID
            sub_id=0,
            title="Severe Flooding in Jakarta, Indonesia",
            category="FL",
            category_name="Flood",
            country="Indonesia",
            continent="Asia",
            severity="high",
            event_date=now_ms - 3600000,  # 1小时前发生
            last_update=now_ms,
            source_url="https://rsoe-edis.org/eventList/details/888888/0",
            status="pending",  # 初始状态：待处理
            created_at=now_ms,
            updated_at=now_ms,
            details_json=json.dumps({
                "description": "Heavy rainfall causes severe flooding in Jakarta metropolitan area",
                "affected_population": "~500,000",
                "damage_estimate": "Moderate to severe",
            }),
        )
        
        self.db.add(event)
        self.db.commit()
        
        print(f"✅ 创建事件成功:")
        print(f"   UUID: {event.uuid}")
        print(f"   Event ID: {event.event_id}")
        print(f"   标题: {event.title}")
        print(f"   状态: {event.status} (待提取坐标)")
        
        return event
    
    def step2_extract_coordinates(self, event: Event):
        """步骤 2: 模拟坐标提取（从 RSOE 详情页获取）"""
        print("\n" + "=" * 70)
        print("步骤 2: 提取事件坐标")
        print("=" * 70)
        
        # 模拟从 RSOE API 获取坐标（雅加达）
        latitude = -6.2088
        longitude = 106.8456
        
        event.latitude = latitude
        event.longitude = longitude
        event.address = "Jakarta, Indonesia"
        event.status = "pool"  # 进入蓄水池
        event.updated_at = self._now_ms()
        
        self.db.commit()
        
        print(f"✅ 坐标提取成功:")
        print(f"   经度: {longitude}")
        print(f"   纬度: {latitude}")
        print(f"   地址: {event.address}")
        print(f"   状态: {event.status} (已进入蓄水池)")
        
        return event
    
    def step3_submit_gee_tasks(self, event: Event):
        """步骤 3: 提交 GEE 影像下载任务"""
        print("\n" + "=" * 70)
        print("步骤 3: 提交 GEE 影像下载任务")
        print("=" * 70)
        
        now_ms = self._now_ms()
        event_date = datetime.fromtimestamp(event.event_date / 1000, tz=timezone.utc)
        
        # 创建灾前影像任务（事件前 30 天）
        pre_start = (event_date - timedelta(days=60)).strftime("%Y-%m-%d")
        pre_end = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
        
        pre_task = GeeTask(
            uuid=event.uuid,
            task_type="pre_disaster",
            status="PENDING",
            roi_geojson=json.dumps({
                "type": "Point",
                "coordinates": [event.longitude, event.latitude]
            }),
            start_date=pre_start,
            end_date=pre_end,
            cloud_threshold=20.0,
            created_at=now_ms,
            updated_at=now_ms,
        )
        
        # 创建灾后影像任务（事件后 7 天）
        post_start = event_date.strftime("%Y-%m-%d")
        post_end = (event_date + timedelta(days=7)).strftime("%Y-%m-%d")
        
        post_task = GeeTask(
            uuid=event.uuid,
            task_type="post_disaster",
            status="PENDING",
            roi_geojson=json.dumps({
                "type": "Point",
                "coordinates": [event.longitude, event.latitude]
            }),
            start_date=post_start,
            end_date=post_end,
            cloud_threshold=20.0,
            created_at=now_ms,
            updated_at=now_ms,
        )
        
        self.db.add(pre_task)
        self.db.add(post_task)
        self.db.commit()
        
        print(f"✅ GEE 任务创建成功:")
        print(f"   灾前影像: {pre_start} ~ {pre_end}")
        print(f"   灾后影像: {post_start} ~ {post_end}")
        print(f"   ⚠️  实际环境中，GEE 会异步下载影像到服务器")
        
        return pre_task, post_task
    
    def step4_simulate_gee_download(self, event: Event, pre_task: GeeTask, post_task: GeeTask):
        """步骤 4: 模拟 GEE 影像下载完成"""
        print("\n" + "=" * 70)
        print("步骤 4: 模拟 GEE 影像下载")
        print("=" * 70)
        
        now_ms = self._now_ms()
        
        # 模拟下载完成
        storage_path = Path("storage/images")
        storage_path.mkdir(parents=True, exist_ok=True)
        
        pre_image_path = f"storage/images/{event.uuid}_pre.tif"
        post_image_path = f"storage/images/{event.uuid}_post.tif"
        
        # 创建空文件模拟影像
        Path(pre_image_path).touch()
        Path(post_image_path).touch()
        
        # 更新任务状态
        pre_task.status = "COMPLETED"
        pre_task.download_url = pre_image_path
        pre_task.image_date = event.event_date - 86400000 * 15  # 15天前
        pre_task.image_source = "Sentinel-2"
        pre_task.completed_at = now_ms
        pre_task.updated_at = now_ms
        
        post_task.status = "COMPLETED"
        post_task.download_url = post_image_path
        post_task.image_date = event.event_date + 86400000 * 2  # 2天后
        post_task.image_source = "Sentinel-2"
        post_task.completed_at = now_ms
        post_task.updated_at = now_ms
        
        # 更新事件
        event.pre_image_path = pre_image_path
        event.pre_image_date = pre_task.image_date
        event.pre_image_source = "Sentinel-2"
        event.pre_image_downloaded = 1
        
        event.post_image_path = post_image_path
        event.post_image_date = post_task.image_date
        event.post_image_source = "Sentinel-2"
        event.post_image_downloaded = 1
        
        event.status = "ready"  # 影像已就绪
        event.updated_at = now_ms
        
        self.db.commit()
        
        print(f"✅ 影像下载完成:")
        print(f"   灾前影像: {pre_image_path}")
        print(f"   灾后影像: {post_image_path}")
        print(f"   状态: {event.status} (影像已就绪)")
        
        return event
    
    def step5_quality_assessment(self, event: Event):
        """步骤 5: 模拟 OpenAI 质量评估"""
        print("\n" + "=" * 70)
        print("步骤 5: AI 质量评估（OpenAI）")
        print("=" * 70)
        
        now_ms = self._now_ms()
        
        # 模拟 OpenAI 评估结果
        quality_score = 0.85
        quality_assessment = {
            "cloud_coverage": "Low (< 10%)",
            "image_quality": "Good",
            "temporal_relevance": "Excellent",
            "spatial_coverage": "Complete",
            "recommendation": "Approved for AI analysis",
            "model": "gpt-4-turbo (simulated)"
        }
        
        event.quality_score = quality_score
        event.quality_assessment = json.dumps(quality_assessment)
        event.quality_checked = 1
        event.quality_pass = 1
        event.quality_check_time = now_ms
        event.status = "checked"  # 质量审核通过
        event.updated_at = now_ms
        
        self.db.commit()
        
        print(f"✅ 质量评估完成:")
        print(f"   评分: {quality_score}")
        print(f"   云量: {quality_assessment['cloud_coverage']}")
        print(f"   影像质量: {quality_assessment['image_quality']}")
        print(f"   结论: {quality_assessment['recommendation']}")
        print(f"   状态: {event.status} (已通过质量审核)")
        
        return event
    
    def step6_enqueue_task(self, event: Event):
        """步骤 6: 创建 GPU 任务队列"""
        print("\n" + "=" * 70)
        print("步骤 6: 创建 GPU 推理任务")
        print("=" * 70)
        
        now_ms = self._now_ms()
        
        task_data = {
            "uuid": event.uuid,
            "pre_image_url": event.pre_image_path,
            "post_image_url": event.post_image_path,
            "event_details": {
                "event_id": event.event_id,
                "title": event.title,
                "category": event.category,
                "country": event.country,
                "severity": event.severity,
                "latitude": event.latitude,
                "longitude": event.longitude,
            },
            "tasks": [
                {"task_id": 1, "type": "IMG_CAP", "prompt": "Describe the disaster scene in detail."},
                {"task_id": 2, "type": "IMG_VQA", "prompt": "Is there visible flood damage?"},
                {"task_id": 3, "type": "IMG_CT", "prompt": "Provide a comprehensive damage assessment."},
                {"task_id": 4, "type": "PIX_SEG", "prompt": "Segment the flooded areas."},
                {"task_id": 5, "type": "PIX_CHG", "prompt": "Detect changes between pre and post images."},
                {"task_id": 6, "type": "REG_DET_HBB", "prompt": "Detect damaged buildings."},
                {"task_id": 7, "type": "REG_VG", "prompt": "Locate the most severely flooded region."},
            ]
        }
        
        task = TaskQueue(
            uuid=event.uuid,
            priority=70,
            status="pending",
            task_data=json.dumps(task_data, ensure_ascii=False),
            created_at=now_ms,
            updated_at=now_ms,
        )
        
        event.status = "queued"
        event.updated_at = now_ms
        
        self.db.add(task)
        self.db.commit()
        
        print(f"✅ Latest Model 推理任务创建成功:")
        print(f"   UUID: {task.uuid}")
        print(f"   优先级: {task.priority}")
        print(f"   任务数: 7 个 AI 分析任务")
        print(f"   状态: {event.status} (已入队，等待 Latest Model Open API 处理)")
        
        return task
    
    def step7_gpu_inference(self, event: Event, task: TaskQueue):
        """步骤 7: 模拟 Latest Model Open API 推理"""
        print("\n" + "=" * 70)
        print("步骤 7: Latest Model Open API 推理处理")
        print("=" * 70)
        
        print("⚠️  此步骤需要运行 Latest Model Open API 测试器:")
        print("   E:/project/full/Scripts/python.exe tests/test_gpu_simulator.py")
        print("\n   或者手动模拟推理结果...")
        
        # 检查是否已有推理结果
        product = self.db.query(Product).filter(Product.uuid == event.uuid).first()
        if product:
            print(f"✅ 推理结果已存在:")
            print(f"   UUID: {product.uuid}")
            result = json.loads(product.inference_result)
            print(f"   任务数: {len(result)} 个")
            return product
        else:
            print("⏳ 等待 Latest Model Open API 返回结果...")
            return None
    
    def step8_generate_summary(self, event: Event):
        """步骤 8: 生成事件摘要（Gemini）"""
        print("\n" + "=" * 70)
        print("步骤 8: 生成事件摘要（Gemini Flash）")
        print("=" * 70)
        
        product = self.db.query(Product).filter(Product.uuid == event.uuid).first()
        if not product:
            print("❌ 未找到推理结果，无法生成摘要")
            return None
        
        # 模拟 Gemini 生成摘要
        summary = f"""
# {event.title}

## 灾害概况
- **类型**: {event.category_name}
- **地点**: {event.country}, {event.address}
- **严重程度**: {event.severity.upper()}
- **发生时间**: {datetime.fromtimestamp(event.event_date/1000).strftime('%Y-%m-%d %H:%M UTC')}

## AI 分析结果
基于卫星遥感影像的 AI 分析显示：

1. **影像描述**: 雅加达市区出现大面积洪水，多栋建筑物被淹没，水体覆盖率显著增加。
2. **损害评估**: 洪水影响范围约 50+ 建筑物，水位高度约 2-3 米。
3. **变化检测**: 与灾前影像对比，新增淹没区域占比 45%，主要集中在低洼居民区。
4. **受损目标**: 检测到 23 栋受损建筑、5 辆被淹车辆、3 处废墟堆积点。

## 建议措施
- 立即组织受灾居民疏散
- 加强排水系统抢修
- 部署应急救援物资

*本报告由 AI 自动生成，基于 Sentinel-2 卫星影像分析*
"""
        
        product.summary = summary.strip()
        product.summary_generated = 1
        product.summary_generated_at = self._now_ms()
        product.updated_at = self._now_ms()
        
        self.db.commit()
        
        print(f"✅ 事件摘要生成成功:")
        print(f"   字数: {len(summary)} 字符")
        print(f"   模型: Gemini Flash (模拟)")
        print(f"\n摘要预览:")
        print(summary[:300] + "...")
        
        return product
    
    def step9_generate_daily_report(self):
        """步骤 9: 生成每日灾害报告（Gemini Pro）"""
        print("\n" + "=" * 70)
        print("步骤 9: 生成每日灾害报告（Gemini Pro）")
        print("=" * 70)
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # 检查是否已有今日报告
        existing = self.db.query(DailyReport).filter(DailyReport.report_date == today).first()
        if existing:
            print(f"⚠️  今日报告已存在: {existing.report_title}")
            return existing
        
        # 统计今日事件
        start_of_day = int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).timestamp() * 1000)
        events = self.db.query(Event).filter(Event.created_at >= start_of_day).all()
        
        # 模拟 Gemini Pro 生成报告
        report_content = f"""
# 全球灾害监测日报 - {today}

## 执行摘要
今日共监测到 {len(events)} 起灾害事件，涵盖洪水、地震等多种类型。本报告基于卫星遥感影像和 AI 分析技术，提供实时灾害评估。

## 重点事件

### 1. 印度尼西亚雅加达洪水灾害
- **严重程度**: 高
- **影响人口**: 约 50 万人
- **AI 分析**: 卫星影像显示大面积淹没区域，建筑物受损严重
- **建议**: 紧急疏散低洼地区居民，加强排水设施

## 灾害分布统计
- **按类型**: 洪水 ({len([e for e in events if e.category == 'FL'])} 起)
- **按严重程度**: 高 ({len([e for e in events if e.severity == 'high'])} 起)
- **按地区**: 亚洲 ({len([e for e in events if e.continent == 'Asia'])} 起)

## 技术说明
- **数据源**: RSOE-EDIS 全球灾害数据库
- **遥感影像**: Sentinel-2 / Landsat 卫星
- **AI 模型**: 多任务灾害识别模型（7 种分析任务）
- **报告生成**: Google Gemini Pro

---
*报告生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""
        
        report = DailyReport(
            report_date=today,
            report_title=f"全球灾害监测日报 - {today}",
            report_content=report_content.strip(),
            event_count=len(events),
            category_stats=json.dumps({"FL": len([e for e in events if e.category == "FL"])}),
            severity_stats=json.dumps({"high": len([e for e in events if e.severity == "high"])}),
            country_stats=json.dumps({"Indonesia": len([e for e in events if e.country == "Indonesia"])}),
            generated_at=self._now_ms(),
            generated_by="gemini-pro (simulated)",
            generation_time_seconds=2.5,
        )
        
        self.db.add(report)
        self.db.commit()
        
        print(f"✅ 每日报告生成成功:")
        print(f"   日期: {today}")
        print(f"   事件数: {len(events)}")
        print(f"   字数: {len(report_content)} 字符")
        print(f"\n报告预览:")
        print(report_content[:400] + "...")
        
        return report
    
    def run_full_workflow(self):
        """运行完整工作流"""
        print("\n" + "=" * 70)
        print("🚀 完整工作流模拟器")
        print("=" * 70)
        print("\n本脚本将模拟以下完整流程:")
        print("  1. RSOE 数据抓取 → 创建灾害事件")
        print("  2. 坐标提取 → 从事件详情获取经纬度")
        print("  3. GEE 任务提交 → 请求下载遥感影像")
        print("  4. GEE 影像下载 → 获取灾前/灾后影像")
        print("  5. OpenAI 质量评估 → AI 审查影像质量")
        print("  6. 任务入队 → 创建 GPU 推理任务")
        print("  7. GPU 推理 → AI 分析灾害影像")
        print("  8. Gemini 摘要生成 → 撰写事件分析")
        print("  9. Gemini 日报生成 → 撰写每日报告")
        print()
        
        try:
            # 步骤 1-6: 自动执行
            event = self.step1_create_rsoe_event()
            time.sleep(1)
            
            event = self.step2_extract_coordinates(event)
            time.sleep(1)
            
            pre_task, post_task = self.step3_submit_gee_tasks(event)
            time.sleep(1)
            
            event = self.step4_simulate_gee_download(event, pre_task, post_task)
            time.sleep(1)
            
            event = self.step5_quality_assessment(event)
            time.sleep(1)
            
            task = self.step6_enqueue_task(event)
            time.sleep(1)
            
            # 步骤 7: 需要手动运行 Latest Model Open API 测试器
            product = self.step7_gpu_inference(event, task)
            
            if product:
                # 步骤 8-9: 生成摘要和报告
                time.sleep(1)
                product = self.step8_generate_summary(event)
                time.sleep(1)
                report = self.step9_generate_daily_report()
                
                print("\n" + "=" * 70)
                print("✅ 完整工作流执行成功！")
                print("=" * 70)
                print(f"\n📊 最终结果:")
                print(f"   事件 UUID: {event.uuid}")
                print(f"   事件状态: {event.status}")
                print(f"   推理结果: 已生成")
                print(f"   事件摘要: 已生成")
                print(f"   每日报告: 已生成")
                print(f"\n🌐 查看结果:")
                print(f"   前端界面: http://localhost:2335")
                print(f"   登录账号: user-707")
                print(f"   登录密码: srgYJKmvr953yj")
            else:
                print("\n" + "=" * 70)
                print("⏸️  工作流暂停")
                print("=" * 70)
                print(f"\n下一步操作:")
                print(f"   1. 运行 Latest Model Open API 测试器:")
                print(f"      E:/project/full/Scripts/python.exe tests/test_gpu_simulator.py")
                print(f"\n   2. 再次运行本脚本完成后续步骤:")
                print(f"      E:/project/full/Scripts/python.exe tests/full_workflow_simulator.py --resume")
                
        except Exception as e:
            print(f"\n❌ 工作流执行失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.db.close()


def main():
    import sys
    
    simulator = FullWorkflowSimulator()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--resume":
        # 恢复模式：只执行步骤 7-9
        print("\n🔄 恢复工作流（从 GPU 推理后继续）...")
        db = get_session_factory()()
        event = db.query(Event).filter(Event.event_id == 888888).first()
        if event:
            product = simulator.step7_gpu_inference(event, None)
            if product:
                simulator.step8_generate_summary(event)
                simulator.step9_generate_daily_report()
        db.close()
    else:
        # 完整模式
        simulator.run_full_workflow()


if __name__ == "__main__":
    main()
