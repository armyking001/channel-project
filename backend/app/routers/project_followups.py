"""项目跟单 / 项目汇报 路由

- 列表（可按 project_id / stage / period 过滤）
- 新建 / 编辑 / 删除跟单
- 单项目的跟单时间轴
- 跟单汇总统计（按阶段分布、预计成交总金额等）
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, select
from typing import Optional
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models import (
    User, UserRole, Project, ProjectFollowup, FollowupStage, ApprovalStatus,
)
from app.services.project_followup_storage import save_followup_to_storage
from app.schemas import (
    ProjectFollowupCreate, ProjectFollowupUpdate, ProjectFollowupResponse,
    ProjectFollowupListResponse, FollowupStageStat, FollowupSummary,
    MessageResponse, FOLLOWUP_STAGE_CHOICES,
)
from app.auth import get_current_user, require_not_archive

router = APIRouter(prefix="/api/project-followups", tags=["项目跟单"])


# ---------- 工具函数 ----------
def _stage_or_400(stage: str) -> str:
    if stage not in FOLLOWUP_STAGE_CHOICES:
        raise HTTPException(
            status_code=400,
            detail=f"非法阶段，可选值: {FOLLOWUP_STAGE_CHOICES}",
        )
    return stage


def _visible_project_ids(db: Session, current_user: User):
    """当前用户能看哪些项目的跟单记录。

    规则：
      admin: 全部
      important: 自己 + 自己下属创建的项目 + 自己是审批人
      archive: 全部（只读）
      normal: 自己创建 + 自己是审批人 + 自己是责任销售
    """
    q = db.query(Project.id)
    if current_user.role == UserRole.admin:
        return q
    if current_user.role == UserRole.archive:
        return q
    my_name = current_user.real_name or current_user.username
    if current_user.role == UserRole.important:
        child_ids = [c.id for c in current_user.children]
        child_ids.append(current_user.id)
        return q.filter(or_(
            Project.created_by.in_(child_ids),
            Project.approver_id == current_user.id,
            Project.responsible_sales == my_name,
        ))
    return q.filter(or_(
        Project.created_by == current_user.id,
        Project.approver_id == current_user.id,
        Project.responsible_sales == my_name,
    ))


def _followable_project_ids(db: Session, current_user: User):
    """当前用户可以对哪些项目新建跟单。

    规则：自己创建的项目 + 责任销售是自己的项目（仅 approved）
      admin: 全部已审批
      其他人: 自己 created_by 或 responsible_sales == 自己 real_name
    """
    from app.models import ApprovalStatus
    q = db.query(Project.id).filter(Project.approval_status == ApprovalStatus.approved)
    if current_user.role == UserRole.admin:
        return q
    my_name = current_user.real_name or current_user.username
    return q.filter(or_(
        Project.created_by == current_user.id,
        Project.responsible_sales == my_name,
    ))


def _to_response(item: ProjectFollowup) -> ProjectFollowupResponse:
    """将 ProjectFollowup ORM 对象转为 Pydantic Response。
    处理 form_data（数据库中是 JSON 字符串）→ dict 的转换，
    兼容老数据中可能存在的非标准 JSON 字符串（如 str(dict)）。

    关于 created_at / updated_at：
    SQLite 中 DateTime(timezone=True) 不存储时区信息，SQLAlchemy 返回 naive datetime。
    SQLite 的 func.now() / CURRENT_TIMESTAMP 返回的是 UTC。
    这里把 naive datetime 标记为 UTC，序列化为 ISO 字符串带 +00:00 后缀，
    前端 dayjs 解析时会自动转本地时区，避免出现 8 小时时差。
    """
    import json as _json
    from datetime import datetime as _dt, timezone as _tz

    def _ensure_utc(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            # SQLite 存的 naive datetime 来自 CURRENT_TIMESTAMP（UTC）
            return dt.replace(tzinfo=_tz.utc)
        return dt

    # 在 model_validate 之前先把 form_data 转为 dict，避免 Pydantic 校验失败
    item_dict = {
        'id': item.id,
        'project_id': item.project_id,
        'stage': item.stage.value if hasattr(item.stage, 'value') else item.stage,
        'progress': item.progress,
        'risks': item.risks,
        'next_plan': item.next_plan,
        'next_owner': item.next_owner,
        'next_deadline': item.next_deadline,
        'expected_amount': item.expected_amount,
        'expected_sign_date': item.expected_sign_date,
        'period_type': item.period_type,
        'period_label': item.period_label,
        'form_data': None,
        'reporter_id': item.reporter_id,
        'created_at': _ensure_utc(item.created_at),
        'updated_at': _ensure_utc(item.updated_at),
    }
    if item.form_data:
        if isinstance(item.form_data, dict):
            item_dict['form_data'] = item.form_data
        elif isinstance(item.form_data, str):
            try:
                item_dict['form_data'] = _json.loads(item.form_data)
            except Exception:
                # 非标准 JSON（如 str(dict)），安全降级为 None
                item_dict['form_data'] = None
    resp = ProjectFollowupResponse.model_validate(item_dict)
    resp.reporter_name = item.reporter.real_name if item.reporter else None
    if item.project:
        resp.project_name = item.project.project_name
        resp.project_code = item.project.project_code
        resp.responsible_sales = item.project.responsible_sales
    return resp


# ---------- API ----------
@router.get("/stage-options", response_model=list)
def get_stage_options():
    """前端获取阶段下拉选项"""
    return FOLLOWUP_STAGE_CHOICES


@router.get("/followable-projects", response_model=list)
def list_followable_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """当前用户可以对哪些项目新建跟单（下拉选项）。
    仅返回：当前用户自建的 或 责任销售是自己的 且 已审批通过 的项目。
    """
    ids = _followable_project_ids(db, current_user)
    rows = db.query(Project).filter(Project.id.in_(ids)).order_by(Project.id.desc()).all()
    return [
        {
            'id': p.id,
            'project_name': p.project_name,
            'project_code': p.project_code,
            'responsible_sales': p.responsible_sales,
            'source': p.source,
            'created_by': p.created_by,
        }
        for p in rows
    ]


@router.get("/template", response_model=dict)
def get_followup_template(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回当前激活的「项目跟单登记表」模板字段定义。
    前端按此模板的 fields 渲染新建跟单弹窗（所见即所得）。
    """
    from app.models import FormTemplate
    tpl = db.query(FormTemplate).filter(
        FormTemplate.name == '项目跟单登记表',
        FormTemplate.is_active == True,
    ).first()
    if not tpl:
        raise HTTPException(404, "「项目跟单登记表」模板不存在或已停用")
    import json as _jt
    fields = _jt.loads(tpl.fields) if tpl.fields else []
    return {
        'id': tpl.id,
        'name': tpl.name,
        'description': tpl.description,
        'fields': fields,
    }


