"""重置任务状态为 pending"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.models import TaskQueue, Event, get_session_factory

db = get_session_factory()()

# 重置所有测试任务
tasks = db.query(TaskQueue).all()
for t in tasks:
    t.status = "pending"
    t.locked_by = None
    t.locked_at = None
    t.locked_until = None
    t.heartbeat = None
    print(f"✅ 重置任务: {t.uuid[:16]}... -> pending")

# 重置关联事件
events = db.query(Event).filter(Event.event_id >= 999990).all()
for e in events:
    if e.status in ["processing", "locked"]:
        e.status = "queued"
        print(f"✅ 重置事件: {e.event_id} -> queued")

db.commit()
db.close()
print("\n✅ 所有测试任务已重置为 pending 状态")
