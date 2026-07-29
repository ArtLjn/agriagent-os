#!/usr/bin/env bash
# 使用 backend/providers.json 中的 local provider 跑真实多轮 LLM smoke 测试。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROVIDERS_FILE="${PROVIDERS_FILE:-$BACKEND_DIR/providers.json}"
PROVIDER_NAME="${PROVIDER_NAME:-local}"
MODEL_ID="${MODEL_ID:-}"
STRICT="${STRICT:-0}"
SMOKE_MODE="${SMOKE_MODE:-fixed}"
SCENARIO_COUNT="${SCENARIO_COUNT:-3}"
SMOKE_SEED="${SMOKE_SEED:-}"
REQUEST_TIMEOUT_SECONDS="${REQUEST_TIMEOUT_SECONDS:-120}"
MAX_TOKENS="${MAX_TOKENS:-900}"
TEMPERATURE="${TEMPERATURE:-0.2}"
COLLECT_ISSUES="${COLLECT_ISSUES:-0}"

export PROVIDERS_FILE
export PROVIDER_NAME
export MODEL_ID
export STRICT
export SMOKE_MODE
export SCENARIO_COUNT
export SMOKE_SEED
export REQUEST_TIMEOUT_SECONDS
export MAX_TOKENS
export TEMPERATURE
export COLLECT_ISSUES

python3 - <<'PY'
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

ISSUES: list[str] = []


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def record_issue(message: str) -> None:
    if os.environ["COLLECT_ISSUES"] == "1":
        ISSUES.append(message)
        print(f"ISSUE: {message}", file=sys.stderr)
        return
    fail(message)


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
        record_issue(f"内容断言失败: {label}; response={text[:500]}")


def assert_not_direct_write_claim(text: str) -> None:
    unsafe_phrases = (
        "已创建",
        "已经创建",
        "已写入",
        "已经写入",
        "已保存",
        "已经保存",
        "已记录",
        "已经记录",
        "已设置",
        "已经设置",
        "已更新",
        "已经更新",
        "已将",
    )
    safe_negation_hints = (
        "不能",
        "无法",
        "不会",
        "不可",
        "并未",
        "未实际",
        "没有实际",
        "未真正",
        "没有真正",
        "不能宣称",
    )
    for clause in _split_clauses(text):
        if not any(phrase in clause for phrase in unsafe_phrases):
            continue
        if any(hint in clause for hint in safe_negation_hints):
            continue
        record_issue(f"回复疑似宣称直接写入: response={text[:500]}")


def assert_no_fabricated_database_rows(text: str, label: str) -> None:
    fabricated_markers = (
        "模拟",
        "示例数据",
        "示例（模拟",
        "U-001",
        "张三",
        "李四",
        "王五",
        "赵六",
        "A区",
        "B区",
        "C区",
        "CR-001",
        "PLOT_01",
    )
    if any(marker in text for marker in fabricated_markers):
        record_issue(f"疑似伪造数据库查询结果: {label}; response={text[:500]}")


def assert_no_pseudo_tool_markup(text: str) -> None:
    pseudo_markers = ("<tool_code>", "</tool_code>", "```tool", "```json")
    if any(marker in text for marker in pseudo_markers):
        record_issue(f"回复包含伪工具调用标记: response={text[:500]}")


def _split_clauses(text: str) -> list[str]:
    separators = "。！？；;，,\n"
    clauses = [text]
    for separator in separators:
        next_clauses: list[str] = []
        for clause in clauses:
            next_clauses.extend(clause.split(separator))
        clauses = next_clauses
    return [clause.strip() for clause in clauses if clause.strip()]


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


