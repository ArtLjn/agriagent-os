import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.agent.llm import get_llm
from app.prompt.composer import get_composer
from app.core.date_context import get_request_date
from app.core.json_repair import safe_parse_json
from app.models.farm import Farm
from app.models.idempotency_key import IdempotencyKey
from app.schemas.cost import CostParseResponse, CostParseResult
from app.schemas.crop import CropTemplateParseResponse
from app.schemas.cycle import CycleParseResponse
from app.schemas.planting import WorkerCreate
from app.schemas.smart_fill import (
    SmartFillParseRequest,
    SmartFillParseResponse,
    SmartFillScenarioResponse,
)
from app.services import crop_service

logger = logging.getLogger(__name__)

ContextBuilder = Callable[[SmartFillParseRequest, Farm, Session], dict[str, Any]]
ResultValidator = Callable[[BaseModel, dict[str, Any]], BaseModel]


@dataclass(frozen=True)
class SmartFillScenario:
    """Agent 应用层智能填写场景注册项。"""

    key: str
    title: str
    description: str
    prompt_key: str
    output_model: type[BaseModel]
    request_example: str
    legacy_endpoint: str | None = None
    result_model: type[BaseModel] | None = None
    context_builder: ContextBuilder | None = None
    validator: ResultValidator | None = None
    enabled: bool = True
    use_request_date: bool = False
    compose_extra: dict[str, Any] = field(default_factory=dict)

    def to_response(self) -> SmartFillScenarioResponse:
        return SmartFillScenarioResponse(
            key=self.key,
            title=self.title,
            description=self.description,
            legacy_endpoint=self.legacy_endpoint,
            enabled=self.enabled,
            request_example=self.request_example,
        )


def list_scenarios() -> list[SmartFillScenarioResponse]:
    """列出所有智能填写场景。"""
    return [scenario.to_response() for scenario in _SCENARIOS.values()]


async def parse_smart_fill(
    req: SmartFillParseRequest,
    farm: Farm,
    db: Session,
    idempotency_key: str | None = None,
) -> SmartFillParseResponse:
    """按场景解析自然语言，返回统一表单草稿。"""
    scenario = get_scenario(req.scene)
    cache_key = _build_cache_key(idempotency_key, scenario.key, farm.id)
    cached = _load_cached_response(db, cache_key)
    if cached:
        return cached

    prompt_vars = _build_prompt_vars(scenario, req, farm, db)
    compose_kwargs = dict(scenario.compose_extra)
    if scenario.use_request_date:
        compose_kwargs["current_date"] = get_request_date()
    prompt = get_composer().compose(scenario.prompt_key, prompt_vars, **compose_kwargs)
    logger.info(
        "智能填写解析 | farm=%s | scene=%s | input=%s",
        farm.id,
        scenario.key,
        req.text,
    )

    llm = get_llm()
    parsed = await parse_with_llm(llm, prompt, scenario.output_model)
    validated = _validate_result(scenario, parsed, prompt_vars)
    metadata = _build_response_metadata(scenario, validated, prompt_vars)
    response = SmartFillParseResponse(
        scene=scenario.key,
        draft=validated.model_dump(mode="json"),
        missing_fields=metadata["missing_fields"],
        warnings=metadata["warnings"],
    )
    _store_cached_response(db, cache_key, response)
    return response


async def parse_with_llm(
    llm,
    prompt: str,
    output_model: type[BaseModel],
) -> BaseModel:
    """统一 LLM 结构化解析，失败时回退到 JSON 容错解析。"""
    try:
        structured_llm = llm.with_structured_output(
            output_model, method="function_calling"
        )
        return await structured_llm.ainvoke([HumanMessage(content=prompt)])
    except ValidationError as structured_err:
        logger.warning(
            "with_structured_output 校验失败，回退到 JSON 解析 | model=%s | errors=%d",
            output_model.__name__,
            len(structured_err.errors()),
        )
    except Exception as structured_err:
        logger.warning(
            "with_structured_output 失败，回退到 JSON 解析 | model=%s | error=%s",
            output_model.__name__,
            structured_err,
            exc_info=True,
        )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
    except Exception as exc:
        logger.error("AI 调用失败 | error=%s", exc)
        raise HTTPException(status_code=503, detail="AI 服务暂时不可用，请稍后重试")

    reply = response.content
    try:
        data = safe_parse_json(reply)
    except ValueError:
        logger.error("AI 返回无法解析 | raw=%s", str(reply)[:200])
        raise HTTPException(
            status_code=422, detail=f"AI 返回格式异常: {str(reply)[:100]}"
        )

    try:
        return output_model.model_validate(data)
    except Exception as exc:
        logger.error(
            "AI 返回数据校验失败 | model=%s | error=%s", output_model.__name__, exc
        )
        raise HTTPException(status_code=422, detail="AI 返回数据无法通过校验")


