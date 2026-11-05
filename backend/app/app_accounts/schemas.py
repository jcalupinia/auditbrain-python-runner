"""Esquemas Pydantic de las Cuentas de Aplicaciones AUDIT-IA."""

from pydantic import BaseModel, Field


class AppCatalogItem(BaseModel):
    key: str
    label: str
    description: str = ""


class AppAccountCreate(BaseModel):
    email: str
    display_name: str | None = None
    client_label: str | None = None
    apps: list[str] = Field(default_factory=list)
    password: str | None = None  # opcional; si no se da, se genera una temporal
    send_email: bool = True  # enviar el acceso (usuario+clave) por correo al cliente


class AppChangePassword(BaseModel):
    current_password: str
    new_password: str


class AppAccountUpdate(BaseModel):
    display_name: str | None = None
    client_label: str | None = None
    is_active: bool | None = None
    apps: list[str] | None = None


class AppAccountOut(BaseModel):
    id: int
    email: str
    display_name: str | None = None
    client_label: str | None = None
    is_active: bool
    password_reset_required: bool
    apps: list[str] = Field(default_factory=list)
    created_by: str | None = None
    created_at: str


class AppAccountCreated(BaseModel):
    account: AppAccountOut
    temp_password: str
    email_sent: bool | None = None  # True enviado, False falló, None no se intentó


class ResetPasswordOut(BaseModel):
    temp_password: str
    email_sent: bool | None = None


class AppLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    apps: list[str] = Field(default_factory=list)
    password_reset_required: bool = False


class AppMeResponse(BaseModel):
    email: str
    display_name: str | None = None
    apps: list[str] = Field(default_factory=list)
    password_reset_required: bool = False
