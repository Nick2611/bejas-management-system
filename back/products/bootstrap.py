import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.db_conn import engine
from db.db_models import ProductInventorySettingsModel, ProductModel
from shared.time_utils import local_now


SEED_PATH = Path(__file__).with_name("products_seed.json")


def initialize_products() -> None:
    with Session(engine) as session:
        existing_names = {
            name.lower()
            for name in session.scalars(
                select(func.lower(ProductModel.name))
            ).all()
        }

        products = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        for data in products:
            if data["name"].lower() in existing_names:
                continue
            product = ProductModel(
                name=data["name"],
                type=data["type"],
                price=data["price"],
                qty=data["qty"],
                unit=data["unit"],
            )
            product.inventory_settings = ProductInventorySettingsModel(
                minimum_qty=data["minimum_qty"],
                capacity_qty=data["capacity_qty"],
                last_restocked_at=local_now() if data["qty"] > 0 else None,
                deleted_at=None,
            )
            session.add(product)
            existing_names.add(data["name"].lower())

        session.commit()
