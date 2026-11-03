
from typing import Literal
from pydantic import BaseModel, EmailStr, Field


class CustomerInfo(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: EmailStr
    phone: str = Field(min_length=5)


class AddressInfo(BaseModel):
    address_line_1: str
    address_line_2: str | None = None
    zip_code: str
    city: str
    state: str


class ProductInfo(BaseModel):
    provider: str = "Provider XX"
    internet_speed: str
    tv: bool = False
    mobile: bool = False
    home_phone: bool = False


class InstallationInfo(BaseModel):
    installation_type: Literal["self_install", "professional"]


class OrderRequest(BaseModel):
    customer: CustomerInfo
    address: AddressInfo
    product: ProductInfo
    installation: InstallationInfo
