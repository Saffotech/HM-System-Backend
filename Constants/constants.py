import enum

class Gender(int, enum.Enum):
    MALE       = 1
    FEMALE     = 2
    OTHER      = 3
    PREFER_NOT = 4

class Role(str, enum.Enum):
    ADMIN        = "admin"
    DOCTOR       = "doctor"
    NURSE        = "nurse"
    RECEPTIONIST = "receptionist"
    PHARMACIST   = "pharmacist"    

# Token expiry (defaults; runtime values come from .env via jwt_token.py)
ACCESS_TOKEN_EXPIRE_MINUTES = 5
REFRESH_TOKEN_EXPIRE_DAYS   = 7

# Pagination
DEFAULT_PAGE      = 1
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE     = 100

# File upload limits
MAX_PROFILE_IMAGE_SIZE_MB = 20
ALLOWED_IMAGE_TYPES       = ["image/jpeg", "image/png", "image/webp"]