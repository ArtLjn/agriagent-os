#!/usr/bin/env python3
"""检测 agent 代码中无日志的 broad except return/pass。"""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

NOQA_MARKER = "noqa: silent-exception"
LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical", "log"}


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    message: str


def find_violations(paths: list[Path]) -> list[Violation]:
    violations: list[Violation] = []
    for path in _iter_python_files(paths):
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source, filename=str(path))
        visitor = _SilentExceptionVisitor(path=path, lines=lines)
        visitor.visit(tree)
        violations.extend(visitor.violations)
    return violations


def _iter_python_files(paths: list[Path]):
    for path in paths:
        if path.is_dir():
            yield from sorted(path.rglob("*.py"))
        elif path.suffix == ".py":
            yield path


class _SilentExceptionVisitor(ast.NodeVisitor):
    def __init__(self, *, path: Path, lines: list[str]) -> None:
        self.path = path
        self.lines = lines
        self.violations: list[Violation] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if (
            self._is_broad_exception(node)
            and self._has_return_or_pass(node)
            and not self._has_log_call(node)
            and not self._has_noqa(node)
        ):
            self.violations.append(
                Violation(
                    path=self.path,
                    line=node.lineno,
                    message="broad except 中 return/pass 必须先记录日志",
                )
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_farm_id_default_get(node):
            self.violations.append(
                Violation(
                    path=self.path,
                    line=node.lineno,
                    message="farm_id 禁止使用整数默认值回退",
                )
            )
        self.generic_visit(node)

    def _is_broad_exception(self, node: ast.ExceptHandler) -> bool:
        if node.type is None:
            return True
        return _contains_broad_exception(node.type)

    def _has_return_or_pass(self, node: ast.ExceptHandler) -> bool:
        return any(isinstance(child, ast.Return | ast.Pass) for child in ast.walk(node))

    def _has_log_call(self, node: ast.ExceptHandler) -> bool:
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if isinstance(func, ast.Name) and func.id in {
                "log_silent_exception",
                "log_event",
            }:
                return True
            if isinstance(func, ast.Attribute) and func.attr in LOG_METHODS:
                return True
        return False

    def _has_noqa(self, node: ast.ExceptHandler) -> bool:
        end_lineno = getattr(node, "end_lineno", node.lineno)
        for lineno in range(node.lineno, end_lineno + 1):
            if NOQA_MARKER in self.lines[lineno - 1]:
                return True
        return False

    def _is_farm_id_default_get(self, node: ast.Call) -> bool:
        if len(node.args) < 2:
            return False
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "get":
            return False
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "state":
            return False
        first_arg = node.args[0]
        default_arg = node.args[1]
        return (
            isinstance(first_arg, ast.Constant)
            and first_arg.value == "farm_id"
            and isinstance(default_arg, ast.Constant)
            and isinstance(default_arg.value, int)
        )


def _contains_broad_exception(expr: ast.expr) -> bool:
    if isinstance(expr, ast.Name):
        return expr.id in {"Exception", "BaseException"}
    if isinstance(expr, ast.Attribute):
        return expr.attr in {"Exception", "BaseException"}
    if isinstance(expr, ast.Tuple):
        return any(_contains_broad_exception(item) for item in expr.elts)
    return False


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    paths = [Path(arg) for arg in args] if args else [Path("app/agent")]
    violations = find_violations(paths)
    for violation in violations:
        print(f"{violation.path}:{violation.line}: {violation.message}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