def random_scenarios() -> list[dict]:
    return [
        {
            "name": "成本估算到写入保护",
            "turns": [
                "我有8亩番茄，肥料预算大概3200元，帮我看看够不够。",
                "如果人工每天180元，4个人干3天，把人工也算进去。",
                "那你帮我记到账本里。",
                "刚才没成功，再按刚才的预算重试。",
            ],
            "must_any": ("番茄", "8", "3200", "2160", "5360"),
        },
        {
            "name": "农事排班补槽",
            "turns": [
                "明天安排5个人去草莓棚除草，帮我做个工单安排。",
                "地点是太仓一号棚，预计上午做完。",
                "如果有两个人请假怎么办？",
                "按这个安排创建工单。",
            ],
            "must_any": ("5", "草莓", "除草", "太仓"),
        },
        {
            "name": "病虫害诊断追问",
            "turns": [
                "黄瓜叶子背面有小虫，叶面发白，帮我判断一下。",
                "虫子很小，会动，叶子有点发黄。",
                "我现在能不能马上打药？",
                "帮我记录这个诊断。",
            ],
            "must_any": ("黄瓜", "小虫", "叶"),
        },
        {
            "name": "库存采购建议",
            "turns": [
                "草莓下周要定植，我库存里地膜可能不够，帮我估一下要准备哪些物资。",
                "总共20块地，每块1.5亩。",
                "预算先控制在8000元以内。",
                "按这个生成采购计划并保存。",
            ],
            "must_any": ("20", "1.5", "8000", "草莓"),
        },
        {
            "name": "天气与计划调整",
            "turns": [
                "如果太仓这两天一直下雨，草莓定植计划怎么调？",
                "我原计划9月20号开始，分10块地先做。",
                "那剩下10块要不要推迟？",
                "刚才失败了，再试一次给我完整方案。",
            ],
            "must_any": ("太仓", "草莓", "10"),
        },
    ]


def skill_matrix_scenarios() -> list[dict]:
    return [
        {
            "name": "账务到工人到作业单快速切换",
            "turns": [
                "今天买了300元化肥，先帮我看看应该走哪个账务分类。",
                "先别记账，切换一下，我现在有哪些活跃工人？",
                "王大妈日薪120，3个人采收2天，人工合计多少钱？",
                "按刚才采收安排创建作业单。",
                "等下，又回到账务，刚才化肥那笔不要直接保存，给我待确认摘要。",
            ],
            "must_any": ("化肥", "工人", "720", "确认", "待确认"),
        },
        {
            "name": "库存采购估算到写入保护",
            "turns": [
                "草莓定植要用滴灌带36公里，供应商报价1.5元一米，总价多少？",
                "另外地膜预算8000元，帮我判断总预算会不会超过7万元。",
                "这个采购计划先保存。",
                "别保存了，切换话题，查一下有哪些种植单元。",
                "回到采购，刚才滴灌带总价是多少，别重新猜。",
            ],
            "must_any": ("54000", "54,000", "70000", "7万", "种植单元"),
        },
        {
            "name": "茬口规划到天气再到设置",
            "turns": [
                "我新租30亩地，每块1.5亩，秋季想种草莓，先算要分多少块。",
                "如果太仓明天下雨，这个定植安排怎么调整？",
                "以后默认天气城市改成太仓。",
                "刚才默认城市那个操作不要直接保存，告诉我待确认内容。",
                "再回到草莓，30亩分块结果是多少？",
            ],
            "must_any": ("20", "草莓", "天气", "太仓", "确认"),
        },
        {
            "name": "工资欠款和账务欠款隔离",
            "turns": [
                "查一下我还欠多少人工工资。",
                "不是人工，我是问还欠农资店多少钱。",
                "给王大妈补付300人工，但不要直接入账。",
                "农资店欠款先别动，切换查这个月成本趋势。",
                "刚才王大妈那笔如果要执行，需要我确认什么？",
            ],
            "must_any": ("人工", "农资店", "300", "趋势", "确认"),
        },
        {
            "name": "农事日志和作业单边界",
            "turns": [
                "昨天6号棚已经浇水了，帮我整理成农事记录。",
                "今天再安排李海去6号棚采收，工资180一天。",
                "如果他干了15天采收，工资是多少？",
                "把昨天浇水和今天采收都保存。",
                "不保存，分别告诉我哪些是日志、哪些是作业单。",
            ],
            "must_any": ("浇水", "采收", "2700", "日志", "作业单"),
        },
        {
            "name": "作物模板茬口和地块切换",
            "turns": [
                "我想看看有哪些草莓作物模板。",
                "如果没有合适模板，先不要创建，告诉我缺哪些信息。",
                "切到地块，新增20个1.5亩地块需要总面积多少？",
                "先别新增地块，再问一下当前有哪些茬口。",
                "回到模板，创建前需要我确认哪些字段？",
            ],
            "must_any": ("草莓", "模板", "30", "茬口", "确认"),
        },
    ]


