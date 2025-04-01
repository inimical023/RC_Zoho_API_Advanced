import os
import base64
import logging
import requests
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.credentials import ApiCredential
from models.call_data import Extension, CallRecord
from utils.security import decrypt_value

# Set up logging
logger = logging.getLogger(__name__)

class RingCentralService:
    """Service for interacting with the RingCentral API."""
    
    def __init__(self, db: Session):
        self.db = db
        self.base_url = "https://platform.ringcentral.com"
        self.access_token = None
        self.token_expiry = None
        self.credentials = self._get_credentials()
        
    def _get_credentials(self) -> Dict[str, str]:
        """Get credentials from database."""
        credentials = {}
        for name in ["jwt_token", "client_id", "client_secret", "account_id"]:
            cred = self.db.query(ApiCredential).filter(
                ApiCredential.service == "ringcentral",
                ApiCredential.name == name,
                ApiCredential.is_active == True
            ).first()
            
            if cred:
                credentials[name] = decrypt_value(cred.encrypted_value)
            else:
                # Fallback to environment variables
                env_var = f"RINGCENTRAL_{name.upper()}"
                credentials[name] = os.getenv(env_var, "")
                
        if not all([credentials.get("jwt_token"), credentials.get("client_id"), credentials.get("client_secret")]):
            logger.error("Missing RingCentral credentials")
            raise ValueError("Missing RingCentral credentials")
            
        if not credentials.get("account_id"):
            credentials["account_id"] = "~"  # Default account ID
            
        return credentials
    
    def _get_oauth_token(self) -> bool:
        """Exchange JWT token for OAuth access token."""
        if self.access_token and self.token_expiry and self.token_expiry > datetime.now():
            return True  # Token still valid
            
        url = f"{self.base_url}/restapi/oauth/token"
        auth_string = f"{self.credentials['client_id']}:{self.credentials['client_secret']}"
        auth_bytes = auth_string.encode()
        base64_auth = base64.b64encode(auth_bytes).decode()
        
        headers = {
            'Authorization': f'Basic {base64_auth}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': self.credentials['jwt_token']
        }
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)  # Default to 1 hour
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)  # 5 minutes buffer
            logger.info("Successfully obtained RingCentral OAuth token")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting OAuth token: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            self.access_token = None
            self.token_expiry = None
            return False
    
    def get_extensions(self) -> List[Dict[str, Any]]:
        """Get all extensions from RingCentral."""
        if not self._get_oauth_token():
            logger.error("Failed to get OAuth token")
            return []
            
        extensions = []
        page = 1
        per_page = 100
        
        while True:
            url = f"{self.base_url}/restapi/v1.0/account/{self.credentials['account_id']}/extension"
            params = {
                'page': page,
                'perPage': per_page,
                'status': 'Enabled',
                'type': ['User', 'Department', 'Announcement', 'Voicemail']
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                records = data.get('records', [])
                extensions.extend(records)
                
                # Check if there are more pages
                if not records or page >= data.get('paging', {}).get('totalPages', 1):
                    break
                    
                page += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error getting extensions: {str(e)}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response: {e.response.text}")
                break
        
        return extensions
    
    def sync_extensions(self) -> Tuple[int, int, int]:
        """Sync extensions with database."""
        extensions = self.get_extensions()
        if not extensions:
            return 0, 0, 0
            
        # Counters for stats
        created = 0
        updated = 0
        disabled = 0
        
        # Get current extensions from DB
        current_extensions = {
            ext.extension_id: ext 
            for ext in self.db.query(Extension).all()
        }
        
        # Set of processed extensions to identify stale records
        processed_ids = set()
        
        # Process extensions
        for ext in extensions:
            ext_id = str(ext.get('id'))
            processed_ids.add(ext_id)
            
            # Skip if not call queue or department extension
            ext_type = ext.get('type')
            if ext_type not in ['Department', 'User']:
                continue
                
            name = ext.get('name', '')
            extension_number = ext.get('extensionNumber', '')
            
            if ext_id in current_extensions:
                # Update existing extension
                db_ext = current_extensions[ext_id]
                db_ext.name = name
                db_ext.extension_number = extension_number
                db_ext.type = ext_type
                db_ext.enabled = True
                updated += 1
            else:
                # Create new extension
                db_ext = Extension(
                    extension_id=ext_id,
                    name=name,
                    extension_number=extension_number,
                    type=ext_type,
                    enabled=True
                )
                self.db.add(db_ext)
                created += 1
        
        # Disable extensions that no longer exist
        for ext_id, db_ext in current_extensions.items():
            if ext_id not in processed_ids and db_ext.enabled:
                db_ext.enabled = False
                disabled += 1
        
        # Commit changes
        self.db.commit()
        
        return created, updated, disabled
    
    def get_call_logs(self, extension_id: str, start_date: datetime, end_date: datetime, call_direction: str = "Inbound", call_type: str = "Voice") -> List[Dict[str, Any]]:
        """Get call logs for an extension."""
        if not self._get_oauth_token():
            logger.error("Failed to get OAuth token")
            return []
            
        logs = []
        page = 1
        per_page = 250  # Maximum allowed by API
        
        # Format dates as ISO 8601
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        
        while True:
            url = f"{self.base_url}/restapi/v1.0/account/{self.credentials['account_id']}/extension/{extension_id}/call-log"
            params = {
                'page': page,
                'perPage': per_page,
                'dateFrom': start_str,
                'dateTo': end_str,
                'direction': call_direction,
                'type': call_type,
                'view': 'Detailed',
                'withRecording': 'true'
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            try:
                response = requests.get(url, headers=headers, params=params)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 10))
                    logger.warning(f"Rate limit exceeded. Waiting {retry_after} seconds.")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                records = data.get('records', [])
                logs.extend(records)
                
                # Check if there are more pages
                if not records or page >= data.get('paging', {}).get('totalPages', 1):
                    break
                    
                page += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error getting call logs: {str(e)}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response: {e.response.text}")
                break
        
        return logs
    
    def get_recording_content(self, recording_id: str) -> Tuple[Optional[bytes], Optional[str]]:
        """Get recording content for a call."""
        if not self._get_oauth_token():
            logger.error("Failed to get OAuth token")
            return None, None
            
        url = f"https://media.ringcentral.com/restapi/v1.0/account/{self.credentials['account_id']}/recording/{recording_id}/content"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, stream=True)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 10))
                    logger.warning(f"Rate limit exceeded. Waiting {retry_after} seconds.")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                
                content_type = response.headers.get('Content-Type', 'application/octet-stream')
                return response.content, content_type
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error getting recording (attempt {attempt+1}/{max_retries}): {str(e)}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response: {e.response.text}")
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
        
        return None, None
    
    def qualify_call(self, call: Dict[str, Any]) -> Tuple[bool, str]:
        """Determine if a call should be qualified as 'accepted' or 'missed'."""
        if 'legs' not in call or not call['legs']:
            return False, "No call legs found"
            
        # Check call direction
        if call.get('direction') != 'Inbound':
            return False, "Not an inbound call"
            
        # Get call result from top level
        result = call.get('result', '').lower()
        
        # Check legs for 'Accepted' result
        is_accepted = False
        for leg in call['legs']:
            leg_result = leg.get('result', '').lower()
            if leg_result == 'accepted':
                is_accepted = True
                break
        
        if is_accepted:
            return True, "accepted"
        elif result == 'missed':
            return True, "missed"
        else:
            return False, f"Unqualified call: {result}"
            
    def process_call_logs(self, start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Process call logs for all extensions."""
        # Get enabled extensions
        extensions = self.db.query(Extension).filter(Extension.enabled == True).all()
        if not extensions:
            logger.warning("No enabled extensions found")
            return {"total": 0, "processed": 0, "accepted": 0, "missed": 0, "skipped": 0}
            
        stats = {
            "total": 0,
            "processed": 0,
            "accepted": 0,
            "missed": 0,
            "skipped": 0
        }
        
        # Process calls for each extension
        for ext in extensions:
            try:
                logs = self.get_call_logs(ext.extension_id, start_date, end_date)
                stats["total"] += len(logs)
                
                for call in logs:
                    # Check if call already exists in database
                    rc_call_id = call.get('id')
                    existing_call = self.db.query(CallRecord).filter(CallRecord.rc_call_id == rc_call_id).first()
                    
                    if existing_call:
                        stats["skipped"] += 1
                        continue
                        
                    # Qualify call
                    is_qualified, call_type = self.qualify_call(call)
                    
                    if not is_qualified:
                        stats["skipped"] += 1
                        continue
                        
                    # Process call based on type
                    if call_type == "accepted":
                        self._process_accepted_call(call, ext)
                        stats["accepted"] += 1
                    elif call_type == "missed":
                        self._process_missed_call(call, ext)
                        stats["missed"] += 1
                    
                    stats["processed"] += 1
                    
            except Exception as e:
                logger.error(f"Error processing calls for extension {ext.name} ({ext.extension_id}): {str(e)}")
                continue
                
        return stats
    
    def _process_accepted_call(self, call: Dict[str, Any], extension: Extension) -> Optional[CallRecord]:
        """Process an accepted call."""
        try:
            # Extract call details
            rc_call_id = call.get('id')
            caller_number = call.get('from', {}).get('phoneNumber', '')
            caller_name = call.get('from', {}).get('name', '')
            
            # Parse dates
            start_time_str = call.get('startTime')
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00')) if start_time_str else datetime.now()
            
            end_time_str = call.get('endTime')
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00')) if end_time_str else None
            
            duration = call.get('duration', 0)
            
            # Get recording info
            recording_id = None
            recording_url = None
            if 'recording' in call and call['recording'] and 'id' in call['recording']:
                recording_id = call['recording']['id']
                recording_url = call['recording'].get('contentUri', '')
            
            # Create call record
            call_record = CallRecord(
                rc_call_id=rc_call_id,
                extension_id=extension.extension_id,
                call_type="Accepted",
                direction="Inbound",
                caller_number=caller_number,
                caller_name=caller_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                recording_id=recording_id,
                recording_url=recording_url,
                raw_data=call,
                processed=False
            )
            
            self.db.add(call_record)
            self.db.commit()
            
            logger.info(f"Processed accepted call {rc_call_id} from {caller_number}")
            return call_record
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing accepted call: {str(e)}")
            return None
    
    def _process_missed_call(self, call: Dict[str, Any], extension: Extension) -> Optional[CallRecord]:
        """Process a missed call."""
        try:
            # Extract call details
            rc_call_id = call.get('id')
            caller_number = call.get('from', {}).get('phoneNumber', '')
            caller_name = call.get('from', {}).get('name', '')
            
            # Parse dates
            start_time_str = call.get('startTime')
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00')) if start_time_str else datetime.now()
            
            end_time_str = call.get('endTime')
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00')) if end_time_str else None
            
            duration = call.get('duration', 0)
            
            # Create call record
            call_record = CallRecord(
                rc_call_id=rc_call_id,
                extension_id=extension.extension_id,
                call_type="Missed",
                direction="Inbound",
                caller_number=caller_number,
                caller_name=caller_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                raw_data=call,
                processed=False
            )
            
            self.db.add(call_record)
            self.db.commit()
            
            logger.info(f"Processed missed call {rc_call_id} from {caller_number}")
            return call_record
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing missed call: {str(e)}")
            return None 