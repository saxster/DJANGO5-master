"""
Pydantic validation schemas for People mutations.

Preserves validation logic from REST serializers with type-safe validation.
"""

from datetime import date
from typing import Optional, Dict
from pydantic import BaseModel, EmailStr, validator, Field
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


class CreatePersonSchema(BaseModel):
    """
    Validation schema for creating a new person.

    Validates:
    - Password strength (Django validators)
    - Password confirmation match
    - Email format
    - Required fields
    """

    username: str = Field(..., min_length=3, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=8)
    password_confirm: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=150)
    last_name: str = Field(..., min_length=1, max_length=150)
    phone: Optional[str] = Field(None, max_length=15)
    department_id: Optional[int] = None
    designation: Optional[str] = Field(None, max_length=100)
    role: Optional[str] = Field(None, max_length=50)
    date_of_birth: Optional[date] = None
    preferred_language: Optional[str] = Field(None, max_length=10)

    @validator('password_confirm')
    def passwords_match(cls, v: str, values: Dict) -> str:
        """Validate that password and password_confirm match."""
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

    @validator('password')
    def password_strength(cls, v: str) -> str:
        """
        Validate password strength using Django's validators.

        Raises ValueError if password doesn't meet requirements.
        """
        try:
            # Django's built-in password validation
            validate_password(v)
        except DjangoValidationError as e:
            # Convert Django validation errors to Pydantic format
            raise ValueError('; '.join(e.messages))
        return v

    @validator('username')
    def username_no_spaces(cls, v: str) -> str:
        """Ensure username has no spaces."""
        if ' ' in v:
            raise ValueError('Username cannot contain spaces')
        return v.lower()

    @validator('phone')
    def phone_format(cls, v: Optional[str]) -> Optional[str]:
        """Basic phone number validation."""
        if v is None:
            return v

        # Remove common formatting characters
        cleaned = v.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')

        if not cleaned.isdigit():
            raise ValueError('Phone number must contain only digits')

        if len(cleaned) < 10:
            raise ValueError('Phone number must be at least 10 digits')

        return cleaned

    class Config:
        str_strip_whitespace = True


class UpdatePersonSchema(BaseModel):
    """
    Validation schema for updating a person.

    All fields are optional for partial updates.
    """

    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=150)
    last_name: Optional[str] = Field(None, min_length=1, max_length=150)
    phone: Optional[str] = Field(None, max_length=15)
    department_id: Optional[int] = None
    designation: Optional[str] = Field(None, max_length=100)
    role: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    preferred_language: Optional[str] = Field(None, max_length=10)

    @validator('phone')
    def phone_format(cls, v: Optional[str]) -> Optional[str]:
        """Basic phone number validation."""
        if v is None:
            return v

        # Remove common formatting characters
        cleaned = v.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')

        if not cleaned.isdigit():
            raise ValueError('Phone number must contain only digits')

        if len(cleaned) < 10:
            raise ValueError('Phone number must be at least 10 digits')

        return cleaned

    class Config:
        str_strip_whitespace = True


class CapabilitiesSchema(BaseModel):
    """
    Validation schema for capabilities JSON.

    Validates:
    - Must be a dictionary
    - All values must be boolean
    - Keys must be valid capability names
    """

    capabilities: Dict[str, bool]

    @validator('capabilities')
    def validate_capabilities_structure(cls, v: Dict) -> Dict:
        """
        Validate capabilities structure.

        All values must be boolean.
        """
        if not isinstance(v, dict):
            raise ValueError('Capabilities must be a dictionary')

        for key, value in v.items():
            if not isinstance(value, bool):
                raise ValueError(
                    f'Capability "{key}" must have a boolean value, got {type(value).__name__}'
                )

            if not key:
                raise ValueError('Capability keys cannot be empty')

        return v

    class Config:
        str_strip_whitespace = True
