"""检查任务数据格式"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.models import TaskQueue, get_session_factory

db = get_session_factory()()

tasks = db.query(TaskQueue).all()
for t in tasks:
    print(f"UUID: {t.uuid[:16]}...")
    print(f"Status: {t.status}")
    print(f"Task Data:")
    try:
        td = json.loads(t.task_data)
        print(json.dumps(td, indent=2, ensure_ascii=False))
        print("\n✅ JSON 格式正确")
    except Exception as e:
        print(f"❌ JSON 解析失败: {e}")
    print("=" * 60)

db.close()
