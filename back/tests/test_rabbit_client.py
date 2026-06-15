from unittest.mock import MagicMock

from rabbitmq.rabbit_client import RabbitClient


def test_queue_declaration_is_compatible_with_existing_queue():
    client = RabbitClient.__new__(RabbitClient)
    client.channel = MagicMock()
    client.logger = MagicMock()

    client.confirm_exchanges_and_queues()

    arguments = client.channel.queue_declare.call_args_list[0].kwargs[
        "arguments"
    ]
    assert "x-delivery-limit" not in arguments
    assert arguments["x-queue-type"] == "quorum"
    assert arguments["x-dead-letter-exchange"] == "dlx.exchange"
