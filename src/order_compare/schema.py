"""Shared case and proposal shapes across providers."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OrderCase(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )
    case_id: str = Field(min_length=1, max_length=128)
    order_id: str = Field(min_length=1, max_length=128)
    customer_request: str = Field(min_length=1, max_length=10000)
    issue: Literal["damaged", "address_change", "delivery_delay"]
    shipped: bool
    captured_cents: int = Field(ge=0, le=2**53 - 1)
    refunded_cents: int = Field(ge=0, le=2**53 - 1)
    replacement_stock: int = Field(ge=0, le=2**53 - 1)

    @model_validator(mode="after")
    def coherent(self):
        if (
            not self.case_id.strip()
            or self.case_id != self.case_id.strip()
            or not self.order_id.strip()
            or self.order_id != self.order_id.strip()
            or not self.customer_request.strip()
        ):
            raise ValueError("case/order IDs and request must be nonblank")
        if self.refunded_cents > self.captured_cents:
            raise ValueError("refunded amount exceeds original capture")
        return self


class Proposal(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )
    order_id: str = Field(min_length=1, max_length=128)
    action: Literal["replace", "refund", "contact", "deny"]
    amount_cents: int = Field(ge=0, le=2**53 - 1)
    reason: str = Field(min_length=5, max_length=2000)

    @field_validator("order_id", "reason")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("proposal fields must be nonblank")
        return value


class Expectation(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )
    action: Literal["replace", "refund", "contact", "deny"]
    amount_cents: int = Field(ge=0, le=2**53 - 1)
