import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models import AIModelConfig, Project, User, UserRole
from app.schemas import (
    AgentAnalyzeResponse,
    AgentQueryResponse,
    EvidenceItem,
    FindingItem,
)

log = logging.getLogger("report_agent")

RETRY_ATTEMPTS = 2

ANALYZE_PROMPT_TEMPLATE = (
    "你是企业项目评估助手。下面给出若干上下文段（每段以 [SOURCE_n] 标注），"
    "以及一些基于规则的基准计算（rule_basis）。\n"
    "请基于这些上下文和基准输出一个单一的 JSON 对象（不要输出任何额外的文本或解释），"
    "格式严格为：\n"
    "{\n"
    '  "reliability_score": number,\n'
    '  "sales_activity_score": number,\n'
    '  "findings": [\n'
    '    {"title":"...","detail":"...","score":number,'
    '"evidences":["SOURCE_1","SOURCE_3"]}\n'
    "  ],\n"
    '  "recommendations": ["...","..."],\n'
    '  "evidences": [\n'
    '    {"source":"SOURCE_1","source_type":"form_field",'
    '"source_id":123,"snippet":"..."}\n'
    "  ],\n"
    '  "rule_basis": {}\n'
    "}\n"
    "要求：\n"
    "1. findings 最多 6 条，每条至少包含 1 条 evidences（引用 SOURCE_n）。\n"
    "2. scores 保持数值类型（允许小数）。\n"
    "3. evidence snippet 最多 300 字，若包含敏感字段（手机号/身份证号），"
    "请对数字中间做脱敏（例如 13****7890）。\n"
    "4. 如果采用 rule_basis 的基线，务必在 JSON 中保留 rule_basis 字段并说明量化依据。\n"
    "5. 本次分析重点：__ANALYZE_TYPES__\n"
    "6. 项目编号：__PROJECT_ID__\n"
    "7. 项目名称：__PROJECT_NAME__\n"
    "\n"
    "rule_basis:\n__RULE_BASIS_JSON__\n"
    "\n"
    "上下文：\n__CONTEXTS_BLOCK__\n"
)

QUERY_PROMPT_TEMPLATE = (
    "你是企业项目评估助手。下面给出若干上下文段（每段以 [SOURCE_n] 标注）。\n"
    "请根据这些上下文回答用户问题，只输出一个单一 JSON 对象"
    "（不要输出任何额外解释），格式严格为：\n"
    "{\n"
    '  "answer": "...",\n'
    '  "score": number,\n'
    '  "sources": ["SOURCE_1", "SOURCE_2"]\n'
    "}\n"
    "要求：\n"
    "1. answer 使用自然语言回答，简洁但可执行。\n"
    "2. sources 至少引用 1 个 SOURCE_n，最多 4 个。\n"
    "3. score 为 0-100 的可信度分数。\n"
    "4. 如果上下文不足，请明确说明，并保持 sources 引用最相关片段。\n"
    "\n"
    "用户问题：__QUESTION__\n"
    "\n"
    "上下文：__CONTEXTS_BLOCK__\n"
)


def _render_prompt(template: str, **values: object) -> str:
    prompt = template
    for key, value in values.items():
        prompt = prompt.replace(f"__{key.upper()}__", str(value))
    return prompt


def _enum_value(value):
    if hasattr(value, "value"):
        return value.value
    return value


def _resolve_model(db: Session, model_id: Optional[int]) -> AIModelConfig:
    if model_id:
        model = (
            db.query(AIModelConfig)
            .filter(
                AIModelConfig.id == model_id,
                AIModelConfig.is_enabled.is_(True),
            )
            .first()
        )
    else:
        model = (
            db.query(AIModelConfig)
            .filter(AIModelConfig.is_enabled.is_(True))
            .order_by(AIModelConfig.is_default.desc(), AIModelConfig.id.asc())
            .first()
        )
    if not model:
        raise HTTPException(status_code=404, detail="未找到可用的 AI 模型配置")
    return model


def load_project_or_403(project_id: int, db: Session, current_user: User) -> Project:
    query = db.query(Project).options(joinedload(Project.followups))
    if current_user.role == UserRole.normal:
        query = query.filter(Project.created_by == current_user.id)
    elif current_user.role == UserRole.important:
        child_ids = [item.id for item in current_user.children]
        child_ids.append(current_user.id)
        query = query.filter(
            (Project.created_by.in_(child_ids))
            | (Project.approver_id == current_user.id)
        )
    elif current_user.role == UserRole.archive:
        raise HTTPException(status_code=403, detail="档案管理账号为只读权限，无法执行此操作")
    project = query.filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")
    return project


def _truncate_snippet(text: str, max_length: int = 300) -> str:
    clean = re.sub(r"\s+", " ", str(text or "").strip())
    return clean[:max_length]


def _mask_sensitive_numbers(text: str) -> str:
    clean = _truncate_snippet(text)

    def _repl(match):
        raw = match.group(0)
        if len(raw) <= 7:
            return raw
        return f"{raw[:2]}****{raw[-4:]}"

    return _truncate_snippet(re.sub(r"\d{8,18}", _repl, clean))