def get_scenario(scene: str) -> SmartFillScenario:
    scenario = _SCENARIOS.get(scene)
    if not scenario or not scenario.enabled:
        raise HTTPException(status_code=404, detail=f"不支持的智能填写场景: {scene}")
    return scenario


def _build_prompt_vars(
    scenario: SmartFillScenario,
    req: SmartFillParseRequest,
    farm: Farm,
    db: Session,
) -> dict[str, Any]:
    values = {"description": req.text, "original_text": req.text}
    if scenario.context_builder:
        values.update(scenario.context_builder(req, farm, db))
    return values


def _build_cycle_context(
    _req: SmartFillParseRequest,
    farm: Farm,
    db: Session,
) -> dict[str, Any]:
    templates = crop_service.get_crop_templates(db, farm_id=farm.id)
    template_list = [
        {"id": item.id, "name": item.name, "variety": item.variety}
        for item in templates
    ]
    return {"templates": template_list, "today": date.today().isoformat()}


def _validate_result(
    scenario: SmartFillScenario,
    parsed: BaseModel,
    prompt_vars: dict[str, Any],
) -> BaseModel:
    result = parsed
    if scenario.validator:
        result = scenario.validator(result, prompt_vars)
    if scenario.result_model:
        try:
            result = scenario.result_model.model_validate(
                result.model_dump(mode="json")
            )
        except Exception:
            logger.warning("智能填写返回数据无法通过响应校验 | scene=%s", scenario.key)
            raise HTTPException(
                status_code=422, detail=_error_message_for(scenario.key)
            )
    return result


def _validate_cost_result(parsed: BaseModel, prompt_vars: dict[str, Any]) -> BaseModel:
    if not isinstance(parsed, CostParseResult):
        parsed = CostParseResult.model_validate(parsed.model_dump(mode="json"))
    if parsed.amount in ("0", "0.0", "0.00"):
        raise HTTPException(status_code=422, detail=_error_message_for("ledger.record"))
    original_text = prompt_vars.get("original_text", "")
    if not parsed.note:
        parsed.note = _infer_cost_note(original_text)
    _apply_debt_fields(parsed, original_text)
    return parsed


def _apply_debt_fields(parsed: CostParseResult, original_text: str) -> None:
    debt_sources = [value for value in (original_text, parsed.note or "") if value]
    debt_source = " ".join(debt_sources)
    if not _looks_like_debt(debt_source):
        return
    parsed.record_subtype = "赊账"
    if not parsed.counterparty:
        parsed.counterparty = _infer_counterparty(debt_sources)


def _looks_like_debt(text: str) -> bool:
    return bool(
        re.search(r"(赊账|赊了|赊|欠账|欠款|欠[^，,。；;]*\d|未付|未收款)", text)
    )


def _infer_counterparty(texts: list[str]) -> str | None:
    patterns = [
        r"(?:向|跟|找|在)(?P<name>[\u4e00-\u9fffA-Za-z0-9·]{1,30})(?:那|那里|这边|处)?(?:赊账|赊了|赊|欠账|欠款)",
        r"欠(?P<name>[\u4e00-\u9fffA-Za-z0-9·]{1,12}?)(?=\d)",
        r"欠(?P<name>[\u4e00-\u9fffA-Za-z0-9·]{1,12}?)(?=(?:两|一|二|四|五|六|七|八|九|十|百|千|万))",
        r"(?:赊账|赊了|赊|欠账|欠款)(?:给|向|跟)?(?P<name>[\u4e00-\u9fffA-Za-z0-9·]{1,30})",
    ]
    for text in texts:
        normalized = re.sub(r"\s+", "", text)
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                return _clean_counterparty(match.group("name"))
    return None


def _clean_counterparty(value: str) -> str | None:
    cleaned = re.sub(
        r"^(今天|昨日|昨天|前天|明天|上午|下午|晚上|早上|中午|买|卖|购入|购买|收入|支出)+",
        "",
        value,
    )
    cleaned = re.sub(r"(那|那里|这边|处)$", "", cleaned)
    return cleaned[:100] or None


