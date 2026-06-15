from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from db.db_models import OutboxModel
from invoices.afip_client import AfipUnavailableError, MockAfipClient
from rabbitmq.worker import RabbitReader


def _delivery(tag=7):
    return SimpleNamespace(delivery_tag=tag)


def test_worker_acknowledges_authorized_invoice():
    session = MagicMock()
    channel = MagicMock()
    service = MagicMock()
    worker = RabbitReader(
        session_factory=lambda: session,
        afip_client=MockAfipClient(1),
    )

    with patch("rabbitmq.worker.InvoiceService", return_value=service):
        worker.consume_message(
            channel,
            _delivery(),
            SimpleNamespace(headers={}),
            b'{"invoice_id": 1, "outbox_id": 2}',
        )

    service.process_outbox.assert_called_once()
    assert service.process_outbox.call_args.args == (
        {"invoice_id": 1, "outbox_id": 2},
    )
    assert service.process_outbox.call_args.kwargs["worker_id"]
    session.commit.assert_called_once()
    channel.basic_ack.assert_called_once_with(delivery_tag=7)
    channel.basic_nack.assert_not_called()
    session.close.assert_called_once()


def test_worker_requeues_when_afip_is_unavailable():
    session = MagicMock()
    channel = MagicMock()
    service = MagicMock()
    service.process_outbox.side_effect = AfipUnavailableError(
        "AFIP no disponible"
    )
    worker = RabbitReader(
        session_factory=lambda: session,
        afip_client=MockAfipClient(0),
    )

    with patch("rabbitmq.worker.InvoiceService", return_value=service):
        worker.consume_message(
            channel,
            _delivery(9),
            SimpleNamespace(headers={"x-delivery-count": 1}),
            b'{"invoice_id": 1, "outbox_id": 2}',
        )

    session.commit.assert_called_once()
    channel.basic_nack.assert_called_once_with(
        delivery_tag=9,
        requeue=True,
    )
    channel.basic_ack.assert_not_called()
    session.close.assert_called_once()


def test_worker_dead_letters_after_third_afip_failure():
    session = MagicMock()
    channel = MagicMock()
    service = MagicMock()
    service.process_outbox.side_effect = AfipUnavailableError(
        "AFIP no disponible"
    )
    worker = RabbitReader(
        session_factory=lambda: session,
        afip_client=MockAfipClient(0),
    )

    with patch("rabbitmq.worker.InvoiceService", return_value=service):
        worker.consume_message(
            channel,
            _delivery(10),
            SimpleNamespace(headers={"x-delivery-count": 2}),
            b'{"invoice_id": 1, "outbox_id": 2}',
        )

    session.commit.assert_called_once()
    channel.basic_reject.assert_called_once_with(
        delivery_tag=10,
        requeue=False,
    )
    channel.basic_nack.assert_not_called()
    session.close.assert_called_once()


def test_worker_rejects_invalid_json_without_opening_database_session():
    session_factory = MagicMock()
    channel = MagicMock()
    worker = RabbitReader(
        session_factory=session_factory,
        afip_client=MockAfipClient(1),
    )

    worker.consume_message(
        channel,
        _delivery(11),
        SimpleNamespace(headers={}),
        b"not-json",
    )

    session_factory.assert_not_called()
    channel.basic_reject.assert_called_once_with(
        delivery_tag=11,
        requeue=False,
    )


def test_worker_only_republishes_explicit_declarations():
    session = MagicMock()
    rabbit = MagicMock()
    legacy = OutboxModel(
        payload={"invoice_id": 1, "outbox_id": 1},
        is_processed=False,
    )
    ticket = OutboxModel(
        payload={
            "invoice_id": 2,
            "outbox_id": 2,
            "declaration_source": "ticket",
        },
        is_processed=False,
    )
    repository = MagicMock()
    repository.get_unprocessed_outboxes.return_value = [legacy, ticket]
    service = MagicMock(repository=repository)
    worker = RabbitReader(
        session_factory=lambda: session,
        afip_client=MockAfipClient(1),
    )

    with patch("rabbitmq.worker.InvoiceService", return_value=service):
        worker._republish_pending_outboxes(rabbit)

    assert legacy.is_processed is True
    assert ticket.is_processed is False
    rabbit.publish.assert_called_once_with(ticket.payload)
    session.commit.assert_called_once()
    session.close.assert_called_once()
