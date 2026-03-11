"""清理测试数据"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.models import TaskQueue, Event, Product, get_session_factory

db = get_session_factory()()

# 删除测试任务
tasks = db.query(TaskQueue).all()
for t in tasks:
    db.delete(t)
    print(f"✅ 删除任务: {t.uuid[:16]}...")

# 删除测试事件
events = db.query(Event).filter(Event.event_id >= 999990).all()
for e in events:
    db.delete(e)
    print(f"✅ 删除事件: {e.event_id}")

# 删除测试成品
products = db.query(Product).all()
for p in products:
    db.delete(p)
    print(f"✅ 删除成品: {p.uuid[:16]}...")

db.commit()
db.close()
print("\n✅ 所有测试数据已清理")
