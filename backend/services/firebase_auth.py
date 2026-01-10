"""
Firebase Authentication Service
Handles user authentication with Firebase Auth (Email + Google Sign-In)
"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, auth
    FIREBASE_ADMIN_AVAILABLE = True
except ImportError:
    FIREBASE_ADMIN_AVAILABLE = False
    logger.warning("firebase-admin not installed. Install with: pip install firebase-admin")

# Initialize Firebase Admin (singleton pattern)
_firebase_app = None


def initialize_firebase_admin():
    """Initialize Firebase Admin SDK (singleton)"""
    global _firebase_app
    
    if _firebase_app is not None:
        return _firebase_app
    
    if not FIREBASE_ADMIN_AVAILABLE:
        logger.warning("Firebase Admin SDK not available. Authentication will be disabled.")
        return None
    
    try:
        # Backend directory - always use this as the base for relative paths
        backend_dir = Path(__file__).parent.parent.resolve()
        
        # PRIORITY 0: Check for Base64 encoded service account (Railway deployment)
        base64_creds = os.environ.get("FIREBASE_SERVICE_ACCOUNT_BASE64")
        if base64_creds:
            logger.info("Priority 0: Found FIREBASE_SERVICE_ACCOUNT_BASE64, decoding...")
            try:
                import base64
                import json
                # Decode Base64 to JSON string, then parse to dict
                creds_json = base64.b64decode(base64_creds).decode('utf-8')
                creds_dict = json.loads(creds_json)
                cred = credentials.Certificate(creds_dict)
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info("SUCCESS: Firebase Admin initialized with Base64 credentials")
                return _firebase_app
            except Exception as e:
                logger.error(f"Failed to decode Base64 credentials: {e}")
        
        # PRIORITY 1: Check for service account file directly in backend folder
        direct_cred_path = backend_dir / "firebase-service-account.json"
        logger.info(f"Priority 1: Checking for direct file: {direct_cred_path}")
        
        if direct_cred_path.exists():
            cred = credentials.Certificate(str(direct_cred_path))
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info(f"SUCCESS: Firebase Admin initialized with direct file: {direct_cred_path}")
            return _firebase_app
        else:
            logger.info(f"Direct file not found at: {direct_cred_path}")
        
        # PRIORITY 2: Check GOOGLE_APPLICATION_CREDENTIALS environment variable
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        logger.info(f"Priority 2: Firebase credentials env var: {credentials_path}")
        
        if credentials_path:
            cred_path_obj = Path(credentials_path)
            
            # If it's an absolute path and exists, use it directly
            if cred_path_obj.is_absolute() and cred_path_obj.exists():
                credentials_path = str(cred_path_obj)
                logger.info(f"Using absolute credentials path: {credentials_path}")
            else:
                # For relative paths or non-existent absolute paths, try multiple locations
                # Extract just the filename if it's a path
                filename = cred_path_obj.name if cred_path_obj.name else "firebase-service-account.json"
                
                # Try 1: Directly in backend directory
                test_path = backend_dir / filename
                logger.info(f"Trying backend dir path: {test_path}")
                if test_path.exists():
                    credentials_path = str(test_path)
                    logger.info(f"Found at backend dir: {credentials_path}")
                else:
                    # Try 2: Full relative path from backend directory
                    # Try 2: Current working directory
                    test_path = Path.cwd() / credentials_path.lstrip('./')
                    logger.info(f"Trying cwd path: {test_path}")
                    if test_path.exists():
                        cred_path_obj = test_path
                    else:
                        cred_path_obj = Path(credentials_path)
                        logger.info(f"Using raw path: {cred_path_obj}")
            credentials_path = str(cred_path_obj.resolve())
            logger.info(f"Resolved credentials path: {credentials_path}")
            
            if Path(credentials_path).exists():
                cred = credentials.Certificate(credentials_path)
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info(f"Firebase Admin initialized with env var credentials: {credentials_path}")
                return _firebase_app
        
        # Priority 3: Try project ID
        project_id = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("NEXT_PUBLIC_FIREBASE_PROJECT_ID")
        if project_id:
            try:
                _firebase_app = firebase_admin.initialize_app(
                    options={"projectId": project_id}
                )
                logger.info(f"Firebase Admin initialized with project ID: {project_id}")
                return _firebase_app
            except ValueError:
                _firebase_app = firebase_admin.get_app()
                logger.info("Firebase Admin already initialized")
                return _firebase_app
        
        # Priority 4: Default credentials (gcloud CLI)
        try:
            _firebase_app = firebase_admin.initialize_app()
            logger.info("Firebase Admin initialized with default credentials")
            return _firebase_app
        except Exception as default_err:
            logger.warning(f"Firebase Admin initialization failed: {default_err}")
            logger.warning("Options:")
            logger.warning("1. Place firebase-service-account.json in backend folder")
            logger.warning("2. Set GOOGLE_APPLICATION_CREDENTIALS for service account file")
            logger.warning("3. Set FIREBASE_PROJECT_ID environment variable")
            logger.warning("4. Use 'gcloud auth application-default login' for default credentials")
            return None
        
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin: {e}")
        return None


def verify_firebase_token(id_token: str) -> Optional[Dict[str, Any]]:
    """
    Verify Firebase ID token and return decoded token claims.
    Only real Firebase tokens - no demo mode.
    
    Args:
        id_token: Firebase ID token from client
        
    Returns:
        Decoded token claims (uid, email, etc.) or None if invalid
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    if not FIREBASE_ADMIN_AVAILABLE:
        logger.warning("Firebase Admin not available. Token verification skipped.")
        return None
    
    # Initialize if not already done
    app = initialize_firebase_admin()
    if app is None:
        logger.warning("Firebase Admin not initialized. Token verification skipped.")
        return None
    
    try:
        # Verify the token
        logger.debug(f"Verifying token (length={len(id_token)}, starts_with={id_token[:20]}...)")
        decoded_token = auth.verify_id_token(id_token)
        
        # Extract user info (including custom claims which are at root level)
        user_info = {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "email_verified": decoded_token.get("email_verified", False),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture"),
            "firebase": decoded_token.get("firebase", {}),
            "iss": decoded_token.get("iss"),
            "aud": decoded_token.get("aud"),
            "auth_time": decoded_token.get("auth_time"),
            "exp": decoded_token.get("exp"),
            # Custom claims are at root level of decoded token
            "role": decoded_token.get("role"),  # Custom claim
            "is_demo": False,
        }
        
        logger.debug(f"Firebase token verified for user: {user_info.get('email')}")
        return user_info
        
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid Firebase token error: {str(e)}")
        logger.warning(f"Token snippet: {id_token[:50]}... (length={len(id_token)})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}"
        )
    except auth.ExpiredIdTokenError as e:
        logger.warning(f"Expired Firebase token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired"
        )
    except Exception as e:
        import traceback
        logger.error(f"Error verifying Firebase token: {type(e).__name__}: {e}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication verification failed: {type(e).__name__}"
        )



