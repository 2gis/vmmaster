import uuid
import logging

from pika import ConnectionParameters, PlainCredentials, BasicProperties, BlockingConnection, adapters

log = logging.getLogger(__name__)


class BlockingQueueProducer(object):
    response = None
    corr_id = None

    def __init__(self, app):
        params = {
            'user': app.cfg.RABBITMQ_USER,
            'password': app.cfg.RABBITMQ_PASSWORD,
            'host': app.cfg.RABBITMQ_HOST
        }
        self.connect(params)

    def connect(self, params):
        self.connection = self.make_connection(**params)
        self.channel = self.connection.channel()
        self.callback_queue = self.create_responses_queue(self.channel)
        log.warn("Queue was declared for responses: %s" % self.callback_queue)
        self.start_listening(self.channel, self.callback_queue, self.on_response)

    @staticmethod
    def create_responses_queue(channel):
        result = channel.queue_declare(exclusive=True)
        return result.method.queue

    @staticmethod
    def start_listening(channel, queue, on_message):
        # channel.basic_qos(prefetch_count=1)
        return channel.basic_consume(on_message, no_ack=True, queue=queue)

    @staticmethod
    def make_connection(user, password, host, port=5672):
        credentials = PlainCredentials(user, password)
        return BlockingConnection(ConnectionParameters(
            host=host, port=port, credentials=credentials
        ))

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def add_msg_to_queue(self, queue, msg):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        log.warn("Sending to %s message %s" % (queue, str(msg)))
        self.channel.basic_publish(
            exchange='',
            routing_key=queue,
            properties=BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,),
            body=str(msg)
        )
        log.info("Message %s was sent to %s" % (queue, str(msg)))
        while self.response is None:
            self.connection.process_data_events()
            yield None

        log.warn("Response from queue %s: %s" % (self.callback_queue, self.response))
        yield self.response


class AsyncQueueProducer(object):
    channel = None
    response = None
    corr_id = None

    def __init__(self):
        print('init')

    def connect(self, loop):
        params = {
            'loop': loop,
            'user': 'n.ustinov',
            'password': 'Paicae6u',
            'host': 'mq1.prod.test'
        }
        self.connection = yield from self.make_connection(**params)
        self.channel = yield from self.connection.channel()
        self.callback_queue = yield from self.create_responses_queue(self.channel)
        log.info("Queue was declared for responses: %s" % self.callback_queue)
        ctag = yield from self.start_listening(self.channel, self.callback_queue, self.on_response)
        return ctag

    @staticmethod
    def create_responses_queue(channel):
        result = yield from channel.queue_declare(exclusive=True)
        return result.method.queue

    @staticmethod
    def start_listening(channel, queue, on_message):
        queue, ctag = yield from channel.basic_consume(on_message, no_ack=True, queue=queue)
        return queue, ctag

    @staticmethod
    def make_connection(loop, user, password, host, port=5672):

        def connection_factory():
            credentials = PlainCredentials(user, password)
            return adapters.asyncio_connection.AsyncioProtocolConnection(ConnectionParameters(
                host=host, credentials=credentials
            ), loop=loop)

        transport, connection = yield from loop.create_connection(connection_factory, host, port)
        yield from connection.ready  # important!
        return connection

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def add_msg_to_queue(self, queue, msg):
        self.response = None
        self.corr_id = str(uuid.uuid4())

        yield from self.channel.basic_publish(
            exchange='',
            routing_key=queue,
            properties=BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=str(msg))

        while self.response is None:
            yield from self.connection.process_data_events()

        ch, method, props, self.response = yield from queue.get()
        log.warn("Response from queue %s: %s" % (self.callback_queue, self.response))
        return self.response
