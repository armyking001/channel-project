from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import date, datetime
from app.models import UserRole, CooperationMode, FeeMode, IsSM, WinBidStatus, ApprovalStatus, ApprovalAction, StorageMode, ProjectType, NotificationType, AIModelType

# ============ 通用 ============
class MessageResponse(BaseModel):
    message: str

# ============ 用户 ============
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    real_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole = UserRole.normal
    parent_id: Optional[int] = None
    is_active: bool = True
    phone: Optional[str] = Field(default=None, max_length=20)
    dingtalk_user_id: Optional[str] = Field(default=None, max_length=100)

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    username: Optional[str] = None
    role: Optional[UserRole] = None
    parent_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)  # 审批通过时设置密码
    phone: Optional[str] = Field(default=None, max_length=20)  # 手机号(短信通道用)
    dingtalk_user_id: Optional[str] = Field(default=None, max_length=100)  # 钉钉用户 id(工作通知用)

class UserPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6)

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    real_name: str
    role: UserRole
    parent_id: Optional[int]
    is_active: bool
    is_rejected: bool = False
    pending_password: Optional[str] = None  # 仅"待审批"用户返回，审批后清除
    phone: Optional[str] = None
    dingtalk_user_id: Optional[str] = None
    created_at: datetime

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ApplyAccountResponse(BaseModel):
    """申请账号响应"""
    username: str
    real_name: str
    status: str  # "pending"
    message: str
    initial_password: Optional[str] = None  # 系统生成的 8 位随机初始密码（返回给申请人保存）

# ============ 项目 ============
class ProjectBase(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=200)
    project_code: Optional[str] = Field(None, max_length=50)
    project_type: ProjectType = ProjectType.other
    tender_time: Optional[date] = None
    bid_time: Optional[date] = None
    owner_contact_person: Optional[str] = Field(None, max_length=100)
    owner_contact_info: Optional[str] = Field(None, max_length=100)
    partner_company: Optional[str] = Field(None, max_length=200)  # 公司名称
    company_address: Optional[str] = Field(None, max_length=200)
    main_qualification: Optional[str] = Field(None, max_length=200)
    legal_representative: Optional[str] = Field(None, max_length=100)
    contact_person: Optional[str] = Field(None, max_length=100)
    contact_info: Optional[str] = Field(None, max_length=100)
    cooperation_mode: CooperationMode
    fee_mode: FeeMode
    fee_amount: Optional[float] = None
    is_sm: IsSM = IsSM.no
    project_amount: float = 0.0
    expected_amount: float = 0.0
    win_bid_status: WinBidStatus = WinBidStatus.in_progress
    project_overview: Optional[str] = None
    tender_file: Optional[str] = None
    bid_file: Optional[str] = None
    approver_id: Optional[int] = None
    responsible_sales: Optional[str] = None
    storage_zone_id: Optional[int] = None  # 存储区域（默认使用系统默认区域）

class ProjectCreate(ProjectBase):
    responsible_sales: Optional[str] = Field(None, max_length=100)  # 责任销售可空（留空则用当前账号姓名）

    @field_validator('tender_time', 'bid_time', mode='before')
    @classmethod
    def _empty_date_to_none(cls, v):
        """前端表单字段为空字符串时转为 None，避免 Pydantic date 解析失败"""
        if v in ('', None):
            return None
        return v


# ============ 项目跟单 ============
FOLLOWUP_STAGE_CHOICES = ["需求对接", "方案提供", "商务沟通", "投标报价", "其他"]


class ProjectFollowupCreate(BaseModel):
    project_id: int
    stage: str = "其他"
    progress: Optional[str] = None
    risks: Optional[str] = None
    next_plan: Optional[str] = None
    next_owner: Optional[str] = None
    next_deadline: Optional[date] = None
    expected_amount: Optional[float] = None
    expected_sign_date: Optional[date] = None
    period_type: Optional[str] = None  # week / month / fixed
    period_label: Optional[str] = None
    form_data: Optional[dict] = None   # 模板自定义字段 {key: value}


class ProjectFollowupUpdate(BaseModel):
    stage: Optional[str] = None
    progress: Optional[str] = None
    risks: Optional[str] = None
    next_plan: Optional[str] = None
    next_owner: Optional[str] = None
    next_deadline: Optional[date] = None
    expected_amount: Optional[float] = None
    expected_sign_date: Optional[date] = None
    period_type: Optional[str] = None
    period_label: Optional[str] = None
    form_data: Optional[dict] = None


class ProjectFollowupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    project_name: Optional[str] = None
    project_code: Optional[str] = None
    responsible_sales: Optional[str] = None
    stage: str
    progress: Optional[str] = None
    risks: Optional[str] = None
    next_plan: Optional[str] = None
    next_owner: Optional[str] = None
    next_deadline: Optional[date] = None
    expected_amount: Optional[float] = None
    expected_sign_date: Optional[date] = None
    period_type: Optional[str] = None
    period_label: Optional[str] = None
    form_data: Optional[dict] = None
    reporter_id: int
    reporter_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator('form_data', mode='before')
    @classmethod
    def parse_form_data(cls, v):
        """ProjectFollowup.form_data 在数据库中是 JSON 字符串，此处解析为 dict。
        兼容老数据中可能存在的非标准 JSON 字符串（如 str(dict)）。"""
        if v is None:
            return None
        if isinstance(v, str):
            import json as _json
            try:
                return _json.loads(v)
            except Exception:
                # 非标准 JSON 字符串（str(dict) 之类），返回 None 以避免 Pydantic 报错
                return None
        if isinstance(v, dict):
            return v
        return None

    @field_validator('stage', mode='before')
    @classmethod
    def parse_stage(cls, v):
        if hasattr(v, 'value'):
            return v.value
        return v


class ProjectFollowupListResponse(BaseModel):
    items: List[ProjectFollowupResponse]
    total: int
    page: int
    page_size: int


class FollowupStageStat(BaseModel):
    stage: str
    count: int


class FollowupSummary(BaseModel):
    total: int
    by_stage: List[FollowupStageStat]
    expected_total_amount: float
    projects_with_followup: int

class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    project_code: Optional[str] = None
    project_type: Optional[ProjectType] = None
    tender_time: Optional[date] = None
    bid_time: Optional[date] = None
    owner_contact_person: Optional[str] = None
    owner_contact_info: Optional[str] = None
    partner_company: Optional[str] = None
    company_address: Optional[str] = None
    main_qualification: Optional[str] = None
    legal_representative: Optional[str] = None
    contact_person: Optional[str] = None
    contact_info: Optional[str] = None
    cooperation_mode: Optional[CooperationMode] = None
    fee_mode: Optional[FeeMode] = None
    fee_amount: Optional[float] = None
    is_sm: Optional[IsSM] = None
    project_amount: Optional[float] = None
    expected_amount: Optional[float] = None
    win_bid_status: Optional[WinBidStatus] = None
    project_overview: Optional[str] = None
    tender_file: Optional[str] = None
    bid_file: Optional[str] = None
    approver_id: Optional[int] = None
    responsible_sales: Optional[str] = None
    storage_zone_id: Optional[int] = None
    # 中标状态非首次修改时使用：修改理由 + 管理员密码验证
    win_bid_change_reason: Optional[str] = None
    admin_password_verify: Optional[str] = None

    @field_validator('tender_time', 'bid_time', mode='before')
    @classmethod
    def _empty_date_to_none(cls, v):
        """编辑模式下空字符串/None 一律视为 None，避免 Pydantic 解析失败"""
        if v in ('', None):
            return None
        return v

class ApprovalRequest(BaseModel):
    comment: Optional[str] = None

class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_name: str
    project_code: Optional[str] = None
    project_type: ProjectType
    source: Optional[str] = 'channel'  # channel=渠道项目 / self=自建项目
    form_instance_id: Optional[int] = None
    tender_time: Optional[date] = None
    bid_time: Optional[date] = None
    owner_contact_person: Optional[str] = None
    owner_contact_info: Optional[str] = None
    partner_company: Optional[str] = None
    company_address: Optional[str] = None
    main_qualification: Optional[str] = None
    legal_representative: Optional[str] = None
    contact_person: Optional[str] = None
    contact_info: Optional[str] = None
    cooperation_mode: CooperationMode
    fee_mode: FeeMode
    fee_amount: Optional[float]
    is_sm: IsSM
    project_amount: float
    expected_amount: float
    win_bid_status: WinBidStatus
    win_bid_status_set_at: Optional[datetime] = None
    project_overview: Optional[str] = None
    tender_file: Optional[str]
    bid_file: Optional[str]
    tender_folder: Optional[str] = None
    bid_folder: Optional[str] = None
    responsible_sales: Optional[str] = None
    storage_zone_id: Optional[int] = None
    storage_zone: Optional['StorageZoneResponse'] = None
    created_by: int
    approver_id: Optional[int]
    approval_status: ApprovalStatus
    created_at: datetime
    updated_at: datetime
    creator: Optional[UserResponse] = None
    approver: Optional[UserResponse] = None

