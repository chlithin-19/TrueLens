import json
import logging
import urllib.request
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger("truelens.auth")
# Trigger reload for .env change
# Security scheme for FastAPI docs / auth extraction
reusable_oauth2 = HTTPBearer(auto_error=False)

class ClerkJWTValidator:
    def __init__(self):
        self.jwks_url = settings.CLERK_JWKS_URL
        self.jwk_client = None
        if self.jwks_url:
            try:
                headers = {}
                if settings.CLERK_SECRET_KEY:
                    headers["Authorization"] = f"Bearer {settings.CLERK_SECRET_KEY}"
                self.jwk_client = PyJWKClient(self.jwks_url, headers=headers)
            except Exception as e:
                logger.error(f"Failed to initialize Clerk JWK Client: {e}")

    def verify_token(self, token: str) -> dict:
        """Decodes and validates a Clerk session JWT token."""
        if not self.jwk_client:
            # Fallback/missing configuration check
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Clerk authentication is not configured on the backend."
            )
        
        try:
            # Fetch the signing key from the JWKS endpoint matching the token's kid
            signing_key = self.jwk_client.get_signing_key_from_jwt(token)
            
            # Decode and verify token
            # Clerk session tokens are signed with RS256
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_exp": True},
                audience=None, # Clerk tokens do not enforce audience by default
            )
            
            # Verify issuer if CLERK_ISSUER is configured
            if settings.CLERK_ISSUER and decoded.get("iss") != settings.CLERK_ISSUER:
                raise jwt.InvalidIssuerError("Issuer mismatch")
                
            return decoded
        except jwt.ExpiredSignatureError:
            logger.warning("Token signature has expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired. Please log in again."
            )
        except (jwt.InvalidSignatureError, jwt.InvalidTokenError, jwt.InvalidIssuerError) as e:
            logger.warning(f"Invalid token signature: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication token: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during token verification: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed."
            )

# Instantiate the global validator
jwt_validator = ClerkJWTValidator()

async def fetch_user_details_from_clerk(user_id: str) -> dict:
    """Fetches user details from the Clerk backend API using CLERK_SECRET_KEY."""
    if not settings.CLERK_SECRET_KEY:
        logger.warning("CLERK_SECRET_KEY not set. Cannot fetch user details from Clerk.")
        return {}
        
    try:
        url = f"https://api.clerk.com/v1/users/{user_id}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {settings.CLERK_SECRET_KEY}",
                "Accept": "application/json"
            }
        )
        
        # Run blocking network call in standard context (or could wrap in loop.run_in_executor)
        # Since this is rare (lazy sync only), simple urllib is fine.
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return json.loads(response.read().decode())
    except Exception as e:
        logger.error(f"Error fetching user {user_id} from Clerk API: {e}")
    return {}

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(reusable_oauth2),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency to extract and verify the Clerk JWT session token,
    returning the corresponding PostgreSQL User model.
    Supports lazy-syncing the user if not found in the local database.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided."
        )
    
    token = credentials.credentials
    
    # 1. Verify the JWT
    payload = jwt_validator.verify_token(token)
    user_id = payload.get("sub") # Clerk stores user ID in the 'sub' claim
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing subject claim."
        )
        
    # 2. Find user in the local database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    # 3. Lazy Sync: If user does not exist locally (e.g. webhook delayed),
    # fetch their details from Clerk's API and create their record.
    if not user:
        logger.info(f"User {user_id} authenticated but not found in DB. Performing lazy sync...")
        clerk_data = await fetch_user_details_from_clerk(user_id)
        
        if clerk_data:
            # Extract emails
            email_addresses = clerk_data.get("email_addresses", [])
            primary_email_id = clerk_data.get("primary_email_address_id")
            email = None
            for email_obj in email_addresses:
                if email_obj.get("id") == primary_email_id or not email:
                    email = email_obj.get("email_address")
                    
            if not email and email_addresses:
                email = email_addresses[0].get("email_address")
                
            if not email:
                email = f"{user_id}@clerk.placeholder" # Fallback if no email
                
            first_name = clerk_data.get("first_name")
            last_name = clerk_data.get("last_name")
            profile_image_url = clerk_data.get("image_url")
            
            # Retrieve role from Clerk public metadata if present
            public_metadata = clerk_data.get("public_metadata", {})
            role = public_metadata.get("role", "user")
            
            user = User(
                id=user_id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                profile_image_url=profile_image_url,
                role=role
            )
            
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Successfully lazy-synced user {user_id} to DB.")
        else:
            # Fallback if Clerk API is unreachable or secret key is missing,
            # but JWT is validated (we create a basic record with mock values).
            # This ensures local development doesn't break if Clerk secret key is omitted.
            email = payload.get("email") or f"{user_id}@placeholder.com"
            user = User(
                id=user_id,
                email=email,
                first_name=payload.get("fname", "User"),
                last_name=payload.get("lname", ""),
                profile_image_url=payload.get("picture"),
                role="user"
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.warning(f"Lazy-synced basic user {user_id} using JWT claims (Clerk API unavailable).")
            
    return user

async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """FastAPI dependency to ensure the user has the 'admin' role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have administrative permissions to perform this action."
        )
    return current_user
