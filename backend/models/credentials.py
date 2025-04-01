from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from .database import Base

class ApiCredential(Base):
    __tablename__ = "api_credentials"

    id = Column(Integer, primary_key=True, index=True)
    service = Column(String, index=True)  # "ringcentral" or "zoho"
    name = Column(String, index=True)  # credential name like "client_id", "refresh_token", etc.
    encrypted_value = Column(Text)
    encrypted_key_id = Column(String)  # Reference to the encryption key used
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    class Config:
        orm_mode = True 