class ProjectListResponse(BaseModel):
    items: List[ProjectResponse]
    total: int
    page: int
    page_size: int

# ============ 审批日志 ============
class ApprovalLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    approver_id: int
    action: ApprovalAction
    comment: Optional[str]
    created_at: datetime
    approver_user: Optional[UserResponse] = None

# ============ 导出 ============
class LLMSummaryResponse(BaseModel):
    total_projects: int
    total_amount: float
    win_rate: float
    status_summary: dict
    top_partners: List[dict]
    monthly_data: List[dict]


# ============ 文件存储配置 ============
class FileStorageConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mode: StorageMode
    local_path: Optional[str] = None
    webdav_url: Optional[str] = None
    webdav_port: Optional[int] = None
    webdav_use_ssl: bool = True
    webdav_username: Optional[str] = None
    webdav_password: Optional[str] = None  # 返回时回显空字符串
    webdav_base_path: Optional[str] = None
    template: str
    updated_at: datetime


class FileStorageConfigUpdate(BaseModel):
    mode: StorageMode
    local_path: Optional[str] = None
    webdav_url: Optional[str] = None
    webdav_port: Optional[int] = None
    webdav_use_ssl: Optional[bool] = None
    webdav_username: Optional[str] = None
    webdav_password: Optional[str] = None
    webdav_base_path: Optional[str] = None
    template: Optional[str] = None


class PathPreviewRequest(BaseModel):
    """预览项目文件夹路径（不实际创建）"""
    project_name: str
    project_code: Optional[str] = None
    # 指定创建者（用于编辑模式下预览原始项目路径）
    creator_username: Optional[str] = None
    creator_real_name: Optional[str] = None
    # 责任销售（用于命名项目根目录，留空则兑底用创建者姓名）
    responsible_sales: Optional[str] = None
    # 已有项目目录直接回传（用数据库存的 tender_folder/bid_folder）
    existing_tender_folder: Optional[str] = None
    existing_bid_folder: Optional[str] = None
    # 项目来源：channel=渠道项目（FileStorageConfig）/ self=自建项目（按 storage_zone_id 找 zone）
    source: Optional[str] = None
    # 存储区域 id（自建项目用，决定 webdav_base_path）
    storage_zone_id: Optional[int] = None


class PathPreviewResponse(BaseModel):
    tender_folder: str
    bid_folder: str
    base_folder: str


# ============ 审计日志 ============
class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: Optional[int]
    username: str
    real_name: Optional[str]
    role: Optional[str]
    action: str
    target_type: Optional[str]
    target_id: Optional[int]
    target_name: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int


# ============ 表单生成器 ============
class FormTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    fields: List[dict] = Field(default_factory=list)
    storage_sub_path: Optional[str] = None
    storage_zone_id: Optional[int] = None

class FormTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    fields: Optional[List[dict]] = None
    is_active: Optional[bool] = None
    storage_sub_path: Optional[str] = None
    storage_zone_id: Optional[int] = None

class FormTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None
    fields: List[dict] = []
    storage_sub_path: Optional[str] = None
    storage_zone_id: Optional[int] = None
    is_active: bool = True
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    creator: Optional[UserResponse] = None
    storage_zone: Optional['StorageZoneResponse'] = None

    @field_validator('fields', mode='before')
    @classmethod
    def parse_fields(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v or []


class AIModelConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    model_type: AIModelType = AIModelType.local
    provider: str = Field(default="openai_compatible", max_length=50)
    base_url: Optional[str] = Field(default=None, max_length=500)
    model_name: str = Field(..., min_length=1, max_length=200)
    api_key: Optional[str] = Field(default=None, max_length=500)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    timeout_seconds: int = Field(default=60, ge=5, le=600)
    is_enabled: bool = True
    is_default: bool = False
    notes: Optional[str] = None


class AIModelConfigUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    model_type: Optional[AIModelType] = None
    provider: Optional[str] = Field(default=None, max_length=50)
    base_url: Optional[str] = Field(default=None, max_length=500)
    model_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    api_key: Optional[str] = Field(default=None, max_length=500)
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    timeout_seconds: Optional[int] = Field(default=None, ge=5, le=600)
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    notes: Optional[str] = None


class AIModelConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    model_type: AIModelType
    provider: str
    base_url: Optional[str] = None
    model_name: str
    api_key: Optional[str] = None
    temperature: float
    max_tokens: Optional[int] = None
    timeout_seconds: int
    is_enabled: bool
    is_default: bool
    notes: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    creator: Optional[UserResponse] = None


class AIModelPresetResponse(BaseModel):
    key: str
    name: str
    provider: str
    model_type: AIModelType
    base_url: str
    model_name: str
    description: Optional[str] = None
    notes: Optional[str] = None
    recommended_timeout_seconds: int = 60
    recommended_temperature: float = 0.2


class AIModelTestRequest(BaseModel):
    prompt: str = Field(default="请只回复“连接成功”四个字。", min_length=1, max_length=500)


class AIModelTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int
    status_code: Optional[int] = None
    provider: str
    model_name: str
    response_preview: Optional[str] = None


class AIAnalysisRequest(BaseModel):
    model_id: Optional[int] = None
    prompt: str = Field(..., min_length=1)
    keyword: Optional[str] = None
    project_type: Optional[str] = None
    project_name: Optional[str] = None
    responsible_sales: Optional[str] = None
    win_bid_status: Optional[str] = None
    partner_company: Optional[str] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    fields: List[str] = Field(default_factory=list)
    display_type: str = Field(default="table", max_length=50)


class AIAnalysisResponse(BaseModel):
    mode: str
    message: str
    model: Optional[AIModelConfigResponse] = None
    agent: dict = Field(default_factory=dict)
    filters: dict = Field(default_factory=dict)
    fields: List[str] = Field(default_factory=list)
    field_labels: dict = Field(default_factory=dict)
    display_type: str
    total_rows: int
    summary_text: Optional[str] = None
    answer: Optional[str] = None
    preview_rows: List[dict] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class AIReportAssistantRequest(BaseModel):
    model_id: Optional[int] = None
    question: str = Field(..., min_length=1, max_length=2000)
    keyword: Optional[str] = None
    project_type: Optional[str] = None
    project_name: Optional[str] = None
    responsible_sales: Optional[str] = None
    win_bid_status: Optional[str] = None
    partner_company: Optional[str] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    history: List[dict] = Field(default_factory=list)


class AIReportAssistantResponse(BaseModel):
    assistant_name: str
    model: Optional[AIModelConfigResponse] = None
    total_rows: int
    summary_text: str
    answer: str
    tips: List[str] = Field(default_factory=list)


# ============ 存储区域 ============
class StorageZoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    mode: str = 'webdav'  # 'local' | 'webdav'
    local_path: Optional[str] = None
    webdav_url: Optional[str] = None
    webdav_port: Optional[int] = None
    webdav_use_ssl: bool = True
    webdav_username: Optional[str] = None
    webdav_password: Optional[str] = None
    webdav_base_path: Optional[str] = None
    sub_path: Optional[str] = None
    description: Optional[str] = None
    sort_order: int = 0

class StorageZoneUpdate(BaseModel):
    name: Optional[str] = None
    mode: Optional[str] = None
    local_path: Optional[str] = None
    webdav_url: Optional[str] = None
    webdav_port: Optional[int] = None
    webdav_use_ssl: Optional[bool] = None
    webdav_username: Optional[str] = None
    webdav_password: Optional[str] = None
    webdav_base_path: Optional[str] = None
    sub_path: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

class StorageZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    mode: str
    local_path: Optional[str] = None
    webdav_url: Optional[str] = None
    webdav_port: Optional[int] = None
    webdav_use_ssl: bool = True
    webdav_username: Optional[str] = None
    # 出于安全考虑不返回密码明文；如需明文密码请用专门接口
    webdav_password_masked: Optional[str] = None
    webdav_base_path: Optional[str] = None
    sub_path: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator('mode', mode='before')
    @classmethod
    def parse_mode(cls, v):
        if hasattr(v, 'value'):
            return v.value
        return v

    @field_validator('webdav_use_ssl', mode='before')
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, int):
            return bool(v)
        return v

