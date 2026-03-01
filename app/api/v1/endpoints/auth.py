from fastapi import APIRouter, Depends, Response, Cookie, HTTPException, status
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.auth import AuthService
from app.schemas.user import UserCreate, UserLogin, TokenResponse, RefreshTokenRequest
from app.core.response import success_response
from app.dependencies import get_current_user, get_auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Register a new user"""
    result = await auth_service.register(
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
        phone=user_data.phone
    )
    
    # Set tokens in HttpOnly cookies
    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,
        secure=False, 
        samesite="strict",  
        max_age=900, 
        path="/"
    )
    
    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=604800, 
        path="/auth/refresh" 
    )
    
    # For testing we will send the tokens in the repons 
    return success_response(
        data={
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "user": result.get("user"),
        },
        message="User registered successfully"
    )


@router.post("/login", response_model=dict)
async def login(
    credentials: UserLogin,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Login user"""
    result = await auth_service.login(
        email=credentials.email,
        password=credentials.password
    )
    
    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=900,  # 15 minutes
        path="/"
    )
    
    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=604800,  # 7 days
        path="/auth/refresh"
    )
    
    return success_response(
        data={
            "user": result.get("user"),
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
        },
        message="Login successful"
    )


@router.post("/refresh", response_model=dict)
async def refresh_token(
    response: Response,
    request: Optional[RefreshTokenRequest] = None,
    refresh_token_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Refresh access token using refresh token from body or cookie"""
    
    token_to_use = None
    if request and request.refresh_token:
        token_to_use = request.refresh_token
    elif refresh_token_cookie:
        token_to_use = refresh_token_cookie
        
    if not token_to_use:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found"
        )
    
    result = await auth_service.refresh_token(token_to_use)
        
    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=900,  # 15 minutes
        path="/"
    )
    
    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=604800,  # 7 days
        path="/auth/refresh"
    )
    
    return success_response(
        data={
            "message": "Token refreshed",
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
        },
        message="Token refreshed successfully"
    )


@router.post("/logout", response_model=dict)
async def logout(response: Response):
    """Logout user by clearing cookies"""
    
    # Clear access token cookie
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        secure=False,
        samesite="strict"
    )
    
    # Clear refresh token cookie
    response.delete_cookie(
        key="refresh_token",
        path="/auth/refresh",
        httponly=True,
        secure=False,
        samesite="strict"
    )
    
    return success_response(
        data={},
        message="Logged out successfully"
    )


@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """Get current authenticated user"""
    return success_response(
        data={"user": current_user},
        message="User retrieved successfully"
    )