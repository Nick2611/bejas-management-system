from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


BUSINESS_TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


def local_now() -> datetime:
    return datetime.now(BUSINESS_TIMEZONE).replace(tzinfo=None)


def local_today() -> date:
    return datetime.now(BUSINESS_TIMEZONE).date()


def day_bounds(value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(value, time.min)
    return start, start + timedelta(days=1)


def period_dates(
    period: str,
    reference_date: date | None = None,
) -> tuple[date, date]:
    reference = reference_date or local_today()
    if period == "diario":
        return reference, reference
    if period == "semanal":
        start = reference - timedelta(days=reference.weekday())
        return start, start + timedelta(days=6)
    if period == "mensual":
        start = reference.replace(day=1)
        next_month = (
            start.replace(year=start.year + 1, month=1)
            if start.month == 12
            else start.replace(month=start.month + 1)
        )
        return start, next_month - timedelta(days=1)
    raise ValueError(f"Período desconocido: {period}")
