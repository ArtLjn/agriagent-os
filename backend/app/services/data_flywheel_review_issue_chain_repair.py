"""ReviewIssueChain repair pack 数据库编排。"""

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.data_flywheel import AgentRepairPack
from app.services.data_flywheel_repair_pack_chain import (
    build_chain_repair_pack_payload,
    derive_chain_repair_candidate,
    validate_chain_repair_export_ready,
)
from app.services.data_flywheel_repair_pack_repository import (
    REPAIR_PACK_STATUS_DISCARDED,
    REPAIR_PACK_STATUS_EXPORTED,
    _open_label_ids_for_samples,
    _pack_to_dict,
    _write_repair_pack_files,
)
from app.services.data_flywheel_review_issue_chain_service import (
    get_review_issue_chain_detail,
)


def create_repair_pack_from_review_issue_chain(
    db: Session,
    *,
    farm_id: int,
    chain_id: str,
    export_base_dir: str | Path,
    created_by: str | None = None,
) -> dict[str, Any]:
    """从单条已审核问题链导出 repair pack。"""
    detail = get_review_issue_chain_detail(db, farm_id=farm_id, chain_id=chain_id)
    validate_chain_repair_export_ready(detail)
    candidate = derive_chain_repair_candidate(detail)
    pack_id = _pack_id(str(candidate["fix_target"]))
    export_path = str(Path(export_base_dir) / pack_id)
    payload = build_chain_repair_pack_payload(
        detail,
        pack_id=pack_id,
        export_path=export_path,
        created_by=created_by,
    )
    manifest = payload["manifest"]
    dedup_key = _compute_chain_dedup_key(
        farm_id=farm_id,
        fix_target=str(manifest["fix_target"]),
        source_chain_ids=list(manifest["source_chain_ids"]),
        labels=list(manifest["labels"]),
    )
    existing = _find_existing_active_pack(db, farm_id=farm_id, dedup_key=dedup_key)
    if existing is not None:
        return {
            **_pack_to_dict(existing),
            "deduplicated": True,
            "dedup_existing_pack_id": existing.pack_id,
        }
    manifest["dedup_key"] = dedup_key
    manifest["dedup_inputs"] = {
        "farm_id": farm_id,
        "fix_target": str(manifest["fix_target"]),
        "chain_ids": sorted(set(map(str, manifest["source_chain_ids"]))),
        "labels": sorted(set(manifest["labels"] or [])),
    }
    source_label_ids = _open_label_ids_for_samples(
        db,
        farm_id=farm_id,
        sample_ids=list(manifest["source_sample_ids"]),
        labels=list(manifest["labels"]),
    )
    export_dir = Path(export_path)
    try:
        _write_repair_pack_files(export_dir, payload)
    except OSError as exc:
        raise ValueError("REPAIR_PACK_EXPORT_FAILED") from exc
    row = AgentRepairPack(
        farm_id=farm_id,
        pack_id=pack_id,
        fix_target=str(manifest["fix_target"]),
        labels=list(manifest["labels"]),
        source_sample_ids=list(manifest["source_sample_ids"]),
        source_label_ids=source_label_ids,
        dedup_key=dedup_key,
        status=REPAIR_PACK_STATUS_EXPORTED,
        export_path=export_path,
        manifest_json=manifest,
        export_error=None,
        created_by=created_by,
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        shutil.rmtree(export_dir, ignore_errors=True)
        raise
    return {**_pack_to_dict(row), "cases": payload["cases_jsonl"], "payload": payload}


def _pack_id(fix_target: str) -> str:
    return f"repair-{fix_target}-{uuid.uuid4().hex[:12]}"


def _compute_chain_dedup_key(
    *,
    farm_id: int,
    fix_target: str,
    source_chain_ids: list[str],
    labels: list[str],
) -> str:
    payload = {
        "farm_id": farm_id,
        "fix_target": (fix_target or "").strip().lower(),
        "chain_ids": sorted(set(map(str, source_chain_ids or []))),
        "labels": sorted(set(labels or [])),
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:16]


def _find_existing_active_pack(
    db: Session, *, farm_id: int, dedup_key: str
) -> AgentRepairPack | None:
    return (
        db.query(AgentRepairPack)
        .filter(
            AgentRepairPack.farm_id == farm_id,
            AgentRepairPack.dedup_key == dedup_key,
            AgentRepairPack.status != REPAIR_PACK_STATUS_DISCARDED,
        )
        .order_by(desc(AgentRepairPack.created_at))
        .first()
    )
