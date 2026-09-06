"""项目跟单文件存储服务 — 根据 FormTemplate.storage_zone_id 将跟单数据写入存储区域

跟单创建/编辑时：
  1. 读取「项目跟单登记表」模板
  2. 取模板关联的 StorageZone
  3. 在 zone 内创建按项目归类的目录
  4. 把跟单数据序列化为 JSON（每条跟单一个文件）+ Markdown 摘要

文件路径结构（webdav 模式）:
  {base_path}/{sub_path}/{project_id}-{project_name}/{followup_id}.json
  {base_path}/{sub_path}/{project_id}-{project_name}/{followup_id}.md

文件路径结构（local 模式）:
  {local_path}/{sub_path?}/{project_id}-{project_name}/{followup_id}.json
"""
import json
import datetime
import urllib.parse
from typing import Tuple, Optional

from sqlalchemy.orm import Session

from app.models import (
    FormTemplate, ProjectFollowup, Project, StorageZone, StorageMode, User,
)


def _get_followup_template(db: Session) -> Optional[FormTemplate]:
    """获取「项目跟单登记表」模板"""
    return db.query(FormTemplate).filter(FormTemplate.name == '项目跟单登记表').first()


def _get_zone(db: Session, zone_id: Optional[int]) -> Optional[StorageZone]:
    """按 ID 取区域；无 ID 返回默认区域"""
    if zone_id:
        z = db.query(StorageZone).filter(StorageZone.id == zone_id).first()
        if z:
            return z
    return db.query(StorageZone).filter(StorageZone.is_active == True).order_by(
        StorageZone.sort_order, StorageZone.id
    ).first()


def _sanitize(s: str) -> str:
    """去掉非法字符（路径分隔符等）"""
    if not s:
        return ''
    # 去掉路径分隔符与控制字符
    bad_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t']
    out = s
    for ch in bad_chars:
        out = out.replace(ch, '_')
    return out.strip()


def _build_paths(zone: StorageZone, project_id: int, project_name: str,
                 followup_id: int, ext: str):
    """构建文件路径。

    返回 dict：
      - mode == 'webdav': {'file_url': str, 'folder_url': str, 'filename': str}
      - mode == 'local' : {'file_path': str, 'filename': str, 'folder_path': str}
    """
    folder = f"{project_id}-{_sanitize(project_name)}"
    filename = f"{followup_id}.{ext}"
    sub_path = (zone.sub_path or '').strip('/').strip()

    if zone.mode == StorageMode.local:
        base = (zone.local_path or '').rstrip('\\/') or '.'
        if sub_path:
            folder_path = f"{base}/{sub_path}/{folder}"
            file_path = f"{folder_path}/{filename}"
        else:
            folder_path = f"{base}/{folder}"
            file_path = f"{folder_path}/{filename}"
        # Windows 本地路径用反斜杠
        file_path = file_path.replace('/', os.sep)
        folder_path = folder_path.replace('/', os.sep)
        return {'file_path': file_path, 'filename': filename, 'folder_path': folder_path}

    # webdav
    scheme = 'https' if zone.webdav_use_ssl else 'http'
    host_part = f"{scheme}://{zone.webdav_url}"
    if zone.webdav_port:
        host_part += f":{zone.webdav_port}"
    base_path = (zone.webdav_base_path or '').strip('/')
    parts = [host_part]
    if base_path:
        parts.append(base_path)
    if sub_path:
        parts.append(sub_path)
    parts.append(folder)
    parts.append(filename)
    file_url = '/'.join(parts)
    folder_url = '/'.join(parts[:-1])
    return {'file_url': file_url, 'folder_url': folder_url, 'filename': filename}