def _infer_cost_note(text: str) -> str | None:
    value = text.strip()
    if not value:
        return None
    value = re.sub(r"[，,。；;！!？?]+$", "", value)
    value = re.sub(
        r"^(今天|昨日|昨天|前天|明天|刚刚|上午|下午|晚上|早上|中午)", "", value
    )
    value = re.sub(r"\d+(?:\.\d+)?\s*(?:元|块|块钱|￥|¥)?", "", value)
    value = re.sub(r"(?:记到|关联到|关联|算到|归到|录到).*$", "", value)
    value = value.strip(" ，,。；;")
    return value[:500] or None


def _validate_crop_template_result(
    parsed: BaseModel,
    _prompt_vars: dict[str, Any],
) -> BaseModel:
    result = CropTemplateParseResponse.model_validate(parsed.model_dump(mode="json"))
    if not result.stages:
        raise HTTPException(status_code=422, detail=_error_message_for("crop.template"))
    return result


def _validate_cycle_result(parsed: BaseModel, prompt_vars: dict[str, Any]) -> BaseModel:
    result = CycleParseResponse.model_validate(parsed.model_dump(mode="json"))
    templates = prompt_vars.get("templates", [])
    template_ids = {item["id"] for item in templates}
    if (
        result.crop_template_id is not None
        and result.crop_template_id not in template_ids
    ):
        result.crop_template_id = None
    if not result.name:
        raise HTTPException(status_code=422, detail=_error_message_for("crop.cycle"))
    return result


def _validate_worker_result(
    parsed: BaseModel,
    _prompt_vars: dict[str, Any],
) -> BaseModel:
    data = parsed.model_dump(mode="json")
    data["name"] = str(data.get("name") or "").strip()
    if not data["name"]:
        raise HTTPException(status_code=422, detail=_error_message_for("labor.worker"))
    data["phone"] = _clean_optional_text(data.get("phone"), max_length=30)
    data["note"] = _clean_optional_text(data.get("note"), max_length=500)
    data["default_pay_type"] = _normalize_pay_type(data.get("default_pay_type"))
    data["status"] = _normalize_worker_status(data.get("status"))
    try:
        return WorkerCreate.model_validate(data)
    except ValidationError:
        logger.warning("智能填写工人草稿无法通过响应校验", exc_info=True)
        raise HTTPException(status_code=422, detail=_error_message_for("labor.worker"))


def _build_response_metadata(
    scenario: SmartFillScenario,
    validated: BaseModel,
    prompt_vars: dict[str, Any],
) -> dict[str, list[str]]:
    if scenario.key == "labor.worker":
        return _build_worker_metadata(validated, prompt_vars)
    return {"missing_fields": [], "warnings": []}


def _build_worker_metadata(
    validated: BaseModel,
    prompt_vars: dict[str, Any],
) -> dict[str, list[str]]:
    worker = (
        validated
        if isinstance(validated, WorkerCreate)
        else WorkerCreate.model_validate(validated.model_dump(mode="json"))
    )
    original_text = str(prompt_vars.get("original_text") or "")
    warnings: list[str] = []
    missing_fields: list[str] = []
    if worker.phone and _looks_like_invalid_mobile_phone(worker.phone, original_text):
        worker.phone = None
        missing_fields.append("phone")
        warnings.append("手机号格式不正确，请检查后再创建工人。")
    if worker.default_unit_price is None and _pay_price_was_mentioned(original_text):
        missing_fields.append("default_unit_price")
        warnings.append("已提到计薪方式，但默认单价不明确，请补充后再创建工人。")
    return {"missing_fields": missing_fields, "warnings": warnings}


def _clean_optional_text(value: Any, *, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:max_length] or None


def _looks_like_invalid_mobile_phone(phone: str, original_text: str) -> bool:
    normalized = re.sub(r"[\s-]+", "", phone)
    if not normalized.isdigit():
        return False
    phone_is_named = bool(re.search(r"(电话|手机号|手机)", original_text))
    if not phone_is_named:
        return False
    if not normalized.startswith("1"):
        return False
    if len(normalized) == 11 and re.fullmatch(r"1[3-9]\d{9}", normalized):
        return False
    return True


