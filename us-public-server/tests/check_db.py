"""检查数据库中的任务状态"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.models import TaskQueue, Event, get_session_factory

db = get_session_factory()()

print("=" * 60)
print("数据库任务状态检查")
print("=" * 60)

# 检查任务队列
tasks = db.query(TaskQueue).all()
print(f"\n任务队列中共 {len(tasks)} 个任务:")
for t in tasks:
    print(f"  UUID: {t.uuid[:16]}...")
    print(f"    status: {t.status}")
    print(f"    priority: {t.priority}")
    print(f"    locked_until: {t.locked_until}")
    print(f"    created_at: {t.created_at}")
    print()

# 检查事件
events = db.query(Event).filter(Event.event_id >= 999990).all()
print(f"\n测试事件共 {len(events)} 个:")
for e in events:
    print(f"  Event ID: {e.event_id}")
    print(f"    UUID: {e.uuid[:16]}...")
    print(f"    title: {e.title[:50]}")
    print(f"    status: {e.status}")
    print()

db.close()
