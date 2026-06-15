import os
import random
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Protocol

from shared.time_utils import local_today


class AfipError(RuntimeError):
    def __init__(
        self,
        message: str,
        response_payload: dict | None = None,
    ):
        super().__init__(message)
        self.response_payload = response_payload or {
            "authorized": False,
            "reason": message,
            "mock": True,
        }


class AfipTemporaryError(AfipError):
    pass


class AfipUnavailableError(AfipTemporaryError):
    pass


class AfipTimeoutError(AfipTemporaryError):
    pass


class AfipRejectedError(AfipError):
    pass


class InvalidFiscalPayloadError(AfipError):
    pass


@dataclass(frozen=True)
class AfipAuthorization:
    cae: str
    cae_expiration: date
    response_payload: dict


class AfipClient(Protocol):
    def authorize(self, request_payload: dict) -> AfipAuthorization:
        ...


class MockAfipClient:
    def __init__(
        self,
        success_rate: float = 0.90,
        random_generator: random.Random | None = None,
    ):
        if not 0 <= success_rate <= 1:
            raise ValueError("success_rate debe estar entre 0 y 1")
        self.success_rate = success_rate
        self.random = random_generator or random.Random()

    def authorize(self, request_payload: dict) -> AfipAuthorization:
        if self.random.random() >= self.success_rate:
            raise AfipRejectedError(
                "Comprobante rechazado por validación fiscal simulada",
                {
                    "authorized": False,
                    "result": "R",
                    "reason": (
                        "Comprobante rechazado por validación fiscal simulada"
                    ),
                    "mock": True,
                    "request_id": request_payload.get("request_id"),
                },
            )

        cae = "".join(str(self.random.randint(0, 9)) for _ in range(14))
        expiration = local_today() + timedelta(days=10)
        return AfipAuthorization(
            cae=cae,
            cae_expiration=expiration,
            response_payload={
                "result": "A",
                "cae": cae,
                "cae_expiration": expiration.isoformat(),
                "mock": True,
                "request_id": request_payload["request_id"],
            },
        )


@lru_cache
def get_afip_client() -> MockAfipClient:
    success_rate = float(os.getenv("AFIP_MOCK_SUCCESS_RATE", "0.90"))
    seed_value = os.getenv("AFIP_MOCK_SEED")
    generator = (
        random.Random(seed_value)
        if seed_value is not None
        else random.Random()
    )
    return MockAfipClient(success_rate, generator)
