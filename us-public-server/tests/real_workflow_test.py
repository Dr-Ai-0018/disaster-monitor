"""
真实完整工作流测试
除了 GPU 模型推理，所有步骤都调用真实 API
"""
import sys
import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.models import Event, GeeTask, TaskQueue, Product, DailyReport, get_session_factory
from core.rsoe_spider import RsoeSpider
from core.gee_manager import GeeManager, initialize_gee
from core.quality_assessor import QualityAssessor
from core.pool_manager import PoolManager
from core.report_generator import ReportGenerator
from utils.logger import get_logger

logger = get_logger(__name__)


class RealWorkflowTest:
    """真实工作流测试器"""
    
    def __init__(self):
        self.db = get_session_factory()()
        self.rsoe_spider = RsoeSpider()
        self.gee_manager = GeeManager()
        self.quality_assessor = QualityAssessor()
        self.pool_manager = PoolManager(self.db)
        self.report_generator = ReportGenerator()
        
    def _now_ms(self):
        return int(datetime.now(timezone.utc).timestamp() * 1000)
    
    def step1_fetch_rsoe_data(self):
        """步骤 1: 真实抓取 RSOE 数据"""
        print("\n" + "=" * 70)
        print("步骤 1: 抓取 RSOE 真实灾害数据")
        print("=" * 70)
        
        # 真实调用 RSOE API（直接返回事件列表）
        events = self.rsoe_spider.fetch_event_list()
        if not events:
            print("❌ 未抓取到任何事件")
            return None
        
        print(f"✅ 成功抓取 {len(events)} 个事件")
        
        # 选择一个有坐标且较早的事件进行测试（至少 7 天前，确保有灾后影像）
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        seven_days_ago = int((now - timedelta(days=7)).timestamp() * 1000)
        
        event_data = None
        for evt in events:
            if evt.get('longitude') and evt.get('latitude'):
                # 优先选择较早的事件
                evt_date = evt.get('event_date')
                if evt_date and evt_date < seven_days_ago:
                    event_data = evt
                    break
        
        # 如果没有找到旧事件，选择任意有坐标的事件
        if not event_data:
            for evt in events:
                if evt.get('longitude') and evt.get('latitude'):
                    event_data = evt
                    break
        
        if not event_data:
            print("❌ 未找到有坐标的事件")
            return None
        
        print(f"\n选择测试事件:")
        print(f"   Event ID: {event_data['event_id']}")
        print(f"   标题: {event_data['title']}")
        print(f"   类别: {event_data['category']}")
        print(f"   国家: {event_data['country']}")
        print(f"   严重程度: {event_data['severity']}")
        print(f"   坐标: ({event_data['latitude']}, {event_data['longitude']})")
        
        # 创建事件记录
        now_ms = self._now_ms()
        event_uuid = str(uuid.uuid4())
        
        event = Event(
            uuid=event_uuid,
            event_id=event_data['event_id'],
            sub_id=event_data['sub_id'],
            title=event_data['title'],
            category=event_data['category'],
            country=event_data['country'],
            continent=event_data.get('continent', ''),
            severity=event_data['severity'],
            longitude=event_data['longitude'],
            latitude=event_data['latitude'],
            event_date=event_data.get('event_date') or now_ms,
            last_update=event_data.get('last_update') or now_ms,
            source_url=event_data['source_url'],
            status="pool",
            created_at=now_ms,
            updated_at=now_ms,
        )
        
        self.db.add(event)
        self.db.commit()
        
        print(f"✅ 事件已保存到数据库")
        print(f"   UUID: {event.uuid}")
        print(f"   状态: {event.status}")
        
        return event
    
    def step2_extract_coordinates(self, event: Event):
        """步骤 2: 验证坐标（API 已返回）"""
        print("\n" + "=" * 70)
        print("步骤 2: 验证事件坐标")
        print("=" * 70)
        
        if not event.longitude or not event.latitude:
            print("❌ 事件缺少坐标")
            return None
        
        print(f"✅ 坐标已就绪:")
        print(f"   经度: {event.longitude}")
        print(f"   纬度: {event.latitude}")
        print(f"   地址: {event.country}")
        print(f"   状态: {event.status}")
        
        return event
    
    def step3_submit_gee_tasks(self, event: Event):
        """步骤 3: 真实提交 GEE 影像下载任务"""
        print("\n" + "=" * 70)
        print("步骤 3: 提交 GEE 影像下载任务")
        print("=" * 70)
        
        # 初始化 GEE
        if not initialize_gee():
            print("❌ GEE 初始化失败，无法下载影像")
            return None, None
        
        now_ms = self._now_ms()
        
        # 提交灾前影像任务
        print("   提交灾前影像下载任务...")
        pre_task_id = self.gee_manager.submit_download_task(
            event.uuid,
            event.longitude,
            event.latitude,
            event.event_date,
            task_type="pre_disaster"
        )
        
        if not pre_task_id:
            print("❌ 灾前影像任务提交失败")
            return None, None
        
        # 提交灾后影像任务
        print("   提交灾后影像下载任务...")
        post_task_id = self.gee_manager.submit_download_task(
            event.uuid,
            event.longitude,
            event.latitude,
            event.event_date,
            task_type="post_disaster"
        )
        
        if not post_task_id:
            print("❌ 灾后影像任务提交失败")
            return None, None
        
        # 创建 GEE 任务记录
        event_date = datetime.fromtimestamp(event.event_date / 1000, tz=timezone.utc)
        
        pre_start = (event_date - timedelta(days=60)).strftime("%Y-%m-%d")
        pre_end = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
        
        pre_task = GeeTask(
            uuid=event.uuid,
            task_type="pre_disaster",
            status="SUBMITTED",
            gee_task_id=pre_task_id,
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
        
        post_start = event_date.strftime("%Y-%m-%d")
        post_end = (event_date + timedelta(days=30)).strftime("%Y-%m-%d")
        
        post_task = GeeTask(
            uuid=event.uuid,
            task_type="post_disaster",
            status="SUBMITTED",
            gee_task_id=post_task_id,
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
        
        print(f"✅ GEE 任务提交成功:")
        print(f"   灾前影像: {pre_start} ~ {pre_end} (Task ID: {pre_task_id[:20]}...)")
        print(f"   灾后影像: {post_start} ~ {post_end} (Task ID: {post_task_id[:20]}...)")
        print(f"   ⏳ GEE 正在异步处理，请等待下载完成...")
        
        return pre_task, post_task
    
    def step4_wait_gee_download(self, event: Event, pre_task: GeeTask, post_task: GeeTask):
        """步骤 4: 等待 GEE 影像下载完成"""
        print("\n" + "=" * 70)
        print("步骤 4: 等待 GEE 影像下载")
        print("=" * 70)
        
        print("⏳ 正在轮询 GEE 任务状态...")
        max_wait = 300  # 最多等待 5 分钟
        interval = 10
        elapsed = 0
        
        while elapsed < max_wait:
            # 检查任务状态
            pre_status = self.gee_manager.check_task_status(pre_task.gee_task_id)
            post_status = self.gee_manager.check_task_status(post_task.gee_task_id)
            
            print(f"   [{elapsed}s] 灾前: {pre_status} | 灾后: {post_status}")
            
            if pre_status == "COMPLETED" and post_status == "COMPLETED":
                print("✅ 影像下载完成！")
                
                # 更新任务状态
                now_ms = self._now_ms()
                
                pre_task.status = "COMPLETED"
                pre_task.completed_at = now_ms
                pre_task.updated_at = now_ms
                
                post_task.status = "COMPLETED"
                post_task.completed_at = now_ms
                post_task.updated_at = now_ms
                
                # 更新事件
                event.pre_image_path = pre_task.download_url
                event.pre_image_date = pre_task.image_date
                event.pre_image_source = pre_task.image_source
                event.pre_image_downloaded = 1
                
                event.post_image_path = post_task.download_url
                event.post_image_date = post_task.image_date
                event.post_image_source = post_task.image_source
                event.post_image_downloaded = 1
                
                event.status = "ready"
                event.updated_at = now_ms
                
                self.db.commit()
                
                print(f"   灾前影像: {event.pre_image_path}")
                print(f"   灾后影像: {event.post_image_path}")
                
                return True
            
            if pre_status == "FAILED" or post_status == "FAILED":
                print("❌ GEE 任务失败")
                return False
            
            time.sleep(interval)
            elapsed += interval
        
        print("⏰ 等待超时，请稍后手动检查")
        return False
    
    def step5_quality_assessment(self, event: Event):
        """步骤 5: 真实调用 OpenAI 质量评估"""
        print("\n" + "=" * 70)
        print("步骤 5: AI 质量评估（OpenAI）")
        print("=" * 70)
        
        # 真实调用 OpenAI API 评估双影像
        result = self.quality_assessor.assess_pair(event.pre_image_path, event.post_image_path)
        
        if not result:
            print("❌ 质量评估失败")
            return None
        
        # 更新事件质量信息
        now_ms = self._now_ms()
        event.quality_score = result.get("score", 0)
        event.quality_assessment = json.dumps(result, ensure_ascii=False)
        event.quality_checked = 1
        event.quality_pass = 1 if result.get("pass") else 0
        event.quality_check_time = now_ms
        event.updated_at = now_ms
        
        if result.get("pass"):
            event.status = "checked"
        
        self.db.commit()
        
        print(f"✅ 质量评估完成:")
        print(f"   评分: {event.quality_score}")
        print(f"   通过: {'是' if event.quality_pass else '否'}")
        print(f"   云量: {result.get('cloud_coverage', 'N/A')}%")
        print(f"   清晰度: {result.get('clarity', 'N/A')}")
        print(f"   建议: {result.get('recommendation', 'N/A')}")
        print(f"   状态: {event.status}")
        
        return event
    
    def step6_enqueue_task(self, event: Event):
        """步骤 6: 创建 GPU 任务队列"""
        print("\n" + "=" * 70)
        print("步骤 6: 创建 GPU 推理任务")
        print("=" * 70)
        
        # 调用 PoolManager 自动入队
        count = self.pool_manager.enqueue_checked_events(limit=1)
        
        if count == 0:
            print("❌ 任务创建失败")
            return None
        
        # 查询任务
        task = self.db.query(TaskQueue).filter(TaskQueue.uuid == event.uuid).first()
        
        if not task:
            print("❌ 任务创建失败")
            return None
        
        print(f"✅ GPU 任务创建成功:")
        print(f"   UUID: {task.uuid}")
        print(f"   优先级: {task.priority}")
        print(f"   状态: {task.status}")
        
        return task
    
    def step7_gpu_inference(self, event: Event):
        """步骤 7: Latest Model Open API 推理（需手动运行测试器）"""
        print("\n" + "=" * 70)
        print("步骤 7: Latest Model Open API 推理处理")
        print("=" * 70)
        
        print("⚠️  此步骤需要运行 Latest Model Open API 测试器:")
        print("   E:/project/full/Scripts/python.exe tests/test_gpu_simulator.py")
        print("\n   测试器会直接调用 Latest Model Open API 并返回模拟/真实结果")
        
        # 检查是否已有推理结果
        product = self.db.query(Product).filter(Product.uuid == event.uuid).first()
        if product:
            print(f"✅ 推理结果已存在")
            return product
        else:
            print("⏳ 等待 Latest Model Open API 返回结果...")
            return None
    
    def step8_generate_summary(self, event: Event):
        """步骤 8: 真实调用 Gemini 生成事件摘要"""
        print("\n" + "=" * 70)
        print("步骤 8: 生成事件摘要（Gemini Flash）")
        print("=" * 70)
        
        product = self.db.query(Product).filter(Product.uuid == event.uuid).first()
        if not product:
            print("❌ 未找到推理结果，无法生成摘要")
            return None
        
        # 真实调用 Gemini API
        summary = self.report_generator.generate_event_summary(product)
        
        if not summary:
            print("❌ 摘要生成失败")
            return None
        
        # 更新成品
        now_ms = self._now_ms()
        product.summary = summary
        product.summary_generated = 1
        product.summary_generated_at = now_ms
        product.updated_at = now_ms
        self.db.commit()
        
        print(f"✅ 事件摘要生成成功:")
        print(f"   字数: {len(summary)} 字符")
        print(f"\n摘要预览:")
        print(summary[:300] + "...")
        
        return product
    
    def step9_generate_daily_report(self):
        """步骤 9: 真实调用 Gemini 生成每日报告"""
        print("\n" + "=" * 70)
        print("步骤 9: 生成每日灾害报告（Gemini Pro）")
        print("=" * 70)
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # 检查是否已有今日报告
        existing = self.db.query(DailyReport).filter(DailyReport.report_date == today).first()
        if existing:
            print(f"⚠️  今日报告已存在: {existing.report_title}")
            return existing
        
        # 真实调用 Gemini API
        report = self.report_generator.generate_daily_report(self.db, today)
        
        if not report:
            print("❌ 报告生成失败")
            return None
        
        print(f"✅ 每日报告生成成功:")
        print(f"   日期: {today}")
        print(f"   事件数: {report.event_count}")
        print(f"   字数: {len(report.report_content)} 字符")
        print(f"\n报告预览:")
        print(report.report_content[:400] + "...")
        
        return report
    
    def run(self):
        """运行完整真实工作流"""
        print("\n" + "=" * 70)
        print("🚀 真实完整工作流测试")
        print("=" * 70)
        print("\n本测试将真实调用以下 API:")
        print("  ✅ RSOE API - 抓取真实灾害数据")
        print("  ✅ Google Earth Engine - 下载真实遥感影像")
        print("  ✅ OpenAI API - AI 质量评估")
        print("  ✅ Google Gemini API - 生成摘要和报告")
        print("  🔧 GPU 推理 - 使用模拟器（唯一模拟部分）")
        print()
        
        try:
            # 步骤 1-2: 抓取 RSOE 数据并提取坐标
            event = self.step1_fetch_rsoe_data()
            if not event:
                return
            
            time.sleep(2)
            
            event = self.step2_extract_coordinates(event)
            if not event:
                print("⚠️  该事件无坐标，无法继续")
                return
            
            time.sleep(2)
            
            # 步骤 3-4: GEE 影像下载
            pre_task, post_task = self.step3_submit_gee_tasks(event)
            if not pre_task or not post_task:
                return
            
            success = self.step4_wait_gee_download(event, pre_task, post_task)
            if not success:
                print("⚠️  GEE 下载未完成，请稍后手动检查")
                print(f"   可运行: python tests/check_gee_status.py {event.uuid}")
                return
            
            time.sleep(2)
            
            # 步骤 5: OpenAI 质量评估
            event = self.step5_quality_assessment(event)
            if not event or not event.quality_pass:
                print("⚠️  质量评估未通过，流程终止")
                return
            
            time.sleep(2)
            
            # 步骤 6: 任务入队
            task = self.step6_enqueue_task(event)
            if not task:
                return
            
            time.sleep(2)
            
            # 步骤 7: GPU 推理（需手动）
            product = self.step7_gpu_inference(event)
            
            if product:
                # 步骤 8-9: 生成摘要和报告
                time.sleep(2)
                product = self.step8_generate_summary(event)
                
                time.sleep(2)
                report = self.step9_generate_daily_report()
                
                print("\n" + "=" * 70)
                print("✅ 完整工作流执行成功！")
                print("=" * 70)
                print(f"\n📊 最终结果:")
                print(f"   事件 UUID: {event.uuid}")
                print(f"   事件 ID: {event.event_id}")
                print(f"   标题: {event.title}")
                print(f"   状态: {event.status}")
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
                print(f"      E:/project/full/Scripts/python.exe tests/real_workflow_test.py --resume {event.uuid}")
                
        except Exception as e:
            print(f"\n❌ 工作流执行失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.db.close()


def main():
    import sys
    
    tester = RealWorkflowTest()
    
    if len(sys.argv) > 2 and sys.argv[1] == "--resume":
        # 恢复模式
        event_uuid = sys.argv[2]
        print(f"\n🔄 恢复工作流（UUID: {event_uuid}）...")
        
        db = get_session_factory()()
        event = db.query(Event).filter(Event.uuid == event_uuid).first()
        
        if not event:
            print(f"❌ 未找到事件: {event_uuid}")
            db.close()
            return
        
        product = tester.step7_gpu_inference(event)
        if product:
            tester.step8_generate_summary(event)
            tester.step9_generate_daily_report()
        
        db.close()
    else:
        # 完整模式
        tester.run()


if __name__ == "__main__":
    main()
