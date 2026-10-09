from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.payment import PaymentStatus
from app.models.user import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: UUID
    sku_id: UUID
    quantity: int = Field(ge=1, le=99)


class OrderCreate(BaseModel):
    store_id: UUID
    items: list[OrderItemCreate] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_unique_items(self) -> "OrderCreate":
        keys = [(item.product_id, item.sku_id) for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("订单商品不能重复")
        return self


class WechatPaymentParameters(BaseModel):
    order_id: UUID
    payment_id: UUID
    timeStamp: str
    nonceStr: str
    package: str
    signType: Literal["RSA"] = "RSA"
    paySign: str


class OrderPaymentStatusResponse(BaseModel):
    order_id: UUID
    order_status: OrderStatus
    payment_status: PaymentStatus | None
