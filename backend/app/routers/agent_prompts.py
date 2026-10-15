"""AI Agent 系统提示词管理（管理员可配置多个角色模板）。

- 普通用户：可读 enable=True 的列表
- 管理员（role=admin）：可创建/修改/删除
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import AgentPrompt, User, UserRole
from app.schemas import (
    AgentPromptCreate,
    AgentPromptResponse,
    AgentPromptUpdate,
)

router = APIRouter(prefix="/api/agent-prompts", tags=["AI Agent Prompts"])
log = logging.getLogger("agent_prompts")


def _ensure_admin(user: User):
    role = getattr(user, 'role', None)
    role_val = role.value if hasattr(role, 'value') else role
    if role_val != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="仅管理员可修改系统提示词")


def _to_response(p: AgentPrompt) -> AgentPromptResponse:
    return AgentPromptResponse(
        id=p.id,
        name=p.name,
        role_key=p.role_key,
        content=p.content,
        description=p.description,
        enabled=p.enabled,
        created_by=p.created_by,
        created_by_name=p.creator.real_name if (p.creator and getattr(p.creator, 'real_name', None)) else (p.creator.username if p.creator else None),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=list[AgentPromptResponse])
def list_prompts(
    role_key: str | None = Query(default=None, description="按角色键筛选"),
    include_disabled: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出系统提示词模板。所有登录用户可读 enable=True 的；管理员可读全部。"""
    role_val = getattr(current_user.role, 'value', current_user.role)
    is_admin = role_val == UserRole.admin.value
    q = db.query(AgentPrompt)
    if role_key:
        q = q.filter(AgentPrompt.role_key == role_key)
    if not is_admin or not include_disabled:
        q = q.filter(AgentPrompt.enabled == True)  # noqa: E712
    rows = q.order_by(AgentPrompt.role_key.asc(), AgentPrompt.id.desc()).all()
    return [_to_response(p) for p in rows]


@router.get("/active", response_model=AgentPromptResponse | None)
def get_active_prompt(
    role_key: str = Query(default='default'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前激活的提示词（默认 role_key=default 的最新一条启用项）。"""
    p = (db.query(AgentPrompt)
         .filter(AgentPrompt.role_key == role_key, AgentPrompt.enabled == True)
         .order_by(AgentPrompt.id.desc())
         .first())
    return _to_response(p) if p else None


@router.post("", response_model=AgentPromptResponse)
def create_prompt(
    data: AgentPromptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    p = AgentPrompt(
        name=data.name,
        role_key=data.role_key,
        content=data.content,
        description=data.description,
        enabled=data.enabled,
        created_by=current_user.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    log.info("管理员 %s 创建了 AI 角色提示词：%s (%s)", current_user.username, p.name, p.role_key)
    return _to_response(p)


@router.put("/{prompt_id}", response_model=AgentPromptResponse)
def update_prompt(
    prompt_id: int,
    data: AgentPromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    p = db.query(AgentPrompt).filter(AgentPrompt.id == prompt_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="提示词不存在")
    if data.name is not None:
        p.name = data.name
    if data.role_key is not None:
        p.role_key = data.role_key
    if data.content is not None:
        p.content = data.content
    if data.description is not None:
        p.description = data.description
    if data.enabled is not None:
        p.enabled = data.enabled
    db.commit()
    db.refresh(p)
    log.info("管理员 %s 更新了 AI 角色提示词 %s：%s", current_user.username, p.id, p.name)
    return _to_response(p)


@router.delete("/{prompt_id}")
def delete_prompt(
    prompt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    p = db.query(AgentPrompt).filter(AgentPrompt.id == prompt_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="提示词不存在")
    db.delete(p)
    db.commit()
    log.info("管理员 %s 删除了 AI 角色提示词 %s", current_user.username, prompt_id)
    return {"ok": True, "id": prompt_id}


# 预置模板，管理员一键创建
PRESET_PROMPTS = [
    {
        "name": "商业分析专家",
        "role_key": "business_analyst",
        "description": "擅长从项目数据中提炼商业洞察，给出策略性建议",
        "content": (
            "你是一位资深的商业分析专家，熟悉 B2B 销售与渠道运营。\n"
            "回答要求：\n"
            "1. 先给出核心结论，再用要点列证。\n"
            "2. 关注金额、转化率、责任销售分布、跟单阶段四个维度的联动。\n"
            "3. 给出至少 1 条可执行的策略建议（如何提升中标率、加快流转、聚焦大单）。\n"
            "4. 数据没有时，明确指出需要补充什么信息。\n"
            "回答语言：中文。保持专业、克制、可执行。"
        ),
    },
    {
        "name": "销售助理",
        "role_key": "sales_expert",
        "description": "侧重销售执行、跟单节奏、客户沟通",
        "content": (
            "你是一位实战派的销售助理，关注跟单推进、责任人协同和成单转化。\n"
            "回答风格：\n"
            "1. 直接回答问题，不绕弯。\n"
            "2. 在合适位置给出本周可执行的 3 个动作。\n"
            "3. 涉及具体项目时，提示项目名称 / 责任人 / 当前阶段。\n"
            "4. 销售术语用得自然，避免空话。"
        ),
    },
    {
        "name": "财务审计视角",
        "role_key": "finance_expert",
        "description": "关注金额、回款、费用、合规",
        "content": (
            "你是一位严谨的财务审计视角专家。\n"
            "关注点：项目金额、预计金额、费用金额、回款风险、合作公司合规。\n"
            "回答要求：\n"
            "1. 给出金额合计 / 区间 / 占比。\n"
            "2. 提示异常或需复核的数据点。\n"
            "3. 在合规上有风险时，明确指出。\n"
            "4. 文字简洁，数字精确到两位小数。"
        ),
    },
    {
        "name": "小销（默认）",
        "role_key": "default",
        "description": "默认销售项目助理角色",
        "content": (
            "你是小销，销售项目数据智能助理。\n"
            "回答要简洁、可执行；遇到不确定的数据，请提示用户补充。"
        ),
    },
]


@router.post("/seed", response_model=list[AgentPromptResponse])
def seed_preset_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """一次性写入预置提示词模板，已存在的 role_key 会被跳过。"""
    _ensure_admin(current_user)
    created = []
    existing = {row.role_key for row in db.query(AgentPrompt).filter(AgentPrompt.role_key.in_([p['role_key'] for p in PRESET_PROMPTS])).all()}
    for preset in PRESET_PROMPTS:
        if preset['role_key'] in existing:
            continue
        p = AgentPrompt(
            name=preset['name'],
            role_key=preset['role_key'],
            content=preset['content'],
            description=preset['description'],
            enabled=True,
            created_by=current_user.id,
        )
        db.add(p)
        db.flush()
        created.append(_to_response(p))
    db.commit()
    return created