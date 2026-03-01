from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper"""
    success: bool
    message: str
    data: Optional[T] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation successful",
                "data": {}
            }
        }


def success_response(data: Any = None, message: str = "Success") -> dict:
    """Create success response"""
    return {
        "success": True,
        "message": message,
        "data": data
    }


def error_response(message: str = "Error occurred", data: Any = None) -> dict:
    """Create error response"""
    return {
        "success": False,
        "message": message,
        "data": data
    }


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper"""
    success: bool = True
    message: str
    data: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Data retrieved",
                "data": [],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5
            }
        }


def paginated_response(
    data: list,
    total: int,
    page: int,
    page_size: int,
    message: str = "Success"
) -> dict:
    """Create paginated response"""
    total_pages = (total + page_size - 1) // page_size  # Ceiling division
    
    return {
        "success": True,
        "message": message,
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }