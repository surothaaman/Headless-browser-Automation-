from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class CustomerInfo(BaseModel):
    prefix: str | None = None
    first_name: str = Field(min_length=1)
    middle_initial: str | None = None
    last_name: str = Field(min_length=1)
    suffix: str | None = None
    email: EmailStr
    phone: str = Field(min_length=5)


class AddressInfo(BaseModel):
    address_line_1: str = Field(min_length=1)
    address_line_2: str | None = None
    zip_code: str = Field(min_length=5)
    secondary_zip_code: str | None = None
    unit_type: str | None = None
    unit_number: str | None = None
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)

    dwelling_type: (
        Literal["apartment", "condo", "duplex", "house", "mobile_home"] | None
    ) = None

    ownership: Literal["own", "rent"] | None = None

    moving: bool = False
    moving_date: date | None = None

    @model_validator(mode="after")
    def validate_moving_date(self):
        if self.moving and self.moving_date is None:
            raise ValueError("Moving date is required when moving is Yes")
        return self


class QualificationInfo(BaseModel):
    customer_type: Literal["new", "transfer"] | None = None

    current_providers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_transfer_providers(self):
        if self.customer_type == "transfer" and not self.current_providers:
            raise ValueError(
                "Select at least one current provider for a transfer customer"
            )
        return self


class ProductInfo(BaseModel):
    provider: str = "Provider XX"

    internet_speed: str = Field(min_length=1)
    internet_plan_name: str | None = None
    pricing_term: str | None = None

    tv: bool = False
    mobile: bool = False
    home_phone: bool = False

    video_plan: str | None = None
    phone_plan: str | None = None

    equipment_choice: Literal["leased_gateway", "own_equipment"] | None = None

    now_tv: bool = False

    broadband_facts_option: Literal["requested", "not_requested"] | None = None

    broadband_facts_read: bool = False


class AccountHolderInfo(BaseModel):
    account_holder_name: str = Field(min_length=1)

    speaking_to_account_holder: bool

    first_name: str = Field(min_length=1)
    middle_initial: str | None = None
    last_name: str = Field(min_length=1)

    prefix: str | None = None
    suffix: str | None = None

    phone: str = Field(min_length=5)
    email: EmailStr

    is_current_customer: bool
    ez_enroll: bool
    automatic_payment_paperless: bool

    disclosure_read: bool

    mailing_same_as_service: bool
    shipping_same_as_service: bool


class InstallationInfo(BaseModel):
    installation_type: Literal[
        "self_install", "professional", "standard_shipping", "pro_install"
    ]

    install_date: date | None = None

    preferred_time: Literal["morning", "afternoon", "evening"] | None = None

    age_18_acknowledged: bool = False
    installation_schedule_read: bool = False


class OrderRequest(BaseModel):
    customer: CustomerInfo
    address: AddressInfo
    qualification: QualificationInfo | None = None
    product: ProductInfo
    account_holder: AccountHolderInfo | None = None
    installation: InstallationInfo
