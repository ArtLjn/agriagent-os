"""数据飞轮 repair pack 数据库编排服务。"""

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.infra.repository_runtime import (
    get_data_flywheel_repository,
    run_maybe_awaitable,
)
from app.models.data_flywheel import AgentDataFlywheelLabel, AgentRepairPack
from app.platforms.data_flywheel.repair_pack_service import (
    build_repair_pack_payload,
    derive_repair_candidate,
    group_samples_by_fix_target,
)
from app.platforms.data_flywheel.service import get_sample_detail, list_samples

REPAIR_PACK_STATUS_DRAFT = "draft"
REPAIR_PACK_STATUS_EXPORTED = "exported"
REPAIR_PACK_STATUS_EXPORT_FAILED = "export_failed"
REPAIR_PACK_STATUS_VERIFICATION_FAILED = "verification_failed"
REPAIR_PACK_STATUS_RESOLVED = "resolved"
REPAIR_PACK_STATUS_DISCARDED = "discarded"
MAX_REPAIR_PACK_SCAN_LIMIT = 500
DEFAULT_REPAIR_PACK_PAGE_SIZE = 20
MAX_REPAIR_PACK_PAGE_SIZE = 100
COMPATIBILITY_DEBUG_ASSET_PATH = "compatibility_debug"