def _pay_price_was_mentioned(original_text: str) -> bool:
    return bool(
        re.search(
            r"(日薪|时薪|计件|按天|按小时|按件|一天|每[天小时件亩棵斤]|工资|工钱)",
            original_text,
        )
    )


def _normalize_pay_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "日薪": "daily",
        "按天": "daily",
        "每天": "daily",
        "天": "daily",
        "daily": "daily",
        "小时": "hourly",
        "时薪": "hourly",
        "按小时": "hourly",
        "hourly": "hourly",
        "计件": "piece",
        "按件": "piece",
        "件": "piece",
        "piece": "piece",
    }
    return aliases.get(raw, "daily")


def _normalize_worker_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"inactive", "disabled", "离职", "停用", "不启用"}:
        return "inactive"
    return "active"


def _error_message_for(scene: str) -> str:
    return _ERROR_MESSAGES.get(scene, "无法识别智能填写内容，请补充更具体的信息")


def _build_cache_key(
    idempotency_key: str | None,
    scene: str,
    farm_id: int,
) -> str | None:
    if not idempotency_key:
        return None
    return f"smart_fill:farm:{farm_id}:{scene}:{idempotency_key}"


def _load_cached_response(
    db: Session,
    cache_key: str | None,
) -> SmartFillParseResponse | None:
    if not cache_key:
        return None
    cached = db.query(IdempotencyKey).filter(IdempotencyKey.key == cache_key).first()
    if not cached:
        return None
    try:
        return SmartFillParseResponse.model_validate(json.loads(cached.response))
    except Exception:
        logger.warning("智能填写幂等缓存解析失败，重新执行 | key=%s", cache_key)
        return None


def _store_cached_response(
    db: Session,
    cache_key: str | None,
    response: SmartFillParseResponse,
) -> None:
    if not cache_key:
        return
    try:
        db.add(IdempotencyKey(key=cache_key, response=response.model_dump_json()))
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("智能填写幂等缓存写入失败 | key=%s", cache_key)


_ERROR_MESSAGES = {
    "ledger.record": "无法识别记账内容，请描述具体的收支信息，例如：买了化肥200块",
    "crop.template": "无法识别作物信息，请描述作物名称，例如：我要种8424西瓜、种番茄",
    "crop.cycle": "无法识别茬口信息，请描述种植计划，例如：春季种番茄、秋茬种西瓜",
    "labor.worker": "无法识别工人信息，请描述工人姓名，例如：新增工人老王，日薪200",
}

_SCENARIOS = {
    "ledger.record": SmartFillScenario(
        key="ledger.record",
        title="智能记账",
        description="从自然语言提取收支类型、分类、金额、日期和备注。",
        legacy_endpoint="/costs/parse",
        prompt_key="cost_parse",
        output_model=CostParseResult,
        result_model=CostParseResponse,
        request_example="今天买复合肥128.5元，记到春季西瓜",
        validator=_validate_cost_result,
        use_request_date=True,
    ),
    "crop.template": SmartFillScenario(
        key="crop.template",
        title="智能作物模板",
        description="从作物描述生成作物名称、品种和生长阶段草稿。",
        legacy_endpoint="/crops/templates/parse",
        prompt_key="crop_template_parse",
        output_model=CropTemplateParseResponse,
        request_example="我要种8424西瓜，生成完整生长阶段",
        validator=_validate_crop_template_result,
    ),
    "crop.cycle": SmartFillScenario(
        key="crop.cycle",
        title="智能茬口",
        description="从种植计划提取茬口名称、模板、开始日期和地块。",
        legacy_endpoint="/cycles/parse",
        prompt_key="cycle_parse",
        output_model=CycleParseResponse,
        request_example="4月1日在东棚种一茬8424西瓜",
        context_builder=_build_cycle_context,
        validator=_validate_cycle_result,
    ),
    "labor.worker": SmartFillScenario(
        key="labor.worker",
        title="智能工人档案",
        description="从用工描述提取工人姓名、电话、默认计薪方式、默认单价和备注。",
        legacy_endpoint="/planting/workers",
        prompt_key="worker_parse",
        output_model=WorkerCreate,
        request_example="新增工人老王，电话 13800138000，日薪 200，擅长授粉",
        validator=_validate_worker_result,
    ),
}

__all__ = [
    "SmartFillScenario",
    "get_scenario",
    "list_scenarios",
    "parse_smart_fill",
    "parse_with_llm",
]
