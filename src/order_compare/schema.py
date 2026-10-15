"""Shared case and proposal shapes across providers."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrderCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    customer_request: str = Field(min_length=1)
    issue: Literal["damaged", "address_change", "delivery_delay"]
    shipped: bool
    captured_cents: int = Field(ge=0)
    refunded_cents: int = Field(ge=0)
    replacement_stock: int = Field(ge=0)


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: str
    action: Literal["replace", "refund", "contact", "deny"]
    amount_cents: int = Field(ge=0)
    reason: str = Field(min_length=5)
