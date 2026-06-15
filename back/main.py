import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from auth.auth_router import auth_router
from closings.router.closing_router import (
    cash_closing_router,
    closing_router,
)
from goals.router.goal_router import goal_router
from invoices.router.invoice_router import invoice_router
from kpis.router.kpi_router import kpi_router
from products.router.products_router import products_router
from stock.router.stock_router import stock_router
from tables.router.table_router import table_router
from users.user_router import user_router

from auth.bootstrap import initialize_users
from products.bootstrap import initialize_products

from logging import INFO, WARNING, basicConfig, getLogger

@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_users()
    initialize_products()
    yield


app = FastAPI(lifespan=lifespan)

basicConfig(
    level=INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
getLogger("pika").setLevel(WARNING)



origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth_router)
app.include_router(products_router)
app.include_router(table_router)
app.include_router(stock_router)
app.include_router(closing_router)
app.include_router(cash_closing_router)
app.include_router(invoice_router)
app.include_router(goal_router)
app.include_router(kpi_router)
app.include_router(user_router)


@app.get("/health")
def health():
    return {"status": "ok"}
