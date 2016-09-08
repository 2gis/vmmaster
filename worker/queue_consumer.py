import ujson
import logging
import aioamqp
from core.utils import async_wait_for


log = logging.getLogger(__name__)


class AsyncQueueConsumer(object):
    connection = None
    service_channel = None
    sessions_channel = None
    platform_channel = None
    commands_queue = None
    platforms_messages = dict()
    sessions_messages = dict()
    service_messages = dict()

    def __init__(self, app):
        self.app = app

    async def connect(self):
        params = {
            'loop': self.app.loop,
            'login': self.app.cfg.RABBITMQ_USER,
            'password': self.app.cfg.RABBITMQ_PASSWORD,
            'host': self.app.cfg.RABBITMQ_HOST,
            'port': self.app.cfg.RABBITMQ_PORT
        }
        self.connection = await self.make_connection(params)
        self.service_channel = await self.connection.channel()
        self.platform_channel = await self.connection.channel()
        self.sessions_channel = await self.connection.channel()
        self.commands_queue = await self.create_queue_and_consume(
            channel=self.service_channel,
            on_message_method=self.on_service_message,
            queue_name=self.app.cfg.RABBITMQ_COMMAND_QUEUE
        )
        self.platforms_messages = await self.start_consuming_for_platforms()

    async def start_consuming_for_platforms(self):
        platforms = dict()
        for platform in ["ubuntu-14.04-x64"]:
            queue_name = await self.create_queue_and_consume(
                channel=self.platform_channel,
                on_message_method=self.on_platform_message,
                queue_name=platform
            )
            platforms[queue_name] = dict()
        return platforms

    @staticmethod
    async def create_queue(channel, queue_name=None):
        if not queue_name:
            result = await channel.queue_declare(exclusive=True)
        else:
            result = await channel.queue_declare(queue_name=queue_name)
        queue, messages, consumers = result.get('queue'), result.get('message_count'), result.get('consumer_count')
        log.info("Queue %s was declared(messages: %s, consumers: %s)" % (queue, messages, consumers))
        return queue

    @staticmethod
    async def delete_queue(channel, queue_name):
        await channel.queue_delete(queue_name)
        log.info('Queue %s was deleted' % queue_name)

    async def create_queue_and_consume(self, channel, on_message_method, queue_name=None):
        if not queue_name:
            queue_name = await self.create_queue(channel)
        else:
            await self.create_queue(channel, queue_name)
        await self.queue_consume(channel, queue_name, on_message_method)
        return queue_name

    @staticmethod
    async def make_connection(params):
        transport, connection = await aioamqp.connect(**params)
        return connection

    @staticmethod
    async def queue_consume(channel, queue_name, on_message_method):
        log.info("Start consuming for queue %s" % queue_name)

        await channel.basic_qos(prefetch_count=1)
        await channel.basic_consume(
            callback=on_message_method, queue_name=queue_name, no_ack=False
        )

    @staticmethod
    async def unwrap_message(channel, _type, msg, envelope, correlation_id):
        log.info("Got new %s message %s with id: %s" % (_type, msg, correlation_id))
        await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
        body_json = ujson.loads(msg)
        return body_json

    async def on_service_message(self, channel, body, envelope, properties):
        correlation_id = properties.correlation_id
        msg = await self.unwrap_message(channel, 'service', body, envelope, correlation_id)
        self.service_messages[correlation_id] = {"request": msg, "response": None}
        await self.wait_for_response_on_message(self.service_messages[correlation_id], correlation_id)
        del self.service_messages[correlation_id]

    async def on_platform_message(self, channel, body, envelope, properties):
        correlation_id = properties.correlation_id
        msg = await self.unwrap_message(channel, 'platform', body, envelope, correlation_id)
        platform = msg["platform"]
        self.platforms_messages[platform][correlation_id] = {"request": msg, "response": None}
        response = await self.wait_for_response_on_message(self.platforms_messages[platform], correlation_id)
        await self.add_msg_to_queue(self.platform_channel, correlation_id, properties.reply_to, response)
        del self.platforms_messages[platform][correlation_id]

    async def on_session_message(self, channel, body, envelope, properties):
        correlation_id = properties.correlation_id
        msg = await self.unwrap_message(channel, 'session', body, envelope, correlation_id)
        session_id = msg["sessionId"]
        self.sessions_messages[session_id][correlation_id] = {"request": msg, "response": None}
        response = await self.wait_for_response_on_message(self.sessions_messages[session_id], correlation_id)
        await self.add_msg_to_queue(self.sessions_channel, correlation_id, properties.reply_to, response)
        del self.sessions_messages[session_id][correlation_id]

    async def add_msg_to_queue(self, channel, correlation_id, queue_name, msg):
        msg = ujson.dumps(msg) if isinstance(msg, dict) else msg
        await channel.basic_publish(
            payload=str(msg),
            exchange_name='',
            routing_key=queue_name
        )
        log.info("Message(id:%s body: %s) was published to %s" % (correlation_id, msg, queue_name))

    async def wait_for_response_on_message(self, storage, correlation_id):
        log.info("Waiting response for message with id: %s" % correlation_id)
        response = await async_wait_for(
            lambda: storage.get(correlation_id).get("response"), self.app.loop, timeout=60
        )
        log.info("Got response %s for message with id: %s" % (response, correlation_id))
        return response
