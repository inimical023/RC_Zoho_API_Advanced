import os
import logging
import argparse
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


def init_db():
    """Initialize the database and create tables."""
    from models.database import engine, Base
    
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def create_admin_user(username, email, password):
    """Create an admin user."""
    from models.database import get_db_session
    from services.user_service import create_user, get_user_by_username
    
    with get_db_session() as db:
        # Check if admin user already exists
        existing_user = get_user_by_username(db, username)
        if existing_user:
            logger.info(f"Admin user '{username}' already exists")
            return
        
        # Create admin user
        user = create_user(
            db=db,
            username=username,
            email=email,
            password=password,
            full_name="System Administrator",
            is_admin=True
        )
        
        if user:
            logger.info(f"Admin user '{username}' created successfully")
        else:
            logger.error(f"Failed to create admin user '{username}'")


def add_default_credentials():
    """Add default API credentials from environment variables."""
    from models.database import get_db_session
    from models.credentials import ApiCredential
    from utils.security import encrypt_value
    
    # RingCentral credentials
    ringcentral_creds = {
        "client_id": os.getenv("RINGCENTRAL_CLIENT_ID"),
        "client_secret": os.getenv("RINGCENTRAL_CLIENT_SECRET"),
        "jwt_token": os.getenv("RINGCENTRAL_JWT_TOKEN"),
        "account_id": os.getenv("RINGCENTRAL_ACCOUNT_ID", "~")
    }
    
    # Zoho credentials
    zoho_creds = {
        "client_id": os.getenv("ZOHO_CLIENT_ID"),
        "client_secret": os.getenv("ZOHO_CLIENT_SECRET"),
        "refresh_token": os.getenv("ZOHO_REFRESH_TOKEN")
    }
    
    with get_db_session() as db:
        # Add RingCentral credentials
        for name, value in ringcentral_creds.items():
            if not value:
                logger.warning(f"RingCentral {name} not found in environment variables")
                continue
                
            # Check if credential already exists
            existing = db.query(ApiCredential).filter(
                ApiCredential.service == "ringcentral",
                ApiCredential.name == name
            ).first()
            
            if existing:
                logger.info(f"RingCentral {name} already exists in database")
                continue
                
            # Encrypt and store credential
            encrypted_value = encrypt_value(value)
            
            credential = ApiCredential(
                service="ringcentral",
                name=name,
                encrypted_value=encrypted_value,
                encrypted_key_id="default",
                is_active=True
            )
            
            db.add(credential)
            logger.info(f"Added RingCentral {name} to database")
            
        # Add Zoho credentials
        for name, value in zoho_creds.items():
            if not value:
                logger.warning(f"Zoho {name} not found in environment variables")
                continue
                
            # Check if credential already exists
            existing = db.query(ApiCredential).filter(
                ApiCredential.service == "zoho",
                ApiCredential.name == name
            ).first()
            
            if existing:
                logger.info(f"Zoho {name} already exists in database")
                continue
                
            # Encrypt and store credential
            encrypted_value = encrypt_value(value)
            
            credential = ApiCredential(
                service="zoho",
                name=name,
                encrypted_value=encrypted_value,
                encrypted_key_id="default",
                is_active=True
            )
            
            db.add(credential)
            logger.info(f"Added Zoho {name} to database")
            
        # Commit changes
        db.commit()
        logger.info("Default credentials added successfully")


def sync_extensions():
    """Sync RingCentral extensions."""
    from models.database import get_db_session
    from services.ringcentral_service import RingCentralService
    
    try:
        with get_db_session() as db:
            rc_service = RingCentralService(db)
            created, updated, disabled = rc_service.sync_extensions()
            
            logger.info(f"Extensions sync: {created} created, {updated} updated, {disabled} disabled")
            
    except Exception as e:
        logger.error(f"Error syncing extensions: {str(e)}")


def sync_lead_owners():
    """Sync Zoho users as lead owners."""
    from models.database import get_db_session
    from services.zoho_service import ZohoService
    
    try:
        with get_db_session() as db:
            zoho_service = ZohoService(db)
            created, updated, deactivated = zoho_service.sync_users()
            
            logger.info(f"Lead owners sync: {created} created, {updated} updated, {deactivated} deactivated")
            
    except Exception as e:
        logger.error(f"Error syncing lead owners: {str(e)}")


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Initialize the RC-Zoho Integration database")
    parser.add_argument("--admin-username", default="admin", help="Admin username")
    parser.add_argument("--admin-email", default="admin@example.com", help="Admin email")
    parser.add_argument("--admin-password", default=None, help="Admin password")
    parser.add_argument("--no-sync", action="store_true", help="Skip syncing extensions and users")
    args = parser.parse_args()
    
    # Set default admin password if not provided
    admin_password = args.admin_password
    if not admin_password:
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    
    # Initialize database
    init_db()
    
    # Create admin user
    create_admin_user(args.admin_username, args.admin_email, admin_password)
    
    # Add default credentials
    add_default_credentials()
    
    # Sync extensions and lead owners
    if not args.no_sync:
        sync_extensions()
        sync_lead_owners()
    
    logger.info("Database initialization completed successfully")


if __name__ == "__main__":
    main() 