def list_repair_candidates(
    db: Session,
    *,
    farm_id: int,
    sample_ids: list[str] | None = None,
    sample_type: str = "session_turn",
    label: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    q: str | None = None,
    unannotated_only: bool = False,
    fix_target: str | None = None,
    regression_ready: bool | None = None,
    min_priority: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """列出 repair pack 修复候选。"""
    scan_limit = limit
    scan_offset = offset
    paginate_after_filter = bool(
        fix_target or regression_ready is not None or min_priority is not None
    )
    if paginate_after_filter and sample_ids is None:
        scan_limit = MAX_REPAIR_PACK_SCAN_LIMIT
        scan_offset = 0
    details = _details_for_selection(
        db,
        farm_id=farm_id,
        sample_ids=sample_ids,
        sample_type=sample_type,
        label=label,
        session_id=session_id,
        request_id=request_id,
        q=q,
        unannotated_only=unannotated_only,
        limit=scan_limit,
        offset=scan_offset,
    )
    candidates = [derive_repair_candidate(detail) for detail in details]
    if fix_target:
        candidates = [
            item for item in candidates if str(item["fix_target"]) == fix_target
        ]
    if regression_ready is not None:
        candidates = [
            item
            for item in candidates
            if bool(item["regression_ready"]) is regression_ready
        ]
    if min_priority is not None:
        candidates = [
            item for item in candidates if int(item["priority"]) >= min_priority
        ]
    total = len(candidates)
    if paginate_after_filter:
        candidates = candidates[offset : offset + limit]
    return {"items": candidates, "total": total}


def create_repair_pack(
    db: Session,
    *,
    farm_id: int,
    export_base_dir: str | Path,
    sample_ids: list[str] | None = None,
    sample_type: str = "session_turn",
    label: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    q: str | None = None,
    unannotated_only: bool = False,
    fix_target: str | None = None,
    fix_target_override: str | None = None,
    regression_ready: bool | None = None,
    min_priority: int | None = None,
    limit: int = 5,
    created_by: str | None = None,
) -> dict[str, Any]:
    """创建 repair pack 元数据并返回内存导出内容。"""
    if limit < 1 or limit > 100:
        raise ValueError("INVALID_REPAIR_PACK_LIMIT")
    if sample_ids and len(sample_ids) > 100:
        raise ValueError("TOO_MANY_REPAIR_PACK_SAMPLES")
    candidates = list_repair_candidates(
        db,
        farm_id=farm_id,
        sample_ids=sample_ids,
        sample_type=sample_type,
        label=label,
        session_id=session_id,
        request_id=request_id,
        q=q,
        unannotated_only=unannotated_only,
        fix_target=fix_target,
        regression_ready=regression_ready,
        min_priority=min_priority,
        limit=limit,
        offset=0,
    )["items"]
    selected_sample_ids = [str(item["sample_id"]) for item in candidates[:limit]]
    if not selected_sample_ids:
        raise ValueError("EMPTY_REPAIR_PACK")

    details = [
        get_sample_detail(db, farm_id=farm_id, sample_id=sample_id)
        for sample_id in selected_sample_ids
    ]
    pack_target = fix_target_override.strip() if fix_target_override else None
    pack_id = _pack_id(pack_target or str(candidates[0]["fix_target"]))
    export_path = str(Path(export_base_dir) / pack_id)
    try:
        payload = build_repair_pack_payload(
            details,
            pack_id=pack_id,
            export_path=export_path,
            created_by=created_by,
            fix_target_override=fix_target_override,
        )
    except ValueError as exc:
        if exc.args and exc.args[0] == "MIXED_FIX_TARGETS":
            raise ValueError(
                {
                    "code": "MIXED_FIX_TARGETS",
                    "groups": _group_suggestions(details),
                }
            ) from exc
        raise

    manifest = payload["manifest"]
    _mark_compatibility_debug_manifest(manifest)
    dedup_key = _compute_dedup_key(
        farm_id=farm_id,
        fix_target=str(manifest["fix_target"]),
        source_sample_ids=list(manifest["source_sample_ids"]),
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
        "sample_ids": sorted(set(map(str, manifest["source_sample_ids"]))),
        "labels": sorted(set(manifest["labels"] or [])),
    }
    source_label_ids = _open_label_ids_for_samples(
        db,
        farm_id=farm_id,
        sample_ids=list(manifest["source_sample_ids"]),
        labels=list(manifest["labels"]),
    )
    try:
        _write_repair_pack_files(Path(export_path), payload)
    except OSError as exc:
        _record_export_failed_pack(
            db,
            farm_id=farm_id,
            pack_id=pack_id,
            fix_target=str(manifest["fix_target"]),
            labels=list(manifest["labels"]),
            source_sample_ids=list(manifest["source_sample_ids"]),
            source_label_ids=source_label_ids,
            dedup_key=dedup_key,
            export_path=export_path,
            manifest=manifest,
            export_error=str(exc),
            created_by=created_by,
        )
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
    row = _repo_call(_repair_pack_repo(db).create, row)
    return {
        **_pack_to_dict(row),
        "cases": payload.get("cases_jsonl", []),
        "payload": payload,
    }


def get_repair_pack(db: Session, *, farm_id: int, pack_id: str) -> dict[str, Any]:
    """获取 repair pack 元数据，并尝试从磁盘加载失败案例详情。"""
    row = _repair_pack_row(db, farm_id=farm_id, pack_id=pack_id)
    data = _pack_to_dict(row)
    data["cases"] = _load_cases_from_disk(row.export_path)
    return data


def rebuild_repair_pack_files(
    db: Session,
    *,
    farm_id: int,
    pack_id: str,
    export_base_dir: str | Path,
) -> dict[str, Any]:
    """按数据库记录重新生成 repair pack 磁盘文件。"""
    row = _repair_pack_row(db, farm_id=farm_id, pack_id=pack_id)
    source_sample_ids = [str(item) for item in row.source_sample_ids or []]
    if not source_sample_ids:
        raise ValueError("EMPTY_REPAIR_PACK")
    export_path = row.export_path or str(Path(export_base_dir) / row.pack_id)
    details = [
        get_sample_detail(db, farm_id=farm_id, sample_id=sample_id)
        for sample_id in source_sample_ids
    ]
    payload = build_repair_pack_payload(
        details,
        pack_id=row.pack_id,
        export_path=export_path,
        created_by=row.created_by,
        fix_target_override=row.fix_target,
    )
    manifest = payload["manifest"]
    _mark_compatibility_debug_manifest(manifest)
    if row.dedup_key:
        manifest["dedup_key"] = row.dedup_key
    existing_manifest = row.manifest_json or {}
    if isinstance(existing_manifest.get("dedup_inputs"), dict):
        manifest["dedup_inputs"] = existing_manifest["dedup_inputs"]
    _write_repair_pack_files(Path(export_path), payload)
    row = _repo_call(
        _repair_pack_repo(db).update_fields,
        farm_id=farm_id,
        pack_id=pack_id,
        export_path=export_path,
        manifest_json=manifest,
        export_error=None,
    )
    if row is None:
        raise ValueError("REPAIR_PACK_NOT_FOUND")
    return {
        **_pack_to_dict(row),
        "cases": payload.get("cases_jsonl", []),
        "payload": payload,
    }


def _load_cases_from_disk(export_path: str | None) -> list[dict[str, Any]]:
    """从 export_path/cases.jsonl 读失败案例；失败返回空列表。"""
    if not export_path:
        return []
    cases_path = Path(export_path) / "cases.jsonl"
    if not cases_path.exists():
        return []
    cases: list[dict[str, Any]] = []
    try:
        for line in cases_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return cases


def mark_repair_pack_resolved(
    db: Session,
    *,
    farm_id: int,
    pack_id: str,
    repair_note: str | None = None,
    verification_summary: dict[str, Any] | None = None,
    resolved_by: str | None = None,
) -> dict[str, Any]:
    """标记 repair pack 已修复，并 resolve 关联 open labels。"""
    row = _repair_pack_row(db, farm_id=farm_id, pack_id=pack_id)
    _resolve_open_labels(db, farm_id=farm_id, label_ids=row.source_label_ids or [])
    row = _repo_call(
        _repair_pack_repo(db).update_fields,
        farm_id=farm_id,
        pack_id=pack_id,
        status=REPAIR_PACK_STATUS_RESOLVED,
        repair_note=repair_note,
        verification_summary=verification_summary,
        resolved_by=resolved_by,
        resolved_at=datetime.now(),
    )
    if row is None:
        raise ValueError("REPAIR_PACK_NOT_FOUND")
    return _pack_to_dict(row)


def record_repair_pack_verification_failure(
    db: Session,
    *,
    farm_id: int,
    pack_id: str,
    verification_summary: dict[str, Any],
) -> dict[str, Any]:
    """记录 repair pack 验证失败，不 resolve 标签。"""
    row = _repair_pack_row(db, farm_id=farm_id, pack_id=pack_id)
    row = _repo_call(
        _repair_pack_repo(db).update_fields,
        farm_id=farm_id,
        pack_id=pack_id,
        status=REPAIR_PACK_STATUS_VERIFICATION_FAILED,
        verification_summary=verification_summary,
    )
    if row is None:
        raise ValueError("REPAIR_PACK_NOT_FOUND")
    return _pack_to_dict(row)


def list_repair_packs(
    db: Session,
    *,
    farm_id: int,
    status: str | None = None,
    fix_target: str | None = None,
    include_discarded: bool = False,
    page: int = 1,
    page_size: int = DEFAULT_REPAIR_PACK_PAGE_SIZE,
) -> dict[str, Any]:
    """分页列出 repair pack，默认不展示已废弃。"""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = DEFAULT_REPAIR_PACK_PAGE_SIZE
    if page_size > MAX_REPAIR_PACK_PAGE_SIZE:
        page_size = MAX_REPAIR_PACK_PAGE_SIZE
    page_result = _repo_call(
        _repair_pack_repo(db).list,
        farm_id=farm_id,
        status=status,
        fix_target=fix_target,
        include_discarded=include_discarded,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [_pack_to_dict(row) for row in page_result.items],
        "total": page_result.total,
        "page": page_result.page,
        "page_size": page_result.page_size,
    }


def mark_repair_pack_discarded(
    db: Session,
    *,
    farm_id: int,
    pack_id: str,
    resolved_by: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """标记 repair pack 为已废弃（软删除），不删 DB 行和磁盘文件。"""
    row = _repair_pack_row(db, farm_id=farm_id, pack_id=pack_id)
    repair_note = row.repair_note
    if reason:
        repair_note = reason if not repair_note else f"{repair_note}\n{reason}"
    row = _repo_call(
        _repair_pack_repo(db).update_fields,
        farm_id=farm_id,
        pack_id=pack_id,
        status=REPAIR_PACK_STATUS_DISCARDED,
        repair_note=repair_note,
        resolved_by=resolved_by,
        resolved_at=datetime.now(),
    )
    if row is None:
        raise ValueError("REPAIR_PACK_NOT_FOUND")
    return _pack_to_dict(row)


def mark_repair_pack_exported(
    db: Session,
    *,
    farm_id: int,
    pack_id: str,
) -> dict[str, Any]:
    """把 repair pack 状态重置为 exported（撤销已修复 / 恢复已废弃）。"""
    row = _repair_pack_row(db, farm_id=farm_id, pack_id=pack_id)
    row = _repo_call(
        _repair_pack_repo(db).update_fields,
        farm_id=farm_id,
        pack_id=pack_id,
        status=REPAIR_PACK_STATUS_EXPORTED,
    )
    if row is None:
        raise ValueError("REPAIR_PACK_NOT_FOUND")
    return _pack_to_dict(row)


def _details_for_selection(
    db: Session,
    *,
    farm_id: int,
    sample_ids: list[str] | None,
    sample_type: str,
    label: str | None,
    session_id: str | None,
    request_id: str | None,
    q: str | None,
    unannotated_only: bool,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    if sample_ids:
        return [
            get_sample_detail(db, farm_id=farm_id, sample_id=sample_id)
            for sample_id in sample_ids
        ]
    listed = list_samples(
        db,
        farm_id=farm_id,
        sample_type=sample_type,
        label=label,
        session_id=session_id,
        request_id=request_id,
        q=q,
        unannotated_only=unannotated_only,
        limit=limit,
        offset=offset,
    )
    return [
        get_sample_detail(db, farm_id=farm_id, sample_id=item["sample_id"])
        for item in listed["items"]
    ]


def _repair_pack_row(db: Session, *, farm_id: int, pack_id: str) -> AgentRepairPack:
    row = _repo_call(
        _repair_pack_repo(db).get_by_pack_id,
        farm_id=farm_id,
        pack_id=pack_id,
    )
    if row is None:
        raise ValueError("REPAIR_PACK_NOT_FOUND")
    return row


def _open_label_ids_for_samples(
    db: Session, *, farm_id: int, sample_ids: list[str], labels: list[str]
) -> list[int]:
    if not sample_ids:
        return []
    query = db.query(AgentDataFlywheelLabel.id).filter(
        AgentDataFlywheelLabel.farm_id == farm_id,
        AgentDataFlywheelLabel.sample_id.in_(sample_ids),
        AgentDataFlywheelLabel.status != "resolved",
    )
    if labels:
        query = query.filter(AgentDataFlywheelLabel.label.in_(labels))
    return [
        int(row.id) for row in query.order_by(AgentDataFlywheelLabel.id.asc()).all()
    ]


def _resolve_open_labels(db: Session, *, farm_id: int, label_ids: list[int]) -> None:
    if not label_ids:
        return
    rows = (
        db.query(AgentDataFlywheelLabel)
        .filter(
            AgentDataFlywheelLabel.farm_id == farm_id,
            AgentDataFlywheelLabel.id.in_(label_ids),
            AgentDataFlywheelLabel.status != "resolved",
        )
        .all()
    )
    for row in rows:
        row.status = "resolved"


def _pack_to_dict(row: AgentRepairPack) -> dict[str, Any]:
    manifest = dict(row.manifest_json or {})
    _mark_compatibility_debug_manifest(manifest)
    return {
        "id": row.id,
        "pack_id": row.pack_id,
        "fix_target": row.fix_target,
        "labels": row.labels or [],
        "source_sample_ids": row.source_sample_ids or [],
        "source_label_ids": row.source_label_ids or [],
        "dedup_key": row.dedup_key,
        "status": row.status,
        "export_path": row.export_path,
        "manifest": manifest,
        "cases": [],
        "export_error": row.export_error,
        "repair_note": row.repair_note,
        "verification_summary": row.verification_summary,
        "created_by": row.created_by,
        "resolved_by": row.resolved_by,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _pack_id(fix_target: str) -> str:
    return f"repair-{fix_target}-{uuid.uuid4().hex[:12]}"


def _compute_dedup_key(
    *,
    farm_id: int,
    fix_target: str,
    source_sample_ids: list[str],
    labels: list[str],
) -> str:
    """对修复包的业务身份做确定性 hash，用于去重。"""
    payload = {
        "farm_id": farm_id,
        "fix_target": (fix_target or "").strip().lower(),
        "sample_ids": sorted(set(map(str, source_sample_ids or []))),
        "labels": sorted(set(labels or [])),
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:16]


def _find_existing_active_pack(
    db: Session, *, farm_id: int, dedup_key: str
) -> AgentRepairPack | None:
    """查找同 dedup_key 的非废弃 pack，命中则复用而非重复导出。"""
    return _repo_call(
        _repair_pack_repo(db).find_active_by_dedup_key,
        farm_id=farm_id,
        dedup_key=dedup_key,
    )


def _group_suggestions(samples: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        target: [
            str(
                (detail.get("sample") or {}).get("sample_id") or detail.get("sample_id")
            )
            for detail in details
        ]
        for target, details in group_samples_by_fix_target(samples).items()
    }


def _record_export_failed_pack(
    db: Session,
    *,
    farm_id: int,
    pack_id: str,
    fix_target: str,
    labels: list[str],
    source_sample_ids: list[str],
    source_label_ids: list[int],
    export_path: str,
    manifest: dict[str, Any],
    export_error: str,
    created_by: str | None,
    dedup_key: str | None = None,
) -> None:
    row = AgentRepairPack(
        farm_id=farm_id,
        pack_id=pack_id,
        fix_target=fix_target,
        labels=labels,
        source_sample_ids=source_sample_ids,
        source_label_ids=source_label_ids,
        dedup_key=dedup_key,
        status=REPAIR_PACK_STATUS_EXPORT_FAILED,
        export_path=export_path,
        manifest_json=manifest,
        export_error=export_error,
        created_by=created_by,
    )
    _repo_call(_repair_pack_repo(db).create, row)


def _write_repair_pack_files(export_path: Path, payload: dict[str, Any]) -> None:
    export_path.mkdir(parents=True, exist_ok=True)
    (export_path / "debug").mkdir(exist_ok=True)
    (export_path / "regression-drafts").mkdir(exist_ok=True)
    _write_json(export_path / "manifest.json", payload["manifest"])
    (export_path / "cases.jsonl").write_text(
        "\n".join(
            json.dumps(item, ensure_ascii=False)
            for item in payload.get("cases_jsonl", [])
        )
        + "\n",
        encoding="utf-8",
    )
    (export_path / "README.md").write_text(payload["readme"], encoding="utf-8")
    for relative_path, content in payload.get("debug_files", {}).items():
        _write_json(export_path / relative_path, content)
    for relative_path, content in payload.get("regression_drafts", {}).items():
        _write_json(export_path / relative_path, content)


def _write_json(path: Path, content: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(content, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _mark_compatibility_debug_manifest(manifest: dict[str, Any]) -> None:
    manifest["asset_path"] = COMPATIBILITY_DEBUG_ASSET_PATH
    manifest["formal_review_required"] = True


def _repair_pack_repo(db: Session):
    return get_data_flywheel_repository(db, "repair_packs")


def _repo_call(method, *args, **kwargs):
    return run_maybe_awaitable(method(*args, **kwargs))
