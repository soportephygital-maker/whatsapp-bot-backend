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

class DecisionTreeUpdate(BaseModel):
    structure: dict

class OutboundMessage(BaseModel):
    to: str
    text: str
