from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.database import Base
import enum
from datetime import datetime


class StorageMode(str, enum.Enum):
    """文件存储模式"""
    local = 'local'        # 本地磁盘
    webdav = 'webdav'      # WebDAV (NAS)


class FileStorageConfig(Base):
    """文件存储配置（单例 id=1）— 已废弃，仅保留兼容旧代码
    新代码请使用 StorageZone
    """
    __tablename__ = 'file_storage_config'

    id = Column(Integer, primary_key=True, default=1)
    mode = Column(Enum(StorageMode), default=StorageMode.local, nullable=False)
    local_path = Column(String(500), nullable=True)
    webdav_url = Column(String(500), nullable=True)
    webdav_port = Column(Integer, nullable=True)
    webdav_use_ssl = Column(Boolean, default=True, nullable=False)
    webdav_username = Column(String(100), nullable=True)
    webdav_password = Column(String(200), nullable=True)
    webdav_base_path = Column(String(500), nullable=True)
    template = Column(String(200), default='{responsible_sales}+{project_name}+{date}', nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StorageZone(Base):
    """存储区域 — 用户自定义的文件存储位置（本地或 WebDAV）

    - mode=local:  local_path = D:\\项目文件\\渠道项目
    - mode=webdav: 远程 NAS (url + username + password + base_path)
    - 命名唯一：用户可创建多个区域（如「172nas」「测试资质」），项目使用 zone_id 关联
    - sub_path: 该区域下存放指定表单/项目的子路径（如「自建项目」「渠道项目」）
    """
    __tablename__ = 'storage_zones'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)  # 区域名（唯一）
    mode = Column(Enum(StorageMode), default=StorageMode.webdav, nullable=False)
    local_path = Column(String(500), nullable=True)  # 本地磁盘路径
    webdav_url = Column(String(500), nullable=True)
    webdav_port = Column(Integer, nullable=True)
    webdav_use_ssl = Column(Boolean, default=True, nullable=False)
    webdav_username = Column(String(100), nullable=True)
    webdav_password = Column(String(200), nullable=True)
    webdav_base_path = Column(String(500), nullable=True)  # 起始路径
    sub_path = Column(String(200), nullable=True)  # 区域下的子路径
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)  # 显示排序
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class UserRole(str, enum.Enum):
    admin = "admin"                   # 系统管理员
    important = "important"           # 重要账号
    normal = "normal"                 # 普通账号
    archive = "archive"               # 档案管理（只读）

class CooperationMode(str, enum.Enum):
    long_term = "long_term"
    short_term = "short_term"

class FeeMode(str, enum.Enum):
    mutual = "mutual"
    charged = "charged"

class IsSM(str, enum.Enum):
    yes = "yes"
    no = "no"

class WinBidStatus(str, enum.Enum):
    yes = "yes"
    no = "no"
    in_progress = "in_progress"

class ApprovalStatus(str, enum.Enum):
    pending_submit = "pending_submit"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"

class ApprovalAction(str, enum.Enum):
    submit = "submit"
    approve = "approve"
    reject = "reject"
    withdraw = "withdraw"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.normal, nullable=False)
    real_name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    is_rejected = Column(Boolean, default=False)  # True = 申请被驳回（区别于 is_active=False 的"正常停用"）
    pending_password = Column(String(50), nullable=True)  # 申请时生成的初始明文密码（审批通过或驳回后清除）
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关联
    children = relationship("User", backref=backref("parent", remote_side=[id]), lazy="select")
    projects_created = relationship("Project", back_populates="creator", foreign_keys="Project.created_by")
    projects_approved = relationship("Project", back_populates="approver", foreign_keys="Project.approver_id")
    approval_logs = relationship("ApprovalLog", back_populates="approver_user")

