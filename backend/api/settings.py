from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, SecretStr, validator
from sqlalchemy import func

from models.database import get_db
from models.user import User
from models.credentials import ApiCredential
from utils.security import encrypt_value
from api.auth import get_current_admin_user

# Define router
router = APIRouter()

# Pydantic models
class CredentialBase(BaseModel):
    service: str
    name: str
    value: SecretStr

    @validator('service')
    def validate_service(cls, v):
        if v not in ["ringcentral", "zoho"]:
            raise ValueError('Service must be either "ringcentral" or "zoho"')
        return v


class CredentialCreate(CredentialBase):
    pass


class CredentialUpdate(BaseModel):
    value: SecretStr


class CredentialOut(BaseModel):
    id: int
    service: str
    name: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        orm_mode = True


# API endpoints
@router.get("/credentials", response_model=List[CredentialOut])
async def get_credentials(
    service: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get all credentials (admin only)."""
    query = db.query(ApiCredential)
    
    if service:
        if service not in ["ringcentral", "zoho"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Service must be either "ringcentral" or "zoho"'
            )
        query = query.filter(ApiCredential.service == service)
    
    credentials = query.order_by(ApiCredential.service, ApiCredential.name).all()
    return credentials


@router.post("/credentials", response_model=CredentialOut, status_code=status.HTTP_201_CREATED)
async def create_credential(
    credential: CredentialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new credential (admin only)."""
    # Check if credential already exists
    existing = db.query(ApiCredential).filter(
        ApiCredential.service == credential.service,
        ApiCredential.name == credential.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Credential {credential.service}/{credential.name} already exists"
        )
    
    # Encrypt the value
    encrypted_value = encrypt_value(credential.value.get_secret_value())
    
    # Create new credential
    db_credential = ApiCredential(
        service=credential.service,
        name=credential.name,
        encrypted_value=encrypted_value,
        encrypted_key_id="default",  # In a more complex system, you'd use key rotation
        is_active=True
    )
    
    db.add(db_credential)
    db.commit()
    db.refresh(db_credential)
    
    return db_credential


@router.put("/credentials/{credential_id}", response_model=CredentialOut)
async def update_credential(
    credential_id: int,
    credential: CredentialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update a credential (admin only)."""
    # Get existing credential
    db_credential = db.query(ApiCredential).filter(ApiCredential.id == credential_id).first()
    
    if not db_credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential with ID {credential_id} not found"
        )
    
    # Encrypt the value
    encrypted_value = encrypt_value(credential.value.get_secret_value())
    
    # Update credential
    db_credential.encrypted_value = encrypted_value
    db_credential.encrypted_key_id = "default"  # In a more complex system, you'd use key rotation
    
    db.commit()
    db.refresh(db_credential)
    
    return db_credential


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a credential (admin only)."""
    # Get existing credential
    db_credential = db.query(ApiCredential).filter(ApiCredential.id == credential_id).first()
    
    if not db_credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential with ID {credential_id} not found"
        )
    
    # Delete credential
    db.delete(db_credential)
    db.commit()
    
    return None


@router.get("/system-info")
async def get_system_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get system information (admin only)."""
    # Count records in tables
    user_count = db.query(func.count(User.id)).scalar()
    extension_count = db.query(func.count("id")).select_from(db.query(ApiCredential).filter(ApiCredential.service == "ringcentral").subquery()).scalar()
    zoho_count = db.query(func.count("id")).select_from(db.query(ApiCredential).filter(ApiCredential.service == "zoho").subquery()).scalar()
    
    # Database info
    db_info = {
        "type": db.bind.dialect.name,
        "version": db.bind.dialect.driver,
    }
    
    # Return system info
    return {
        "database": db_info,
        "counts": {
            "users": user_count,
            "ringcentral_credentials": extension_count,
            "zoho_credentials": zoho_count
        },
        "current_user": {
            "id": current_user.id,
            "username": current_user.username,
            "is_admin": current_user.is_admin
        }
    } 