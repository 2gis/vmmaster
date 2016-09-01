import aioamqp
import uuid
import asyncio
import logging
from core import utils


log = logging.getLogger(__name__)


class AsyncQueueProducer(object):
    messages = {}
    connection = None
    channel = None
    callback_queue = None

    def __init__(self, app):
        self.app = app
        asyncio.gather(asyncio.ensure_future(self.connect(), loop=app.loop), loop=app.loop)

    async def connect(self):
        params = {
            'loop': self.app.loop,
            'login': self.app.cfg.RABBITMQ_USER,
            'password': self.app.cfg.RABBITMQ_PASSWORD,
            'host': self.app.cfg.RABBITMQ_HOST,
            'port': self.app.cfg.RABBITMQ_PORT
        }
        self.connection = await self.make_connection(params)
        self.channel = await self.connection.channel()
        self.callback_queue = await self.create_responses_queue(self.channel)
        await self.start_consuming()

    @staticmethod
    async def create_responses_queue(channel):
        result = await channel.queue_declare(exclusive=True)
        queue, messages, consumers = result.get('queue'), result.get('message_count'), result.get('consumer_count')
        log.info("Queue %s was declared(messages: %s, consumers: %s)" % (queue, messages, consumers))
        return queue

    @staticmethod
    async def make_connection(params):
        transport, connection = await aioamqp.connect(**params)
        return connection

    async def start_consuming(self):
        log.info("Start consuming for queue %s" % self.callback_queue)
        await self.channel.basic_consume(
            callback=self.on_message, queue_name=self.callback_queue, no_ack=False
        )

    async def on_message(self, channel, body, envelope, properties):
        log.debug("Got new message %s" % body)
        for correlation_id in list(self.messages.keys()):
            if correlation_id == properties.correlation_id:
                log.info("Response from queue %s: %s" % (self.callback_queue, body))
                self.messages[correlation_id]["response"] = body
                channel.basic_client_ack(delivery_tag=envelope.delivery_tag)

    async def add_msg_to_queue(self, queue_name, msg):
        await utils.async_wait_for(lambda: self.channel, self.app.loop, timeout=60)
        correlation_id = str(uuid.uuid4())
        await self.channel.basic_publish(
            payload=str(msg),
            exchange_name='',
            routing_key=queue_name,
            properties={
                "reply_to": self.callback_queue,
                "correlation_id": correlation_id
            })
        log.info("Message(id:%s body: %s) was published to %s" % (correlation_id, msg, queue_name))
        self.messages[correlation_id] = {"request": msg, "response": None}
        return correlation_id

    async def get_message_from_queue(self, correlation_id):
        from core.utils import async_wait_for
        log.info("Waiting response for message with id: %s" % correlation_id)
        response = await async_wait_for(
            lambda: self.messages.get(correlation_id).get("response"), self.app.loop, timeout=60
        )
        del self.messages[correlation_id]
        log.info("Got response %s for message with id: %s" % (response, correlation_id))
        return response
