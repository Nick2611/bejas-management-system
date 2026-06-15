from json import dumps
from logging import getLogger

from pika import BasicProperties, BlockingConnection, ConnectionParameters
from pika.credentials import PlainCredentials


AFIP_EXCHANGE = "afip-messages"
AFIP_QUEUE = "bejas.queue"
AFIP_ROUTING_KEY = "fiscal.document.requested"
AFIP_DEAD_LETTER_EXCHANGE = "dlx.exchange"
AFIP_DEAD_LETTER_QUEUE = "dlx.queue"
AFIP_DEAD_LETTER_ROUTING_KEY = "fiscal.document.failed"
AFIP_MAX_DELIVERY_ATTEMPTS = 3


class RabbitClient:
    def __init__(
        self,
        rabbit_host: str,
        rabbit_port: int,
        rabbit_user: str,
        rabbit_pass: str,
    ):
        self.host = rabbit_host
        self.port = int(rabbit_port)
        self.user = rabbit_user
        self.password = rabbit_pass

        creds = PlainCredentials(username=self.user, password=self.password)
        self.connection = BlockingConnection(
            ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=creds,
                connection_attempts=1,
                socket_timeout=1,
                stack_timeout=2,
                heartbeat=60,
                blocked_connection_timeout=5,
            )
        )
        self.channel = self.connection.channel()
        self.channel.confirm_delivery()

        self.logger = getLogger(name="rabbit_logger")
        self.logger.info("channel created")

    def confirm_exchanges_and_queues(
        self,
        queue: str = AFIP_QUEUE,
        routing_key: str = AFIP_ROUTING_KEY,
    ):
        self.channel.exchange_declare(
            exchange=AFIP_EXCHANGE,
            exchange_type="direct",
            durable=True,
        )
        self.channel.exchange_declare(
            exchange=AFIP_DEAD_LETTER_EXCHANGE,
            exchange_type="direct",
            durable=True,
        )

        self.queue_state = self.channel.queue_declare(
            queue=queue,
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-dead-letter-exchange": AFIP_DEAD_LETTER_EXCHANGE,
                "x-dead-letter-routing-key": AFIP_DEAD_LETTER_ROUTING_KEY,
            },
        )
        self.dlq_state = self.channel.queue_declare(
            queue=AFIP_DEAD_LETTER_QUEUE,
            durable=True,
        )

        self.channel.queue_bind(
            exchange=AFIP_EXCHANGE,
            queue=queue,
            routing_key=routing_key,
        )
        self.channel.queue_bind(
            queue=AFIP_DEAD_LETTER_QUEUE,
            exchange=AFIP_DEAD_LETTER_EXCHANGE,
            routing_key=AFIP_DEAD_LETTER_ROUTING_KEY,
        )

        self.logger.info(msg="queues and exchanges up")

    def publish(
        self,
        payload: dict,
        queue: str = AFIP_QUEUE,
        routing_key: str = AFIP_ROUTING_KEY,
    ):
        self.channel.basic_publish(
            exchange=AFIP_EXCHANGE,
            routing_key=routing_key,
            body=dumps(payload).encode("utf-8"),
            mandatory=True,
            properties=BasicProperties(
                delivery_mode=2,  # persistent
                content_type="application/json",
            ),
        )

        self.logger.info(msg="message published")

    def consume(
        self,
        callback,
        queue: str = AFIP_QUEUE,
    ):
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=queue,
            on_message_callback=callback,
            auto_ack=False,
        )
        self.channel.start_consuming()

    def get_channel(self):
        return self.channel

    def get_queues_states(self):
        return self.queue_state, self.dlq_state

    def close(self):
        if self.connection.is_open:
            self.connection.close()
