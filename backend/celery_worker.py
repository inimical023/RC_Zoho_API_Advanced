import os
import logging
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Try to load from default locations

# Create Celery app
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery("rc_zoho_integration", broker=redis_url, backend=redis_url)

# Load celery config
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=2,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)

# Define periodic tasks
app.conf.beat_schedule = {
    "sync-extensions-daily": {
        "task": "celery_worker.sync_extensions",
        "schedule": crontab(hour=1, minute=0),  # 1:00 AM every day
    },
    "sync-lead-owners-daily": {
        "task": "celery_worker.sync_lead_owners",
        "schedule": crontab(hour=1, minute=15),  # 1:15 AM every day
    },
    "fetch-missed-calls-hourly": {
        "task": "celery_worker.fetch_missed_calls",
        "schedule": crontab(minute=5),  # Every hour at 5 minutes past
    },
    "fetch-accepted-calls-hourly": {
        "task": "celery_worker.fetch_accepted_calls",
        "schedule": crontab(minute=15),  # Every hour at 15 minutes past
    },
    "process-calls-every-15-min": {
        "task": "celery_worker.process_calls",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
    },
}


# Import models and services within tasks to avoid circular imports
@app.task(bind=True, name="celery_worker.sync_extensions")
def sync_extensions(self):
    """Sync RingCentral extensions with database."""
    logger.info("Starting scheduled task: sync_extensions")
    try:
        from models.database import get_db_session
        from services.ringcentral_service import RingCentralService
        
        with get_db_session() as db:
            rc_service = RingCentralService(db)
            created, updated, disabled = rc_service.sync_extensions()
            
            result = {
                "created": created,
                "updated": updated,
                "disabled": disabled,
                "total": created + updated + disabled
            }
            
            logger.info(f"Task sync_extensions completed: {result}")
            return result
            
    except Exception as e:
        logger.error(f"Error in task sync_extensions: {str(e)}")
        self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True, name="celery_worker.sync_lead_owners")
def sync_lead_owners(self):
    """Sync Zoho users as lead owners."""
    logger.info("Starting scheduled task: sync_lead_owners")
    try:
        from models.database import get_db_session
        from services.zoho_service import ZohoService
        
        with get_db_session() as db:
            zoho_service = ZohoService(db)
            created, updated, deactivated = zoho_service.sync_users()
            
            result = {
                "created": created,
                "updated": updated,
                "deactivated": deactivated,
                "total": created + updated + deactivated
            }
            
            logger.info(f"Task sync_lead_owners completed: {result}")
            return result
            
    except Exception as e:
        logger.error(f"Error in task sync_lead_owners: {str(e)}")
        self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True, name="celery_worker.fetch_missed_calls")
def fetch_missed_calls(self):
    """Fetch missed calls from the last hour."""
    logger.info("Starting scheduled task: fetch_missed_calls")
    try:
        from models.database import get_db_session
        from services.ringcentral_service import RingCentralService
        
        # Set time range for the last hour
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=1)
        
        with get_db_session() as db:
            rc_service = RingCentralService(db)
            result = rc_service.process_call_logs(start_date, end_date)
            
            logger.info(f"Task fetch_missed_calls completed: {result}")
            return result
            
    except Exception as e:
        logger.error(f"Error in task fetch_missed_calls: {str(e)}")
        self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True, name="celery_worker.fetch_accepted_calls")
def fetch_accepted_calls(self):
    """Fetch accepted calls with recordings from the last hour."""
    logger.info("Starting scheduled task: fetch_accepted_calls")
    try:
        from models.database import get_db_session
        from services.ringcentral_service import RingCentralService
        
        # Set time range for the last hour
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=1)
        
        with get_db_session() as db:
            rc_service = RingCentralService(db)
            result = rc_service.process_call_logs(start_date, end_date)
            
            logger.info(f"Task fetch_accepted_calls completed: {result}")
            return result
            
    except Exception as e:
        logger.error(f"Error in task fetch_accepted_calls: {str(e)}")
        self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True, name="celery_worker.process_calls")
def process_calls(self):
    """Process unprocessed calls and create leads in Zoho CRM."""
    logger.info("Starting scheduled task: process_calls")
    try:
        from models.database import get_db_session
        from services.zoho_service import ZohoService
        
        with get_db_session() as db:
            zoho_service = ZohoService(db)
            result = zoho_service.process_unprocessed_calls()
            
            logger.info(f"Task process_calls completed: {result}")
            return result
            
    except Exception as e:
        logger.error(f"Error in task process_calls: {str(e)}")
        self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True, name="celery_worker.fetch_calls_range")
def fetch_calls_range(self, start_date, end_date):
    """Fetch calls from a specific date range (can be triggered manually)."""
    logger.info(f"Starting task: fetch_calls_range ({start_date} to {end_date})")
    try:
        from models.database import get_db_session
        from services.ringcentral_service import RingCentralService
        
        # Convert string dates to datetime if needed
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        with get_db_session() as db:
            rc_service = RingCentralService(db)
            result = rc_service.process_call_logs(start_date, end_date)
            
            logger.info(f"Task fetch_calls_range completed: {result}")
            return result
            
    except Exception as e:
        logger.error(f"Error in task fetch_calls_range: {str(e)}")
        self.retry(exc=e, countdown=60, max_retries=3) 