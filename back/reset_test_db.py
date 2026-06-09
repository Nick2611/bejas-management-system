from sqlalchemy import text

from db.db_conn import engine


def reset_test_database() -> None:
    if engine.url.database != "bejas-test":
        raise RuntimeError(
            "reset_test_db.py sólo puede ejecutarse sobre bejas-test"
        )

    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))


if __name__ == "__main__":
    reset_test_database()
