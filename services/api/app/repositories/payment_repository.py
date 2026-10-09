from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payment import Payment, PaymentStatus
from app.models.user import IdentityProvider, Order, ProviderAccount


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_order(
        self,
        *,
        order_id: UUID,
        user_id: UUID,
        for_update: bool = False,
    ) -> Order | None:
        statement = (
            select(Order)
            .where(Order.id == order_id, Order.user_id == user_id)
            .options(selectinload(Order.items), selectinload(Order.payments))
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Order | None, await self.session.scalar(statement))

    async def get_payment_by_merchant_order_no(
        self,
        merchant_order_no: str,
        *,
        for_update: bool = False,
    ) -> Payment | None:
        statement = (
            select(Payment)
            .where(Payment.merchant_order_no == merchant_order_no)
            .options(selectinload(Payment.order).selectinload(Order.items))
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Payment | None, await self.session.scalar(statement))

    async def get_order_by_id_for_update(self, order_id: UUID) -> Order | None:
        return cast(
            Order | None,
            await self.session.scalar(
                select(Order)
                .where(Order.id == order_id)
                .options(selectinload(Order.items), selectinload(Order.payments))
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    async def list_other_pending_payments_for_update(
        self,
        *,
        order_id: UUID,
        payment_id: UUID,
    ) -> list[Payment]:
        return list(
            (
                await self.session.scalars(
                    select(Payment)
                    .where(
                        Payment.order_id == order_id,
                        Payment.id != payment_id,
                        Payment.status == PaymentStatus.PENDING,
                    )
                    .order_by(Payment.attempt_no)
                    .with_for_update()
                )
            ).all()
        )

    async def get_wechat_openid(self, user_id: UUID) -> str | None:
        return cast(
            str | None,
            await self.session.scalar(
                select(ProviderAccount.provider_subject).where(
                    ProviderAccount.user_id == user_id,
                    ProviderAccount.provider == IdentityProvider.WEAPP,
                )
            ),
        )