def get_user_role(user_info: Dict[str, Any]) -> str:
    """
    Extract user role from Firebase custom claims or email domain.
    
    Supported roles (NO ADMIN):
    - college: College user (can access all departments)
    - department: Department user (single department only)
    
    Args:
        user_info: Decoded Firebase token claims
        
    Returns:
        Role string: "college" or "department"
    """
    # Check custom claims first (they're at root level of decoded token)
    if "role" in user_info and user_info["role"]:
        role = user_info["role"]
        # Map old roles to new roles
        if role in ["admin", "institution"]:
            return "college"
        if role in ["department", "college"]:
            return role
    
    # Also check nested custom claims (legacy support)
    custom_claims = user_info.get("firebase", {}).get("custom_claims", {})
    if "role" in custom_claims:
        role = custom_claims["role"]
        # Map old roles to new roles
        if role in ["admin", "institution"]:
            return "college"
        if role in ["department", "college"]:
            return role
    
    # Fallback to email domain
    email = user_info.get("email", "")
    if not email:
        return "department"  # Default role
    
    email_domain = email.split("@")[-1].lower()
    
    # Role mapping based on domain
    # College users: .edu domains or college-related domains
    if email_domain.endswith(".edu") or "college" in email_domain or "university" in email_domain:
        return "college"
    else:
        return "department"


def set_user_role(uid: str, role: str) -> bool:
    """
    Set custom claims (role) for a Firebase user.
    
    Args:
        uid: Firebase user UID
        role: Role to set ('department' or 'institution')
        
    Returns:
        True if successful, False otherwise
    """
    if not FIREBASE_ADMIN_AVAILABLE:
        logger.warning("Firebase Admin not available. Cannot set user role.")
        return False
    
    # Initialize if not already done
    app = initialize_firebase_admin()
    if app is None:
        logger.warning("Firebase Admin not initialized. Cannot set user role.")
        return False
    
    # Validate role
    if role not in ['department', 'college']:
        logger.error(f"Invalid role: {role}. Must be 'department' or 'college'")
        return False
    
    try:
        # Set custom claims
        auth.set_custom_user_claims(uid, {'role': role})
        logger.info(f"Set role '{role}' for user {uid}")
        return True
    except Exception as e:
        logger.error(f"Failed to set user role: {e}")
        return False


def require_auth(token: Optional[str] = None) -> Dict[str, Any]:
    """
    Require authentication and return user info.
    
    Args:
        token: Firebase ID token (from Authorization header)
        
    Returns:
        User info dictionary
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return verify_firebase_token(token)

