# coding: utf-8

import ujson
import logging
import asyncio
import aioamqp

from worker import actions


log = logging.getLogger(__name__)


async def error_callback(exception):
    log.exception(exception)


class CustomAmqpProtocol(aioamqp.AmqpProtocol):
    def __init__(self, *args, **kwargs):
        super(CustomAmqpProtocol, self).__init__(heartbeat=10, *args, **kwargs)


class AsyncQueueConsumer(object):
    transport = None
    connection = None
    channels = dict()
    service_queue = None
    messages = {
        "platforms": dict(),
        "sessions": dict(),
        "services": dict()
    }

    def __init__(self, app):
        self.app = app

    async def connect(self):
        params = {
            'loop': self.app.loop,
            'login': self.app.cfg.RABBITMQ_USER,
            'password': self.app.cfg.RABBITMQ_PASSWORD,
            'host': self.app.cfg.RABBITMQ_HOST,
            'port': self.app.cfg.RABBITMQ_PORT,
            'protocol_factory': CustomAmqpProtocol,
            'on_error': error_callback,
        }
        self.transport, self.connection = await self.make_connection(params)
        self.service_queue = await self.start_consuming_for_commands()
        await self.start_consuming_for_platforms()

    async def disconnect(self):
        log.info("Closing connection...")
        await self.connection.close()
        self.transport.close()

    async def start_consuming_for_platforms(self):
        for platform in self.app.platforms:
            channel = await self.make_channel("platforms")
            queue_name, consumer_tag = await self.create_queue_and_consume(
                channel=channel,
                on_message_method=self.on_platform_message,
                queue_name=platform
            )
            self.channels[channel.channel_id].update({
                "platform": platform,
                "consumer_tag": consumer_tag
            })
            self.messages["platforms"][queue_name] = dict()

    async def start_consuming_for_session(self, session_id):
        channel = await self.make_channel("sessions")
        queue_name, consumer_tag = await self.create_queue_and_consume(
            channel=channel,
            on_message_method=self.on_session_message,
            queue_name="%s_%s" % (self.app.cfg.RABBITMQ_SESSION_QUEUE, session_id)
        )
        self.channels[channel.channel_id].update({
            "session": session_id,
            "consumer_tag": consumer_tag
        })
        self.messages["sessions"][session_id] = dict()
        return queue_name

    async def start_consuming_for_commands(self):
        channel = await self.make_channel("services")
        queue_name, consumer_tag = await self.create_queue_and_consume(
            channel=channel,
            on_message_method=self.on_service_message,
            queue_name=self.app.cfg.RABBITMQ_COMMAND_QUEUE
        )
        self.channels[channel.channel_id].update({
            "consumer_tag": consumer_tag
        })
        self.messages["services"] = dict()
        return queue_name

    @staticmethod
    async def create_queue(channel, queue_name=None):
        if not queue_name:
            result = await channel.queue_declare(exclusive=True)
        else:
            result = await channel.queue_declare(queue_name=queue_name)
        queue, messages, consumers = result.get('queue'), result.get('message_count'), result.get('consumer_count')
        log.info("Queue %s was declared(messages: %s, consumers: %s)" % (queue, messages, consumers))
        return queue

    async def delete_queue(self, channel, queue_name, no_wait=True):
        await channel.queue_delete(queue_name, no_wait=no_wait, timeout=self.app.cfg.RABBITMQ_REQUEST_TIMEOUT)
        log.info('Queue %s was deleted' % queue_name)

    async def create_queue_and_consume(self, channel, on_message_method, queue_name=None):
        if not queue_name:
            queue_name = await self.create_queue(channel)
        else:
            await self.create_queue(channel, queue_name)
        consumer_tag = await self.queue_consume(channel, queue_name, on_message_method)
        return queue_name, consumer_tag

    async def make_channel(self, _type="undefined"):
        channel = await self.connection.channel()
        self.channels[channel.channel_id] = {"mute": False, "type": _type, "channel": channel}
        return channel

    def get_session_channel_by_id(self, session_id):
        session_channel = None
        for channel in list(self.channels.values()):
            if channel.get("type") == "sessions" and channel.get("session") == int(session_id):
                session_channel = channel["channel"]
        return session_channel

    def get_platform_channel_by_platform(self, platform):
        platform_channel = None
        for channel in list(self.channels.values()):
            if channel.get("type") == "platforms" and channel.get("platform") == platform:
                platform_channel = channel["channel"]
        return platform_channel

    async def delete_channel(self, channel):
        try:
            del self.channels[channel.channel_id]
            await channel.close()
        except Exception:
            log.exception("Channel was not deleted")

    @staticmethod
    async def make_connection(params):
        try:
            return await aioamqp.connect(**params)
        except aioamqp.AmqpClosedConnection:
            log.warn("closed connection")

    async def queue_consume(self, channel, queue_name, on_message_method):
        log.info("Start consuming for queue %s" % queue_name)
        await channel.basic_qos(prefetch_count=self.app.cfg.RABBITMQ_PREFETCH_COUNT)
        consumer_tag = await channel.basic_consume(
            callback=on_message_method,
            queue_name=queue_name,
            no_ack=False,
            timeout=self.app.cfg.RABBITMQ_REQUEST_TIMEOUT
        )
        return consumer_tag["consumer_tag"] if isinstance(consumer_tag, dict) else consumer_tag

    async def mute_channel(self, channel, consumer_tag, no_wait=True):
        self.channels[channel.channel_id]["mute"] = True
        await channel.basic_cancel(
            consumer_tag=consumer_tag, no_wait=no_wait, timeout=self.app.cfg.RABBITMQ_REQUEST_TIMEOUT
        )
        log.info("Channel %s was muted" % channel.channel_id)

    async def unmute_channel(self, channel, callback, queue_name):
        consumer_tag = await self.queue_consume(channel, queue_name, callback)
        self.channels[channel.channel_id]["mute"] = False
        self.channels[channel.channel_id]["consumer_tag"] = consumer_tag
        log.info("Channel %s was unmuted" % channel.channel_id)

    async def on_service_message(self, channel, body, envelope, properties):
        log.info("Got new service message %s with id: %s" % (body, properties.correlation_id))
        msg = ujson.loads(body)
        self.messages["services"][properties.correlation_id] = msg
        session_channel = self.get_session_channel_by_id(msg["vmmaster_session"])
        platform_channel = self.get_platform_channel_by_platform(msg["platform"])
        if session_channel and platform_channel:
            if msg.get("command") in ("CLIENT_DISCONNECTED", "SESSION_CLOSING"):
                await actions.make_service_command(msg)
                await self.mute_channel(session_channel, self.channels[session_channel.channel_id]["consumer_tag"])
                await self.delete_queue(session_channel, "%s_%s" % (self.app.cfg.RABBITMQ_SESSION_QUEUE, msg["vmmaster_session"]))
                del self.channels[session_channel.channel_id]
                del self.messages["sessions"][int(msg["vmmaster_session"])]
                self.app.platforms[msg["platform"]] += 1
                if self.app.platforms[msg["platform"]] > 0 and self.channels[platform_channel.channel_id]["mute"]:
                    asyncio.ensure_future(
                        self.unmute_channel(platform_channel, self.on_platform_message, msg["platform"]),
                        loop=self.app.loop
                    )
            else:
                log.warn("Action for undefined command %s" % msg.get("command"))
            await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
        else:
            await channel.basic_client_nack(delivery_tag=envelope.delivery_tag, multiple=True, requeue=True)
            log.warn("Command with unknown session_id %s and platform %s . "
                     "Ignore this message..." % (msg["vmmaster_session"], msg["platform"]))

        del self.messages["services"][properties.correlation_id]

    async def on_platform_message(self, channel, body, envelope, properties):
        log.info("Got new platform message %s with id: %s" % (body, properties.correlation_id))
        msg = ujson.loads(body)
        if not self.channels[channel.channel_id]["mute"]:
            self.messages["platforms"][msg["platform"]][properties.correlation_id] = msg

            response = await actions.start_session(msg)

            self.app.platforms[msg["platform"]] -= 1
            await self.add_msg_to_queue(channel, properties.correlation_id, properties.reply_to, response)
            del self.messages["platforms"][msg["platform"]][properties.correlation_id]
            asyncio.ensure_future(self.start_consuming_for_session(msg["vmmaster_session"]), loop=self.app.loop)
            await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
        else:
            await channel.basic_client_nack(delivery_tag=envelope.delivery_tag, multiple=True, requeue=True)

        if self.app.platforms[msg["platform"]] <= 0 and not self.channels[channel.channel_id]["mute"]:
            await self.mute_channel(channel, envelope.consumer_tag)

    async def on_session_message(self, channel, body, envelope, properties):
        log.info("Got new session message %s with id: %s" % (body, properties.correlation_id))
        await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
        msg = ujson.loads(body)
        self.messages["sessions"][msg["vmmaster_session"]][properties.correlation_id] = msg

        response = await actions.make_request_for_session(msg)

        await self.add_msg_to_queue(channel, properties.correlation_id, properties.reply_to, response)
        del self.messages["sessions"][msg["vmmaster_session"]][properties.correlation_id]

    @staticmethod
    async def add_msg_to_queue(channel, correlation_id, queue_name, msg):
        msg = ujson.dumps(msg) if isinstance(msg, dict) else msg
        await channel.basic_publish(
            payload=str(msg),
            exchange_name='',
            routing_key=queue_name,
            properties={
                "correlation_id": correlation_id
            }
        )
        log.info("Message(id:%s body: %s) was published to %s" % (correlation_id, msg, queue_name))
