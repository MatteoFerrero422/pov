from decimal import Decimal

from services.businesses import (
    business_income_per_minute,
    get_business_info,
    business_stars_per_minute,
    vip_multiplier,
)


def calculate_income_per_minute(
    instances,
    vip_type=None,
    vip_expires_at=None
):
    """
    Считает общий денежный доход ЗА МИНУТУ.

    Пример:

    Ларёк = 50$/мин
    Завод L4 = 350$/мин

    Результат:
    400$/мин
    """

    base = Decimal("0")

    for business in instances:

        info = get_business_info(
            business["business_type"]
        )

        if not info:
            continue

        base += (
            business_income_per_minute(
                info,
                business["level"]
            )
        )

    return (
        base
        * Decimal(
            str(
                vip_multiplier(
                    vip_type,
                    vip_expires_at
                )
            )
        )
    )


def calculate_star_income_per_minute(
    instances
):
    """
    Считает доход ⭐ ЗА МИНУТУ.
    """

    total = Decimal("0")

    for business in instances:

        info = get_business_info(
            business["business_type"]
        )

        if not info:
            continue

        total += (
            business_stars_per_minute(
                info,
                business["level"]
            )
        )

    return total