def _clamp_score(value: Optional[float], fallback: float) -> float:
    try:
        score = float(value)
    except Exception:
        score = float(fallback)
    return max(0.0, min(100.0, score))


def _context_lookup(contexts: List[dict]) -> Dict[str, dict]:
    return {item["source"]: item for item in contexts}


def _build_context_block(contexts: List[dict]) -> str:
    blocks = []
    for item in contexts:
        snippet = _mask_sensitive_numbers(item.get("text") or "")
        blocks.append(
            f"[{item['source']}]\n"
            "source_type="
            f"{item.get('source_type')}; "
            f"source_id={item.get('source_id')}; "
            f"field_name={item.get('field_name')}\n"
            f"{snippet}"
        )
    return "\n\n".join(blocks) if blocks else "[SOURCE_1]\n暂无可用上下文"


def _followup_stats(project: Project) -> dict:
    now = datetime.utcnow()
    followups = sorted(
        project.followups or [],
        key=lambda item: item.created_at or datetime.min,
    )
    last_followup = followups[-1] if followups else None
    recent_30d = 0
    for item in followups:
        created_at = item.created_at
        if created_at and (now - created_at) <= timedelta(days=30):
            recent_30d += 1
    return {
        "followup_count_total": len(followups),
        "followup_count_30d": recent_30d,
        "last_followup_at": (
            last_followup.created_at.isoformat()
            if last_followup and last_followup.created_at
            else None
        ),
        "last_followup_stage": (
            _enum_value(last_followup.stage) if last_followup else None
        ),
        "last_followup_progress": last_followup.progress if last_followup else None,
        "last_followup_days_ago": (
            (now - last_followup.created_at).days
            if last_followup and last_followup.created_at
            else None
        ),
    }


def _build_rule_basis(project: Project) -> dict:
    followup_stats = _followup_stats(project)
    reliability_baseline = 45.0
    sales_baseline = 35.0

    if project.partner_company:
        reliability_baseline += 8
    if project.responsible_sales:
        reliability_baseline += 6
        sales_baseline += 8
    if project.project_amount and float(project.project_amount) > 0:
        reliability_baseline += 8
    if project.tender_file or project.tender_folder:
        reliability_baseline += 10
    if project.bid_file or project.bid_folder:
        reliability_baseline += 6
    if project.form_instance_id:
        reliability_baseline += 5
    if followup_stats["followup_count_30d"] >= 2:
        sales_baseline += 20
    elif followup_stats["followup_count_30d"] == 1:
        sales_baseline += 10
    last_days = followup_stats["last_followup_days_ago"]
    if last_days is not None and last_days <= 7:
        sales_baseline += 12
    if followup_stats["followup_count_total"] >= 3:
        reliability_baseline += 5
        sales_baseline += 8

    return {
        "project_id": project.id,
        "approval_status": _enum_value(project.approval_status),
        "win_bid_status": _enum_value(project.win_bid_status),
        "has_tender_file": bool(project.tender_file or project.tender_folder),
        "has_bid_file": bool(project.bid_file or project.bid_folder),
        "has_responsible_sales": bool(project.responsible_sales),
        "has_partner_company": bool(project.partner_company),
        "has_form_instance": bool(project.form_instance_id),
        "project_amount": float(project.project_amount or 0),
        "expected_amount": float(project.expected_amount or 0),
        "baseline_reliability_score": round(min(reliability_baseline, 95.0), 2),
        "baseline_sales_activity_score": round(min(sales_baseline, 95.0), 2),
        **followup_stats,
    }


def _build_openai_client(model: AIModelConfig):
    try:
        from openai import OpenAI
    except Exception as exc:
        raise HTTPException(status_code=500, detail="缺少 openai 依赖，无法调用 LLM") from exc

    api_key = os.getenv("OPENAI_API_KEY") or model.api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="当前模型未配置 API Key")
    return OpenAI(
        api_key=api_key,
        base_url=model.base_url or None,
        timeout=float(model.timeout_seconds or 60),
    )


def _extract_message_text(response) -> str:
    try:
        content = response.choices[0].message.content
    except Exception as exc:
        raise HTTPException(status_code=500, detail="LLM 返回内容为空") from exc
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif hasattr(item, "text"):
                text_parts.append(getattr(item, "text"))
        content = "".join(text_parts)
    return str(content or "").strip()


def _call_llm(model: AIModelConfig, prompt: str) -> str:
    client = _build_openai_client(model)
    last_error = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = client.chat.completions.create(
                model=model.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=float(model.temperature or 0.2),
                max_tokens=int(model.max_tokens or 1200),
            )
            return _extract_message_text(response)
        except HTTPException:
            raise
        except Exception as exc:
            last_error = exc
            log.warning(
                "LLM 调用失败，第 %s/%s 次：%s",
                attempt,
                RETRY_ATTEMPTS,
                exc,
            )
            if attempt < RETRY_ATTEMPTS:
                time.sleep(0.5)
    log.exception("LLM 调用失败")
    raise HTTPException(status_code=500, detail="LLM 调用失败") from last_error