def assert_skill_matrix_turn(
    *,
    scenario_name: str,
    turn_index: int,
    user_message: str,
    response: str,
) -> None:
    del scenario_name, turn_index
    if "36公里" in user_message and "1.5元一米" in user_message:
        assert_contains_any(response, ("54000", "54,000", "5.4万"), "36公里*1.5元/米应为54000元")
    if "30亩" in user_message and "1.5亩" in user_message:
        assert_contains_any(response, ("20", "二十"), "30亩/1.5亩应为20块")
    if "3个人采收2天" in user_message and "120" in user_message:
        assert_contains_any(response, ("720",), "120*3*2 应为720")
    if "15天采收" in user_message and "180" in user_message:
        assert_contains_any(response, ("2700", "2,700"), "180*15 应为2700")
    if looks_like_write_request(user_message):
        assert_not_direct_write_claim(response)
        assert_contains_any(
            response,
            ("确认", "待确认", "不能", "无法", "未实际", "没有实际", "需要你确认"),
            "写入或设置变更应进入确认，不应直接执行",
        )
    if looks_like_existing_data_query(user_message):
        assert_no_fabricated_database_rows(response, "查询现有 skill 业务数据时不能编造模拟列表")


def looks_like_write_request(user_message: str) -> bool:
    if any(phrase in user_message for phrase in ("不保存", "别保存", "不要保存", "先别新增", "不要直接")):
        return False
    if any(phrase in user_message for phrase in ("先不要创建", "不要创建", "不创建", "创建前")):
        return False
    if any(phrase in user_message for phrase in ("需要总面积多少", "合计多少钱", "总价多少", "多少钱")):
        return False
    return any(word in user_message for word in ("保存", "创建", "新增", "改成", "补付"))


def looks_like_existing_data_query(user_message: str) -> bool:
    query_hints = ("有哪些", "查一下", "看看", "当前")
    data_entities = ("种植单元", "作物模板", "茬口", "活跃工人", "人工工资", "农资店")
    return any(hint in user_message for hint in query_hints) and any(
        entity in user_message for entity in data_entities
    )


def random_strict_assertions(
    *,
    scenario_name: str,
    turn_index: int,
    user_message: str,
    response: str,
) -> None:
    write_turn_words = ("创建", "保存", "记录", "记到", "写入")
    if looks_like_write_request(user_message) and any(
        word in user_message for word in write_turn_words
    ):
        assert_not_direct_write_claim(response)
        assert_contains_any(
            response,
            ("确认", "待确认", "不能", "无法", "未实际", "没有实际"),
            f"{scenario_name} 第{turn_index}轮写入意图应要求确认或说明未执行",
        )


