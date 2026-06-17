"""Seed 60 days of realistic historical sales data for demo/evaluation purposes."""

from __future__ import annotations

import random
from datetime import date, datetime, time as dtime, timedelta
from typing import Any

from alembic import op
from sqlalchemy import text

revision: str = "0009_seed_historical_data"
down_revision: str = "0008_closing_business_date"
branch_labels = None
depends_on = None

DAYS_BACK = 60
_SEED = 2024


def _people_for_day(d: date) -> int:
    """Returns expected number of people for the day. 0 = closed (Sunday)."""
    wd = d.weekday()
    if wd == 6:   return 0                         # Domingo — cerrado
    if wd == 4:   return random.randint(18, 28)    # Viernes
    if wd == 5:   return random.randint(22, 30)    # Sábado
    if wd == 0:   return random.randint(3, 6)      # Lunes
    return random.randint(5, 10)                   # Mar–Jue


def _make_sittings(n: int) -> list[int]:
    groups: list[int] = []
    while n > 0:
        size = min(random.randint(2, 5), n)
        groups.append(size)
        n -= size
    return groups


def upgrade() -> None:
    conn = op.get_bind()

    # Idempotency: skip if historical data already exists
    count = conn.execute(
        text("SELECT COUNT(*) FROM closings WHERE closing_time < NOW() - INTERVAL '1 day'")
    ).scalar()
    if count and count > 0:
        return

    # Resolve admin user
    row = conn.execute(
        text("SELECT id FROM \"user\" WHERE role = 'admin' ORDER BY id LIMIT 1")
    ).fetchone()
    if row is None:
        row = conn.execute(text('SELECT id FROM "user" ORDER BY id LIMIT 1')).fetchone()
    if row is None:
        return
    admin_id: int = row[0]

    # Resolve products
    prods = conn.execute(
        text("SELECT id, name, type, price, unit FROM products ORDER BY type, id")
    ).fetchall()
    if not prods:
        return

    by_type: dict[str, list] = {}
    for p in prods:
        by_type.setdefault(p[2], []).append(p)

    cervezas = by_type.get("cerveza", [])
    comidas  = by_type.get("comida", [])
    tragos   = by_type.get("trago", [])
    bebidas  = by_type.get("bebida", [])

    # Resolve tables
    tables = conn.execute(
        text(
            "SELECT id, table_number, table_name FROM open_tables "
            "WHERE deleted_at IS NULL ORDER BY table_number"
        )
    ).fetchall()
    if not tables:
        return

    random.seed(_SEED)
    today = date.today()

    closing_rows: list[dict[str, Any]] = []
    item_rows_by_closing: list[tuple[int, list[dict[str, Any]]]] = []
    payment_rows_by_closing: list[tuple[int, str, int]] = []

    for days_ago in range(DAYS_BACK, 0, -1):
        d = today - timedelta(days=days_ago)
        n_people = _people_for_day(d)
        if n_people == 0:
            continue  # closed day

        sittings = _make_sittings(n_people)

        for i, group_size in enumerate(sittings):
            tid, tnum, tname = tables[i % len(tables)]

            open_h = random.randint(19, 23)
            open_m = random.randint(0, 59)
            duration_min = random.randint(70, 160)

            open_dt  = datetime.combine(d, dtime(open_h, open_m))
            close_dt = open_dt + timedelta(minutes=duration_min)

            items: list[dict[str, Any]] = []

            if cervezas:
                for _ in range(group_size):
                    n_beers = random.choices([1, 2, 3], weights=[35, 50, 15])[0]
                    for _ in range(n_beers):
                        p = random.choice(cervezas)
                        items.append({"pid": p[0], "name": p[1], "type": p[2],
                                      "price": p[3], "unit": p[4], "qty": 1})

            if comidas and group_size >= 2:
                for _ in range(random.randint(0, max(1, group_size // 2))):
                    p = random.choice(comidas)
                    items.append({"pid": p[0], "name": p[1], "type": p[2],
                                  "price": p[3], "unit": p[4], "qty": 1})

            if tragos:
                for _ in range(group_size):
                    if random.random() < 0.25:
                        p = random.choice(tragos)
                        items.append({"pid": p[0], "name": p[1], "type": p[2],
                                      "price": p[3], "unit": p[4], "qty": 1})

            if bebidas:
                for _ in range(group_size):
                    if random.random() < 0.15:
                        p = random.choice(bebidas)
                        items.append({"pid": p[0], "name": p[1], "type": p[2],
                                      "price": p[3], "unit": p[4], "qty": 1})

            if not items:
                continue

            subtotal = sum(it["price"] * it["qty"] for it in items)

            r = random.random()
            if r < 0.40:
                method, discount = "efectivo", int(subtotal * 0.10)
            elif r < 0.75:
                method, discount = "mercado_pago", 0
            elif r < 0.90:
                method, discount = "tarjeta_debito", 0
            else:
                method, discount = "tarjeta_credito", 0

            total = subtotal - discount
            cidx = len(closing_rows)

            closing_rows.append({
                "table_id":         tid,
                "table_number":     tnum,
                "table_name":       tname,
                "opening_time":     open_dt,
                "closing_time":     close_dt,
                "business_date":    d,
                "people":           group_size,
                "served_by":        admin_id,
                "subtotal":         subtotal,
                "discount":         discount,
                "total":            total,
                "status":           "cerrada",
                "invoicing_status": "SALE_REGISTERED",
            })
            item_rows_by_closing.append((cidx, items))
            payment_rows_by_closing.append((cidx, method, total, close_dt))

    if not closing_rows:
        return

    closing_ids: list[int] = []
    for row in closing_rows:
        result = conn.execute(
            text(
                """
                INSERT INTO closings (
                    table_id, table_number, table_name,
                    opening_time, closing_time, business_date,
                    people, served_by, subtotal, discount, total,
                    status, invoicing_status
                ) VALUES (
                    :table_id, :table_number, :table_name,
                    :opening_time, :closing_time, :business_date,
                    :people, :served_by, :subtotal, :discount, :total,
                    :status, :invoicing_status
                ) RETURNING id
                """
            ),
            row,
        )
        closing_ids.append(result.fetchone()[0])

    all_items: list[dict[str, Any]] = []
    for cidx, items in item_rows_by_closing:
        cid = closing_ids[cidx]
        for it in items:
            all_items.append({
                "closing_id":   cid,
                "product_id":   it["pid"],
                "product_name": it["name"],
                "product_type": it["type"],
                "unit":         it["unit"],
                "quantity":     it["qty"],
                "unit_price":   it["price"],
                "subtotal":     it["price"] * it["qty"],
            })

    if all_items:
        conn.execute(
            text(
                """
                INSERT INTO closing_items
                    (closing_id, product_id, product_name, product_type,
                     unit, quantity, unit_price, subtotal)
                VALUES
                    (:closing_id, :product_id, :product_name, :product_type,
                     :unit, :quantity, :unit_price, :subtotal)
                """
            ),
            all_items,
        )

    payment_rows: list[dict[str, Any]] = [
        {"closing_id": closing_ids[cidx], "method": method, "amount": amount, "created_at": close_dt}
        for cidx, method, amount, close_dt in payment_rows_by_closing
    ]
    if payment_rows:
        conn.execute(
            text(
                "INSERT INTO closing_payments (closing_id, method, amount, created_at) "
                "VALUES (:closing_id, :method, :amount, :created_at)"
            ),
            payment_rows,
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "DELETE FROM closings "
            "WHERE invoicing_status = 'SALE_REGISTERED' "
            "AND closing_time < NOW() - INTERVAL '1 day'"
        )
    )
