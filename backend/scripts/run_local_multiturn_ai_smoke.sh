#!/usr/bin/env bash
# 使用 backend/providers.json 中的 local provider 跑真实多轮 LLM smoke 测试。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROVIDERS_FILE="${PROVIDERS_FILE:-$BACKEND_DIR/providers.json}"
PROVIDER_NAME="${PROVIDER_NAME:-local}"
MODEL_ID="${MODEL_ID:-}"
STRICT="${STRICT:-0}"
REQUEST_TIMEOUT_SECONDS="${REQUEST_TIMEOUT_SECONDS:-120}"
MAX_TOKENS="${MAX_TOKENS:-900}"
TEMPERATURE="${TEMPERATURE:-0.2}"

export PROVIDERS_FILE
export PROVIDER_NAME
export MODEL_ID
export STRICT
export REQUEST_TIMEOUT_SECONDS
export MAX_TOKENS
export TEMPERATURE

python3 - <<'PY'
import json
import os
import sys
import time
import urllib.error
import urllib.request


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def load_local_provider() -> tuple[dict, dict]:
    providers_file = os.environ["PROVIDERS_FILE"]
    provider_name = os.environ["PROVIDER_NAME"]
    try:
        with open(providers_file, encoding="utf-8") as handle:
            config = json.load(handle)
    except FileNotFoundError:
        fail(f"找不到 providers.json: {providers_file}")
    except json.JSONDecodeError as exc:
        fail(f"providers.json 不是合法 JSON: {exc}")

    provider = next(
        (
            item
            for item in config.get("providers", [])
            if item.get("name") == provider_name
        ),
        None,
    )
    if not provider:
        fail(f"providers.json 中找不到 provider: {provider_name}")
    if provider.get("enabled") is False:
        fail(f"provider 已禁用: {provider_name}")
    if not provider.get("api_keys"):
        fail(f"provider 没有 api_keys: {provider_name}")

    model_id = os.environ.get("MODEL_ID") or ""
    enabled_models = [
        model for model in provider.get("models", []) if model.get("enabled", True)
    ]
    if model_id:
        model = next(
            (item for item in enabled_models if item.get("id") == model_id),
            None,
        )
        if not model:
            fail(f"{provider_name} 中找不到启用模型: {model_id}")
    elif enabled_models:
        model = sorted(enabled_models, key=lambda item: item.get("priority", 99))[0]
    else:
        fail(f"provider 没有启用模型: {provider_name}")
    return provider, model


def post_chat_completion(
    *,
    provider: dict,
    model: dict,
    messages: list[dict],
) -> str:
    base_url = str(provider["base_url"]).rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model["id"],
        "messages": messages,
        "temperature": float(os.environ["TEMPERATURE"]),
        "max_tokens": int(os.environ["MAX_TOKENS"]),
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {provider['api_keys'][0]}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(
            request,
            timeout=int(os.environ["REQUEST_TIMEOUT_SECONDS"]),
        ) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:600]
        fail(f"LLM HTTP {exc.code}: {error_body}")
    except urllib.error.URLError as exc:
        fail(f"LLM 连接失败: {exc}")
    except TimeoutError:
        fail("LLM 请求超时")

    try:
        data = json.loads(response_body)
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        fail(f"LLM 响应格式异常: {exc}; raw={response_body[:600]}")
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    if not str(content).strip():
        fail("LLM 返回空内容")
    print(f"耗时: {elapsed_ms}ms")
    return str(content).strip()


def assert_contains_any(text: str, values: tuple[str, ...], label: str) -> None:
    if not any(value in text for value in values):
        fail(f"内容断言失败: {label}; response={text[:500]}")


def assert_not_direct_write_claim(text: str) -> None:
    unsafe_phrases = ("已创建", "已经创建", "已写入", "已经写入", "已保存", "已经保存")
    if any(phrase in text for phrase in unsafe_phrases):
        fail(f"回复疑似宣称直接写入: response={text[:500]}")


def strict_assertions(turn_index: int, response: str) -> None:
    if turn_index == 1:
        assert_contains_any(response, ("草莓",), "首轮应保留作物")
        assert_contains_any(response, ("30", "三十"), "首轮应保留总面积")
        assert_contains_any(response, ("1.5", "一点五"), "首轮应保留单块面积")
        assert_contains_any(response, ("20", "二十"), "首轮应包含派生块数")
    if turn_index == 2:
        assert_contains_any(response, ("天气", "不确定", "暂时"), "二轮应承接天气不可用")
    if turn_index == 3:
        assert_not_direct_write_claim(response)
        assert_contains_any(response, ("确认", "待确认", "不会直接", "不能直接"), "写入意图应要求确认")
    if turn_index == 4:
        assert_contains_any(response, ("上", "刚才", "继续", "重试", "恢复"), "重试轮应承接上下文")


def main() -> None:
    provider, model = load_local_provider()
    print(
        f"Local LLM smoke: provider={provider['name']} "
        f"model={model['id']} base_url={provider['base_url']}"
    )
    messages = [
        {
            "role": "system",
            "content": (
                "你是 farm-manager 的真实多轮 AI smoke 测试助手。"
                "必须保留多轮上下文。针对种植规划，事实来源要区分用户输入和派生计算；"
                "如果用户表达创建/写入意图，只能说明需要先生成待确认操作，不能宣称已创建、已保存或已写入。"
            ),
        }
    ]
    turns = [
        "我在太仓新租了30亩地，每块地1.5亩，秋季种草莓，帮我规划下茬口。",
        "那如果天气暂时查不到呢？",
        "按这个创建。",
        "刚才失败了，再试一下。",
    ]
    strict = os.environ["STRICT"] == "1"
    for index, user_message in enumerate(turns, start=1):
        print(f"\n--- Turn {index} user ---")
        print(user_message)
        messages.append({"role": "user", "content": user_message})
        response = post_chat_completion(provider=provider, model=model, messages=messages)
        print(f"--- Turn {index} assistant ---")
        print(response)
        if strict:
            strict_assertions(index, response)
        messages.append({"role": "assistant", "content": response})
    print("\nPASS: 真实 local 模型多轮 smoke 完成")


if __name__ == "__main__":
    main()
PY
