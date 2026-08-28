import os
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Text, event
from sqlalchemy.orm import Mapped, Session as SASession, mapped_column, relationship
from .database import Base


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default='operador')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GlobalSetting(Base):
    __tablename__ = 'global_settings'
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RolePolicy(Base):
    __tablename__ = 'role_policies'
    role: Mapped[str] = mapped_column(String(30), primary_key=True)
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserPermission(Base):
    __tablename__ = 'user_permissions'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Company(Base):
    __tablename__ = 'companies'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    decision_tree: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    stores: Mapped[list['Store']] = relationship(back_populates='company', cascade='all, delete-orphan')
    files: Mapped[list['CompanyFile']] = relationship(back_populates='company', cascade='all, delete-orphan')
    support_contacts: Mapped[list['SupportContact']] = relationship(back_populates='company', cascade='all, delete-orphan')


class UserCompanyAccess(Base):
    __tablename__ = 'user_company_access'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Store(Base):
    __tablename__ = 'stores'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(160))
    whatsapp_number: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    whatsapp_phone_number_id: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True, index=True)
    company: Mapped[Company] = relationship(back_populates='stores')


class Contact(Base):
    __tablename__ = 'contacts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default='mobile')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WhatsAppTestRecipient(Base):
    __tablename__ = 'whatsapp_test_recipients'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    added_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = 'conversations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey('companies.id'), nullable=True)
    wa_user_id: Mapped[str] = mapped_column(String(80), index=True)
    state: Mapped[str] = mapped_column(String(120), default='nodo_raiz')
    status: Mapped[str] = mapped_column(String(30), default='open')
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConversationChannel(Base):
    __tablename__ = 'conversation_channels'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey('conversations.id', ondelete='CASCADE'), unique=True, index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey('companies.id'), nullable=True, index=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey('stores.id'), nullable=True, index=True)
    phone_number_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = 'messages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey('conversations.id'), nullable=True)
    direction: Mapped[str] = mapped_column(String(20))
    sender: Mapped[str | None] = mapped_column(String(80), nullable=True)
    body: Mapped[str] = mapped_column(Text, default='')
    provider_message_id: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True, index=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class HelpRequest(Base):
    __tablename__ = 'help_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey('companies.id'), nullable=True, index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey('conversations.id'), nullable=True, index=True)
    wa_user_id: Mapped[str] = mapped_column(String(80), index=True)
    body: Mapped[str] = mapped_column(Text, default='')
    reason: Mapped[str] = mapped_column(String(120), default='help_keyword')
    status: Mapped[str] = mapped_column(String(30), default='new', index=True)
    is_known_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    is_group: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SupportTicket(Base):
    __tablename__ = 'support_tickets'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey('stores.id', ondelete='SET NULL'), nullable=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey('conversations.id', ondelete='CASCADE'), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default='open', index=True)
    subject: Mapped[str] = mapped_column(String(240), default='Incidencia')
    description: Mapped[str] = mapped_column(Text, default='')
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    closed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    close_result: Mapped[str | None] = mapped_column(String(30), nullable=True)


class SupportEmailRecipient(Base):
    __tablename__ = 'support_email_recipients'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(160), default='Soporte')
    email: Mapped[str] = mapped_column(String(254), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompanyFile(Base):
    __tablename__ = 'company_files'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120), default='application/octet-stream')
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    company: Mapped[Company] = relationship(back_populates='files')


class SupportContact(Base):
    __tablename__ = 'support_contacts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey('contacts.id'), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40), index=True)
    role: Mapped[str] = mapped_column(String(20), default='primary', index=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    escalation_after_minutes: Mapped[int] = mapped_column(Integer, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company: Mapped[Company] = relationship(back_populates='support_contacts')


class AppNotification(Base):
    __tablename__ = 'app_notifications'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audience: Mapped[str] = mapped_column(String(20), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default='')
    event_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action: Mapped[str] = mapped_column(String(120))
    entity: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


@event.listens_for(SASession, 'before_flush')
def _suppress_primary_admin_audit(session, flush_context, instances):
    primary_admin = (os.getenv('BOOTSTRAP_ADMIN_USERNAME') or '').strip()
    if not primary_admin:
        return
    for obj in list(session.new):
        if isinstance(obj, AuditLog) and obj.username == primary_admin:
            session.expunge(obj)
