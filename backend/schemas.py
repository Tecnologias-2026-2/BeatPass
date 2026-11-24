"""Contratos entre navegador y API; validaciones de entrada explícitas."""
# FLUJO: main.py y profile.py validan aquí las entradas recibidas desde api.js.
from typing import Literal
from pydantic import BaseModel, Field, field_validator

class RegisterBody(BaseModel):
    fullname: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=12, max_length=128)
    profile: Literal['cliente', 'organizador'] = 'cliente'
    organization: str | None = Field(default=None, max_length=140)
    phone: str | None = Field(default=None, max_length=40)
    city: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator('fullname', 'email')
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value: raise ValueError('El campo no puede estar vacío.')
        return value

class LoginBody(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str
    profile: Literal['cliente', 'organizador', 'administracion'] = 'cliente'

class ReviewBody(BaseModel):
    reason: str = Field(default='', max_length=500)

class EmailBody(BaseModel):
    email: str = Field(min_length=5, max_length=255)

class TokenBody(BaseModel):
    token: str = Field(min_length=20, max_length=256)

class PasswordResetBody(TokenBody):
    password: str = Field(min_length=12, max_length=128)

class InvitationAcceptBody(TokenBody):
    email: str = Field(min_length=5, max_length=255)
    password: str

# Mi perfil: el JS envía solo los datos editables. No se aceptan roles ni estados.
class ProfileNameBody(BaseModel):
    model_config = {'extra': 'forbid'}
    fullname: str = Field(min_length=2, max_length=120)

class ProfilePasswordBody(BaseModel):
    model_config = {'extra': 'forbid'}
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=12, max_length=128)
