import logging

from aiogram import BaseMiddleware

from typing import (
    Any,
    Awaitable,
    Callable,
)

from database.database import db
from database import queries

from services.afk import settle_activity


logger = logging.getLogger(__name__)


class EconomyActivityMiddleware(
    BaseMiddleware
):

    async def __call__(
        self,
        handler: Callable[
            [Any, dict],
            Awaitable[Any]
        ],
        event: Any,
        data: dict
    ):

        user_id = getattr(
            getattr(
                event,
                "from_user",
                None
            ),
            "id",
            None
        )

        if user_id:

            try:

                async with db.connect() as conn:

                    user = (
                        await queries
                        .get_user_by_telegram_id(
                            conn,
                            user_id
                        )
                    )

                    if user:

                        try:

                            (
                                income,
                                produced,
                                elapsed,
                                star_units
                            ) = await settle_activity(
                                conn,
                                user.id
                            )

                            await conn.commit()

                            # =================================
                            # СООБЩЕНИЕ ПОСЛЕ AFK
                            # =================================

                            # Показываем только если человек
                            # отсутствовал хотя бы минуту.
                            if elapsed >= 60:

                                minutes = int(
                                    elapsed // 60
                                )

                                if minutes >= 60:
                                    afk_time = "1 час"
                                else:
                                    afk_time = (
                                        f"{minutes} мин."
                                    )

                                text = (
                                    "💤 <b>Вы вернулись!</b>\n\n"
                                    f"⏱ AFK: "
                                    f"<b>{afk_time}</b>\n"
                                    f"💵 Заработано: "
                                    f"<b>{income}$</b>"
                                )

                                if star_units:

                                    stars = (
                                        star_units / 100
                                    )

                                    text += (
                                        f"\n⭐ Заработано: "
                                        f"<b>{stars:g} ⭐</b>"
                                    )

                                if produced:

                                    text += (
                                        "\n\n"
                                        "📦 Получено ресурсов:"
                                    )

                                    for (
                                        resource,
                                        amount
                                    ) in produced.items():

                                        text += (
                                            f"\n• "
                                            f"{resource}: "
                                            f"+{amount}"
                                        )

                                # Message
                                if isinstance(
                                    event,
                                    type(None)
                                ):
                                    pass

                                elif hasattr(
                                    event,
                                    "answer"
                                ):

                                    try:

                                        await event.answer(
                                            text,
                                            parse_mode="HTML"
                                        )

                                    except Exception:

                                        # Для CallbackQuery
                                        # event.answer() — это
                                        # callback alert, поэтому
                                        # отправляем нормальное
                                        # сообщение в чат.

                                        if (
                                            hasattr(
                                                event,
                                                "message"
                                            )
                                            and event.message
                                        ):

                                            await (
                                                event.message
                                                .answer(
                                                    text,
                                                    parse_mode="HTML"
                                                )
                                            )

                        except Exception:

                            logger.warning(
                                "settle_activity "
                                "failed for user_id=%s",
                                user_id,
                                exc_info=True
                            )

            except Exception:

                logger.warning(
                    "DB unavailable while "
                    "settling activity "
                    "for user_id=%s",
                    user_id,
                    exc_info=True
                )

        return await handler(
            event,
            data
        )
