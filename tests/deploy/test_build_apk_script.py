from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "deploy" / "build-apk.sh"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def test_help_prints_usage_without_building() -> None:
    result = run_script("--help")

    assert result.returncode == 0
    assert "用法:" in result.stdout
    assert "--dry-run" in result.stdout
    assert "flutter build apk" not in result.stdout


def test_dry_run_accepts_api_presets_and_output_dir() -> None:
    result = run_script(
        "--debug",
        "--home",
        "--output-dir",
        "output/apk",
        "--dry-run",
    )

    assert result.returncode == 0
    assert "构建类型: debug" in result.stdout
    assert "API 地址: http://10.167.110.141:8099" in result.stdout
    assert "输出目录:" in result.stdout
    assert "DRY RUN" in result.stdout
    assert "GRADLE_USER_HOME=" in result.stdout
    assert "farm-manager/gradle" in result.stdout
    assert "--dart-define=API_BASE_URL=http://10.167.110.141:8099" in result.stdout


def test_dry_run_uses_custom_api_and_versioned_filename() -> None:
    result = run_script("--api", "http://127.0.0.1:8099", "--dry-run")

    assert result.returncode == 0
    assert "API 地址: http://127.0.0.1:8099" in result.stdout
    assert "FarmManager-v" in result.stdout
    assert "-release-" in result.stdout
    assert ".apk" in result.stdout


def test_unknown_argument_fails_with_usage_hint() -> None:
    result = run_script("--wat")

    assert result.returncode == 1
    assert "未知参数: --wat" in result.stdout
    assert "使用 --help 查看用法" in result.stdout


def test_custom_gradle_home_is_used_in_dry_run() -> None:
    result = run_script("--gradle-home", "output/gradle-cache", "--dry-run")
    expected_gradle_home = PROJECT_ROOT / "output" / "gradle-cache"

    assert result.returncode == 0
    assert f"Gradle缓存: {expected_gradle_home}" in result.stdout
    assert f"GRADLE_USER_HOME={expected_gradle_home}" in result.stdout
