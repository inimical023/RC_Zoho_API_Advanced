from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Extension(Base):
    __tablename__ = "extensions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    extension_id = Column(String, unique=True, index=True)
    name = Column(String)
    extension_number = Column(String, nullable=True)
    type = Column(String, nullable=True)  # "User", "Department", etc.
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class LeadOwner(Base):
    __tablename__ = "lead_owners"

    id = Column(Integer, primary_key=True, autoincrement=True)
    zoho_id = Column(String, unique=True, index=True)
    name = Column(String)
    email = Column(String)
    role = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    last_assignment = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CallRecord(Base):
    __tablename__ = "call_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rc_call_id = Column(String, unique=True, index=True)
    extension_id = Column(String, index=True)
    call_type = Column(String, index=True)  # "Missed", "Accepted", etc.
    direction = Column(String)  # "Inbound", "Outbound"
    caller_number = Column(String, index=True)
    caller_name = Column(String, nullable=True)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration = Column(Integer, nullable=True)  # Duration in seconds
    recording_id = Column(String, nullable=True)
    recording_url = Column(String, nullable=True)
    raw_data = Column(JSON, nullable=True)  # Store the original call data
    processed = Column(Boolean, default=False)
    processing_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ZohoLead(Base):
    __tablename__ = "zoho_leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    zoho_lead_id = Column(String, unique=True, index=True)
    call_record_id = Column(Integer, ForeignKey("call_records.id"), nullable=True)
    lead_owner_id = Column(Integer, ForeignKey("lead_owners.id"), nullable=True)
    phone_number = Column(String, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    lead_source = Column(String, nullable=True)
    lead_status = Column(String, nullable=True)
    recording_attached = Column(Boolean, default=False)
    note_added = Column(Boolean, default=False)
    synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    call_record = relationship("CallRecord", backref="zoho_leads")
    lead_owner = relationship("LeadOwner", backref="zoho_leads") 