def _serialize_followup_json(item: ProjectFollowup, project: Project, reporter: Optional[User],
                             form_template: Optional[FormTemplate]) -> bytes:
    """将跟单数据序列化为 JSON 字节串"""
    import json as _json
    # 解析 form_data
    form_data = {}
    if item.form_data:
        try:
            form_data = _json.loads(item.form_data) if isinstance(item.form_data, str) else item.form_data
        except Exception:
            form_data = {}
    # 模板字段顺序
    tpl_fields = []
    if form_template and form_template.fields:
        try:
            tpl_fields = _json.loads(form_template.fields)
        except Exception:
            pass
    # 构建字段值列表（按模板顺序）
    field_values = []
    for f in tpl_fields:
        if not isinstance(f, dict):
            continue
        key = f.get('key')
        label = f.get('label') or key or ''
        if not key:
            continue
        # 优先 ORM 字段，再 form_data
        val = getattr(item, key, None)
        if val is None:
            val = form_data.get(key)
        # 序列化 datetime
        if hasattr(val, 'isoformat'):
            val = val.isoformat()
        elif hasattr(val, 'strftime'):
            val = val.strftime('%Y-%m-%d')
        field_values.append({'label': label, 'key': key, 'value': val})

    stage_val = item.stage.value if hasattr(item.stage, 'value') else item.stage
    payload = {
        'followup_id': item.id,
        'project_id': item.project_id,
        'project_name': project.project_name if project else f'#{item.project_id}',
        'responsible_sales': project.responsible_sales if project else '',
        'reporter': reporter.real_name if reporter else '',
        'reporter_username': reporter.username if reporter else '',
        'stage': stage_val,
        'progress': item.progress,
        'risks': item.risks,
        'next_plan': item.next_plan,
        'next_owner': item.next_owner,
        'next_deadline': item.next_deadline.strftime('%Y-%m-%d') if item.next_deadline else None,
        'expected_amount': item.expected_amount,
        'expected_sign_date': item.expected_sign_date.strftime('%Y-%m-%d') if item.expected_sign_date else None,
        'period_type': item.period_type,
        'period_label': item.period_label,
        'form_data': form_data,
        'template_fields': field_values,
        'created_at': item.created_at.isoformat() if item.created_at else None,
        'updated_at': item.updated_at.isoformat() if item.updated_at else None,
    }
    return _json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')


def _serialize_followup_markdown(item: ProjectFollowup, project: Project, reporter: Optional[User],
                                 form_template: Optional[FormTemplate]) -> bytes:
    """将跟单数据序列化为 Markdown（人类可读）"""
    lines = []
    stage_val = item.stage.value if hasattr(item.stage, 'value') else item.stage
    lines.append(f"# 跟单记录 #{item.id}")
    lines.append('')
    lines.append(f"- **项目名称**: {project.project_name if project else f'#{item.project_id}'}")
    if project:
        lines.append(f"- **责任销售**: {project.responsible_sales or ''}")
    lines.append(f"- **汇报人**: {reporter.real_name if reporter else ''}")
    lines.append(f"- **所处阶段**: {stage_val or ''}")
    lines.append(f"- **汇报时间**: {item.created_at.strftime('%Y-%m-%d %H:%M') if item.created_at else ''}")
    if item.expected_amount is not None:
        lines.append(f"- **预计成交金额**: {item.expected_amount} 万元")
    if item.expected_sign_date:
        lines.append(f"- **预计签单日期**: {item.expected_sign_date.strftime('%Y-%m-%d')}")
    if item.next_owner:
        lines.append(f"- **下一步责任人**: {item.next_owner}")
    if item.next_deadline:
        lines.append(f"- **下一步截止时间**: {item.next_deadline.strftime('%Y-%m-%d')}")
    lines.append('')
    lines.append('## 当前进展')
    lines.append(item.progress or '（未填报）')
    lines.append('')
    if item.risks:
        lines.append('## 风险与所需支持')
        lines.append(item.risks)
        lines.append('')
    if item.next_plan:
        lines.append('## 下一步计划')
        lines.append(item.next_plan)
        lines.append('')
    # 自定义字段
    if item.form_data and form_template and form_template.fields:
        import json as _json
        try:
            tpl_fields = _json.loads(form_template.fields)
            form_dict = _json.loads(item.form_data) if isinstance(item.form_data, str) else item.form_data
            custom_items = []
            for f in tpl_fields:
                if not isinstance(f, dict):
                    continue
                key = f.get('key')
                label = f.get('label') or key
                if not key:
                    continue
                # 跳过 ORM 字段（已经在上面展示过）
                orm_fields = {'progress', 'risks', 'next_plan', 'next_owner', 'next_deadline',
                              'expected_amount', 'expected_sign_date'}
                if key in orm_fields:
                    continue
                v = form_dict.get(key)
                if v not in (None, ''):
                    custom_items.append((label, v))
            if custom_items:
                lines.append('## 自定义字段')
                for label, v in custom_items:
                    lines.append(f"- **{label}**: {v}")
                lines.append('')
        except Exception:
            pass
    return ('\n'.join(lines)).encode('utf-8')