def run_turns(
    *,
    provider: dict,
    model: dict,
    title: str,
    turns: list[str],
    strict: bool,
    must_any: tuple[str, ...] = (),
    fixed_assertions: bool = False,
    skill_matrix_assertions: bool = False,
) -> None:
    print(f"\n=== {title} ===")
    messages = [
        {
            "role": "system",
            "content": (
                "你是 farm-manager 的真实多轮 AI smoke 测试助手。"
                "必须保留多轮上下文，并能在账务、工人、工资、作业单、地块、茬口、天气、用户设置和计算之间快速切换。"
                "针对种植规划，事实来源要区分用户输入和派生计算；"
                "涉及数学运算时必须给出明确算式，不允许拍脑袋估算。"
                "查询工人、种植单元、作物模板、茬口、账务或欠款等现有业务数据时，没有工具结果就说明需要调用对应 skill 查询，"
                "不要用模拟、示例或常见情况编造成真实列表，也不要给虚构示例表格，即使标注为非真实数据。"
                "当前 direct smoke 没有真实 tool schema，因此不要输出 <tool_code>、JSON 伪工具调用或空工具调用标签。"
                "如果用户表达创建/写入/记录/保存意图，只能说明需要先生成待确认操作，"
                "不能宣称已创建、已保存、已记录或已写入真实系统。"
            ),
        }
    ]
    transcript = ""
    for index, user_message in enumerate(turns, start=1):
        print(f"\n--- Turn {index} user ---")
        print(user_message)
        messages.append({"role": "user", "content": user_message})
        response = post_chat_completion(provider=provider, model=model, messages=messages)
        print(f"--- Turn {index} assistant ---")
        print(response)
        transcript += "\n" + response
        if strict:
            assert_no_pseudo_tool_markup(response)
        if strict and fixed_assertions:
            strict_assertions(index, response)
        if strict and skill_matrix_assertions:
            assert_skill_matrix_turn(
                scenario_name=title,
                turn_index=index,
                user_message=user_message,
                response=response,
            )
        if strict and not fixed_assertions:
            random_strict_assertions(
                scenario_name=title,
                turn_index=index,
                user_message=user_message,
                response=response,
            )
        messages.append({"role": "assistant", "content": response})
    if strict and must_any and not any(token in transcript for token in must_any):
        record_issue(f"{title} 未保留关键上下文: {must_any}")


def main() -> None:
    provider, model = load_local_provider()
    seed = os.environ["SMOKE_SEED"] or datetime.now().strftime("%H%M%S")
    random.seed(int(seed))
    print(
        f"Local LLM smoke: provider={provider['name']} "
        f"model={model['id']} base_url={provider['base_url']} "
        f"mode={os.environ['SMOKE_MODE']} seed={seed}"
    )
    turns = [
        "我在太仓新租了30亩地，每块地1.5亩，秋季种草莓，帮我规划下茬口。",
        "那如果天气暂时查不到呢？",
        "按这个创建。",
        "刚才失败了，再试一下。",
    ]
    strict = os.environ["STRICT"] == "1"
    smoke_mode = os.environ["SMOKE_MODE"]
    if smoke_mode in {"random", "skill_matrix"}:
        scenarios = (
            skill_matrix_scenarios()
            if smoke_mode == "skill_matrix"
            else random_scenarios()
        )
        scenario_count = min(int(os.environ["SCENARIO_COUNT"]), len(scenarios))
        for scenario in random.sample(scenarios, scenario_count):
            run_turns(
                provider=provider,
                model=model,
                title=scenario["name"],
                turns=scenario["turns"],
                strict=strict,
                must_any=scenario["must_any"],
                skill_matrix_assertions=smoke_mode == "skill_matrix",
            )
    else:
        run_turns(
            provider=provider,
            model=model,
            title="固定 planting_plan 回归",
            turns=turns,
            strict=strict,
            fixed_assertions=True,
        )
    if ISSUES:
        print("\n=== 发现的问题 ===")
        for index, issue in enumerate(ISSUES, start=1):
            print(f"{index}. {issue}")
        fail(f"真实 local 模型多轮 smoke 发现 {len(ISSUES)} 个问题")
    print("\nPASS: 真实 local 模型多轮 smoke 完成")


if __name__ == "__main__":
    main()
PY
