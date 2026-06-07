#!/usr/bin/env python3
"""启动服务并运行全量 API 测试，输出带分析结果的报告。

用法:
    cd backend && python ../scripts/run_api_tests.py
    # 或带选项
    python ../scripts/run_api_tests.py --port 8001 --keep-db
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen


# ── 配置 ──────────────────────────────────────────────
DEFAULT_PORT = 8000
HEALTH_URL_TEMPLATE = "http://127.0.0.1:{port}/health"
STARTUP_TIMEOUT = 30  # 秒
TEST_TIMEOUT = 300  # 秒

# 颜色代码
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _color(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── 服务生命周期 ──────────────────────────────────────


async def _wait_for_health(port: int, timeout: float) -> bool:
    """轮询 /health 直到服务就绪或超时。"""
    url = HEALTH_URL_TEMPLATE.format(port=port)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


def _start_server(port: int, db_path: str | None, log_file: Path) -> subprocess.Popen:
    """在后台启动 uvicorn，stdout/stderr 重定向到 log_file。"""
    env = dict(os.environ)
    if db_path:
        env["FARM_DB_PATH"] = db_path

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "info",
    ]

    log_fp = log_file.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        cwd=Path(__file__).resolve().parent.parent / "backend",
        env=env,
    )
    return proc


def _kill_server(proc: subprocess.Popen) -> None:
    """优雅终止服务进程。"""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


# ── 测试执行 ──────────────────────────────────────────


class TestResult:
    """解析后的 pytest 结果。"""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.error = 0
        self.total = 0
        self.duration = 0.0
        self.failures: list[str] = []
        self.failure_details: list[str] = []
        self.raw_output = ""


def _run_pytest(port: int, timeout: float) -> TestResult:
    """运行 pytest 并解析结果。"""
    result = TestResult()

    # 使用 subprocess 运行 pytest，捕获输出
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--color=no",
    ]

    _log(_color("开始运行全量测试...", CYAN))
    start = time.monotonic()

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(__file__).resolve().parent.parent / "backend",
        )
    except subprocess.TimeoutExpired:
        _log(_color("测试超时！", RED))
        result.error = 1
        return result

    result.duration = time.monotonic() - start
    result.raw_output = proc.stdout + proc.stderr

    # 解析 pytest 汇总行
    # 示例: "================== 408 passed, 3 skipped in 9.98s =================="
    summary_pattern = re.compile(
        r"=+\s+(\d+)\s+passed.*?"  # passed
        r"(?:,\s+(\d+)\s+failed)?.*?"  # failed (optional)
        r"(?:,\s+(\d+)\s+skipped)?.*?"  # skipped (optional)
        r"(?:,\s+(\d+)\s+error)?.*?"  # error (optional)
        r"in\s+([\d.]+)s"
    )

    for line in result.raw_output.splitlines():
        m = summary_pattern.search(line)
        if m:
            result.passed = int(m.group(1) or 0)
            result.failed = int(m.group(2) or 0)
            result.skipped = int(m.group(3) or 0)
            result.error = int(m.group(4) or 0)
            break

    result.total = result.passed + result.failed + result.skipped + result.error

    # 提取失败用例名称和详情
    lines = result.raw_output.splitlines()
    failure_pattern = re.compile(r"FAILED\s+(\S+)")
    for i, line in enumerate(lines):
        m = failure_pattern.search(line)
        if m:
            test_name = m.group(1)
            result.failures.append(test_name)
            # 收集该失败用例后的 traceback 上下文（直到下一个 PASSED/FAILED/ERROR 或空行分隔）
            detail_lines = [line]
            for j in range(i + 1, min(i + 30, len(lines))):
                next_line = lines[j]
                if re.match(r"(PASSED|FAILED|ERROR|tests?/|={10,})", next_line):
                    break
                if next_line.strip():
                    detail_lines.append(next_line)
            result.failure_details.append("\n".join(detail_lines))

    return result


# ── 日志分析 ──────────────────────────────────────────


class LogAnalysis:
    """服务端日志分析结果。"""

    def __init__(self) -> None:
        self.error_count = 0
        self.warning_count = 0
        self.exceptions: list[str] = []
        self.error_lines: list[str] = []


def _analyze_server_logs(log_file: Path) -> LogAnalysis:
    """分析服务端日志中的错误和异常。"""
    analysis = LogAnalysis()

    if not log_file.exists():
        return analysis

    content = log_file.read_text(encoding="utf-8")

    for line in content.splitlines():
        if "ERROR" in line or "CRITICAL" in line:
            analysis.error_count += 1
            analysis.error_lines.append(line.strip())
            # 提取异常类型
            exc_match = re.search(r"(\w+Error|Exception):", line)
            if exc_match:
                exc_type = exc_match.group(1)
                if exc_type not in analysis.exceptions:
                    analysis.exceptions.append(exc_type)
        elif "WARNING" in line:
            analysis.warning_count += 1

    return analysis


# ── 错误日志写入 ──────────────────────────────────────


def _write_error_log(
    error_log_file: Path,
    result: TestResult,
    log_analysis: LogAnalysis,
    server_log_file: Path,
    port: int,
) -> None:
    """将所有错误信息写入专门的错误日志文件，方便排查。"""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("                    API 测试错误日志")
    lines.append("=" * 70)
    lines.append(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"端口: {port}")
    lines.append(f"服务日志: {server_log_file}")
    lines.append("")

    # 测试统计
    lines.append("-" * 70)
    lines.append("测试统计")
    lines.append("-" * 70)
    lines.append(f"  总用例: {result.total}")
    lines.append(f"  通过:   {result.passed}")
    lines.append(f"  失败:   {result.failed}")
    lines.append(f"  跳过:   {result.skipped}")
    lines.append(f"  错误:   {result.error}")
    lines.append(f"  耗时:   {result.duration:.2f}s")
    lines.append("")

    # 测试失败详情
    if result.failure_details:
        lines.append("-" * 70)
        lines.append(f"测试失败详情 ({len(result.failure_details)} 个)")
        lines.append("-" * 70)
        for idx, detail in enumerate(result.failure_details, 1):
            lines.append("")
            lines.append(f"【失败 {idx}/{len(result.failure_details)}】")
            lines.append(detail)
            lines.append("")

    # 服务端错误日志
    if log_analysis.error_lines:
        lines.append("-" * 70)
        lines.append(f"服务端 ERROR/CRITICAL 日志 ({log_analysis.error_count} 条)")
        lines.append("-" * 70)
        for idx, err_line in enumerate(log_analysis.error_lines, 1):
            lines.append(f"[{idx}] {err_line}")
        lines.append("")

    if log_analysis.exceptions:
        lines.append("-" * 70)
        lines.append("异常类型汇总")
        lines.append("-" * 70)
        for exc in log_analysis.exceptions:
            lines.append(f"  - {exc}")
        lines.append("")

    lines.append("=" * 70)
    lines.append("                            END")
    lines.append("=" * 70)

    error_log_file.write_text("\n".join(lines), encoding="utf-8")


# ── 报告输出 ──────────────────────────────────────────


def _print_report(
    result: TestResult,
    log_analysis: LogAnalysis,
    server_log_file: Path,
    error_log_file: Path,
    port: int,
) -> None:
    """打印测试报告摘要。"""
    print()
    print(_color("=" * 60, BOLD))
    print(_color("                 API 测试报告", BOLD))
    print(_color("=" * 60, BOLD))
    print()

    # 测试统计
    pass_rate = (result.passed / result.total * 100) if result.total > 0 else 0

    print(f"  总用例数: {result.total}")
    print(f"  {_color('通过', GREEN)}: {result.passed}")
    print(f"  {_color('失败', RED)}: {result.failed}")
    print(f"  {_color('跳过', YELLOW)}: {result.skipped}")
    print(f"  {_color('错误', RED)}: {result.error}")
    print(f"  通过率: {pass_rate:.1f}%")
    print(f"  耗时: {result.duration:.2f}s")
    print()

    # 失败详情
    if result.failures:
        print(_color("失败的测试:", RED))
        for name in result.failures:
            print(f"  - {name}")
        print()

    # 服务端日志分析
    print(_color("服务端日志分析:", BOLD))
    print(f"  ERROR/CRITICAL: {log_analysis.error_count}")
    print(f"  WARNING: {log_analysis.warning_count}")

    if log_analysis.exceptions:
        print(f"  异常类型: {', '.join(log_analysis.exceptions)}")

    if log_analysis.error_lines:
        print()
        print(_color("错误日志片段 (前 5 条):", YELLOW))
        for line in log_analysis.error_lines[:5]:
            print(f"  {line[:120]}")
    print()

    # 日志文件路径
    print(f"  完整服务日志: {server_log_file}")
    has_errors = result.failed > 0 or result.error > 0 or log_analysis.error_count > 0
    if has_errors:
        print(f"  {_color('错误汇总日志', RED)}: {error_log_file}")
    print()

    # 结论
    if result.failed == 0 and result.error == 0 and log_analysis.error_count == 0:
        print(_color("  结果: 全部通过，无服务端错误", GREEN))
    elif result.failed == 0 and result.error == 0:
        print(_color("  结果: 测试通过，但服务端有非致命错误日志", YELLOW))
    else:
        print(_color("  结果: 存在失败用例或错误，需要修复", RED))

    print(_color("=" * 60, BOLD))


# ── 主流程 ────────────────────────────────────────────


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="启动后端服务并运行全量 API 测试",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"服务端口号 (默认 {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--keep-db",
        action="store_true",
        help="保留测试数据库，不自动清理",
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="不启动服务，假设服务已在运行",
    )
    args = parser.parse_args()

    port = args.port
    server_proc: subprocess.Popen | None = None
    temp_db: Path | None = None
    server_log = Path(tempfile.gettempdir()) / f"farm_test_server_{port}.log"
    error_log = Path(tempfile.gettempdir()) / f"farm_test_error_{port}.log"

    try:
        # 1. 准备测试数据库
        if not args.keep_db:
            temp_db = Path(tempfile.gettempdir()) / f"farm_test_{port}.db"
            _log(f"使用临时数据库: {temp_db}")
        else:
            _log("使用默认数据库")

        # 2. 启动服务
        if not args.no_server:
            _log(_color(f"启动服务 (端口 {port})...", CYAN))
            server_proc = _start_server(
                port, str(temp_db) if temp_db else None, server_log
            )

            _log("等待服务就绪...")
            if not await _wait_for_health(port, STARTUP_TIMEOUT):
                _log(_color("服务启动超时！", RED))
                return 1
            _log(_color("服务已就绪", GREEN))
        else:
            _log("跳过服务启动，使用已有服务")

        # 3. 运行测试
        result = _run_pytest(port, TEST_TIMEOUT)

        # 4. 分析日志
        log_analysis = _analyze_server_logs(server_log)

        # 5. 写入错误汇总日志
        has_errors = (
            result.failed > 0 or result.error > 0 or log_analysis.error_count > 0
        )
        if has_errors:
            _write_error_log(
                error_log, result, log_analysis, server_log, port
            )
            _log(_color(f"错误日志已写入: {error_log}", YELLOW))

        # 6. 输出报告
        _print_report(result, log_analysis, server_log, error_log, port)

        # 返回退出码
        return 1 if has_errors else 0

    finally:
        # 清理
        if server_proc:
            _log("关闭服务...")
            _kill_server(server_proc)

        if temp_db and temp_db.exists() and not args.keep_db:
            temp_db.unlink()
            _log(f"清理临时数据库: {temp_db}")


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        _log(_color("\n用户中断", YELLOW))
        exit_code = 130
    sys.exit(exit_code)