@router.get("", response_model=ProjectFollowupListResponse)
def list_followups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[int] = None,
    stage: Optional[str] = None,
    project_name: Optional[str] = None,
    responsible_sales: Optional[str] = None,
    aggregate: bool = Query(True, description="True=按项目聚合（每个项目仅返回最新一条），False=全部明细"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """跟单列表（可筛选）。

    默认按项目维度聚合（一个项目只显示最新一条跟单），
    全部历史可通过 /timeline 接口查看。
    """
    visible_ids = select(_visible_project_ids(db, current_user).subquery().c.id)
    q = db.query(ProjectFollowup).filter(ProjectFollowup.project_id.in_(visible_ids)).options(
        joinedload(ProjectFollowup.project),
        joinedload(ProjectFollowup.reporter),
    )
    if project_id is not None:
        q = q.filter(ProjectFollowup.project_id == project_id)
    if stage:
        q = q.filter(ProjectFollowup.stage == stage)
    if responsible_sales:
        # 责任销售存在项目上，需要 join 到 project 表再 contains 匹配
        q = q.join(Project, Project.id == ProjectFollowup.project_id).filter(
            Project.responsible_sales.contains(responsible_sales)
        )
    if project_name:
        q = q.join(Project, Project.id == ProjectFollowup.project_id).filter(
            Project.project_name.contains(project_name)
        )

    if aggregate:
        # 按项目聚合：每项目仅返回最新一条
        # 子查询：按 project_id 分组取每组 max(id)
        latest_ids_q = (
            db.query(func.max(ProjectFollowup.id).label('max_id'))
            .filter(ProjectFollowup.project_id.in_(visible_ids))
        )
        # 在子查询里应用同样的筛选项，避免聚合后过滤掉 stage 不符的项
        if project_id is not None:
            latest_ids_q = latest_ids_q.filter(ProjectFollowup.project_id == project_id)
        if stage:
            latest_ids_q = latest_ids_q.filter(ProjectFollowup.stage == stage)
        if responsible_sales:
            latest_ids_q = latest_ids_q.join(Project, Project.id == ProjectFollowup.project_id).filter(
                Project.responsible_sales.contains(responsible_sales)
            )
        if project_name:
            latest_ids_q = latest_ids_q.join(Project, Project.id == ProjectFollowup.project_id).filter(
                Project.project_name.contains(project_name)
            )
        latest_ids_sub = latest_ids_q.group_by(ProjectFollowup.project_id).subquery()
        # 主查询仅保留每项目的最新一条
        q = q.filter(ProjectFollowup.id.in_(select(latest_ids_sub.c.max_id)))

    total = q.count()
    items = q.order_by(ProjectFollowup.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return ProjectFollowupListResponse(
        items=[_to_response(it) for it in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/export")
def export_followups(
    project_name: Optional[str] = None,
    stage: Optional[str] = None,
    responsible_sales: Optional[str] = None,
    project_ids: Optional[str] = Query(None, description="逗号分隔的 project_id 列表；为空表示全部"),
    aggregate: bool = Query(False, description="True=按项目聚合（每个项目最新一条），False=全部明细（每条历史）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出项目跟单 / 项目汇报为 Excel。

    默认输出**全部明细**（每个项目所有历史跟单），列表中多选项目后只导出所选项目。
    Excel 列：项目名称、责任销售、汇报时间、所处阶段 + 模板所有字段（含未填报列）。
    """
    from fastapi.responses import StreamingResponse
    from app.models import FormTemplate
    import io
    from datetime import datetime as _dt
    from openpyxl import Workbook

    # 1. 取模板字段（决定 Excel 列）
    tpl = db.query(FormTemplate).filter(
        FormTemplate.name == '项目跟单登记表',
        FormTemplate.is_active == True,
    ).first()
    import json as _jt
    template_fields = _jt.loads(tpl.fields) if tpl and tpl.fields else []

    # 解析 project_ids（逗号分隔）
    pid_list = None
    if project_ids:
        try:
            pid_list = [int(x) for x in project_ids.split(',') if x.strip()]
        except Exception:
            pid_list = None

    # 2. 构造与 list 相同的查询（不带分页）
    visible_ids = select(_visible_project_ids(db, current_user).subquery().c.id)
    q = db.query(ProjectFollowup).filter(ProjectFollowup.project_id.in_(visible_ids)).options(
        joinedload(ProjectFollowup.project),
        joinedload(ProjectFollowup.reporter),
    )
    if stage:
        q = q.filter(ProjectFollowup.stage == stage)
    if responsible_sales:
        q = q.join(Project, Project.id == ProjectFollowup.project_id).filter(
            Project.responsible_sales.contains(responsible_sales)
        )
    if project_name:
        q = q.join(Project, Project.id == ProjectFollowup.project_id).filter(
            Project.project_name.contains(project_name)
        )
    if pid_list:
        q = q.filter(ProjectFollowup.project_id.in_(pid_list))

    if aggregate:
        latest_ids_q = (
            db.query(func.max(ProjectFollowup.id).label('max_id'))
            .filter(ProjectFollowup.project_id.in_(visible_ids))
        )
        if stage:
            latest_ids_q = latest_ids_q.filter(ProjectFollowup.stage == stage)
        if responsible_sales:
            latest_ids_q = latest_ids_q.join(Project, Project.id == ProjectFollowup.project_id).filter(
                Project.responsible_sales.contains(responsible_sales)
            )
        if project_name:
            latest_ids_q = latest_ids_q.join(Project, Project.id == ProjectFollowup.project_id).filter(
                Project.project_name.contains(project_name)
            )
        if pid_list:
            latest_ids_q = latest_ids_q.filter(ProjectFollowup.project_id.in_(pid_list))
        latest_ids_sub = latest_ids_q.group_by(ProjectFollowup.project_id).subquery()
        q = q.filter(ProjectFollowup.id.in_(select(latest_ids_sub.c.max_id)))

    items = q.order_by(ProjectFollowup.created_at.desc()).all()

    # 3. 构建 Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "项目跟单"

    # 基础列 + 模板字段列 + 责任销售 + 汇报人
    headers = ["项目名称", "责任销售", "汇报时间", "所处阶段"]
    # 模板字段（label 作为列名，key 作为取值键）
    tpl_field_keys = []  # 用于从 item 中取值
    for f in template_fields:
        if not isinstance(f, dict):
            continue
        label = f.get('label') or f.get('key') or ''
        if label and label not in headers:
            headers.append(label)
            tpl_field_keys.append(f.get('key'))
    # 汇报人
    headers.append("汇报人")

    ws.append(headers)

    # 数据行
    for it in items:
        # 项目名称 / 责任销售
        proj = it.project
        proj_name = proj.project_name if proj else f'#{it.project_id}'
        resp_sales = proj.responsible_sales if proj else ''
        # 汇报时间：SQLite 中存的是 UTC naive datetime，转为本地时间（Asia/Shanghai +8h）显示
        if it.created_at:
            dt = it.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local_dt = dt.astimezone(timezone(timedelta(hours=8)))  # Asia/Shanghai
            report_time = local_dt.strftime('%Y-%m-%d %H:%M')
        else:
            report_time = ''
        reporter = it.reporter.real_name if it.reporter else ''
        stage_val = it.stage.value if hasattr(it.stage, 'value') else it.stage

        row = [proj_name, resp_sales, report_time, stage_val]

        # 模板字段取值（先尝试 ORM 列，再尝试 form_data 中存储的自定义字段）
        import json as _jdec
        form_data_dict = {}
        if it.form_data:
            try:
                form_data_dict = _jdec.loads(it.form_data) if isinstance(it.form_data, str) else (it.form_data or {})
            except Exception:
                form_data_dict = {}

        for k in tpl_field_keys:
            # 优先从 ORM 字段读取
            val = getattr(it, k, None) if k else None
            if val is None and k:
                val = form_data_dict.get(k, '')
            # 格式化日期
            if hasattr(val, 'isoformat'):
                val = val.isoformat()
            elif val is None:
                val = ''
            row.append(val)

        row.append(reporter)
        ws.append(row)

    # 列宽
    widths = [30, 14, 18, 12] + [20] * len(tpl_field_keys) + [14]
    for col_idx, w in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"project_followups_{_dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@router.get("/timeline", response_model=list)
def project_timeline(
    project_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """单项目的跟单时间轴（按时间倒序）。"""
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(404, "项目不存在")
    items = db.query(ProjectFollowup).filter(
        ProjectFollowup.project_id == project_id
    ).options(
        joinedload(ProjectFollowup.reporter),
        joinedload(ProjectFollowup.project),
    ).order_by(ProjectFollowup.created_at.desc()).all()
    # 通知跟单被查看:仅通知最近的 reporter(汇报人,可能多人),
    # 并跳过自己看自己、按项目去重(同一账号 60 秒内只发一次)
    try:
        from app.services.notifications import send_notification
        from app.models import NotificationType
        import time as _time
        key = (current_user.id, project_id)
        last_seen = getattr(project_timeline, "_seen_cache", None)
        if last_seen is None:
            last_seen = {}
            setattr(project_timeline, "_seen_cache", last_seen)
        now = _time.time()
        if now - last_seen.get(key, 0) > 60:  # 60s 节流
            last_seen[key] = now
            seen_reporter = set()
            for it in items:
                if it.reporter_id in seen_reporter:
                    continue
                if it.reporter_id == current_user.id:
                    continue  # 自己看自己的不通知
                seen_reporter.add(it.reporter_id)
                send_notification(
                    db,
                    receiver_id=it.reporter_id,
                    type=NotificationType.followup_viewed,
                    title="您的跟单被查看",
                    content="{0} 查看了项目 \"{1}\" 的跟单时间轴".format(
                        current_user.real_name or current_user.username,
                        proj.project_name,
                    ),
                    target_type="followup_project", target_id=project_id,
                    extra={"viewer_id": current_user.id, "viewer_name": current_user.real_name},
                )
            if seen_reporter:
                db.commit()
    except Exception:
        pass
    return [_to_response(it) for it in items]


@router.get("/summary", response_model=FollowupSummary)
def followup_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """汇总统计：阶段分布 / 预计成交总金额 / 涉及项目数。"""
    visible_ids = select(_visible_project_ids(db, current_user).subquery().c.id)
    base = db.query(ProjectFollowup).filter(
        ProjectFollowup.project_id.in_(visible_ids)
    )
    total = base.count()

    # 阶段分布
    rows = db.query(
        ProjectFollowup.stage,
        func.count(ProjectFollowup.id),
    ).filter(
        ProjectFollowup.project_id.in_(visible_ids)
    ).group_by(ProjectFollowup.stage).all()
    by_stage = []
    seen = set()
    for st, cnt in rows:
        if hasattr(st, 'value'):
            st = st.value
        seen.add(st)
        by_stage.append(FollowupStageStat(stage=st, count=cnt))
    # 补齐未出现阶段 count=0
    for s in FOLLOWUP_STAGE_CHOICES:
        if s not in seen:
            by_stage.append(FollowupStageStat(stage=s, count=0))
    by_stage.sort(key=lambda x: FOLLOWUP_STAGE_CHOICES.index(x.stage))

    # 预计成交金额合计（最新一次跟单的 expected_amount 之和：每个项目只算一次）
    # 实现：取每个 project_id 的 max(created_at) 跟单行，再 sum(expected_amount)
    sub = db.query(
        ProjectFollowup.project_id,
        func.max(ProjectFollowup.created_at).label('mx'),
    ).group_by(ProjectFollowup.project_id).subquery()
    latest_rows = db.query(ProjectFollowup).join(
        sub,
        (ProjectFollowup.project_id == sub.c.project_id) &
        (ProjectFollowup.created_at == sub.c.mx),
    ).all()
    expected_total = sum(
        float(r.expected_amount or 0) for r in latest_rows
    )
    projects_count = len(latest_rows)

    return FollowupSummary(
        total=total,
        by_stage=by_stage,
        expected_total_amount=round(expected_total, 2),
        projects_with_followup=projects_count,
    )


@router.post("", response_model=ProjectFollowupResponse)
def create_followup(
    payload: ProjectFollowupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_not_archive),
):
    """新建跟单记录（保留历史）。

    每次提交都创建一条新记录，旧记录不被覆盖、不被删除。
    列表默认按项目聚合（每个项目仅显示最新一条），
    全部历史可通过 /timeline 接口查看。
    """
    proj = db.query(Project).filter(Project.id == payload.project_id).first()
    if not proj:
        raise HTTPException(404, "项目不存在")
    # 只有已审批通过的项目才能跟单
    if proj.approval_status != ApprovalStatus.approved:
        raise HTTPException(
            status_code=400,
            detail=f"项目未审批通过（当前状态：{proj.approval_status.value if hasattr(proj.approval_status, 'value') else proj.approval_status}），不可跟单",
        )

    _stage_or_400(payload.stage)

    import json as _json_create
    form_data_str = _json_create.dumps(payload.form_data, ensure_ascii=False) if payload.form_data else None
    item = ProjectFollowup(
        project_id=payload.project_id,
        stage=payload.stage,
        progress=payload.progress,
        risks=payload.risks,
        next_plan=payload.next_plan,
        next_owner=payload.next_owner,
        next_deadline=payload.next_deadline,
        expected_amount=payload.expected_amount,
        expected_sign_date=payload.expected_sign_date,
        period_type=payload.period_type,
        period_label=payload.period_label,
        form_data=form_data_str,
        reporter_id=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    # 写入存储区域（best-effort：失败不影响主流程）
    try:
        ok, msg = save_followup_to_storage(db, item)
        print(f'[followup_storage] create id={item.id} -> {ok}: {msg}')
    except Exception as _e:
        print(f'[followup_storage] create exception: {_e}')
    return _to_response(item)


@router.put("/{followup_id}", response_model=ProjectFollowupResponse)
def update_followup(
    followup_id: int,
    payload: ProjectFollowupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_not_archive),
):
    """编辑跟单：作为"新版本"追加历史，不覆盖原记录。

    实现方式：
    - 读取原记录的所有字段
    - 应用 payload 中的修改（exclude_unset，未传则保持原值）
    - 创建一条新 ProjectFollowup 记录（reporter_id = 当前操作者，created_at = 当前时间）
    - 原记录保留，作为历史可在 /timeline 中查看

    权限：
      - admin: 可编辑任何跟单
      - 其他人: 仅原 reporter 本人可编辑
      - 其他情况（含重要账号）只读
    """
    item = db.query(ProjectFollowup).filter(ProjectFollowup.id == followup_id).first()
    if not item:
        raise HTTPException(404, "跟单记录不存在")
    if current_user.role != UserRole.admin and item.reporter_id != current_user.id:
        raise HTTPException(403, "仅创建人本人或管理员可修改")

    data = payload.model_dump(exclude_unset=True)
    if "stage" in data and data["stage"] is not None:
        _stage_or_400(data["stage"])

    import json as _json_edit
    # 以原记录字段为基准，再覆盖 payload 中实际传入的字段
    new_fields = {
        'project_id': item.project_id,
        'stage': item.stage.value if hasattr(item.stage, 'value') else item.stage,
        'progress': item.progress,
        'risks': item.risks,
        'next_plan': item.next_plan,
        'next_owner': item.next_owner,
        'next_deadline': item.next_deadline,
        'expected_amount': item.expected_amount,
        'expected_sign_date': item.expected_sign_date,
        'period_type': item.period_type,
        'period_label': item.period_label,
    }
    # form_data：原 dict + payload 的 form_data dict（payload 优先）
    orig_fd = {}
    if item.form_data:
        try:
            orig_fd = _json_edit.loads(item.form_data) if isinstance(item.form_data, str) else (item.form_data or {})
        except Exception:
            orig_fd = {}
    new_fields['form_data'] = _json_edit.dumps(orig_fd, ensure_ascii=False) if orig_fd else None

    # 应用 payload 修改
    for k, v in data.items():
        if k == 'form_data':
            new_fd = {**orig_fd, **(v or {})}
            new_fields['form_data'] = _json_edit.dumps(new_fd, ensure_ascii=False) if new_fd else None
        else:
            new_fields[k] = v

    new_item = ProjectFollowup(
        project_id=new_fields['project_id'],
        stage=new_fields['stage'],
        progress=new_fields['progress'],
        risks=new_fields['risks'],
        next_plan=new_fields['next_plan'],
        next_owner=new_fields['next_owner'],
        next_deadline=new_fields['next_deadline'],
        expected_amount=new_fields['expected_amount'],
        expected_sign_date=new_fields['expected_sign_date'],
        period_type=new_fields['period_type'],
        period_label=new_fields['period_label'],
        form_data=new_fields['form_data'],
        reporter_id=current_user.id,  # 编辑者
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    # 写入存储区域（best-effort）
    try:
        ok, msg = save_followup_to_storage(db, new_item)
        print(f'[followup_storage] edit id={new_item.id} -> {ok}: {msg}')
    except Exception as _e:
        print(f'[followup_storage] edit exception: {_e}')
    return _to_response(new_item)


@router.delete("/{followup_id}", response_model=MessageResponse)
def delete_followup(
    followup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_not_archive),
):
    """删除跟单记录 — 仅 admin 可删除。"""
    if current_user.role != UserRole.admin:
        raise HTTPException(403, "仅项目管理员（admin）可删除跟单")
    item = db.query(ProjectFollowup).filter(ProjectFollowup.id == followup_id).first()
    if not item:
        raise HTTPException(404, "跟单记录不存在")
    db.delete(item)
    db.commit()
    return MessageResponse(message="已删除")