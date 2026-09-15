import logging
from aiogram import BaseMiddleware
from typing import Any, Awaitable, Callable
from database.database import db
from database import queries
from services.afk import settle_activity
from services.businesses import get_business_info

logger = logging.getLogger(__name__)


class EconomyActivityMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[Any, dict], Awaitable[Any]], event: Any, data: dict):
        user_id = getattr(getattr(event, 'from_user', None), 'id', None)
        if user_id:
            try:
                async with db.connect() as conn:
                    user = await queries.get_user_by_telegram_id(conn, user_id)
                    if user:
                        try:
                            income, produced, elapsed, star_units = await settle_activity(conn, user.id)
                            await conn.commit()

                            # Show an AFK report only after the bot has actually
                            # considered the user inactive. This avoids spam on
                            # normal button presses and makes the report useful.
                            if elapsed >= 10 * 60:
                                minutes = int(elapsed // 60)
                                hours, mins = divmod(minutes, 60)
                                time_text = f"{hours} ч. {mins} мин." if hours else f"{mins} мин."
                                parts = [f"💤 <b>AFK завершён</b>\n⏱ В AFK: <code>{time_text}</code>",
                                         f"💵 Заработано: <code>{income}$</code>"]
                                if star_units:
                                    if star_units % 100 == 0:
                                        stars_text = str(star_units // 100)
                                    else:
                                        stars_text = f"{star_units / 100:.2f}".rstrip('0').rstrip('.')
                                    parts.append(f"⭐ Заработано: <code>{stars_text} ⭐</code>")
                                resource_labels = {'stone': '🪨 Камень', 'wood': '🌲 Дерево', 'food': '🌾 Еда', 'ore': '⛏️ Руда'}
                                for resource, amount in produced.items():
                                    if amount:
                                        parts.append(f"{resource_labels.get(resource, resource)}: <code>+{amount}</code>")
                                if elapsed >= 60 * 60:
                                    parts.append("\nℹ️ Максимальный AFK-фарм за один период — 1 час.")
                                target_message = getattr(event, 'message', None) or event
                                answer = getattr(target_message, 'answer', None)
                                if answer:
                                    await answer('\n'.join(parts), parse_mode='HTML')
                        except Exception:
                            # Don't manually rollback here: if this failed
                            # because the connection itself died mid-query,
                            # rollback() on the same dead connection just
                            # raises a second error. `db.connect()` exiting
                            # abnormally already lets the pool deal with the
                            # connection correctly (see database.py).
                            logger.warning("settle_activity failed for user_id=%s", user_id, exc_info=True)
            except Exception:
                # AFK income settlement is a side effect, not the thing the
                # user is waiting for. A transient DB blip here (network hiccup,
                # a connection being recycled) should never stop the user's
                # actual button press/command from being handled.
                logger.warning("DB unavailable while settling activity for user_id=%s", user_id, exc_info=True)
        return await handler(event, data)
