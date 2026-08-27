"""表单生成器路由 — 模板CRUD + 实例CRUD + 文件存储"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import logging
import traceback
import os
import time
import requests

from app.database import get_db
from app.models import User, UserRole, FormTemplate, FormInstance, FileStorageConfig, StorageMode, StorageZone, ApprovalStatus, AIModelConfig, Project, ProjectType, WinBidStatus
from app.schemas import (
    FormTemplateCreate, FormTemplateUpdate, FormTemplateResponse,
    FormInstanceCreate, FormInstanceResponse, FormInstanceListResponse,
    MessageResponse, AIModelConfigCreate, AIModelConfigUpdate, AIModelConfigResponse,
    AIModelPresetResponse, AIModelTestRequest, AIModelTestResponse,
)
from app.auth import get_current_user, require_admin
from app.services.form_file_storage import (
    compute_form_folders, resolve_form_folder, _ensure_form_directories,
)
from app.services.file_storage import (
    render_subfolder, sanitize_path_segment, webdav_request,
    ensure_local_folders, create_project_folders,
)

router = APIRouter(prefix="/api/forms", tags=["表单生成器"])
log = logging.getLogger("forms")


def _resolve_config_for_instance(db: Session, instance_id: int) -> FileStorageConfig:
    """根据 form_instance_id 反查关联 StorageZone 的 cfg；fallback 老单例"""
    try:
        instance = db.query(FormInstance).filter(FormInstance.id == instance_id).first()
        if instance and instance.storage_zone_id:
            zone = db.query(StorageZone).filter(StorageZone.id == instance.storage_zone_id).first()
            if zone:
                return FileStorageConfig(
                    id=9999 + (zone.id or 0),
                    mode=zone.mode or StorageMode.webdav,
                    webdav_url=zone.webdav_url,
                    webdav_port=zone.webdav_port,
                    webdav_use_ssl=zone.webdav_use_ssl if zone.webdav_use_ssl is not None else True,
                    webdav_username=zone.webdav_username,
                    webdav_password=zone.webdav_password,
                    webdav_base_path=zone.webdav_base_path,
                    local_path=zone.local_path,
                    template='{responsible_sales}+{project_name}+{date}',
                )
    except Exception as e:
        log.exception(f"_resolve_config_for_instance 反查失败: {e}")
    return _ensure_config(db)

AI_MODEL_PRESETS = [
    {
        "key": "kimi",
        "name": "Kimi",
        "provider": "kimi",
        "model_type": "cloud",
        "base_url": "https://api.moonshot.ai/v1",
        "model_name": "kimi-k3",
        "description": "Moonshot 官方 OpenAI 兼容接口，适合中文分析和长上下文场景。",
        "notes": "只需填写 API Key 即可运行。",
        "recommended_timeout_seconds": 90,
        "recommended_temperature": 0.2,
    },
    {
        "key": "minimax",
        "name": "MiniMax",
        "provider": "minimax",
        "model_type": "cloud",
        "base_url": "https://api.minimax.io/v1",
        "model_name": "MiniMax-M3",
        "description": "MiniMax 官方 OpenAI 兼容接口，适合多模态与高上下文分析。",
        "notes": "只需填写 API Key 即可运行。",
        "recommended_timeout_seconds": 90,
        "recommended_temperature": 0.2,
    },
    {
        "key": "deepseek",
        "name": "DeepSeek",
        "provider": "deepseek",
        "model_type": "cloud",
        "base_url": "https://api.deepseek.com",
        "model_name": "deepseek-v4-flash",
        "description": "DeepSeek 官方 OpenAI 兼容接口，默认使用速度较快的 v4-flash。",
        "notes": "只需填写 API Key 即可运行。",
        "recommended_timeout_seconds": 60,
        "recommended_temperature": 0.2,
    },
]


def _mask_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def _serialize_ai_model(model: AIModelConfig):
    return {
        "id": model.id,
        "name": model.name,
        "model_type": model.model_type,
        "provider": model.provider,
        "base_url": model.base_url,
        "model_name": model.model_name,
        "api_key": _mask_secret(model.api_key),
        "temperature": model.temperature,
        "max_tokens": model.max_tokens,
        "timeout_seconds": model.timeout_seconds,
        "is_enabled": model.is_enabled,
        "is_default": model.is_default,
        "notes": model.notes,
        "created_by": model.created_by,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
        "creator": model.creator,
    }


def _get_preset_by_key(preset_key: str):
    return next((item for item in AI_MODEL_PRESETS if item["key"] == preset_key), None)


def _build_chat_completion_url(base_url: Optional[str]) -> str:
    if not base_url:
        raise HTTPException(status_code=400, detail="模型未配置接入地址")
    root = base_url.rstrip("/")
    if root.endswith("/chat/completions"):
        return root
    if root.endswith("/v1"):
        return f"{root}/chat/completions"
    return f"{root}/chat/completions"


def _build_test_payload(model: AIModelConfig, prompt: str) -> dict:
    payload = {
        "model": model.model_name,
        "messages": [
            {"role": "system", "content": "你是一个用于检测接口连通性和响应速度的助手。请尽量简短回答。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": float(model.temperature or 0.2),
        "stream": False,
    }
    if model.max_tokens:
        payload["max_tokens"] = int(model.max_tokens)
    else:
        payload["max_tokens"] = 128
    if model.provider == "deepseek":
        payload["reasoning_effort"] = "low"
        payload["thinking"] = {"type": "disabled"}
    return payload


def _extract_response_preview(data: dict) -> Optional[str]:
    try:
        choices = data.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            content = "".join(parts)
        if content is None:
            return None
        return str(content)[:200]
    except Exception:
        return None


# ============ 模板 CRUD ============

@router.get("/templates", response_model=List[FormTemplateResponse])
def list_templates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取所有表单模板"""
    templates = db.query(FormTemplate).order_by(FormTemplate.created_at.desc()).all()
    return templates


