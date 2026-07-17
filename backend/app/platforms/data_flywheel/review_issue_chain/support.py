"""ReviewIssueChain repository 调用辅助。"""

from app.infra.repository_runtime import (
    get_data_flywheel_repository,
    run_maybe_awaitable,
)


def review_chain_repo(db):
    return get_data_flywheel_repository(db, "review_issue_chains")


def repo_call(method, *args, **kwargs):
    return run_maybe_awaitable(method(*args, **kwargs))
