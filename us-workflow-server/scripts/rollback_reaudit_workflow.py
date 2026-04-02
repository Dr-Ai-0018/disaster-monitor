from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.models import WorkflowItem, get_session_factory
from services.workflow_service import rollback_to_reaudit_pool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将分析池/摘要池事件批量打回待审核或影像准备池。")
    parser.add_argument("--apply", action="store_true", help="真正写入数据库；默认仅 dry-run")
    parser.add_argument(
        "--pool",
        dest="pools",
        action="append",
        choices=["inference_pool", "summary_report_pool"],
        help="限定需要处理的池子，可重复传入；默认同时处理 inference_pool 和 summary_report_pool",
    )
    parser.add_argument("--uuid", action="append", help="只处理指定 UUID，可重复传入")
    parser.add_argument("--sample-limit", type=int, default=20, help="输出样本数量，默认 20")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pools = args.pools or ["inference_pool", "summary_report_pool"]

    session = get_session_factory()()
    try:
        query = session.query(WorkflowItem).filter(WorkflowItem.current_pool.in_(pools))
        if args.uuid:
            query = query.filter(WorkflowItem.uuid.in_(args.uuid))

        uuids = [row.uuid for row in query.order_by(WorkflowItem.updated_at.desc()).all()]
        print(f"mode={'apply' if args.apply else 'dry-run'}")
        print(f"matched={len(uuids)}")

        transitions = Counter()
        samples: list[dict] = []
        updated = 0

        for uuid in uuids:
            result = rollback_to_reaudit_pool(session, uuid, operator="script:rollback_reaudit", commit=False)
            transitions[
                f"{result['before_pool']}/{result['before_status']} -> {result['after_pool']}/{result['after_status']}"
            ] += 1
            if len(samples) < args.sample_limit:
                samples.append(result)
            if result["before_pool"] != result["after_pool"] or result["before_status"] != result["after_status"] or result["affected"] > 0:
                updated += 1

        print("\ntransitions:")
        for key, count in transitions.items():
            print(f"{count:>7}  {key}")

        print("\nsamples:")
        for sample in samples:
            print(sample)

        if args.apply:
            session.commit()
            print(f"\nupdated={updated}")
        else:
            session.rollback()
            print("\ndry-run only; no changes committed")
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