@router.get("/templates/{template_id}", response_model=FormTemplateResponse)
def get_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取单个表单模板"""
    tpl = db.query(FormTemplate).filter(FormTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="表单模板不存在")
    return tpl


@router.post("/templates", response_model=FormTemplateResponse)
def create_template(data: FormTemplateCreate, request: Request, db: Session = Depends(get_db),
                    current_user: User = Depends(require_admin)):
    tpl = FormTemplate(
        name=data.name,
        description=data.description,
        fields=json.dumps(data.fields, ensure_ascii=False),
        storage_sub_path=data.storage_sub_path,
        storage_zone_id=data.storage_zone_id,
        created_by=current_user.id,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    log.info(f"[create_template] id={tpl.id} name={tpl.name} zone_id={tpl.storage_zone_id}")
    return tpl


@router.put("/templates/{template_id}", response_model=FormTemplateResponse)
def update_template(template_id: int, data: FormTemplateUpdate, request: Request,
                    db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """更新表单模板（仅管理员）"""
    tpl = db.query(FormTemplate).filter(FormTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="表单模板不存在")

    if data.name is not None:
        tpl.name = data.name
    if data.description is not None:
        tpl.description = data.description
    if data.fields is not None:
        tpl.fields = json.dumps(data.fields, ensure_ascii=False)
    if data.is_active is not None:
        tpl.is_active = data.is_active
    if data.storage_sub_path is not None:
        tpl.storage_sub_path = data.storage_sub_path
    if data.storage_zone_id is not None:
        tpl.storage_zone_id = data.storage_zone_id

    db.commit()
    db.refresh(tpl)
    log.info(f"[update_template] id={tpl.id} name={tpl.name} zone_id={tpl.storage_zone_id}")
    return tpl


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(require_admin)):
    """删除表单模板（仅管理员）"""
    tpl = db.query(FormTemplate).filter(FormTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="表单模板不存在")
    db.delete(tpl)
    db.commit()
    log.info(f"[delete_template] id={template_id}")
    return {"message": "已删除"}


# ============ AI 模型配置 ============

@router.get("/ai-models", response_model=List[AIModelConfigResponse])
def list_ai_models(enabled_only: bool = False,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    q = db.query(AIModelConfig).order_by(AIModelConfig.is_default.desc(), AIModelConfig.id.asc())
    if enabled_only or current_user.role != UserRole.admin:
        q = q.filter(AIModelConfig.is_enabled == True)
    return [_serialize_ai_model(item) for item in q.all()]


@router.get("/ai-model-presets", response_model=List[AIModelPresetResponse])
def list_ai_model_presets(current_user: User = Depends(require_admin)):
    return AI_MODEL_PRESETS


@router.post("/ai-models", response_model=AIModelConfigResponse)
def create_ai_model(data: AIModelConfigCreate,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(require_admin)):
    if data.is_default:
        db.query(AIModelConfig).update({AIModelConfig.is_default: False})
    model = AIModelConfig(
        name=data.name,
        model_type=data.model_type,
        provider=data.provider,
        base_url=data.base_url,
        model_name=data.model_name,
        api_key=data.api_key,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        timeout_seconds=data.timeout_seconds,
        is_enabled=data.is_enabled,
        is_default=data.is_default,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return _serialize_ai_model(model)


@router.put("/ai-models/{model_id}", response_model=AIModelConfigResponse)
def update_ai_model(model_id: int,
                    data: AIModelConfigUpdate,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(require_admin)):
    model = db.query(AIModelConfig).filter(AIModelConfig.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="AI 模型配置不存在")

    if data.is_default:
        db.query(AIModelConfig).filter(AIModelConfig.id != model_id).update({AIModelConfig.is_default: False})

    for field in (
        "name", "model_type", "provider", "base_url", "model_name", "temperature",
        "max_tokens", "timeout_seconds", "is_enabled", "is_default", "notes"
    ):
        value = getattr(data, field)
        if value is not None:
            setattr(model, field, value)
    if data.api_key is not None and data.api_key != "":
        model.api_key = data.api_key

    db.commit()
    db.refresh(model)
    return _serialize_ai_model(model)


@router.delete("/ai-models/{model_id}", response_model=MessageResponse)
def delete_ai_model(model_id: int,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(require_admin)):
    model = db.query(AIModelConfig).filter(AIModelConfig.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="AI 模型配置不存在")
    db.delete(model)
    db.commit()
    return {"message": "已删除"}


@router.post("/ai-models/{model_id}/test", response_model=AIModelTestResponse)
def test_ai_model(model_id: int,
                  data: AIModelTestRequest,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(require_admin)):
    model = db.query(AIModelConfig).filter(AIModelConfig.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="AI 模型配置不存在")
    if not model.api_key:
        raise HTTPException(status_code=400, detail="请先填写 API Key 再测试")
    if model.model_type.value == "local" and not model.base_url:
        raise HTTPException(status_code=400, detail="请先填写本地模型接入地址")

    url = _build_chat_completion_url(model.base_url)
    payload = _build_test_payload(model, data.prompt)
    headers = {
        "Authorization": f"Bearer {model.api_key}",
        "Content-Type": "application/json",
    }
    started = time.perf_counter()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=int(model.timeout_seconds or 60))
        latency_ms = int((time.perf_counter() - started) * 1000)
        preview = None
        message = f"测试完成，接口响应耗时 {latency_ms} ms"
        try:
            body = resp.json()
            preview = _extract_response_preview(body)
            if resp.status_code >= 400:
                err = body.get("error") if isinstance(body, dict) else None
                if isinstance(err, dict):
                    message = err.get("message") or err.get("type") or message
        except Exception:
            body = None
        if resp.status_code >= 400:
            raise HTTPException(status_code=400, detail={
                "success": False,
                "message": message,
                "latency_ms": latency_ms,
                "status_code": resp.status_code,
                "provider": model.provider,
                "model_name": model.model_name,
                "response_preview": preview,
            })
        return {
            "success": True,
            "message": message,
            "latency_ms": latency_ms,
            "status_code": resp.status_code,
            "provider": model.provider,
            "model_name": model.model_name,
            "response_preview": preview,
        }
    except requests.Timeout:
        latency_ms = int((time.perf_counter() - started) * 1000)
        raise HTTPException(status_code=400, detail={
            "success": False,
            "message": f"测试超时，超过 {int(model.timeout_seconds or 60)} 秒未返回",
            "latency_ms": latency_ms,
            "status_code": None,
            "provider": model.provider,
            "model_name": model.model_name,
            "response_preview": None,
        })
    except HTTPException:
        raise
    except Exception as e:
        latency_ms = int((time.perf_counter() - started) * 1000)
        raise HTTPException(status_code=400, detail={
            "success": False,
            "message": f"测试失败：{str(e)}",
            "latency_ms": latency_ms,
            "status_code": None,
            "provider": model.provider,
            "model_name": model.model_name,
            "response_preview": None,
        })


# ============ 实例 CRUD ============

@router.get("/instances", response_model=FormInstanceListResponse)
def list_instances(template_id: int = None, page: int = 1, page_size: int = 20,
                   db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取表单实例列表"""
    q = db.query(FormInstance)
    if template_id:
        q = q.filter(FormInstance.template_id == template_id)
    total = q.count()
    items = q.order_by(FormInstance.created_at.desc()) \
             .offset((page - 1) * page_size) \
             .limit(page_size) \
             .all()
    return {"items": items, "total": total}


