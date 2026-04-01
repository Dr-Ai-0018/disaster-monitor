from __future__ import annotations

import json
import subprocess
import textwrap

from config.settings import settings

LEGACY_RUNNER = textwrap.dedent(
    """
    import json
    import os
    import sqlite3
    import sys
    import time
    from datetime import datetime, timezone

    legacy_root = sys.argv[1]
    action = sys.argv[2]
    payload = json.loads(sys.argv[3])

    os.chdir(legacy_root)
    if legacy_root not in sys.path:
        sys.path.insert(0, legacy_root)

    from config.settings import settings
    from core.pool_manager import PoolManager
    from core.report_generator import ReportGenerator
    from models.models import DailyReport, Event, Product, TaskQueue, get_session_factory
    from utils.helpers import safe_json_loads

    def now_ms():
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    def emit(obj, code=0):
        print(json.dumps(obj, ensure_ascii=False))
        raise SystemExit(code)

    db = get_session_factory()()
    try:
        if action == "trigger_inference":
            uuid = payload["uuid"]
            selected_image_type = payload.get("selected_image_type")
            event = db.query(Event).filter(Event.uuid == uuid).first()
            if not event:
                emit({"ok": False, "error": "事件不存在"}, 2)

            task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
            pm = PoolManager(db)
            if task and selected_image_type:
                task_data = safe_json_loads(task.task_data, {}) or {}
                rebuilt = pm._build_task_data(event, preferred_image_type=selected_image_type)
                task_data["image_path"] = rebuilt.get("image_path")
                task_data["image_kind"] = rebuilt.get("image_kind")
                task_data["selected_image_type"] = selected_image_type
                task_data["tasks"] = rebuilt.get("tasks") or task_data.get("tasks") or []
                task_data["event_details"] = rebuilt.get("event_details") or task_data.get("event_details")
                task.task_data = json.dumps(task_data, ensure_ascii=False)
                task.updated_at = now_ms()
                db.commit()

            processed = 0
            refreshed = db.query(Event).filter(Event.uuid == uuid).first()
            current_status = refreshed.status if refreshed else event.status
            if current_status == "pending":
                processed = pm.process_pending_events(limit=1)
            elif current_status == "pool":
                pm.submit_gee_tasks_for_pool(limit=1)
                pm.assess_ready_events(limit=1)
            elif current_status == "checked":
                pm.enqueue_checked_events(limit=1, target_uuid=uuid, preferred_image_type=selected_image_type)
                processed = pm.process_pending_inference_tasks(limit=1, target_uuid=uuid)
            elif current_status == "queued":
                processed = pm.process_pending_inference_tasks(limit=1, target_uuid=uuid)

            event = db.query(Event).filter(Event.uuid == uuid).first()
            task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
            product = db.query(Product).filter(Product.uuid == uuid).first()
            emit(
                {
                    "ok": True,
                    "processed": processed,
                    "event_status": event.status if event else None,
                    "task_status": task.status if task else None,
                    "product_ready": bool(product and product.inference_result),
                }
            )

        if action == "generate_summary":
            uuid = payload["uuid"]
            persist = bool(payload.get("persist", True))
            product = db.query(Product).filter(Product.uuid == uuid).first()
            if not product:
                emit({"ok": False, "error": "成品不存在，请先完成推理"}, 2)

            rg = ReportGenerator()
            summary = rg.generate_event_summary(product)
            if not summary:
                emit({"ok": False, "error": "摘要生成失败"}, 2)

            if persist:
                stamp = now_ms()
                product.summary = summary
                product.summary_generated = 1
                product.summary_generated_at = stamp
                product.updated_at = stamp
                db.commit()

            emit({"ok": True, "summary": summary, "persisted": persist})

        if action == "generate_candidate_report":
            report_date = payload["report_date"]
            conn = sqlite3.connect(payload["database_path"])
            try:
                rows = conn.execute(
                    "SELECT uuid FROM report_candidates WHERE report_date = ? AND included = 1 ORDER BY updated_at DESC, id DESC",
                    (report_date,),
                ).fetchall()
            finally:
                conn.close()

            uuids = [row[0] for row in rows]
            if not uuids:
                emit({"ok": False, "error": f"日期 {report_date} 没有准入日报的候选事件"}, 2)

            products = db.query(Product).filter(Product.uuid.in_(uuids)).all()
            if not products:
                emit({"ok": False, "error": "候选事件缺少成品，无法生成日报"}, 2)

            rg = ReportGenerator()
            for product in products:
                if not product.summary:
                    product.summary = rg.generate_event_summary(product)
                    if product.summary:
                        product.summary_generated = 1
                        product.summary_generated_at = now_ms()
            db.commit()

            category_stats = {}
            severity_stats = {}
            country_stats = {}
            summaries = []

            for product in products:
                if product.event_category:
                    category_stats[product.event_category] = category_stats.get(product.event_category, 0) + 1
                if product.event_country:
                    country_stats[product.event_country] = country_stats.get(product.event_country, 0) + 1
                event = db.query(Event).filter(Event.uuid == product.uuid).first()
                if event and event.severity:
                    severity_stats[event.severity] = severity_stats.get(event.severity, 0) + 1
                summaries.append(
                    f"**{product.event_title or 'Unknown'}** ({product.event_country or 'N/A'}): "
                    f"{(product.summary or 'No summary available.')[:300]}"
                )

            if settings.GEMINI_API_KEY:
                report_content = rg._call_gemini_pro(
                    report_date,
                    summaries,
                    category_stats,
                    severity_stats,
                    country_stats,
                )
            else:
                report_content = rg._generate_fallback_report(
                    report_date,
                    products,
                    category_stats,
                    severity_stats,
                    country_stats,
                )

            stamp = now_ms()
            existing = db.query(DailyReport).filter(DailyReport.report_date == report_date).first()
            if existing:
                existing.report_content = report_content
                existing.report_title = f"全球灾害监测日报 — {report_date}"
                existing.event_count = len(products)
                existing.category_stats = json.dumps(category_stats, ensure_ascii=False)
                existing.severity_stats = json.dumps(severity_stats, ensure_ascii=False)
                existing.country_stats = json.dumps(country_stats, ensure_ascii=False)
                existing.generated_at = stamp
                existing.generation_time_seconds = 0
                report = existing
            else:
                report = DailyReport(
                    report_date=report_date,
                    report_content=report_content,
                    report_title=f"全球灾害监测日报 — {report_date}",
                    event_count=len(products),
                    category_stats=json.dumps(category_stats, ensure_ascii=False),
                    severity_stats=json.dumps(severity_stats, ensure_ascii=False),
                    country_stats=json.dumps(country_stats, ensure_ascii=False),
                    generated_at=stamp,
                    generated_by=settings.GEMINI_PRO_MODEL,
                    generation_time_seconds=0,
                    published=0,
                )
                db.add(report)
            db.commit()
            emit(
                {
                    "ok": True,
                    "report_date": report.report_date,
                    "report_title": report.report_title,
                    "event_count": report.event_count,
                    "published": bool(report.published),
                }
            )

        emit({"ok": False, "error": f"unknown action: {action}"}, 2)
    except SystemExit:
        raise
    except Exception as exc:
        emit({"ok": False, "error": str(exc)}, 1)
    finally:
        db.close()
    """
).strip()


def run_legacy_action(action: str, payload: dict) -> dict:
    command = [
        settings.LEGACY_PYTHON,
        "-c",
        LEGACY_RUNNER,
        str(settings.LEGACY_ROOT),
        action,
        json.dumps(payload, ensure_ascii=False),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if not stdout:
        raise RuntimeError(stderr or f"legacy action failed: {action}")
    try:
        data = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(stderr or stdout) from exc
    if result.returncode != 0 or not data.get("ok"):
        raise RuntimeError(data.get("error") or stderr or f"legacy action failed: {action}")
    return data