class ProjectType(str, enum.Enum):
    """项目类型"""
    information = "信息化"
    intelligent = "智能化"
    mep_fire = "机电消防"
    software = "软件开放"
    ops = "系统运维"
    xc_sm = "XC/SM"
    military = "军队武警"
    other = "其他"


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_name = Column(String(200), nullable=False)
    project_code = Column(String(50), nullable=True, unique=True)
    project_type = Column(Enum(ProjectType, values_callable=lambda x: [e.value for e in x]), default=ProjectType.other, nullable=False)
    source = Column(String(20), nullable=True, default='channel')  # channel=渠道项目 / self=自建项目（来自 form_instance）
    form_instance_id = Column(Integer, ForeignKey("form_instances.id"), nullable=True)
    tender_time = Column(Date, nullable=True)
    bid_time = Column(Date, nullable=True)
    owner_contact_person = Column(String(100), nullable=True)
    owner_contact_info = Column(String(100), nullable=True)
    partner_company = Column(String(200), nullable=True)  # 公司名称
    company_address = Column(String(200), nullable=True)
    main_qualification = Column(String(200), nullable=True)
    legal_representative = Column(String(100), nullable=True)
    contact_person = Column(String(100), nullable=True)
    contact_info = Column(String(100), nullable=True)
    cooperation_mode = Column(Enum(CooperationMode), nullable=False)
    fee_mode = Column(Enum(FeeMode), nullable=False)
    fee_amount = Column(Float, nullable=True)
    is_sm = Column(Enum(IsSM), nullable=False, default=IsSM.no)
    project_amount = Column(Float, default=0.0)  # 预计金额（万元，前端用 0.0 表示）
    expected_amount = Column(Float, default=0.0)
    win_bid_status = Column(Enum(WinBidStatus), default=WinBidStatus.in_progress)
    win_bid_status_set_at = Column(DateTime, nullable=True)  # 中标状态首次设置时间（锁定后不允许修改）
    project_overview = Column(Text, nullable=True)
    tender_file = Column(String(500), nullable=True)
    bid_file = Column(String(500), nullable=True)
    tender_folder = Column(String(500), nullable=True)
    bid_folder = Column(String(500), nullable=True)
    responsible_sales = Column(String(100), nullable=True)  # 责任销售（用于命名项目文件夹，留空则用创建者姓名）
    storage_zone_id = Column(Integer, ForeignKey("storage_zones.id"), nullable=True)  # 使用的存储区域
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approval_status = Column(Enum(ApprovalStatus), default=ApprovalStatus.pending_submit)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now(), nullable=False)

    # 关联
    creator = relationship("User", back_populates="projects_created", foreign_keys=[created_by])
    approver = relationship("User", back_populates="projects_approved", foreign_keys=[approver_id])
    storage_zone = relationship("StorageZone", foreign_keys=[storage_zone_id])
    approval_logs = relationship("ApprovalLog", back_populates="project", cascade="all, delete-orphan")

class ApprovalLog(Base):
    __tablename__ = "approval_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(Enum(ApprovalAction), nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联
    project = relationship("Project", back_populates="approval_logs")
    approver_user = relationship("User", back_populates="approval_logs")


class AuditAction(str, enum.Enum):
    """审计操作类型"""
    # 用户
    user_login = "user.login"                # 登录
    user_logout = "user.logout"              # 登出
    user_create = "user.create"              # 创建用户
    user_update = "user.update"              # 编辑用户
    user_delete = "user.delete"              # 停用用户
    user_reset_password = "user.reset_password"  # 重置密码
    user_password_change = "user.password_change"  # 用户自己修改密码
    # 项目
    project_create = "project.create"
    project_update = "project.update"
    project_delete = "project.delete"
    project_submit = "project.submit"
    project_withdraw = "project.withdraw"
    project_approve = "project.approve"
    project_reject = "project.reject"
    # 文件
    file_upload = "file.upload"
    file_delete = "file.delete"


class AuditLog(Base):
    """审计日志 - 记录所有关键操作
    注意：表结构由 services/audit.py 通过直接 sqlite3 管理（不依赖 SA）
    """
    __tablename__ = "audit_logs"
    __table_args__ = {'extend_existing': True, 'info': {'managed_externally': True}}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(50), nullable=False)
    real_name = Column(String(100), nullable=True)
    role = Column(String(20), nullable=True)
    action = Column(String(50), nullable=False)
    target_type = Column(String(50), nullable=True)
    target_id = Column(Integer, nullable=True)
    target_name = Column(String(200), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FormTemplate(Base):
    """表单模板 — 管理员通过表单生成器设计的表单定义"""
    __tablename__ = "form_templates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    fields = Column(Text, nullable=False, default='[]')  # JSON: [{type, label, key, required, ...}]
    storage_sub_path = Column(String(200), nullable=True)  # 兼容旧字段（已弃用，新代码使用 storage_zone_id）
    storage_zone_id = Column(Integer, ForeignKey("storage_zones.id"), nullable=True)  # 关联的存储区域
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    creator = relationship("User", foreign_keys=[created_by])
    storage_zone = relationship("StorageZone", foreign_keys=[storage_zone_id])
    instances = relationship("FormInstance", back_populates="template", cascade="all, delete-orphan")


class FormInstance(Base):
    """表单实例 — 用户根据模板提交的表单数据"""
    __tablename__ = "form_instances"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey("form_templates.id"), nullable=False)
    data = Column(Text, nullable=False, default='{}')
    tender_folder = Column(String(500), nullable=True)
    bid_folder = Column(String(500), nullable=True)
    storage_zone_id = Column(Integer, ForeignKey("storage_zones.id"), nullable=True)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approval_status = Column(Enum(ApprovalStatus), default=ApprovalStatus.pending_submit)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    template = relationship("FormTemplate", back_populates="instances")
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approver_id])
    storage_zone = relationship("StorageZone", foreign_keys=[storage_zone_id])
