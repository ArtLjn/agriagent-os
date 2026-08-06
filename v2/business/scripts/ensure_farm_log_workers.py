"""Create farm_log_workers table if missing."""
import logging
import sys
from pathlib import Path

# 允许从 v2/business/scripts/ 直接运行，复用 agent 的 logging 配置
_PARENT = str(Path(__file__).resolve().parent.parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from sqlalchemy import create_engine, text

from agent.infra.logging import setup_logging
from business.config import settings

setup_logging(app_name="scripts")
logger = logging.getLogger("ensure_farm_log_workers")

DDL = """
CREATE TABLE IF NOT EXISTS farm_log_workers (
  id int NOT NULL AUTO_INCREMENT,
  farm_log_id int NOT NULL,
  worker_id int NOT NULL,
  role varchar(50) DEFAULT NULL,
  note varchar(500) DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_farm_log_workers_log_worker (farm_log_id, worker_id),
  KEY ix_farm_log_workers_farm_log_id (farm_log_id),
  KEY ix_farm_log_workers_worker_id (worker_id),
  CONSTRAINT farm_log_workers_ibfk_1 FOREIGN KEY (farm_log_id)
      REFERENCES farm_logs (id) ON DELETE CASCADE,
  CONSTRAINT farm_log_workers_ibfk_2 FOREIGN KEY (worker_id)
      REFERENCES workers (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def main() -> None:
    e = create_engine(settings.database.url)
    with e.begin() as c:
        c.execute(text(DDL))
    with e.connect() as c:
        r = c.execute(text("SHOW TABLES LIKE 'farm_log_workers'"))
        rows = r.fetchall()
        logger.info("verified: %s", rows)
        if rows:
            logger.info("farm_log_workers table is ready")
        else:
            logger.warning("table creation did not persist")


if __name__ == "__main__":
    main()
