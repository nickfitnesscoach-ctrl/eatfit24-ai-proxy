"""
API Key authentication middleware
"""
from fastapi import Header, HTTPException, status
from app.config import settings


async def verify_api_key(x_api_key: str = Header(..., description="API key for authentication")):
    """
    Verify API key from X-API-Key header

    Args:
        x_api_key: API key from request header

    Raises:
        HTTPException: 401 if API key is invalid or missing
    """
    if x_api_key != settings.api_proxy_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    return x_api_key
