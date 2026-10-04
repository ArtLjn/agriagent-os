from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "deploy/flutter-android.sh"


@pytest.fixture
def startup(tmp_path: Path):
    """用隔离的命令替身验证启动配置，避免操作真实模拟器和构建缓存。"""
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    app = tmp_path / "agri_mobile_app"
    app.mkdir()
    shutil.copyfile(SCRIPT, deploy / SCRIPT.name)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    log = tmp_path / "commands.log"
    commands = {
        "adb": """#!/usr/bin/env bash
echo "adb $*" >> "$ANDROID_TEST_LOG"
if [ "$1" = devices ]; then
  printf 'List of devices attached\n%s\tdevice\n' "$ANDROID_TEST_DEVICE"
fi
if [ "${3:-}" = reverse ] && [ "${ANDROID_TEST_FAIL_REVERSE:-0}" = 1 ]; then
  exit 1
fi
""",
        "flutter": """#!/usr/bin/env bash
echo "flutter $*" >> "$ANDROID_TEST_LOG"
""",
    }
    for name, source in commands.items():
        command = binaries / name
        command.write_text(source)
        command.chmod(0o755)

    def run(**overrides: str) -> tuple[subprocess.CompletedProcess[str], str]:
        """运行脚本并返回调用记录，检查设备选择、端口和编译参数的边界。"""
        environment = {
            **os.environ,
            "PATH": f"{binaries}:{os.environ['PATH']}",
            "GRADLE_USER_HOME": str(tmp_path / "gradle"),
            "ANDROID_TEST_LOG": str(log),
            "ANDROID_TEST_DEVICE": "emulator-5554",
            "DEVICE_ID": "emulator-5554",
        }
        environment.pop("BUSINESS_API_URL", None)
        environment.pop("AGENT_API_URL", None)
        environment.update(overrides)
        result = subprocess.run(
            ["bash", str(deploy / SCRIPT.name)],
            cwd=tmp_path,
            env=environment,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return result, log.read_text()

    return run


def test_emulator_defaults_use_host_alias_without_tunnels(startup) -> None:
    """模拟器默认直连宿主机专用地址，避免依赖 ADB 隧道生命周期。"""
    result, commands = startup()

    assert result.returncode == 0
    assert "reverse" not in commands
    assert "--dart-define=BUSINESS_API_BASE_URL=http://10.0.2.2:9876/api/v2" in commands
    assert "--dart-define=AGENT_API_BASE_URL=http://10.0.2.2:8000/api/v2" in commands


def test_usb_device_defaults_forward_local_ports_before_flutter(startup) -> None:
    """USB 真机没有模拟器宿主机别名，必须先建立回环端口转发。"""
    result, commands = startup(DEVICE_ID="usb-phone", ANDROID_TEST_DEVICE="usb-phone")

    assert result.returncode == 0
    assert "adb -s usb-phone reverse tcp:9876 tcp:9876" in commands
    assert "adb -s usb-phone reverse tcp:8000 tcp:8000" in commands
    assert commands.index("reverse tcp:8000") < commands.index("flutter run")
    assert "BUSINESS_API_BASE_URL=http://127.0.0.1:9876/api/v2" in commands
    assert "AGENT_API_BASE_URL=http://127.0.0.1:8000/api/v2" in commands


def test_remote_overrides_do_not_create_local_tunnels(startup) -> None:
    """显式配置的远程地址不能被启动脚本替换。"""
    result, commands = startup(
        BUSINESS_API_URL="https://business.example.com/api/v2",
        AGENT_API_URL="http://192.168.1.20:8000/api/v2",
    )

    assert result.returncode == 0
    assert "reverse" not in commands
    assert "BUSINESS_API_BASE_URL=https://business.example.com/api/v2" in commands
    assert "AGENT_API_BASE_URL=http://192.168.1.20:8000/api/v2" in commands


def test_custom_device_and_local_port_are_forwarded(startup) -> None:
    """自定义设备和本机端口使用对应隧道，避免误连其他模拟器。"""
    result, commands = startup(
        DEVICE_ID="emulator-5556",
        ANDROID_TEST_DEVICE="emulator-5556",
        BUSINESS_API_URL="http://localhost:9988/api/v2",
        AGENT_API_URL="https://agent.example.com/api/v2",
    )

    assert result.returncode == 0
    assert "adb -s emulator-5556 reverse tcp:9988 tcp:9988" in commands
    assert "reverse tcp:8000" not in commands
    assert "flutter run -d emulator-5556" in commands


def test_failed_tunnel_stops_launch_with_context(startup) -> None:
    """转发失败就停止启动，避免让用户进入必然无法连接的 App。"""
    result, commands = startup(
        ANDROID_TEST_FAIL_REVERSE="1",
        BUSINESS_API_URL="http://127.0.0.1:9876/api/v2",
    )

    assert result.returncode == 1
    assert "BACKEND_TUNNEL_FAILED" in result.stdout
    assert "emulator-5554" in result.stdout
    assert "9876" in result.stdout
    assert "flutter run" not in commands
