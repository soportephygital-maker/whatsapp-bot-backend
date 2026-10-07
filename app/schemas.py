from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=8)
    role: str = Field(default='operador', pattern='^(gerente|operador|lector)$')


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern='^(gerente|operador|lector)$')
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class UIAuditEvent(BaseModel):
    action: str = Field(min_length=1, max_length=80)
    element_id: str | None = Field(default=None, max_length=120)
    label: str | None = Field(default=None, max_length=160)
    path: str | None = Field(default=None, max_length=300)


class ConversationReply(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class TestRecipientCreate(BaseModel):
    phone: str = Field(min_length=6, max_length=40)
    name: str | None = Field(default=None, max_length=160)


class CompanyCreate(BaseModel):
    company_key: str
    name: str
    stores: list[str] = []
    whatsapp_numbers: list[str] = []
    phone_number_ids: list[str] = []


class CompanyUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class StoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class StoreUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class CompanyIdentificationUpdate(BaseModel):
    aliases: list[str] = []
    keywords: list[str] = []
    tags: list[str] = []


class DecisionTreeUpdate(BaseModel):
    structure: dict


class SupportContactCreate(BaseModel):
    contact_id: int
    role: str = Field(default='primary', pattern='^(primary|secondary)$')
    priority: int = Field(default=1, ge=1, le=20)
    escalation_after_minutes: int = Field(default=5, ge=1, le=1440)


class OutboundMessage(BaseModel):
    to: str
    text: str


class ContactItem(BaseModel):
    phone: str
    name: str | None = None


class ContactSync(BaseModel):
    contacts: list[ContactItem]


class HelpRequestStatus(BaseModel):
    status: str = Field(pattern='^(new|reviewing|resolved|ignored)$')
