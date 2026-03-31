"""
分阶段工作流测试器

用法示例:
  python tests/workflow_stage_tester.py inspect --uuid <UUID>
  python tests/workflow_stage_tester.py quality --uuid <UUID>
  python tests/workflow_stage_tester.py inference --uuid <UUID>
  python tests/workflow_stage_tester.py summary --uuid <UUID>
  python tests/workflow_stage_tester.py report --date 2026-03-31
  python tests/workflow_stage_tester.py all --uuid <UUID> --date 2026-03-31
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.models import Event, Product, TaskQueue, get_session_factory
from core.pool_manager import PoolManager
from core.quality_assessor import QualityAssessor
from core.report_generator import ReportGenerator
from utils.task_progress import safe_json_loads


def print_json(title: str, data) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def inspect_event(db, uuid: str) -> dict:
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise SystemExit(f"事件不存在: {uuid}")

    payload = {
        "uuid": event.uuid,
        "title": event.title,
        "status": event.status,
        "pre_image_path": event.pre_image_path,
        "pre_exists": bool(event.pre_image_path and Path(event.pre_image_path).exists()),
        "post_image_path": event.post_image_path,
        "post_exists": bool(event.post_image_path and Path(event.post_image_path).exists()),
        "quality_checked": bool(event.quality_checked),
        "quality_pass": bool(event.quality_pass),
        "quality_score": event.quality_score,
    }
    print_json("EVENT", payload)
    return payload


def inspect_task(db, uuid: str) -> Optional[dict]:
    task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    if not task:
        print("\n=== TASK ===")
        print("任务不存在")
        return None

    task_data = safe_json_loads(task.task_data, {})
    payload = {
        "uuid": task.uuid,
        "status": task.status,
        "progress_stage": task.progress_stage,
        "progress_message": task.progress_message,
        "image_path": task_data.get("image_path"),
        "image_kind": task_data.get("image_kind"),
        "selected_image_type": task_data.get("selected_image_type"),
        "retry_count": task.retry_count,
        "failure_reason": task.failure_reason,
    }
    print_json("TASK", payload)
    return payload


def run_quality(db, uuid: str) -> None:
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise SystemExit(f"事件不存在: {uuid}")
    if not event.pre_image_path or not event.post_image_path:
        raise SystemExit("质量评估需要同时具备 pre/post 两张影像")

    qa = QualityAssessor()
    result = qa.assess_pair(event.pre_image_path, event.post_image_path)
    print_json("QUALITY_RESULT", result)


def run_inference(db, uuid: str) -> None:
    pm = PoolManager(db)
    processed = pm.process_pending_inference_tasks(limit=1, target_uuid=uuid)
    print_json("INFERENCE", {"processed": processed})
    inspect_task(db, uuid)


def run_summary(db, uuid: str, persist: bool = False) -> None:
    product = db.query(Product).filter(Product.uuid == uuid).first()
    if not product:
        raise SystemExit(f"成品不存在: {uuid}")

    rg = ReportGenerator()
    summary = rg.generate_event_summary(product)
    print_json("SUMMARY", {"uuid": uuid, "summary": summary})

    if persist and summary:
        from datetime import datetime, timezone

        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        product.summary = summary
        product.summary_generated = 1
        product.summary_generated_at = now_ms
        product.updated_at = now_ms
        db.commit()
        print("摘要已写回数据库")


def run_report(db, report_date: str) -> None:
    rg = ReportGenerator()
    report = rg.generate_daily_report(db, report_date)
    if not report:
        print_json("REPORT", {"date": report_date, "created": False})
        return

    print_json("REPORT", {
        "date": report.report_date,
        "title": report.report_title,
        "event_count": report.event_count,
        "published": bool(report.published),
    })


def main() -> None:
    parser = argparse.ArgumentParser(description="分阶段工作流测试器")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_inspect = subparsers.add_parser("inspect", help="检查事件/任务/成品基础状态")
    p_inspect.add_argument("--uuid", required=True)

    p_quality = subparsers.add_parser("quality", help="单独测试 AI 质检")
    p_quality.add_argument("--uuid", required=True)

    p_inference = subparsers.add_parser("inference", help="单独消费指定 UUID 的推理任务")
    p_inference.add_argument("--uuid", required=True)

    p_summary = subparsers.add_parser("summary", help="单独测试单事件摘要生成")
    p_summary.add_argument("--uuid", required=True)
    p_summary.add_argument("--persist", action="store_true")

    p_report = subparsers.add_parser("report", help="单独测试日报生成")
    p_report.add_argument("--date", required=True)

    p_all = subparsers.add_parser("all", help="串行跑检查/质检/推理/摘要/日报")
    p_all.add_argument("--uuid", required=True)
    p_all.add_argument("--date", required=True)
    p_all.add_argument("--persist-summary", action="store_true")

    args = parser.parse_args()
    db = get_session_factory()()
    try:
        if args.command == "inspect":
            inspect_event(db, args.uuid)
            inspect_task(db, args.uuid)
            product = db.query(Product).filter(Product.uuid == args.uuid).first()
            print_json("PRODUCT", {
                "exists": bool(product),
                "summary_generated": bool(product.summary_generated) if product else False,
            })
        elif args.command == "quality":
            run_quality(db, args.uuid)
        elif args.command == "inference":
            run_inference(db, args.uuid)
        elif args.command == "summary":
            run_summary(db, args.uuid, persist=args.persist)
        elif args.command == "report":
            run_report(db, args.date)
        elif args.command == "all":
            inspect_event(db, args.uuid)
            inspect_task(db, args.uuid)
            run_quality(db, args.uuid)
            run_inference(db, args.uuid)
            run_summary(db, args.uuid, persist=args.persist_summary)
            run_report(db, args.date)
    finally:
        db.close()


if __name__ == "__main__":
    main()
