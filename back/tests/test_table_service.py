import sys
import unittest
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tables.models.table_models import (
    AddProductRequest,
    CreateTableRequest,
    OccupyTableRequest,
    RemovePeopleRequest,
    RemoveProductRequest,
)
from tables.service.table_service import TableService


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.deleted = []
        self.added = []

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def delete(self, entity):
        self.deleted.append(entity)

    def add(self, entity):
        self.added.append(entity)


class TableServiceTest(unittest.TestCase):
    def setUp(self):
        self.session = FakeSession()
        self.service = TableService(session=self.session)
        self.service.repository = MagicMock()

    def test_create_table_is_independent_from_fiscal_declarations(self):
        self.service.repository.get_any_by_number.return_value = None

        table = self.service.create_table(CreateTableRequest(table_number=9))

        self.assertEqual(table.table_number, 9)
        self.assertEqual(self.session.commits, 1)
        self.service.repository.add.assert_called_once_with(table)

    def test_occupy_table_is_independent_from_fiscal_declarations(self):
        table = SimpleNamespace(
            table_number=4,
            people=0,
            items=[],
            opening_time=None,
        )
        self.service.repository.get_by_number.return_value = table

        result = self.service.occupy_table(
            4,
            OccupyTableRequest(people=2),
        )

        self.assertEqual(result.people, 2)
        self.assertIsNotNone(result.opening_time)
        self.assertEqual(self.session.commits, 1)

    @patch("tables.service.table_service.ProductsRepository")
    def test_add_products_is_independent_from_fiscal_declarations(
        self,
        products_repository_class,
    ):
        table = SimpleNamespace(id=1, table_number=4, items=[])
        product = SimpleNamespace(
            id=2,
            name="IPA",
            type="cerveza",
            unit="pinta",
            price=1000,
            qty=10,
        )
        self.service.repository.get_by_number.return_value = table
        products_repository_class.return_value.get_active_by_id.return_value = (
            product
        )
        original_commit = self.session.commit

        def assign_item_ids():
            for index, item in enumerate(table.items, 1):
                item.id = index
                item.product_id = product.id
            original_commit()

        self.session.commit = assign_item_ids

        response = self.service.add_products(
            4,
            [AddProductRequest(product_id=2, quantity=1)],
        )

        self.assertEqual(response.table_number, 4)
        self.assertEqual(product.qty, 9)
        self.assertEqual(len(table.items), 1)
        self.assertEqual(self.session.commits, 1)

    @patch("tables.service.table_service.ProductsRepository")
    def test_remove_product_reduces_quantity_and_restores_stock(
        self,
        products_repository_class,
    ):
        table = SimpleNamespace(id=1, table_number=4)
        item = SimpleNamespace(id=10, product_id=20, quantity=3)
        product = SimpleNamespace(id=20, qty=7)
        self.service.repository.get_by_number.return_value = table
        self.service.repository.get_item.return_value = item
        products_repository_class.return_value.get_active_by_id.return_value = (
            product
        )

        response = self.service.remove_product(
            number=4,
            item_id=10,
            payload=RemoveProductRequest(quantity_to_remove=2),
        )

        self.assertEqual(item.quantity, 1)
        self.assertEqual(product.qty, 9)
        self.assertEqual(response.remaining_quantity, 1)
        self.assertEqual(self.session.commits, 1)
        self.assertEqual(self.session.deleted, [])
        self.assertEqual(len(self.session.added), 1)
        self.assertEqual(self.session.added[0].movement_type, "devolucion_mesa")
        self.assertEqual(self.session.added[0].quantity_delta, 2)

    @patch("tables.service.table_service.ProductsRepository")
    def test_remove_product_deletes_item_when_quantity_reaches_zero(
        self,
        products_repository_class,
    ):
        table = SimpleNamespace(id=1, table_number=4)
        item = SimpleNamespace(id=10, product_id=20, quantity=3)
        product = SimpleNamespace(id=20, qty=7)
        self.service.repository.get_by_number.return_value = table
        self.service.repository.get_item.return_value = item
        products_repository_class.return_value.get_active_by_id.return_value = (
            product
        )

        response = self.service.remove_product(
            number=4,
            item_id=10,
            payload=RemoveProductRequest(quantity_to_remove=3),
        )

        self.assertEqual(product.qty, 10)
        self.assertEqual(response.remaining_quantity, 0)
        self.assertEqual(self.session.deleted, [item])
        self.assertEqual(self.session.commits, 1)
        self.assertEqual(len(self.session.added), 1)

    @patch("tables.service.table_service.ProductsRepository")
    def test_remove_product_rejects_quantity_above_current_amount(
        self,
        products_repository_class,
    ):
        table = SimpleNamespace(id=1, table_number=4)
        item = SimpleNamespace(id=10, product_id=20, quantity=2)
        self.service.repository.get_by_number.return_value = table
        self.service.repository.get_item.return_value = item

        with self.assertRaises(HTTPException) as context:
            self.service.remove_product(
                number=4,
                item_id=10,
                payload=RemoveProductRequest(quantity_to_remove=3),
            )

        self.assertEqual(context.exception.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(self.session.commits, 0)
        products_repository_class.assert_not_called()

    def test_remove_people_can_leave_table_empty(self):
        table = SimpleNamespace(id=1, table_number=4, people=2)
        self.service.repository.get_by_number.return_value = table

        response = self.service.remove_people(
            number=4,
            payload=RemovePeopleRequest(quantity_to_remove=2),
        )

        self.assertEqual(table.people, 0)
        self.assertEqual(response.previous_people, 2)
        self.assertEqual(response.current_people, 0)
        self.assertEqual(self.session.commits, 1)

    def test_remove_people_rejects_negative_result(self):
        table = SimpleNamespace(id=1, table_number=4, people=1)
        self.service.repository.get_by_number.return_value = table

        with self.assertRaises(HTTPException) as context:
            self.service.remove_people(
                number=4,
                payload=RemovePeopleRequest(quantity_to_remove=2),
            )

        self.assertEqual(context.exception.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(table.people, 1)
        self.assertEqual(self.session.commits, 0)

    def test_remove_people_handles_legacy_null_value_as_empty(self):
        table = SimpleNamespace(id=1, table_number=4, people=None)
        self.service.repository.get_by_number.return_value = table

        with self.assertRaises(HTTPException) as context:
            self.service.remove_people(
                number=4,
                payload=RemovePeopleRequest(quantity_to_remove=1),
            )

        self.assertEqual(context.exception.status_code, HTTPStatus.CONFLICT)
        self.assertIsNone(table.people)
        self.assertEqual(self.session.commits, 0)

    def test_delete_free_table_uses_soft_delete(self):
        table = SimpleNamespace(
            id=1,
            table_number=4,
            people=0,
            items=[],
            deleted_at=None,
        )
        self.service.repository.get_by_number.return_value = table

        self.service.delete_table(4)

        self.assertIsNotNone(table.deleted_at)
        self.assertEqual(self.session.commits, 1)

    def test_delete_occupied_table_is_rejected(self):
        table = SimpleNamespace(
            id=1,
            table_number=4,
            people=2,
            items=[],
            deleted_at=None,
        )
        self.service.repository.get_by_number.return_value = table

        with self.assertRaises(HTTPException) as context:
            self.service.delete_table(4)

        self.assertEqual(context.exception.status_code, HTTPStatus.CONFLICT)
        self.assertIsNone(table.deleted_at)
        self.assertEqual(self.session.commits, 0)


if __name__ == "__main__":
    unittest.main()
