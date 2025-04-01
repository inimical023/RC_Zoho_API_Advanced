from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models.database import get_db
from models.user import User
from models.call_data import CallRecord, Extension, LeadOwner, ZohoLead
from services.ringcentral_service import RingCentralService
from services.zoho_service import ZohoService
from api.auth import get_current_active_user, get_current_admin_user

# Define router
router = APIRouter()

# Pydantic models
class DateRange(BaseModel):
    start_date: datetime
    end_date: datetime


class CallRecordOut(BaseModel):
    id: int
    rc_call_id: str
    extension_id: str
    call_type: str
    direction: str
    caller_number: str
    caller_name: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    recording_id: Optional[str] = None
    recording_url: Optional[str] = None
    processed: bool
    processing_time: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class ExtensionOut(BaseModel):
    id: int
    extension_id: str
    name: str
    extension_number: Optional[str] = None
    type: Optional[str] = None
    enabled: bool

    class Config:
        orm_mode = True


class LeadOwnerOut(BaseModel):
    id: int
    zoho_id: str
    name: str
    email: str
    role: Optional[str] = None
    is_active: bool

    class Config:
        orm_mode = True


class ProcessResult(BaseModel):
    status: str
    message: str
    stats: Dict[str, Any]


# API endpoints
@router.get("/extensions", response_model=List[ExtensionOut])
async def get_extensions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all RingCentral extensions."""
    extensions = db.query(Extension).all()
    return extensions


@router.post("/extensions/sync", response_model=ProcessResult)
async def sync_extensions(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Sync RingCentral extensions with database."""
    try:
        rc_service = RingCentralService(db)
        
        # Run in background task to avoid request timeout
        def sync_task():
            try:
                created, updated, disabled = rc_service.sync_extensions()
                return {
                    "created": created,
                    "updated": updated,
                    "disabled": disabled,
                    "total": created + updated + disabled
                }
            except Exception as e:
                return {"error": str(e)}
        
        background_tasks.add_task(sync_task)
        
        return {
            "status": "success",
            "message": "Extensions sync started in background",
            "stats": {}
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing extensions: {str(e)}"
        )


@router.get("/lead-owners", response_model=List[LeadOwnerOut])
async def get_lead_owners(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all Zoho lead owners."""
    lead_owners = db.query(LeadOwner).all()
    return lead_owners


@router.post("/lead-owners/sync", response_model=ProcessResult)
async def sync_lead_owners(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Sync Zoho users as lead owners."""
    try:
        zoho_service = ZohoService(db)
        
        # Run in background task to avoid request timeout
        def sync_task():
            try:
                created, updated, deactivated = zoho_service.sync_users()
                return {
                    "created": created,
                    "updated": updated,
                    "deactivated": deactivated,
                    "total": created + updated + deactivated
                }
            except Exception as e:
                return {"error": str(e)}
        
        background_tasks.add_task(sync_task)
        
        return {
            "status": "success",
            "message": "Lead owners sync started in background",
            "stats": {}
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing lead owners: {str(e)}"
        )


@router.get("/recent", response_model=List[CallRecordOut])
async def get_recent_calls(
    limit: int = Query(50, gt=0, le=1000),
    offset: int = Query(0, ge=0),
    call_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get recent calls with optional filtering."""
    query = db.query(CallRecord)
    
    if call_type:
        query = query.filter(CallRecord.call_type == call_type)
        
    calls = query.order_by(CallRecord.start_time.desc()).offset(offset).limit(limit).all()
    return calls


@router.post("/fetch", response_model=ProcessResult)
async def fetch_calls(
    date_range: DateRange,
    background_tasks: BackgroundTasks,
    call_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Fetch calls from RingCentral within a date range."""
    try:
        rc_service = RingCentralService(db)
        
        # Check if the date range is valid
        if date_range.end_date <= date_range.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date must be after start date"
            )
            
        # Limit to max 30 days to prevent overloading
        if (date_range.end_date - date_range.start_date).days > 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date range cannot exceed 30 days"
            )
        
        # Run in background task to avoid request timeout
        def fetch_task():
            try:
                return rc_service.process_call_logs(date_range.start_date, date_range.end_date)
            except Exception as e:
                return {"error": str(e)}
        
        background_tasks.add_task(fetch_task)
        
        return {
            "status": "success",
            "message": f"Fetching calls from {date_range.start_date} to {date_range.end_date} started in background",
            "stats": {}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching calls: {str(e)}"
        )


@router.post("/process", response_model=ProcessResult)
async def process_calls(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Process unprocessed calls and create leads in Zoho CRM."""
    try:
        zoho_service = ZohoService(db)
        
        # Run in background task to avoid request timeout
        def process_task():
            try:
                return zoho_service.process_unprocessed_calls()
            except Exception as e:
                return {"error": str(e)}
        
        background_tasks.add_task(process_task)
        
        return {
            "status": "success",
            "message": "Call processing started in background",
            "stats": {}
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing calls: {str(e)}"
        )


@router.get("/stats")
async def get_stats(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get call statistics for the specified number of days."""
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get call counts by type
        accepted_count = db.query(CallRecord).filter(
            CallRecord.call_type == "Accepted",
            CallRecord.start_time >= start_date,
            CallRecord.start_time <= end_date
        ).count()
        
        missed_count = db.query(CallRecord).filter(
            CallRecord.call_type == "Missed",
            CallRecord.start_time >= start_date,
            CallRecord.start_time <= end_date
        ).count()
        
        # Get processed vs unprocessed counts
        processed_count = db.query(CallRecord).filter(
            CallRecord.processed == True,
            CallRecord.start_time >= start_date,
            CallRecord.start_time <= end_date
        ).count()
        
        unprocessed_count = db.query(CallRecord).filter(
            CallRecord.processed == False,
            CallRecord.start_time >= start_date,
            CallRecord.start_time <= end_date
        ).count()
        
        # Get leads created
        leads_created = db.query(ZohoLead).filter(
            ZohoLead.created_at >= start_date,
            ZohoLead.created_at <= end_date
        ).count()
        
        # Get call recordings attached
        recordings_count = db.query(ZohoLead).filter(
            ZohoLead.recording_attached == True,
            ZohoLead.created_at >= start_date,
            ZohoLead.created_at <= end_date
        ).count()
        
        return {
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "days": days
            },
            "calls": {
                "total": accepted_count + missed_count,
                "accepted": accepted_count,
                "missed": missed_count,
                "processed": processed_count,
                "unprocessed": unprocessed_count
            },
            "leads": {
                "created": leads_created,
                "with_recordings": recordings_count
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting stats: {str(e)}"
        ) 