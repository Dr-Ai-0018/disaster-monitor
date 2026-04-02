from __future__ import annotations

import argparse
from collections import Counter

from sqlalchemy.orm import Session

from models.models import DailyReport, Event, ImageReview, Product, ReportCandidate, SummaryReview, TaskQueue, WorkflowItem, get_session_factory
from services.workflow_service import derive_workflow_state


def _latest_by_uuid(rows):
    result = {}
    for row in rows:
        result.setdefault(row.uuid, row)
    return result


def _load_related_maps(db: Session, uuids: list[str]) -> dict:
    tasks = {row.uuid: row for row in db.query(TaskQueue).filter(TaskQueue.uuid.in_(uuids)).all()}
    products = {row.uuid: row for row in db.query(Product).filter(Product.uuid.in_(uuids)).all()}
    summary_reviews = {row.uuid: row for row in db.query(SummaryReview).filter(SummaryReview.uuid.in_(uuids)).all()}
    report_candidates = _latest_by_uuid(
        db.query(ReportCandidate)
        .filter(ReportCandidate.uuid.in_(uuids), ReportCandidate.included == 1)
        .order_by(ReportCandidate.uuid.asc(), ReportCandidate.updated_at.desc(), ReportCandidate.id.desc())
        .all()
    )
    image_reviews = _latest_by_uuid(
        db.query(ImageReview)
        .filter(ImageReview.uuid.in_(uuids))
        .order_by(ImageReview.uuid.asc(), ImageReview.updated_at.desc(), ImageReview.id.desc())
        .all()
    )
    report_dates = {row.report_date for row in report_candidates.values()}
    daily_reports = {}
    if report_dates:
        daily_reports = {
            row.report_date: row
            for row in db.query(DailyReport).filter(DailyReport.report_date.in_(report_dates)).all()
        }
    return {
        "tasks": tasks,
        "products": products,
        "summary_reviews": summary_reviews,
        "report_candidates": report_candidates,
        "image_reviews": image_reviews,
        "daily_reports": daily_reports,
    }


def _target_events(db: Session, only_uuid: str | None) -> list[Event]:
    query = (
        db.query(Event)
        .join(TaskQueue, TaskQueue.uuid == Event.uuid)
        .join(Product, Product.uuid == Event.uuid)
        .outerjoin(ImageReview, ImageReview.uuid == Event.uuid)
        .filter(TaskQueue.status == "completed", ImageReview.uuid.is_(None))
        .order_by(Event.updated_at.desc())
    )
    if only_uuid:
        query = query.filter(Event.uuid == only_uuid)
    return query.all()


def _apply_state(item: WorkflowItem, new_state: dict, now_ms: int) -> bool:
    pool_changed = item.current_pool != new_state["current_pool"] or item.pool_status != new_state["pool_status"]
    field_changed = (
        pool_changed
        or item.auto_stage != new_state["auto_stage"]
        or item.manual_stage != new_state["manual_stage"]
        or item.selected_image_type != new_state["selected_image_type"]
    )
    if not field_changed:
        return False

    item.current_pool = new_state["current_pool"]
    item.pool_status = new_state["pool_status"]
    item.auto_stage = new_state["auto_stage"]
    item.manual_stage = new_state["manual_stage"]
    item.selected_image_type = new_state["selected_image_type"]
    item.updated_at = now_ms
    if pool_changed or not item.last_transition_at:
        item.last_transition_at = now_ms
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair legacy workflow_items for completed products without image_reviews")
    parser.add_argument("--apply", action="store_true", help="Persist changes. Default is dry-run.")
    parser.add_argument("--uuid", help="Only inspect/repair a single UUID.")
    parser.add_argument("--limit", type=int, default=20, help="Sample rows to print.")
    args = parser.parse_args()

    db = get_session_factory()()
    try:
        events = _target_events(db, args.uuid)
        uuids = [event.uuid for event in events]
        related = _load_related_maps(db, uuids)
        workflow_items = {row.uuid: row for row in db.query(WorkflowItem).filter(WorkflowItem.uuid.in_(uuids)).all()}

        print(f"mode={'apply' if args.apply else 'dry-run'}")
        print(f"matched={len(events)}")

        transitions = Counter()
        changed = 0
        samples: list[dict] = []

        for event in events:
            item = workflow_items.get(event.uuid)
            if item is None:
                continue

            state = derive_workflow_state(
                event=event,
                task=related["tasks"].get(event.uuid),
                product=related["products"].get(event.uuid),
                image_review=related["image_reviews"].get(event.uuid),
                summary_review=related["summary_reviews"].get(event.uuid),
                report_candidate=related["report_candidates"].get(event.uuid),
                daily_report=related["daily_reports"].get(
                    related["report_candidates"].get(event.uuid).report_date
                ) if related["report_candidates"].get(event.uuid) else None,
            )

            before = (item.current_pool, item.pool_status)
            after = (state["current_pool"], state["pool_status"])
            transitions[f"{before[0]}/{before[1]} -> {after[0]}/{after[1]}"] += 1

            if len(samples) < args.limit:
                samples.append(
                    {
                        "uuid": event.uuid,
                        "title": event.title,
                        "before_pool": item.current_pool,
                        "before_status": item.pool_status,
                        "after_pool": state["current_pool"],
                        "after_status": state["pool_status"],
                        "selected_image_type": state["selected_image_type"],
                    }
                )

            if args.apply and _apply_state(item, state, event.updated_at or item.updated_at or 0):
                changed += 1

        print("\ntransitions:")
        for key, count in transitions.most_common():
            print(f"  {count:>5}  {key}")

        print("\nsamples:")
        for row in samples:
            print(row)

        if args.apply:
            db.commit()
            print(f"\nupdated={changed}")
        else:
            print("\ndry-run only; no changes committed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
