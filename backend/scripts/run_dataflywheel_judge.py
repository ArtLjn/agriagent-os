"""运行 DataFlywheel discovery Judge 批处理。"""

from app.core.database import SessionLocal
from app.evaluation.discovery.judge_worker import (
    build_default_judge_client,
    run_judge_batch,
)


def main() -> None:
    db = SessionLocal()
    try:
        summary = run_judge_batch(
            db,
            judge_client=build_default_judge_client(),
            month_cost_usd=0.0,
        )
        print(
            "dataflywheel_judge "
            f"processed={summary.processed} updated={summary.updated} "
            f"failed={summary.failed} cost={summary.estimated_cost_usd:.6f}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
