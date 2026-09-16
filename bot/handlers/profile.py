from datetime import datetime, timezone
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import queries
from database.database import db
from keyboards.main import main_menu_keyboard
import config

from services.economy import calculate_income_per_minute
from services.quests import format_stars


router = Router()


def vip_remaining(user):
    if not user.vip_type or not user.vip_expires_at:
        return None

    try:
        end = datetime.fromisoformat(
            user.vip_expires_at
        )

        if end.tzinfo is None:
            end = end.replace(
                tzinfo=timezone.utc
            )

        left = max(
            0,
            int(
                (
                    end
                    - datetime.now(timezone.utc)
                ).total_seconds()
            )
        )

        if left <= 0:
            return None

        return left

    except ValueError:
        return None


def format_profile_text(
    user,
    resources,
    businesses,
    cases
):
    from services.businesses import (
        get_business_info,
        business_income_per_minute,
        vip_multiplier,
    )

    # =========================================================
    # ДОХОД БИЗНЕСОВ
    # =========================================================
    #
    # ВАЖНО:
    # Все значения бизнеса уже указаны ЗА МИНУТУ.
    #
    # Поэтому здесь НЕЛЬЗЯ умножать на 60.
    #
    # Например:
    # Ларёк = 50$/мин
    # Завод 4 уровня = 350$/мин
    #
    # Итог:
    # 50 + 350 = 400$/мин
    #

    base = sum(
        (
            business_income_per_minute(
                get_business_info(
                    business.business_type
                ),
                business.level
            )
            * business.quantity

            for business in businesses

            if get_business_info(
                business.business_type
            )
        ),
        Decimal("0")
    )

    income = (
        base
        * Decimal(
            str(
                vip_multiplier(
                    user.vip_type,
                    user.vip_expires_at
                )
            )
        )
    )

    income_text = format(
        income,
        "f"
    ).rstrip("0").rstrip(".")

    # =========================================================
    # РЕФЕРАЛЬНАЯ ССЫЛКА
    # =========================================================

    referral = (
        f"<a href='https://t.me/"
        f"{config.BOT_USERNAME}"
        f"?start={user.referral_code}'>"
        f"пригласить друга"
        f"</a>"
        if config.BOT_USERNAME
        else f"<code>{user.referral_code}</code>"
    )

    count = sum(
        business.quantity
        for business in businesses
    )

    vip = vip_remaining(user)

    if vip:
        vip_text = (
            f"VIP {user.vip_type.title()}\n"
            f"⏳ Осталось: "
            f"{vip // 86400} дн. "
            f"{(vip % 86400) // 3600} ч."
        )
    else:
        vip_text = "Нет"

    # =========================================================
    # ПРОФИЛЬ
    # =========================================================

    return (
        f"👤 <b>Профиль</b>\n\n"

        f"👤 Никнейм: "
        f"<code>{user.nickname}</code>\n\n"

        f"💵 Деньги: "
        f"<code>{user.money}$</code>\n"

        f"⭐ Звёзды: "
        f"<code>{format_stars(user.stars)} ⭐</code>\n"

        f"📦 <b>Ресурсы</b>\n\n"

        f"🪨 Камень: "
        f"<code>{resources.stone}</code>\n"

        f"🌲 Дерево: "
        f"<code>{resources.wood}</code>\n"

        f"🌾 Еда: "
        f"<code>{resources.food}</code>\n"

        f"⛏️ Руда: "
        f"<code>{resources.ore}</code>\n\n"

        f"🛡 Привилегия: "
        f"<code>{vip_text}</code>\n"

        f"🏠 Дом: "
        f"<code>"
        f"{user.house_id if user.house_id else 'Нет'}"
        f"</code>\n"

        f"🏭 Бизнесов: "
        f"<code>{count}</code>\n"

        # ИМЕННО МИНУТА.
        f"💰 Доход в минуту: "
        f"<code>{income_text}$/мин</code>\n\n"

        f"🎁 Кейсы: "
        f"<code>"
        f"{cases['money_cases']} 💵 / "
        f"{cases['star_cases']} ⭐"
        f"</code>\n\n"

        f"🔗 Реферальная ссылка: "
        f"{referral}"
    )


async def render_profile(user_id):
    async with db.connect() as conn:
        user = await queries.get_user_by_id(
            conn,
            user_id
        )

        resources = await queries.get_resources(
            conn,
            user_id
        )

        businesses = await queries.get_businesses(
            conn,
            user_id
        )

        cases = await queries.get_case_inventory(
            conn,
            user_id
        )

    return format_profile_text(
        user,
        resources,
        businesses,
        cases
    )


async def show_profile(
    message,
    user_id
):
    await message.answer(
        await render_profile(user_id),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )


async def edit_to_profile(
    callback,
    user_id
):
    await callback.message.edit_text(
        await render_profile(user_id),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )


async def _get_authorized_user_id(
    callback,
    state
):
    async with db.connect() as conn:
        user = await queries.get_user_by_telegram_id(
            conn,
            callback.from_user.id
        )

    if not user:
        await callback.answer(
            "Сначала войдите в аккаунт: /start",
            show_alert=True
        )

        return None

    return user.id


@router.callback_query(
    F.data == "back:main"
)
async def cb_back_main(
    callback: CallbackQuery,
    state: FSMContext
):
    await state.clear()

    uid = await _get_authorized_user_id(
        callback,
        state
    )

    if uid is not None:
        await edit_to_profile(
            callback,
            uid
        )

        await callback.answer()
