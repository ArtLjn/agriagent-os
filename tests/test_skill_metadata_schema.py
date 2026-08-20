from pathlib import Path

from scripts.validate_skill_metadata import validate_directory


def test_all_v2_skill_metadata_uses_the_same_schema() -> None:
    errors = validate_directory(Path("agri_backend_v2/agent/skills"))

    assert errors == [], "\n".join(errors)
