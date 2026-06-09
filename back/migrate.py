from alembic import command
from alembic.config import Config


def run_migrations() -> None:
    command.upgrade(Config("alembic.ini"), "head")


if __name__ == "__main__":
    run_migrations()