@router.post("/instances", response_model=FormInstanceResponse)
def create_instance(data: FormInstanceCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """提交表单实例 — 与渠道项目 create_project 逻辑一致：
    - 自动分配审批人（用户上级 / 兜底 admin）
    - 自动解析存储区域 + 创建 NAS 目录（招标资料/投标文档）
    - 自动进入「待审批」状态
    """
    tpl = db.query(FormTemplate).filter(FormTemplate.id == data.template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="表单模板不存在")
    if not tpl.is_active:
        raise HTTPException(status_code=400, detail="该表单模板已停用")

    # === 1. 自动分配审批人（与渠道项目一致） ===
    approver_id = None
    if current_user.parent_id:
        approver_id = current_user.parent_id
    else:
        admin_user = db.query(User).filter(User.role == UserRole.admin, User.is_active == True).first()
        if admin_user:
            approver_id = admin_user.id
    if not approver_id:
        raise HTTPException(status_code=422, detail="未找到可用审批人，请在用户管理中为该账号设置上级")

    # === 2. 解析项目来源（自营/渠道）与存储区域 ===
    # 关键修复：根据「模板名」识别项目类型（之前无条件 source='self' 导致渠道项目也被记成自营），
    # 同时根据 source 自动选择匹配的 storage_zone（避免渠道项目落到自营 zone 的问题）。
    # 优先级：前端显式传的 storage_zone_id > 按 source 选出的默认 zone > 模板的 zone > 第一个启用的 zone。
    form_data = dict(data.data or {})

    # ★ 关键修复 #1：按模板名（或前端显式传的 source）判断项目类型
    explicit_source = (form_data.get('source') or '').strip().lower()
    tpl_name = (tpl.name or '').strip()
    if explicit_source in ('channel', 'self'):
        project_source = explicit_source
    elif '渠道' in tpl_name:
        project_source = 'channel'
    elif '自营' in tpl_name or '自建' in tpl_name:
        project_source = 'self'
    else:
        project_source = 'self'  # 未知模板默认归到自营（兼容老规则）
    log.warning(f"[create_instance] template='{tpl_name}' source={project_source}")

    # ★ 关键修复 #2：按 source 选默认 zone。
    # 由于 admin 创建模板时不一定配对了 storage_zone_id，这里根据 source 反查正确的 zone：
    #   - channel（渠道）→ 找名为"渠道资料"的 zone
    #   - self（自营）   → 找名为"自营资料"的 zone
    def _find_default_zone(source):
        if source == 'channel':
            zone = db.query(StorageZone).filter(
                StorageZone.is_active == True
            ).filter(
                (StorageZone.name.like('%渠道%')) | (StorageZone.webdav_base_path.like('%渠道%'))
            ).first()
            if zone:
                return zone
        elif source == 'self':
            zone = db.query(StorageZone).filter(
                StorageZone.is_active == True
            ).filter(
                (StorageZone.name.like('%自营%')) | (StorageZone.webdav_base_path.like('%自营%'))
            ).first()
            if zone:
                return zone
        return None

    explicit_zone_id = form_data.get('storage_zone_id')
    tpl_zone_id = tpl.storage_zone_id
    default_zone = _find_default_zone(project_source)

    # 优先级：前端显式 > 模板自带 > 按 source 默认查 > 第一个启用
    storage_zone_id = explicit_zone_id or tpl_zone_id or (default_zone.id if default_zone else None)
    zone = None
    if storage_zone_id:
        zone = db.query(StorageZone).filter(StorageZone.id == storage_zone_id, StorageZone.is_active == True).first()
    if not zone:
        zone = default_zone
    if not zone:
        zone = db.query(StorageZone).filter(StorageZone.is_active == True).order_by(StorageZone.sort_order, StorageZone.id).first()

    # === 3. 创建 NAS 目录（严格调用渠道项目 create_project_folders）===
    # 根据 zone 决定目录路径：
    #   - 渠道项目（zone 名含"渠道"）→ 落到「渠道资料」目录
    #   - 自营项目（zone 名含"自营"）→ 落到「自营资料」目录

    tender_folder = None
    bid_folder = None
    project_name = form_data.get('project_name') or form_data.get('name') or f'表单{current_user.real_name}'
    responsible_sales = form_data.get('responsible_sales') or current_user.real_name

    # 解析模板的存储区域
    target_zone = None
    if tpl.storage_zone_id:
        target_zone = db.query(StorageZone).filter(StorageZone.id == tpl.storage_zone_id).first()
    # 兜底：用第一个启用的区域
    if not target_zone:
        target_zone = db.query(StorageZone).filter(StorageZone.is_active == True).order_by(StorageZone.sort_order, StorageZone.id).first()

    # 根据 zone 决定使用哪个 FileStorageConfig
    # 方案：动态构造一个内存中的 FileStorageConfig（不持久化），保证 create_project_folders
    # 用 zone 的路径建文件夹
    if target_zone:
        storage_cfg = FileStorageConfig(
            id=9999 + target_zone.id,  # 虚拟 id，不入数据库
            mode=target_zone.mode,
            webdav_url=target_zone.webdav_url,
            webdav_port=target_zone.webdav_port,
            webdav_username=target_zone.webdav_username,
            webdav_password=target_zone.webdav_password,
            webdav_base_path=target_zone.webdav_base_path,
            webdav_use_ssl=target_zone.webdav_use_ssl,
            local_path=target_zone.local_path,
            template='{responsible_sales}+{project_name}+{date}',
        )
        try:
            folders = create_project_folders(
                db, storage_cfg, current_user.username, current_user.real_name,
                project_name, responsible_sales=responsible_sales
            )
            tender_folder = folders['tender_folder']
            bid_folder = folders['bid_folder']
            log.warning(f"[create_instance] folders ok (zone={target_zone.name}): tender={tender_folder} bid={bid_folder}")
        except Exception as e:
            log.error(f"[create_instance] 文件夹创建失败 (zone): {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"项目文件夹创建失败: {e}")
    else:
        # 兜底：用默认 FileStorageConfig (id=1)
        storage_cfg = db.query(FileStorageConfig).filter(FileStorageConfig.id == 1).first()
        if storage_cfg:
            try:
                folders = create_project_folders(
                    db, storage_cfg, current_user.username, current_user.real_name,
                    project_name, responsible_sales=responsible_sales
                )
                tender_folder = folders['tender_folder']
                bid_folder = folders['bid_folder']
                log.warning(f"[create_instance] folders ok (default cfg): tender={tender_folder} bid={bid_folder}")
            except Exception as e:
                log.error(f"[create_instance] 文件夹创建失败: {e}\n{traceback.format_exc()}")

    # === 4. 创建实例 ===
    # 删除 data 中重复字段（如果前端误传）
    for k in ('storage_zone_id', 'approver_id'):
        form_data.pop(k, None)

    instance = FormInstance(
        template_id=data.template_id,
        data=json.dumps(form_data, ensure_ascii=False),
        tender_folder=tender_folder,
        bid_folder=bid_folder,
        storage_zone_id=zone.id if zone else None,
        approver_id=approver_id,
        approval_status=ApprovalStatus.pending_approval,  # 直接进入「待审批」状态
        created_by=current_user.id,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)

    # === 5. 同时在 projects 表创建一条记录（让自建项目也出现在项目列表中） ===
    try:
        from app.models import Project, ProjectType, CooperationMode, FeeMode, IsSM, WinBidStatus
        # 映射合作模式 / 费用模式 / 中标状态
        def _coerce_enum(enum_cls, value, default):
            if not value:
                return default
            try:
                return enum_cls(value)
            except Exception:
                return default

        # 解析项目类型（与 ProjectCreate 共用）
        pt_str = form_data.get('project_type') or form_data.get('type')
        try:
            project_type = ProjectType(pt_str) if pt_str else ProjectType.other
        except Exception:
            project_type = ProjectType.other

        # 解析日期
        from datetime import date as _date
        def _parse_date(v):
            if not v:
                return None
            if isinstance(v, _date):
                return v
            try:
                return _date.fromisoformat(str(v)[:10])
            except Exception:
                return None

        # 解析金额
        def _parse_amount(v):
            if v in (None, '', 'None'):
                return None
            try:
                return float(v)
            except Exception:
                return None

        project = Project(
            project_name=project_name,
            project_code=(form_data.get('project_code') or '').strip() or None,
            project_type=project_type,
            source=project_source,  # ★ 修复：按模板名/前端 source 区分自营 vs 渠道，不再硬编码 self
            form_instance_id=instance.id,
            tender_time=_parse_date(form_data.get('tender_time')),
            bid_time=_parse_date(form_data.get('bid_time')),
            owner_contact_person=form_data.get('owner_contact_person'),
            owner_contact_info=form_data.get('owner_contact_info'),
            partner_company=form_data.get('partner_company'),
            company_address=form_data.get('company_address'),
            main_qualification=form_data.get('main_qualification'),
            legal_representative=form_data.get('legal_representative'),
            contact_person=form_data.get('contact_person'),
            contact_info=form_data.get('contact_info'),
            cooperation_mode=_coerce_enum(CooperationMode, form_data.get('cooperation_mode'), CooperationMode.long_term),
            fee_mode=_coerce_enum(FeeMode, form_data.get('fee_mode'), FeeMode.mutual),
            fee_amount=_parse_amount(form_data.get('fee_amount')),
            is_sm=_coerce_enum(IsSM, form_data.get('is_sm'), IsSM.no),
            project_amount=_parse_amount(form_data.get('project_amount')) or 0.0,
            expected_amount=_parse_amount(form_data.get('expected_amount')) or 0.0,
            win_bid_status=_coerce_enum(WinBidStatus, form_data.get('win_bid_status'), WinBidStatus.in_progress),
            project_overview=form_data.get('project_overview'),
            tender_folder=tender_folder,
            bid_folder=bid_folder,
            tender_file=str(form_data.get('tender_file') or '') or None,
            bid_file=str(form_data.get('bid_file') or '') or None,
            approver_id=approver_id,
            approval_status=ApprovalStatus.pending_approval,
            responsible_sales=responsible_sales,
            storage_zone_id=zone.id if zone else None,
            created_by=current_user.id,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        log.warning(f"[create_instance] projects row created: id={project.id} name={project.project_name} source={project_source}")
        # 通知审批人 — 自营/渠道项目流程
        try:
            from app.services.notifications import send_notification
            from app.models import NotificationType
            if approver_id and approver_id != current_user.id:
                send_notification(
                    db,
                    receiver_id=approver_id,
                    type=NotificationType.project_pending,
                    title="新项目待审批",
                    content="{0} 通过「{1}」提交了{2}项目「{3}」,请尽快审批。".format(
                        current_user.real_name or current_user.username,
                        (instance.template.name if instance and instance.template else ('渠道项目登记表' if project_source == 'channel' else '自营项目登记表')),
                        '渠道' if project_source == 'channel' else '自营',
                        project.project_name,
                    ),
                    target_type="project", target_id=project.id,
                    extra={"creator_id": current_user.id, "creator_name": current_user.real_name},
                )
                db.commit()
        except Exception as _e:
            log.warning(f"[create_instance] 通知失败: {_e}")
    except Exception as e:
        log.error(f"[create_instance] projects row 创建失败: {e}\n{traceback.format_exc()}")

    log.info(f"[create_instance] id={instance.id} template={data.template_id} user={current_user.username} approver={approver_id}")
    return instance


@router.get("/instances/{instance_id}", response_model=FormInstanceResponse)
def get_instance(instance_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """获取单个表单实例"""
    inst = db.query(FormInstance).filter(FormInstance.id == instance_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="表单实例不存在")
    return inst


@router.put("/instances/{instance_id}", response_model=FormInstanceResponse)
def update_instance(instance_id: int, payload: dict, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """更新表单实例 — 同时联动更新关联的 projects 表（让自营项目编辑走表单格式保持一致）

    payload: { "data": { ...字段值 }, "approval_status": "pending_approval"|"approved"等（可选） }
    """
    inst = db.query(FormInstance).filter(FormInstance.id == instance_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="表单实例不存在")

    # 1) 更新表单实例的 data
    new_data = payload.get('data') or {}
    # 同样清掉重复字段
    for k in ('storage_zone_id', 'approver_id'):
        new_data.pop(k, None)
    inst.data = json.dumps(new_data, ensure_ascii=False)

    # 2) 提取约定的中文字段映射（与 create_instance 行为一致）
    proj_name = new_data.get('project_name') or new_data.get('name')
    resp_sales = new_data.get('responsible_sales')
    partner = new_data.get('partner_company')
    project_type = new_data.get('project_type')
    owner_cp = new_data.get('owner_contact_person')
    owner_ci = new_data.get('owner_contact_info')
    company_addr = new_data.get('company_address')
    main_qual = new_data.get('main_qualification')
    legal_rep = new_data.get('legal_representative')
    contact_person = new_data.get('contact_person')
    contact_info = new_data.get('contact_info')
    project_overview = new_data.get('project_overview')
    tender_time = new_data.get('tender_time')
    bid_time = new_data.get('bid_time')

    # 3) 联动更新关联的 projects 表（保持数据库双写一致）
    proj = db.query(Project).filter(Project.form_instance_id == instance_id).first()
    if proj:
        if proj_name: proj.project_name = proj_name
        if resp_sales: proj.responsible_sales = resp_sales
        if partner is not None: proj.partner_company = partner
        if project_type:
            try:
                proj.project_type = ProjectType(project_type)
            except Exception:
                pass
        if owner_cp is not None: proj.owner_contact_person = owner_cp
        if owner_ci is not None: proj.owner_contact_info = owner_ci
        if company_addr is not None: proj.company_address = company_addr
        if main_qual is not None: proj.main_qualification = main_qual
        if legal_rep is not None: proj.legal_representative = legal_rep
        if contact_person is not None: proj.contact_person = contact_person
        if contact_info is not None: proj.contact_info = contact_info
        if project_overview is not None: proj.project_overview = project_overview
        if tender_time is not None: proj.tender_time = tender_time
        if bid_time is not None: proj.bid_time = bid_time

    db.commit()
    db.refresh(inst)
    return inst


@router.delete("/instances/{instance_id}")
def delete_instance(instance_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin)):
    inst = db.query(FormInstance).filter(FormInstance.id == instance_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="表单实例不存在")
    db.delete(inst)
    db.commit()
    return {"message": "已删除"}


# ============ 文件存储（基于 FormTemplate.storage_sub_path）============

def _ensure_config(db: Session) -> FileStorageConfig:
    cfg = db.query(FileStorageConfig).filter(FileStorageConfig.id == 1).first()
    if not cfg:
        cfg = FileStorageConfig(id=1, mode=StorageMode.local)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.post("/file-storage/init-folders")
async def init_form_folders(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """表单提交时初始化文件目录"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, detail="请求体必须是 JSON")

    instance_id = body.get('instance_id')
    project_name = body.get('project_name', '未命名')
    if not instance_id:
        raise HTTPException(400, detail="instance_id 必填")

    tender_dir, bid_dir = compute_form_folders(
        db, int(body.get('template_id', 0)), int(instance_id),
        current_user.username, current_user.real_name, project_name,
    )
    return {
        'tender_folder': tender_dir,
        'bid_folder': bid_dir,
        'message': '目录已就绪',
    }


@router.post("/file-storage/list-files")
async def list_form_files(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出表单实例的已上传文件"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, detail="请求体必须是 JSON")

    instance_id = body.get('instance_id')
    folder_type = body.get('folder_type')
    if not instance_id or not folder_type:
        raise HTTPException(400, detail="instance_id 和 folder_type 必填")

    target_dir, project_name, source = resolve_form_folder(db, int(instance_id), folder_type)
    if not target_dir:
        return {"files": [], "total": 0, "target_dir": "", "project_name": str(instance_id)}

    cfg = _resolve_config_for_instance(db, int(instance_id))
    files = []

    if cfg.mode == StorageMode.local:
        if os.path.isdir(target_dir):
            for fname in sorted(os.listdir(target_dir)):
                fpath = os.path.join(target_dir, fname)
                if os.path.isfile(fpath):
                    stat = os.stat(fpath)
                    files.append({
                        'name': fname,
                        'size': stat.st_size,
                        'upload_time': None,
                        'uploader': None,
                        'path': fpath,
                    })
    else:
        from app.services.webdav_client import list_files_webdav
        ok, file_list = list_files_webdav(cfg, target_dir, project_name_hint=project_name)
        if ok:
            files = file_list
        else:
            log.warning(f"[list-form-files] WebDAV list 失败: dir={target_dir}")

    log.info(f"[list-form-files] instance={instance_id} type={folder_type} dir={target_dir} files={len(files)}")
    return {
        "files": files,
        "total": len(files),
        "target_dir": target_dir,
        "project_name": project_name,
    }


@router.post("/file-storage/upload")
async def upload_form_file(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    files: List[UploadFile] = File(...),
    instance_id: int = Form(...),
    folder_type: str = Form(...),
):
    """上传文件到表单实例目录"""
    if folder_type not in ('tender', 'bid'):
        raise HTTPException(400, detail="folder_type 必须是 tender 或 bid")

    target_dir, project_name, source = resolve_form_folder(db, instance_id, folder_type)
    if not target_dir:
        raise HTTPException(400, detail="无法解析存储目录")

    # 优先用 StorageZone，否则兜底 FileStorageConfig
    instance = db.query(FormInstance).filter(FormInstance.id == instance_id).first()
    zone = None
    if instance and instance.storage_zone_id:
        zone = db.query(StorageZone).filter(StorageZone.id == instance.storage_zone_id).first()
    if not zone:
        # 兜底
        zone = db.query(StorageZone).filter(StorageZone.is_active == True).order_by(StorageZone.sort_order, StorageZone.id).first()

    cfg = _ensure_config(db) if not zone else None
    use_zone = zone is not None
    uploaded = []

    from app.services.webdav_client import upload_file as webdav_upload_file

    for f in files:
        safe_name = sanitize_path_segment(f.filename or 'unnamed')
        content = await f.read()
        if use_zone and zone.mode == StorageMode.local:
            os.makedirs(target_dir, exist_ok=True)
            fpath = os.path.join(target_dir, safe_name)
            with open(fpath, 'wb') as out:
                out.write(content)
            uploaded.append({'name': safe_name, 'size': len(content), 'path': fpath})
        elif use_zone and zone.mode == StorageMode.webdav:
            # 直接用 zone 的凭据上传（用底层 requests.put，绕过 webdav_request 无 data/headers 参数的问题）
            url = target_dir.rstrip('/') + '/' + safe_name
            try:
                import requests as _req
                import urllib3 as _u3
                _u3.disable_warnings(_u3.exceptions.InsecureRequestWarning)
                # 先确保父目录存在
                from app.services.webdav_client import _ensure_parent_dir, _request, _auth
                _ensure_parent_dir(url, zone)
                resp = _req.put(
                    url,
                    data=content,
                    auth=_auth(zone),
                    headers={'Content-Type': 'application/octet-stream'},
                    timeout=30,
                    verify=False,
                )
                if 200 <= resp.status_code < 300:
                    uploaded.append({'name': safe_name, 'size': len(content), 'path': url})
                else:
                    log.error(f"[upload] WebDAV PUT 失败 {url}: HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                log.error(f"[upload] 异常 {url}: {e}")
        else:
            # 兜底：旧 FileStorageConfig
            if cfg.mode == StorageMode.local:
                os.makedirs(target_dir, exist_ok=True)
                fpath = os.path.join(target_dir, safe_name)
                with open(fpath, 'wb') as out:
                    out.write(content)
                uploaded.append({'name': safe_name, 'size': len(content), 'path': fpath})
            else:
                url = target_dir.rstrip('/') + '/' + safe_name
                ok, msg = webdav_upload_file(cfg, url, content)
                if ok:
                    uploaded.append({'name': safe_name, 'size': len(content), 'path': url})
                else:
                    log.error(f"[upload] WebDAV PUT 失败 {url}: {msg}")

    log.info(f"[upload-form-file] instance={instance_id} type={folder_type} uploaded={len(uploaded)} use_zone={use_zone}")
    return {"uploaded": uploaded, "total": len(uploaded)}


@router.post("/file-storage/delete-file")
async def delete_form_file(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除表单实例的文件"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, detail="请求体必须是 JSON")

    instance_id = body.get('instance_id')
    folder_type = body.get('folder_type')
    file_name = body.get('file_name')
    if not instance_id or not folder_type or not file_name:
        raise HTTPException(400, detail="instance_id, folder_type, file_name 必填")

    target_dir, _, _ = resolve_form_folder(db, int(instance_id), folder_type)
    if not target_dir:
        raise HTTPException(400, detail="无法解析存储目录")

    cfg = _resolve_config_for_instance(db, int(instance_id))
    safe_name = sanitize_path_segment(file_name)

    if cfg.mode == StorageMode.local:
        fpath = os.path.join(target_dir, safe_name)
        if os.path.exists(fpath):
            os.remove(fpath)
            return {"message": f"已删除 {file_name}"}
        raise HTTPException(404, detail="文件不存在")
    else:
        url = target_dir.rstrip('/') + '/' + safe_name
        ok, msg = webdav_request('DELETE', url, cfg.webdav_username, cfg.webdav_password)
        if ok:
            return {"message": f"已删除 {file_name}"}
        raise HTTPException(400, detail=f"删除失败: {msg}")