class StorageZoneListResponse(BaseModel):
    items: List[StorageZoneResponse]
    total: int


# ============ 通知中心 ============
class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    receiver_id: int
    type: NotificationType
    title: str
    content: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread_count: int


class NotificationUnreadResponse(BaseModel):
    unread_count: int


class NotificationSettingUpdate(BaseModel):
    """按事件类型更新三个推送开关"""
    in_app: Optional[bool] = None
    sms: Optional[bool] = None
    dingtalk: Optional[bool] = None


class NotificationSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    type: NotificationType
    in_app: bool
    sms: bool
    dingtalk: bool


class SystemAnnouncementRequest(BaseModel):
    """admin 群发系统公告"""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


class NotificationChannelConfig(BaseModel):
    """通知通道配置（in_skill_admin 配置)
    type='dingtalk_webhook' : { "webhook": "https://oapi.dingtalk.com/robot/send?access_token=..." , "sign_secret": "可选" }
    type='sms_aliyun'       : { "access_key_id": "...", "access_key_secret": "...", "sign_name": "...", "template_id": "..." }
    type='sms_tencent'      : { "secret_id": "...", "secret_key": "...", "app_id": "...", "template_id": "...", "sign_name": "..." }
    """
    name: str = Field(..., min_length=1, max_length=100)
    config: dict
    enabled: bool = True


class NotificationChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    name: str
    config: str  # JSON 字符串
    enabled: bool


class NotificationTemplateConfig(BaseModel):
    """通知文案模板(自定义编辑)"""
    title_template: str = Field(..., max_length=200)
    content_template: str = Field(..., max_length=4000)
    enabled: bool = True


class NotificationTemplateResponse(BaseModel):
    id: int
    type: str
    channel: str
    title_template: str
    content_template: str
    enabled: bool

    class Config:
        from_attributes = True


class NotificationGlobalConfigUpdate(BaseModel):
    """全局通知配置更新(单一记录)"""
    title_prefix: Optional[str] = Field(default=None, max_length=100)
    apply_in_app: Optional[bool] = None


class NotificationGlobalConfigResponse(BaseModel):
    title_prefix: str
    apply_in_app: bool
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True

class FormInstanceCreate(BaseModel):
    template_id: int
    data: dict

class FormInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    template_id: int
    data: dict = {}
    tender_folder: Optional[str] = None
    bid_folder: Optional[str] = None
    storage_zone_id: Optional[int] = None
    storage_zone: Optional['StorageZoneResponse'] = None
    approver_id: Optional[int] = None
    approver: Optional[UserResponse] = None
    approval_status: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    creator: Optional[UserResponse] = None
    template: Optional[FormTemplateResponse] = None

    @field_validator('data', mode='before')
    @classmethod
    def parse_data(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v or {}

    @field_validator('approval_status', mode='before')
    @classmethod
    def parse_status(cls, v):
        if hasattr(v, 'value'):
            return v.value
        return v

class FormInstanceListResponse(BaseModel):
    items: List[FormInstanceResponse]
    total: int


# ============ 通知中心 ============
class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    receiver_id: int
    type: NotificationType
    title: str
    content: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread_count: int


class NotificationUnreadResponse(BaseModel):
    unread_count: int


class NotificationSettingUpdate(BaseModel):
    """按事件类型更新三个推送开关"""
    in_app: Optional[bool] = None
    sms: Optional[bool] = None
    dingtalk: Optional[bool] = None


class NotificationSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    type: NotificationType
    in_app: bool
    sms: bool
    dingtalk: bool


class SystemAnnouncementRequest(BaseModel):
    """admin 群发系统公告"""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


class NotificationChannelConfig(BaseModel):
    """通知通道配置（admin 配置)
    type='dingtalk_webhook' : { 'webhook': 'https://oapi.dingtalk.com/robot/send?access_token=...' , 'sign_secret': '可选' }
    type='sms_aliyun'       : { 'access_key_id': '...', 'access_key_secret': '...', 'sign_name': '...', 'template_id': '...' }
    type='sms_tencent'      : { 'secret_id': '...', 'secret_key': '...', 'app_id': '...', 'template_id': '...', 'sign_name': '...' }
    """
    name: str = Field(..., min_length=1, max_length=100)
    config: dict
    enabled: bool = True


class NotificationChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    name: str
    config: str  # JSON 字符串
    enabled: bool
