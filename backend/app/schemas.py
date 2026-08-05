from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import date, datetime
from app.models import UserRole, CooperationMode, FeeMode, IsSM, WinBidStatus, ApprovalStatus, ApprovalAction, StorageMode, ProjectType

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

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    username: Optional[str] = None
    role: Optional[UserRole] = None
    parent_id: Optional[int] = None
    is_active: Optional[bool] = None

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
    created_at: datetime

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

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

class ProjectCreate(ProjectBase):
    @field_validator('tender_time', 'bid_time', mode='before')
    @classmethod
    def _empty_date_to_none(cls, v):
        """前端表单字段为空字符串时转为 None，避免 Pydantic date 解析失败"""
        if v in ('', None):
            return None
        return v

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
    project_overview: Optional[str] = None
    tender_file: Optional[str]
    bid_file: Optional[str]
    tender_folder: Optional[str] = None
    bid_folder: Optional[str] = None
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
    # 已有项目目录直接回传（用数据库存的 tender_folder/bid_folder）
    existing_tender_folder: Optional[str] = None
    existing_bid_folder: Optional[str] = None


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
    page: int
    page_size: int
