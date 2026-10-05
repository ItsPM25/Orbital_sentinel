from app.schemas.common import CamelModel


class LoginRequest(CamelModel):
    email: str = ""
    password: str = ""


class UserOut(CamelModel):
    user_id: str
    first_name: str
    last_name: str
    role: str
    email: str


class LoginResponse(CamelModel):
    user: UserOut
