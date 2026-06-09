import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app
from shared.time_utils import local_today


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="La prueba de integración requiere la base temporal de Compose",
)


def _login(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/auth",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_full_business_flow_against_postgresql():
    suffix = uuid4().hex[:8]

    with TestClient(app) as client:
        admin_headers = _login(client, "admin", "admin")
        seeded_products = client.get(
            "/products/all",
            headers=admin_headers,
        )
        assert seeded_products.status_code == 200
        assert any(
            product["name"] == "Empanadas"
            for product in seeded_products.json()
        )

        employee_username = f"empleado-{suffix}"
        register = client.post(
            "/auth/register",
            headers=admin_headers,
            json={
                "username": employee_username,
                "password": "empleado",
                "role": "empleado",
            },
        )
        assert register.status_code == 200, register.text

        product = client.post(
            "/products/create",
            headers=admin_headers,
            json={
                "name": f"IPA Smoke {suffix}",
                "type": "cerveza",
                "price": 1000,
                "qty": 10,
                "unit": "pinta",
                "minimum_qty": 2,
                "capacity_qty": 20,
            },
        )
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        adjustment = client.post(
            f"/stock/products/{product_id}/adjustments",
            headers=admin_headers,
            json={
                "quantity_delta": 5,
                "movement_type": "reposicion",
                "note": "Smoke test",
            },
        )
        assert adjustment.status_code == 200, adjustment.text
        assert adjustment.json()["current_qty"] == 15

        employee_headers = _login(client, employee_username, "empleado")
        table_number = 900
        table = client.post(
            "/tables",
            headers=employee_headers,
            json={
                "table_number": table_number,
                "table_name": "Smoke",
                "people": 0,
            },
        )
        assert table.status_code == 201, table.text

        assert client.get(
            "/products/all",
            headers=employee_headers,
        ).status_code == 200
        assert client.get(
            "/tables",
            headers=employee_headers,
        ).status_code == 200
        assert client.get(
            "/kpis/summary",
            headers=employee_headers,
        ).status_code == 403
        assert client.post(
            "/products/create",
            headers=employee_headers,
            json={
                "name": "Prohibido",
                "type": "comida",
                "price": 1,
                "qty": 0,
                "unit": "unidad",
            },
        ).status_code == 403
        assert client.post(
            "/auth/register",
            headers=employee_headers,
            json={
                "username": "prohibido",
                "password": "prohibido",
                "role": "admin",
            },
        ).status_code == 403

        empty_table_number = 901
        assert client.post(
            "/tables",
            headers=employee_headers,
            json={"table_number": empty_table_number, "people": 0},
        ).status_code == 201
        assert client.patch(
            f"/tables/{empty_table_number}/occupancy",
            headers=employee_headers,
            json={"people": 2},
        ).status_code == 200
        empty_close = client.post(
            f"/tables/{empty_table_number}/close",
            headers=employee_headers,
            json={"payments": []},
        )
        assert empty_close.status_code == 200, empty_close.text
        assert empty_close.json()["closing"]["total"] == 0

        for method, amount, expected_total in (
            ("efectivo", 1000, 900),
            ("tarjeta_debito", 1000, 1000),
        ):
            occupy = client.patch(
                f"/tables/{table_number}/occupancy",
                headers=employee_headers,
                json={"people": 2},
            )
            assert occupy.status_code == 200, occupy.text

            order = client.post(
                f"/tables/{table_number}/items",
                headers=employee_headers,
                json=[{"product_id": product_id, "quantity": 1}],
            )
            assert order.status_code == 201, order.text

            close = client.post(
                f"/tables/{table_number}/close",
                headers=employee_headers,
                json={
                    "payments": [
                        {"method": method, "amount": amount}
                    ]
                },
            )
            assert close.status_code == 200, close.text
            assert close.json()["closing"]["total"] == expected_total
            assert close.json()["closing"]["amount_received"] == amount
            assert (
                close.json()["closing"]["change"]
                == amount - expected_total
            )
            if method != "efectivo":
                assert close.json()["afip_authorized"] is True
                assert (
                    close.json()["closing"]["invoice"]["status"]
                    == "autorizada"
                )

        invoices = client.get("/invoices", headers=admin_headers)
        assert invoices.status_code == 200
        assert len(invoices.json()) == 1
        assert len(invoices.json()[0]["attempts"]) == 1

        goal = client.post(
            "/goals",
            headers=admin_headers,
            json={
                "period": "diario",
                "target_amount": 5000,
                "description": "Smoke",
            },
        )
        assert goal.status_code == 201, goal.text
        assert goal.json()["current_sales"] == 1900

        kpis = client.get("/kpis/summary", headers=admin_headers)
        assert kpis.status_code == 200
        assert kpis.json()["daily"]["total_sales"] == 1900
        assert kpis.json()["employee_performance"][0]["username"] == (
            employee_username
        )
        assert kpis.json()["employee_performance"][0]["closed_tables"] == 3

        cash_closing = client.post(
            "/cash-closings",
            headers=admin_headers,
            json={
                "business_date": local_today().isoformat(),
                "counted_cash": 900,
                "notes": "Smoke test",
            },
        )
        assert cash_closing.status_code == 201, cash_closing.text
        assert cash_closing.json()["difference"] == 0
        assert cash_closing.json()["total_sales"] == 1900
        assert cash_closing.json()["sales_count"] == 3
        assert client.post(
            "/cash-closings",
            headers=admin_headers,
            json={"business_date": "2026-06-08", "notes": "Sin efectivo"},
        ).status_code == 422

        cash_closing_id = cash_closing.json()["id"]
        corrected_cash_closing = client.patch(
            f"/cash-closings/{cash_closing_id}",
            headers=admin_headers,
            json={"counted_cash": 0, "notes": "Conteo corregido"},
        )
        assert corrected_cash_closing.status_code == 200
        assert corrected_cash_closing.json()["counted_cash"] == 0
        revisions = client.get(
            f"/cash-closings/{cash_closing_id}/revisions",
            headers=admin_headers,
        )
        assert revisions.status_code == 200
        assert len(revisions.json()) == 1

        assert client.delete(
            f"/tables/{table_number}",
            headers=employee_headers,
        ).status_code == 204
        assert client.delete(
            f"/tables/{empty_table_number}",
            headers=employee_headers,
        ).status_code == 204

        users = client.get("/users", headers=admin_headers).json()
        admin_id = next(user["id"] for user in users if user["role"] == "admin")
        employee_id = next(
            user["id"]
            for user in users
            if user["username"] == employee_username
        )
        updated_username = f"actualizado-{suffix}"
        update_user = client.patch(
            f"/users/{employee_id}",
            headers=admin_headers,
            json={
                "username": updated_username,
                "password": "nueva-clave",
                "role": "empleado",
            },
        )
        assert update_user.status_code == 200, update_user.text
        assert update_user.json()["username"] == updated_username
        assert _login(
            client,
            updated_username,
            "nueva-clave",
        )["Authorization"].startswith("Bearer ")
        assert client.delete(
            f"/users/{admin_id}",
            headers=admin_headers,
        ).status_code == 409
        assert client.delete(
            f"/users/{employee_id}",
            headers=admin_headers,
        ).status_code == 204
        assert client.post(
            "/auth",
            json={"username": updated_username, "password": "nueva-clave"},
        ).status_code == 400

        delete_product = client.delete(
            f"/products/{product_id}",
            headers=admin_headers,
        )
        assert delete_product.status_code == 204, delete_product.text
