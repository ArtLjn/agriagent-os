"""Repair pack debug evidence 脱敏。"""

import hashlib
import re
from typing import Any

from app.platforms.data_flywheel.repair_pack.constants import (
    REDACTED_SECRET,
    _ADDRESS_RE,
    _ASSIGNMENT_SECRET_RE,
    _INLINE_SECRET_RE,
    _PHONE_RE,
    _SECRET_KEY_RE,
)


def sanitize_debug_evidence(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                _redacted_secret(item)
                if _is_secret_field(str(key))
                else sanitize_debug_evidence(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_debug_evidence(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _is_secret_field(key: str) -> bool:
    return bool(_SECRET_KEY_RE.search(key)) or ".env" in key.lower()


def _sanitize_text(value: str) -> str:
    text = _ASSIGNMENT_SECRET_RE.sub(_redact_match_secret, value)
    text = _INLINE_SECRET_RE.sub(_redact_match_secret, text)
    text = _PHONE_RE.sub(lambda match: _mask_phone(match.group(0)), text)
    return _ADDRESS_RE.sub(lambda match: _redacted_address(match.group(0)), text)


def _redact_match_secret(match: re.Match[str]) -> str:
    return f"{match.group('key')}={_redacted_secret(match.group('value'))}"


def _redacted_secret(value: Any) -> str:
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]
    return f"{REDACTED_SECRET}:{digest}"


def _redacted_address(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"[REDACTED_ADDRESS:{digest}]"


def _mask_phone(value: str) -> str:
    return f"{value[:3]}****{value[-4:]}"
