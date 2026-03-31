"""
创建测试事件 - 用于快速生成测试数据
"""
import sys
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.models import Event, TaskQueue, get_session_factory
from utils.logger import get_logger

logger = get_logger(__name__)


def _resolve_sample_images() -> tuple[str, str]:
    """优先复用仓库内现有影像，避免生成的测试任务指向不存在的文件。"""
    storage_root = Path(__file__).resolve().parent.parent / "storage" / "images"
    for folder in storage_root.iterdir():
        if not folder.is_dir():
            continue
        pre_path = folder / "pre_disaster.tif"
        post_path = folder / "post_disaster.tif"
        if pre_path.exists() and post_path.exists():
            return str(pre_path), str(post_path)
    raise FileNotFoundError("未在 storage/images 中找到可复用的 pre/post 测试影像")


def create_test_event():
    """创建一个测试灾害事件"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    # 创建测试事件（带坐标，可以进入蓄水池流程）
    event = Event(
        uuid=str(uuid.uuid4()),
        event_id=999999,  # 测试 ID
        sub_id=0,
        title="[TEST] Severe Flooding in Test City",
        category="FL",
        category_name="Flood",
        country="United States",
        severity="high",
        event_date=now_ms,
        last_update=now_ms,
        source_url="https://rsoe-edis.org/eventList/details/999999/0",
        status="pending",
        created_at=now_ms,
        updated_at=now_ms,
        # 添加坐标（美国某地）
        latitude=40.7128,
        longitude=-74.0060,
    )
    
    try:
        db.add(event)
        db.commit()
        print(f"✅ 测试事件创建成功:")
        print(f"   UUID: {event.uuid}")
        print(f"   Event ID: {event.event_id}")
        print(f"   标题: {event.title}")
        print(f"   坐标: ({event.latitude}, {event.longitude})")
        print(f"   状态: {event.status}")
        return event
    except Exception as e:
        db.rollback()
        print(f"❌ 创建失败: {e}")
        return None
    finally:
        db.close()


def create_ready_task():
    """创建一个已入队的测试任务（可直接进入 Latest Model 队列测试）"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    event_uuid = str(uuid.uuid4())
    try:
        pre_image_path, post_image_path = _resolve_sample_images()
    except FileNotFoundError as e:
        print(f"❌ 创建失败: {e}")
        db.close()
        return None, None
    
    # 1. 创建事件
    event = Event(
        uuid=event_uuid,
        event_id=999997,
        sub_id=0,
        title="[TEST] Earthquake Damage Assessment - Ready for AI",
        category="EQ",
        category_name="Earthquake",
        country="Japan",
        severity="extreme",
        event_date=now_ms,
        last_update=now_ms,
        source_url="https://rsoe-edis.org/eventList/details/999997/0",
        status="queued",  # 已入队
        created_at=now_ms,
        updated_at=now_ms,
        latitude=35.6762,
        longitude=139.6503,
        pre_image_downloaded=1,
        post_image_downloaded=1,
        pre_image_path=pre_image_path,
        post_image_path=post_image_path,
        quality_pass=1,
        quality_score=0.92,
    )
    
    # 2. 创建任务队列
    task_data = {
        "uuid": event_uuid,
        "pre_image_url": event.pre_image_path,
        "post_image_url": event.post_image_path,
        "image_path": event.post_image_path,
        "image_kind": "post_disaster",
        "selected_image_type": "post",
        "event_details": {
            "event_id": event.event_id,
            "title": event.title,
            "category": event.category,
            "category_name": event.category_name,
            "country": event.country,
            "severity": event.severity,
            "latitude": event.latitude,
            "longitude": event.longitude,
            "event_date": event.event_date,
            "details": {},
        },
        "tasks": [
            {"task_id": 1, "type": "IMG_CAP", "prompt": "Describe this disaster scene in detail."},
            {"task_id": 2, "type": "IMG_VQA", "prompt": "Is there visible structural damage?"},
            {"task_id": 3, "type": "IMG_CT", "prompt": "Provide a comprehensive damage assessment."},
            {"task_id": 4, "type": "PIX_SEG", "prompt": "Segment the damaged areas."},
            {"task_id": 5, "type": "PIX_CHG", "prompt": "Detect changes between pre and post images."},
            {"task_id": 6, "type": "REG_DET_HBB", "prompt": "Detect damaged buildings and infrastructure."},
            {"task_id": 7, "type": "REG_VG", "prompt": "Locate the most severely damaged region."},
        ]
    }
    
    task = TaskQueue(
        uuid=event_uuid,
        priority=80,  # 高优先级
        status="pending",
        task_data=json.dumps(task_data, ensure_ascii=False),
        created_at=now_ms,
        updated_at=now_ms,
    )
    
    try:
        db.add(event)
        db.add(task)
        db.commit()
        print(f"✅ Latest Model 队列测试任务创建成功:")
        print(f"   UUID: {event.uuid}")
        print(f"   Event ID: {event.event_id}")
        print(f"   标题: {event.title}")
        print(f"   任务状态: {task.status}")
        print(f"   优先级: {task.priority}")
        print(f"   使用影像: {task_data['image_kind']} -> {task_data['image_path']}")
        print(f"\n💡 现在可以运行 Latest Model Open API 测试器验证链路:")
        print(f"   python tests/test_gpu_simulator.py")
        return event, task
    except Exception as e:
        db.rollback()
        print(f"❌ 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("测试数据生成工具")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--ready":
        print("\n创建已入队的测试任务（可直接进入 Latest Model 队列测试）...\n")
        create_ready_task()
    else:
        print("\n创建基础测试事件（需手动推进流程）...\n")
        create_test_event()
        print("\n提示: 使用 --ready 参数创建可直接进入推理队列的任务")
