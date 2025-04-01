from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging

from models.user import User
from utils.security import get_password_hash

# Set up logging
logger = logging.getLogger(__name__)


def get_user(db: Session, user_id: int) -> Optional[User]:
    """Get a user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get a user by username."""
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get a user by email."""
    return db.query(User).filter(User.email == email).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """Get a list of users with pagination."""
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, username: str, email: str, password: str, full_name: str = None, is_admin: bool = False) -> Optional[User]:
    """Create a new user."""
    try:
        # Check if user already exists
        if get_user_by_username(db, username):
            logger.warning(f"User with username '{username}' already exists")
            return None
        
        if get_user_by_email(db, email):
            logger.warning(f"User with email '{email}' already exists")
            return None
        
        # Create new user
        hashed_password = get_password_hash(password)
        
        db_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_admin=is_admin
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"Created new user: {username}")
        return db_user
    
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating user: {str(e)}")
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating user: {str(e)}")
        return None


def update_user(db: Session, user_id: int, **kwargs) -> Optional[User]:
    """Update a user's details."""
    try:
        user = get_user(db, user_id)
        if not user:
            logger.warning(f"User with ID {user_id} not found")
            return None
        
        # Update allowed fields
        for key, value in kwargs.items():
            if key == 'password':
                user.hashed_password = get_password_hash(value)
            elif hasattr(user, key):
                setattr(user, key, value)
        
        db.commit()
        db.refresh(user)
        
        logger.info(f"Updated user ID {user_id}")
        return user
    
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating user: {str(e)}")
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error updating user: {str(e)}")
        return None


def delete_user(db: Session, user_id: int) -> bool:
    """Delete a user."""
    try:
        user = get_user(db, user_id)
        if not user:
            logger.warning(f"User with ID {user_id} not found")
            return False
        
        db.delete(user)
        db.commit()
        
        logger.info(f"Deleted user ID {user_id}")
        return True
    
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deleting user: {str(e)}")
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error deleting user: {str(e)}")
        return False 