from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=8)
    role: str = 'operador'


class CompanyCreate(BaseModel):
    company_key: str
    name: str
    stores: list[str] = []
    whatsapp_numbers: list[str] = []
    phone_number_ids: list[str] = []


class CompanyUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class DecisionTreeUpdate(BaseModel):
    structure: dict


class SupportContactCreate(BaseModel):
    name: str
    phone: str
    role: str = Field(default='primary', pattern='^(primary|secondary)$')
    priority: int = Field(default=1, ge=1, le=20)
    escalation_after_minutes: int = Field(default=15, ge=1, le=1440)


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