def _ensure_webdav_dirs(zone: StorageZone, dir_urls: list) -> Tuple[bool, str]:
    """递归 MKCOL 创建 WebDAV 目录"""
    from app.services.file_storage import webdav_request, ensure_webdav_folders
    pw = zone.webdav_password or ''
    # 先确保根目录
    if not dir_urls:
        return True, 'no dirs'
    root_url = dir_urls[0].rsplit('/', 1)[0] if '/' in dir_urls[0] else dir_urls[0]
    ok, msg = webdav_request('PROPFIND', root_url, zone.webdav_username, pw)
    if not ok and '405' not in msg:
        webdav_request('MKCOL', root_url, zone.webdav_username, pw)
    # 逐级创建
    for url in dir_urls:
        ok, msg = webdav_request('PROPFIND', url, zone.webdav_username, pw)
        if ok or '405' in msg:
            continue
        ok, msg = webdav_request('MKCOL', url, zone.webdav_username, pw)
        if not (ok or '405' in msg):
            return False, f'创建目录失败 {url}: {msg}'
    return True, 'ok'


def save_followup_to_storage(db: Session, item: ProjectFollowup) -> Tuple[bool, str]:
    """将一条跟单写入其模板关联的存储区域

    返回 (是否成功, 消息)。失败不抛异常（仅记录），不影响主流程写库。
    """
    try:
        tpl = _get_followup_template(db)
        zone = _get_zone(db, tpl.storage_zone_id if tpl else None)
        if not zone:
            return False, '未配置跟单模板的存储区域（模板或 zone 不存在）'
        # 关联项目与汇报人
        project = db.query(Project).filter(Project.id == item.project_id).first()
        reporter = db.query(User).filter(User.id == item.reporter_id).first() if item.reporter_id else None

        # 序列化为 JSON + Markdown
        json_bytes = _serialize_followup_json(item, project, reporter, tpl)
        md_bytes = _serialize_followup_markdown(item, project, reporter, tpl)

        # 构建文件路径
        proj_name = project.project_name if project else f'p{item.project_id}'
        paths_json = _build_paths(zone, item.project_id, proj_name, item.id, 'json')
        paths_md = _build_paths(zone, item.project_id, proj_name, item.id, 'md')

        if zone.mode == StorageMode.local:
            from app.services.file_storage import ensure_local_folders, write_local_file
            ok, m = ensure_local_folders([paths_json['folder_path'], paths_md['folder_path']])
            if not ok:
                return False, f'创建本地目录失败: {m}'
            ok1, m1 = write_local_file(paths_json['file_path'], json_bytes)
            ok2, m2 = write_local_file(paths_md['file_path'], md_bytes)
            if ok1 and ok2:
                return True, f'已保存到本地: {paths_json["file_path"]}'
            return False, f'本地写文件失败: {m1} | {m2}'
        else:
            from app.services.file_storage import webdav_upload_file
            # 1. 确保目录存在
            ok, m = _ensure_webdav_dirs(zone, [paths_json['folder_url']])
            if not ok:
                return False, f'创建 WebDAV 目录失败: {m}'
            # 2. 上传两个文件
            ok1, m1 = webdav_upload_file(paths_json['file_url'], json_bytes, zone.webdav_username,
                                         zone.webdav_password, content_type='application/json; charset=utf-8')
            ok2, m2 = webdav_upload_file(paths_md['file_url'], md_bytes, zone.webdav_username,
                                         zone.webdav_password, content_type='text/markdown; charset=utf-8')
            if ok1 and ok2:
                return True, f'已保存到 WebDAV: {paths_json["file_url"]}'
            return False, f'WebDAV 写文件失败: {m1} | {m2}'
    except Exception as e:
        import traceback
        return False, f'存储写入异常: {e}\n{traceback.format_exc()}'


# 兼容路径
import os