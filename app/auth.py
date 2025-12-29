# app/auth.py
"""
API Key authentication dependency
"""

import secrets
from fastapi import Header, HTTPException, status
from app.config import settings


async def verify_api_key(
    x_api_key: str = Header(..., description="API key for authentication"),
):
    if not secrets.compare_digest(x_api_key, settings.api_proxy_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key
