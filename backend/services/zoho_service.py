import os
import logging
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from sqlalchemy.orm import Session

from models.credentials import ApiCredential
from models.call_data import CallRecord, ZohoLead, LeadOwner
from utils.security import decrypt_value

# Set up logging
logger = logging.getLogger(__name__)

class ZohoService:
    """Service for interacting with the Zoho CRM API."""
    
    def __init__(self, db: Session):
        self.db = db
        self.base_url = "https://www.zohoapis.com/crm/v7"
        self.access_token = None
        self.token_expiry = None
        self.credentials = self._get_credentials()
        
    def _get_credentials(self) -> Dict[str, str]:
        """Get credentials from database."""
        credentials = {}
        for name in ["client_id", "client_secret", "refresh_token"]:
            cred = self.db.query(ApiCredential).filter(
                ApiCredential.service == "zoho",
                ApiCredential.name == name,
                ApiCredential.is_active == True
            ).first()
            
            if cred:
                credentials[name] = decrypt_value(cred.encrypted_value)
            else:
                # Fallback to environment variables
                env_var = f"ZOHO_{name.upper()}"
                credentials[name] = os.getenv(env_var, "")
                
        if not all([credentials.get("client_id"), credentials.get("client_secret"), credentials.get("refresh_token")]):
            logger.error("Missing Zoho credentials")
            raise ValueError("Missing Zoho credentials")
            
        return credentials
    
    def _get_access_token(self) -> bool:
        """Get a new access token using refresh token."""
        if self.access_token and self.token_expiry and self.token_expiry > datetime.now():
            return True  # Token still valid
            
        url = "https://accounts.zoho.com/oauth/v2/token"
        data = {
            "refresh_token": self.credentials["refresh_token"],
            "client_id": self.credentials["client_id"],
            "client_secret": self.credentials["client_secret"],
            "grant_type": "refresh_token"
        }
        
        max_retries = 3
        backoff_factor = 2
        delay = 1
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, data=data)
                response.raise_for_status()
                token_data = response.json()
                self.access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)  # 5 minutes buffer
                logger.info(f"Successfully obtained Zoho access token. Expires in {expires_in} seconds")
                return True
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error refreshing Zoho token (attempt {attempt+1}/{max_retries}): {str(e)}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response: {e.response.text}")
                    
                # Exponential backoff
                time.sleep(delay)
                delay *= backoff_factor
        
        logger.error("Failed to refresh Zoho token after multiple attempts")
        self.access_token = None
        self.token_expiry = None
        return False
    
    def _ensure_token(self):
        """Ensure we have a valid access token."""
        if not self._get_access_token():
            raise ValueError("Failed to get Zoho access token")
    
    def get_users(self) -> List[Dict[str, Any]]:
        """Get Zoho CRM users."""
        self._ensure_token()
        
        users = []
        page = 1
        per_page = 200
        
        while True:
            url = f"{self.base_url}/users"
            params = {
                "page": page,
                "per_page": per_page
            }
            
            headers = {
                "Authorization": f"Zoho-oauthtoken {self.access_token}",
                "Content-Type": "application/json"
            }
            
            try:
                response = requests.get(url, headers=headers, params=params)
                
                # Handle token expiry
                if response.status_code == 401:  # Unauthorized - token expired
                    logger.warning("Zoho token expired, refreshing...")
                    self._get_access_token()
                    headers["Authorization"] = f"Zoho-oauthtoken {self.access_token}"
                    continue  # Retry with new token
                
                response.raise_for_status()
                data = response.json()
                
                if not data.get("users"):
                    break
                    
                users.extend(data["users"])
                
                # Check if there are more pages
                if len(data["users"]) < per_page:
                    break
                    
                page += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error getting Zoho users: {str(e)}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response: {e.response.text}")
                break
        
        return users
    
    def sync_users(self) -> Tuple[int, int, int]:
        """Sync Zoho users with database as lead owners."""
        users = self.get_users()
        if not users:
            return 0, 0, 0
            
        # Counters for stats
        created = 0
        updated = 0
        deactivated = 0
        
        # Get current lead owners from DB
        current_owners = {
            owner.zoho_id: owner 
            for owner in self.db.query(LeadOwner).all()
        }
        
        # Set of processed users to identify stale records
        processed_ids = set()
        
        # Process users
        for user in users:
            user_id = user.get("id")
            if not user_id:
                continue
                
            processed_ids.add(user_id)
            
            name = user.get("full_name", "")
            email = user.get("email", "")
            role = user.get("role", {}).get("name", "")
            is_active = user.get("status") == "active"
            
            if user_id in current_owners:
                # Update existing lead owner
                owner = current_owners[user_id]
                owner.name = name
                owner.email = email
                owner.role = role
                owner.is_active = is_active
                updated += 1
            else:
                # Create new lead owner
                owner = LeadOwner(
                    zoho_id=user_id,
                    name=name,
                    email=email,
                    role=role,
                    is_active=is_active
                )
                self.db.add(owner)
                created += 1
        
        # Deactivate lead owners that no longer exist
        for owner_id, owner in current_owners.items():
            if owner_id not in processed_ids and owner.is_active:
                owner.is_active = False
                deactivated += 1
        
        # Commit changes
        self.db.commit()
        
        return created, updated, deactivated
    
    def search_leads(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Search for existing leads by phone number."""
        self._ensure_token()
        
        url = f"{self.base_url}/Leads/search"
        params = {
            "criteria": f"Phone:equals:{phone_number}"
        }
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            
            # Handle token expiry
            if response.status_code == 401:  # Unauthorized - token expired
                logger.warning("Zoho token expired, refreshing...")
                self._get_access_token()
                headers["Authorization"] = f"Zoho-oauthtoken {self.access_token}"
                response = requests.get(url, headers=headers, params=params)
            
            response.raise_for_status()
            data = response.json()
            
            if data and "data" in data and data["data"]:
                return data["data"][0]
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching leads: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return None
    
    def create_lead(self, call_record: CallRecord, lead_owner: LeadOwner) -> Optional[Dict[str, Any]]:
        """Create a new lead in Zoho CRM."""
        self._ensure_token()
        
        # Determine lead source from extension
        lead_source = "Unknown"
        extension_id = call_record.extension_id
        
        # Extract call details
        caller_number = call_record.caller_number
        caller_name = call_record.caller_name or "Unknown Caller"
        
        # Format call time
        call_time = call_record.start_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine lead status based on call type
        if call_record.call_type == "Missed":
            lead_status = "Missed Call"
        else:
            lead_status = "Accepted Call"
        
        # Split name if available
        first_name = "Unknown"
        last_name = "Caller"
        if caller_name and ' ' in caller_name:
            name_parts = caller_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1]
        elif caller_name:
            first_name = caller_name
        
        # Prepare lead data
        lead_data = {
            "data": [
                {
                    "First_Name": first_name,
                    "Last_Name": last_name,
                    "Phone": caller_number,
                    "Lead_Source": lead_source,
                    "Lead_Status": lead_status,
                    "Description": f"Lead created from {call_record.call_type.lower()} call received on {call_time}",
                    "Owner": {
                        "id": lead_owner.zoho_id
                    }
                }
            ]
        }
        
        url = f"{self.base_url}/Leads"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, headers=headers, json=lead_data)
            
            # Handle token expiry
            if response.status_code == 401:  # Unauthorized - token expired
                logger.warning("Zoho token expired, refreshing...")
                self._get_access_token()
                headers["Authorization"] = f"Zoho-oauthtoken {self.access_token}"
                response = requests.post(url, headers=headers, json=lead_data)
            
            response.raise_for_status()
            data = response.json()
            
            if data and "data" in data and data["data"]:
                # Extract lead ID from response
                lead_details = None
                lead_id = None
                
                if "details" in data["data"][0]:
                    lead_details = data["data"][0]["details"]
                    lead_id = lead_details.get("id")
                elif "id" in data["data"][0]:
                    lead_id = data["data"][0]["id"]
                
                if lead_id:
                    logger.info(f"Successfully created lead {lead_id}")
                    
                    # Create note with call details
                    self.add_note_to_lead(lead_id, self._format_call_note(call_record))
                    
                    return {"id": lead_id, "details": lead_details}
            
            logger.error(f"Failed to create lead - unexpected response: {data}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating lead: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return None
    
    def update_lead(self, zoho_lead_id: str, call_record: CallRecord, status: Optional[str] = None) -> bool:
        """Update a lead in Zoho CRM."""
        self._ensure_token()
        
        # Determine lead status based on call type if not provided
        if not status:
            if call_record.call_type == "Missed":
                status = "Missed Call"
            else:
                status = "Accepted Call"
        
        # Prepare lead data
        lead_data = {
            "data": [
                {
                    "id": zoho_lead_id,
                    "Lead_Status": status
                }
            ]
        }
        
        url = f"{self.base_url}/Leads"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.put(url, headers=headers, json=lead_data)
            
            # Handle token expiry
            if response.status_code == 401:  # Unauthorized - token expired
                logger.warning("Zoho token expired, refreshing...")
                self._get_access_token()
                headers["Authorization"] = f"Zoho-oauthtoken {self.access_token}"
                response = requests.put(url, headers=headers, json=lead_data)
            
            response.raise_for_status()
            
            # Add note with call details
            self.add_note_to_lead(zoho_lead_id, self._format_call_note(call_record))
            
            logger.info(f"Successfully updated lead {zoho_lead_id}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating lead: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return False
    
    def add_note_to_lead(self, zoho_lead_id: str, note_content: str) -> bool:
        """Add a note to a lead in Zoho CRM."""
        self._ensure_token()
        
        note_data = {
            "data": [
                {
                    "Note_Title": "Call Information",
                    "Note_Content": note_content
                }
            ]
        }
        
        url = f"{self.base_url}/Leads/{zoho_lead_id}/Notes"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, headers=headers, json=note_data)
            
            # Handle token expiry
            if response.status_code == 401:  # Unauthorized - token expired
                logger.warning("Zoho token expired, refreshing...")
                self._get_access_token()
                headers["Authorization"] = f"Zoho-oauthtoken {self.access_token}"
                response = requests.post(url, headers=headers, json=note_data)
            
            response.raise_for_status()
            
            logger.info(f"Successfully added note to lead {zoho_lead_id}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error adding note to lead: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            
            # Try with simplified note if the note is too long
            if len(note_content) > 1000 and "413" in str(e):
                logger.info("Note too long, trying with simplified content")
                simplified_note = note_content[:997] + "..."
                return self.add_note_to_lead(zoho_lead_id, simplified_note)
                
            return False
    
    def _format_call_note(self, call_record: CallRecord) -> str:
        """Format a note with call details."""
        call_time = call_record.start_time.strftime("%Y-%m-%d %H:%M:%S")
        call_type = call_record.call_type
        duration = f"{call_record.duration} seconds" if call_record.duration else "unknown duration"
        
        # Create note content
        note_lines = [
            f"{call_type} call received on {call_time}",
            "---",
            f"Call time: {call_time}",
            f"Call direction: {call_record.direction}",
            f"Call duration: {duration}",
            f"Caller number: {call_record.caller_number}",
            f"Caller name: {call_record.caller_name or 'Unknown'}",
            f"Extension ID: {call_record.extension_id}",
            f"Recording available: {'Yes' if call_record.recording_id else 'No'}",
            f"Call ID: {call_record.rc_call_id}"
        ]
        
        return "\n".join(note_lines)
    
    def attach_recording_to_lead(self, zoho_lead_id: str, recording_content: bytes, filename: str, content_type: str) -> bool:
        """Attach a recording to a lead in Zoho CRM."""
        self._ensure_token()
        
        url = f"{self.base_url}/Leads/{zoho_lead_id}/Attachments"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}"
        }
        
        files = {
            'file': (filename, recording_content, content_type)
        }
        
        try:
            response = requests.post(url, headers=headers, files=files)
            
            # Handle token expiry
            if response.status_code == 401:  # Unauthorized - token expired
                logger.warning("Zoho token expired, refreshing...")
                self._get_access_token()
                headers["Authorization"] = f"Zoho-oauthtoken {self.access_token}"
                response = requests.post(url, headers=headers, files=files)
            
            response.raise_for_status()
            
            logger.info(f"Successfully attached recording {filename} to lead {zoho_lead_id}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error attaching recording to lead: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return False
    
    def process_unprocessed_calls(self) -> Dict[str, int]:
        """Process unprocessed calls and sync with Zoho CRM."""
        # Get active lead owners for round-robin assignment
        lead_owners = self.db.query(LeadOwner).filter(LeadOwner.is_active == True).all()
        if not lead_owners:
            logger.warning("No active lead owners found")
            return {"total": 0, "processed": 0, "created": 0, "updated": 0, "failed": 0}
            
        # Get unprocessed calls
        unprocessed_calls = self.db.query(CallRecord).filter(CallRecord.processed == False).all()
        if not unprocessed_calls:
            logger.info("No unprocessed calls found")
            return {"total": 0, "processed": 0, "created": 0, "updated": 0, "failed": 0}
            
        # Counters for stats
        stats = {
            "total": len(unprocessed_calls),
            "processed": 0,
            "created": 0,
            "updated": 0,
            "failed": 0
        }
        
        # Get last lead owner for round-robin assignment
        lead_owner_index = 0
        last_assignment = self.db.query(LeadOwner).filter(LeadOwner.last_assignment != None).order_by(LeadOwner.last_assignment.desc()).first()
        if last_assignment:
            for i, owner in enumerate(lead_owners):
                if owner.zoho_id == last_assignment.zoho_id:
                    lead_owner_index = (i + 1) % len(lead_owners)
                    break
        
        # Process each call
        for call in unprocessed_calls:
            try:
                # Check if already processed (double-check)
                if call.processed:
                    stats["processed"] += 1
                    continue
                    
                # Skip if no phone number
                if not call.caller_number:
                    logger.warning(f"No phone number for call {call.rc_call_id}, skipping")
                    call.processed = True
                    self.db.commit()
                    stats["processed"] += 1
                    continue
                
                # Search for existing lead
                existing_lead = self.search_leads(call.caller_number)
                
                if existing_lead:
                    # Update existing lead
                    lead_id = existing_lead["id"]
                    success = self.update_lead(lead_id, call)
                    
                    if success:
                        # Create or update ZohoLead record
                        zoho_lead = self.db.query(ZohoLead).filter(ZohoLead.zoho_lead_id == lead_id).first()
                        
                        if not zoho_lead:
                            # Get lead owner
                            owner_id = None
                            lead_owner_zoho_id = existing_lead.get("Owner", {}).get("id")
                            if lead_owner_zoho_id:
                                owner = self.db.query(LeadOwner).filter(LeadOwner.zoho_id == lead_owner_zoho_id).first()
                                if owner:
                                    owner_id = owner.id
                            
                            # Create new ZohoLead record
                            zoho_lead = ZohoLead(
                                zoho_lead_id=lead_id,
                                call_record_id=call.id,
                                lead_owner_id=owner_id,
                                phone_number=call.caller_number,
                                first_name=existing_lead.get("First_Name"),
                                last_name=existing_lead.get("Last_Name"),
                                email=existing_lead.get("Email"),
                                lead_source=existing_lead.get("Lead_Source"),
                                lead_status=existing_lead.get("Lead_Status"),
                                note_added=True,
                                synced_at=datetime.now()
                            )
                            self.db.add(zoho_lead)
                        else:
                            # Update existing ZohoLead record
                            zoho_lead.call_record_id = call.id
                            zoho_lead.note_added = True
                            zoho_lead.synced_at = datetime.now()
                        
                        # Handle recording if available
                        if call.recording_id and call.call_type == "Accepted":
                            self._attach_recording(call, lead_id, zoho_lead)
                        
                        # Mark call as processed
                        call.processed = True
                        call.processing_time = datetime.now()
                        self.db.commit()
                        
                        stats["updated"] += 1
                        stats["processed"] += 1
                    else:
                        stats["failed"] += 1
                        
                else:
                    # Create new lead with round-robin assignment
                    lead_owner = lead_owners[lead_owner_index]
                    lead_owner_index = (lead_owner_index + 1) % len(lead_owners)
                    
                    # Update lead owner's last assignment time for round-robin
                    lead_owner.last_assignment = datetime.now()
                    
                    # Create lead
                    lead_result = self.create_lead(call, lead_owner)
                    
                    if lead_result and "id" in lead_result:
                        lead_id = lead_result["id"]
                        
                        # Create ZohoLead record
                        zoho_lead = ZohoLead(
                            zoho_lead_id=lead_id,
                            call_record_id=call.id,
                            lead_owner_id=lead_owner.id,
                            phone_number=call.caller_number,
                            first_name="Unknown" if not call.caller_name else call.caller_name.split(" ")[0],
                            last_name="Caller" if not call.caller_name or " " not in call.caller_name else " ".join(call.caller_name.split(" ")[1:]),
                            lead_source="Unknown",
                            lead_status="Accepted Call" if call.call_type == "Accepted" else "Missed Call",
                            note_added=True,
                            synced_at=datetime.now()
                        )
                        self.db.add(zoho_lead)
                        
                        # Handle recording if available
                        if call.recording_id and call.call_type == "Accepted":
                            self._attach_recording(call, lead_id, zoho_lead)
                        
                        # Mark call as processed
                        call.processed = True
                        call.processing_time = datetime.now()
                        self.db.commit()
                        
                        stats["created"] += 1
                        stats["processed"] += 1
                    else:
                        stats["failed"] += 1
                
            except Exception as e:
                logger.error(f"Error processing call {call.rc_call_id}: {str(e)}")
                stats["failed"] += 1
                continue
                
        return stats
    
    def _attach_recording(self, call: CallRecord, lead_id: str, zoho_lead: ZohoLead) -> bool:
        """Attach recording to a lead from a RingCentral service."""
        from services.ringcentral_service import RingCentralService
        
        try:
            rc_service = RingCentralService(self.db)
            
            # Get recording content
            recording_content, content_type = rc_service.get_recording_content(call.recording_id)
            
            if not recording_content or not content_type:
                logger.warning(f"Failed to get recording content for {call.recording_id}")
                return False
            
            # Determine file extension
            if content_type == "audio/mpeg":
                extension = "mp3"
            elif content_type == "audio/wav":
                extension = "wav"
            else:
                extension = content_type.split('/')[1] if '/' in content_type else "bin"
            
            # Generate filename with timestamp
            timestamp = call.start_time.strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_recording_{call.recording_id}.{extension}"
            
            # Attach recording to lead
            success = self.attach_recording_to_lead(lead_id, recording_content, filename, content_type)
            
            if success:
                zoho_lead.recording_attached = True
                self.db.commit()
                logger.info(f"Successfully attached recording to lead {lead_id}")
                return True
            else:
                logger.warning(f"Failed to attach recording to lead {lead_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error attaching recording: {str(e)}")
            return False 