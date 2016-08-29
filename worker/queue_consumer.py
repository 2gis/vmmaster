import uuid
import ujson
import logging
import asyncio
from pika import ConnectionParameters, PlainCredentials, BasicProperties, BlockingConnection, adapters


log = logging.getLogger(__name__)


class BlockingQueueConsumer(object):
    def __init__(self, app):
        self.app = app
        self.credentials = {
            'user': app.cfg.RABBITMQ_USER,
            'password': app.cfg.RABBITMQ_PASSWORD,
            'host': app.cfg.RABBITMQ_HOST
        }
        self.start_consuming_for_platforms()

    def start_consuming_for_platforms(self):
        for platform in ["ubuntu-14.04-x64"]:
            self.parallel_task_run(self.start_consuming, (platform, self.credentials))

    @staticmethod
    def start_consuming(platform, params):
        connection = make_connection(**params)
        channel = connection.channel()
        create_queue(channel, platform)
        consume(channel, platform, on_message)

    def parallel_task_run(self, task, args):
        return asyncio.ensure_future(self.app.loop.run_in_executor(self.app.executor, task, *args))


def create_queue(channel, queue_name):
    channel.queue_declare(queue=queue_name)
    log.info("Queue %s was declared" % queue_name)


def make_connection(user, password, host, port=5672):
    credentials = PlainCredentials(user, password)
    return BlockingConnection(ConnectionParameters(
        host=host, port=port, credentials=credentials
    ))


def consume(channel, queue, _on_message):
    channel.basic_qos(prefetch_count=1)
    log.info("Starting consume for queue %s (channel:%s)" % (queue, channel.channel_number))
    channel.basic_consume(_on_message, no_ack=True, queue=queue)
    channel.start_consuming()


def on_message(channel, method, props, body):
    log.info("Got message %s %s %s (channel:%s)" % (channel, method, props, body))
    body = ujson.loads(body)
    body['status'] = 200
    body['headers'] = '{"Content-Length": 123}'
    body['content'] = '{"sessionId": "123qwe"}'
    response = ujson.dumps(body)
    send_results(channel, props.reply_to, props.correlation_id, response, method.delivery_tag)


def send_results(channel, queue, corr_id, message, delivery_tag):
    # log.info(
    #     "Sending response on message: \nqueue=%s, \nmessage=%s, \ncorr_id=%s, \ndelivery_tag=%s" %
    #     channel, queue, corr_id, message, delivery_tag
    # )
    channel.basic_publish(
        exchange='',
        routing_key=queue,
        properties=BasicProperties(correlation_id=corr_id),
        body=str(message))
    channel.basic_ack(delivery_tag=delivery_tag)
    log.info("Response was sent")


class AsyncQueueConsumer(object):
    def connect(self, loop, app):
        self.credentials = {
            'loop': loop,
            'user': app.cfg.RABBITMQ_USER,
            'password': app.cfg.RABBITMQ_PASSWORD,
            'host': app.cfg.RABBITMQ_HOST
        }
        self.connection = yield from self.make_connection(**self.credentials)
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
