from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from app.repositories.user import UserRepository
from app.core.security import (
    verify_password, 
    get_password_hash,
    create_access_token,
    create_refresh_token,
    create_email_verification_token,
    decode_token
)
from app.core.exceptions import (
    UserAlreadyExistsException,
    InvalidCredentialsException,
    UnauthorizedException
)
from app.config import settings
from app.integerations.email.client import send_email,render_email, EmailSendError

class AuthService:
    """Authentication service"""
    
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
    
    async def register(self, email: str, password: str, full_name: str, phone: str) -> dict:
        """Register a new user"""
        # Check if user exists
        if await self.user_repo.email_exists(email):
            raise UserAlreadyExistsException("Email already registered")
        
        if await self.user_repo.phone_exists(phone):
            raise UserAlreadyExistsException("Phone number already registered")
        
        password_hash = get_password_hash(password)
        
        user_data = {
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "phone": phone
        }
        
        user = await self.user_repo.create(user_data)
        
        # Generate tokens
        tokens = self._generate_tokens(user.user_id, email)
        
        return {
            **tokens,
            "user": {
                "user_id": user.user_id,
                "email": user.email,
                "full_name": user.full_name,
                "phone": user.phone,
                "kyc_status": user.kyc_status.value,
                "created_at": user.created_at
            }
        }
    
    async def login(self, email: str, password: str) -> dict:
        """Login user"""
        user = await self.user_repo.get_by_email(email)
        
        if not user:
            raise InvalidCredentialsException()
        
        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsException()
        
        # Generate tokens
        tokens = self._generate_tokens(user.user_id, email)
        
        return {
            **tokens,
            "user": {
                "user_id": user.user_id,
                "email": user.email,
                "full_name": user.full_name,
                "phone": user.phone,
                "kyc_status": user.kyc_status.value,
                "created_at": user.created_at
            }
        }
    
    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token"""
        payload = decode_token(refresh_token,expected_type="refresh")
        if not payload or payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid refresh token")
        
        user_id = payload.get("sub")
        email = payload.get("email")
        
        if not user_id or not email:
            raise UnauthorizedException("Invalid token payload")
        
        # Verify user exists
        user = await self.user_repo.get(int(user_id))
        if not user:
            raise UnauthorizedException("User not found")
            
        # Generate new tokens
        return self._generate_tokens(user.user_id, user.email)

    async def get_current_user(self, token: str) -> dict:
        """Get current user from token"""
        payload = decode_token(token)
        if not payload:
            raise UnauthorizedException("Invalid token")
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Invalid token payload")
        
        user = await self.user_repo.get(int(user_id))
        if not user:
            raise UnauthorizedException("User not found")
        
        return {
            "user_id": user.user_id,
            "email": user.email,
            "full_name": user.full_name
        }
    
    def _generate_tokens(self, user_id: int, email: str) -> dict:
        """Generate access and refresh tokens"""
        access_token = create_access_token(
            data={"sub": str(user_id), "email": email}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user_id), "email": email}
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    async def verify_email(self, token: str) -> bool:
        """Verify user email using token"""
        payload = decode_token(token, expected_type="email_verification")
        print(payload)
        if not payload:
            raise UnauthorizedException("Invalid token")
        
        email = payload.get("sub")
        if not email:
            raise UnauthorizedException("Invalid token payload")
        
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise UnauthorizedException("User not found")
        
        tokens = self._generate_tokens(user.user_id, email)
        print(tokens)
        return {
            **tokens,
            "user": {
                "user_id"   : user.user_id,
                "email"     : user.email,
                "full_name" : user.full_name,
                "phone"     : user.phone,
                "kyc_status": user.kyc_status.value,
                "created_at": user.created_at
            }
        }

    async def send_welcome_email(self,full_name:str,user_email: str):
        token = create_email_verification_token(user_email)
        html = await render_email(
            "registeration_verification.html",
            {
                "name": full_name,
                "verification_url": f'{settings.APP_URL}/api/v1/auth/verify-email?token={token}'
            }
        )

        await send_email(
            smtp_server=settings.SMTP_SERVER,
            smtp_port=settings.SMTP_PORT,
            sender_email=settings.SENDER_EMAIL,
            app_password=settings.APP_PASSWORD,
            recipients=[user_email],
            subject= "Welcome!",
            text_content= "Welcome to our platform!",
            html_content= html
        )
      