def _parse_single_json(raw_text: str) -> dict:
    return json.loads(raw_text)


def _json_or_retry(model: AIModelConfig, prompt: str) -> dict:
    last_raw = ""
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        raw = _call_llm(model, prompt)
        last_raw = raw
        try:
            return _parse_single_json(raw)
        except Exception:
            log.warning(
                "LLM 返回非法 JSON，第 %s/%s 次：%s",
                attempt,
                RETRY_ATTEMPTS,
                raw[:500],
            )
    log.warning("LLM 最终返回非法 JSON：%s", last_raw)
    raise HTTPException(status_code=500, detail="AI 模型返回了无效的 JSON")


def _context_to_evidence(
    context: Optional[dict],
    score: Optional[float] = None,
    snippet: Optional[str] = None,
) -> EvidenceItem:
    context = context or {}
    return EvidenceItem(
        source_type=str(context.get("source_type") or "form_field"),
        source_id=context.get("source_id"),
        score=score if score is not None else context.get("score"),
        snippet=_mask_sensitive_numbers(snippet or context.get("text") or ""),
    )


def _normalize_findings(findings: list, context_map: Dict[str, dict]) -> List[FindingItem]:
    normalized: List[FindingItem] = []
    for item in findings[:6]:
        evidence_refs = item.get("evidences") or []
        evidences = [
            _context_to_evidence(context_map.get(ref))
            for ref in evidence_refs
            if ref in context_map
        ]
        if not evidences:
            continue
        normalized.append(
            FindingItem(
                title=str(item.get("title") or "未命名发现"),
                detail=str(item.get("detail") or ""),
                score=item.get("score"),
                evidences=evidences,
            )
        )
    return normalized


def _normalize_top_evidences(evidences: list, context_map: Dict[str, dict]) -> List[EvidenceItem]:
    normalized: List[EvidenceItem] = []
    for item in evidences:
        source = item.get("source")
        context = context_map.get(source) if source else None
        default_snippet = context.get("text") if context else ""
        snippet = item.get("snippet") or default_snippet
        normalized.append(
            _context_to_evidence(
                context,
                score=item.get("score"),
                snippet=snippet,
            )
        )
    return normalized


def analyze(
    project_id: int,
    contexts: List[dict],
    analyze_types: List[str],
    model_id: Optional[int],
    db: Session,
    current_user: User,
    query: Optional[str] = None,
) -> AgentAnalyzeResponse:
    project = load_project_or_403(project_id, db, current_user)
    model = _resolve_model(db, model_id)
    context_map = _context_lookup(contexts)
    rule_basis = _build_rule_basis(project)
    prompt = _render_prompt(
        ANALYZE_PROMPT_TEMPLATE,
        analyze_types="、".join(analyze_types),
        project_id=project.id,
        project_name=project.project_name,
        user_query=query or "无",
        rule_basis_json=json.dumps(rule_basis, ensure_ascii=False, indent=2),
        contexts_block=_build_context_block(contexts),
    )
    payload = _json_or_retry(model, prompt)
    findings = _normalize_findings(payload.get("findings") or [], context_map)
    evidences = _normalize_top_evidences(payload.get("evidences") or [], context_map)
    if not evidences and findings:
        deduped: List[EvidenceItem] = []
        seen = set()
        for finding in findings:
            for evidence in finding.evidences:
                key = (evidence.source_type, evidence.source_id, evidence.snippet)
                if key not in seen:
                    seen.add(key)
                    deduped.append(evidence)
        evidences = deduped
    return AgentAnalyzeResponse(
        project_id=project.id,
        reliability_score=_clamp_score(
            payload.get("reliability_score"),
            rule_basis["baseline_reliability_score"],
        ),
        sales_activity_score=_clamp_score(
            payload.get("sales_activity_score"),
            rule_basis["baseline_sales_activity_score"],
        ),
        findings=findings,
        recommendations=[str(item) for item in (payload.get("recommendations") or [])][:6],
        evidences=evidences,
        rule_basis=payload.get("rule_basis") or rule_basis,
    )


def query(
    project_id: int,
    question: str,
    contexts: List[dict],
    model_id: Optional[int],
    db: Session,
    current_user: User,
) -> AgentQueryResponse:
    load_project_or_403(project_id, db, current_user)
    model = _resolve_model(db, model_id)
    prompt = _render_prompt(
        QUERY_PROMPT_TEMPLATE,
        question=question,
        contexts_block=_build_context_block(contexts),
    )
    payload = _json_or_retry(model, prompt)
    context_map = _context_lookup(contexts)
    source_refs = payload.get("sources") or []
    sources = [_context_to_evidence(context_map.get(ref)) for ref in source_refs if ref in context_map]
    return AgentQueryResponse(
        project_id=project_id,
        answer=str(payload.get("answer") or ""),
        sources=sources,
        score=_clamp_score(payload.get("score"), 60.0),
    )
