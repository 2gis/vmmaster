# coding: utf-8

import ujson
from asyncio import coroutine
from mock import Mock, patch
from core.common import BaseApplication
from worker.queue_consumer import AsyncQueueConsumer


async def test_add_message(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qp = AsyncQueueConsumer(app)
    channel = Mock()
    channel.basic_publish = Mock(side_effect=coroutine(
        lambda payload, exchange_name, routing_key, properties: None
    ))

    await qp.add_msg_to_queue(channel, '5236s4d7f8gy', 'q1', 'message')
    assert channel.basic_publish.called


async def test_on_platform_message_with_channel_mute(loop):
    with patch('worker.actions.start_session', Mock(side_effect=coroutine(lambda msg: "response"))):
        app = BaseApplication('app', loop=loop, CONFIG='config.tests')
        app.platforms = {"ubuntu-14.04-x64": 1}
        msg = ujson.dumps({
            "platform": "ubuntu-14.04-x64",
            "vmmaster_session": 1
        })
        qc = AsyncQueueConsumer(app)

        # mocks
        channel = Mock(channel_id=1)
        qc.messages["platforms"]["ubuntu-14.04-x64"] = {}
        qc.channels[channel.channel_id] = {"mute": False, "type": "platforms", "channel": channel}
        channel.basic_client_ack = Mock(side_effect=coroutine(
            lambda delivery_tag: None
        ))
        qc.add_msg_to_queue = Mock(side_effect=coroutine(
            lambda _channel, correlation_id, queue_name, msg: None
        ))
        qc.start_consuming_for_session = Mock(side_effect=coroutine(
            lambda session_id: None
        ))
        qc.mute_channel = Mock(side_effect=coroutine(
            lambda _channel, _ct: None
        ))

        await qc.on_platform_message(
            channel, msg, Mock(delivery_tag='dtag1.2134234'), Mock(correlation_id='6ivtyubhnj')
        )
        assert channel.basic_client_ack.called
        assert qc.add_msg_to_queue.called
        assert qc.start_consuming_for_session.called
        assert qc.mute_channel.called
        assert app.platforms["ubuntu-14.04-x64"] == 0


async def test_on_platform_message_with_muted_channel(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    app.platforms = {"ubuntu-14.04-x64": 0}
    msg = ujson.dumps({
        "platform": "ubuntu-14.04-x64",
        "vmmaster_session": 1
    })

    qc = AsyncQueueConsumer(app)

    # mocks
    channel = Mock(channel_id=1)
    qc.messages["platforms"]["ubuntu-14.04-x64"] = {}
    qc.channels[channel.channel_id] = {"mute": True, "type": "platforms", "channel": channel}
    channel.basic_client_nack = Mock(side_effect=coroutine(
        lambda delivery_tag, multiple, requeue: None
    ))

    await qc.on_platform_message(
        channel, msg, Mock(delivery_tag='dtag1.2134234'), Mock(correlation_id='6ivtyubhnj')
    )
    assert channel.basic_client_nack.called


async def test_on_session_message(loop):
    with patch('worker.actions.make_request_for_session', Mock(side_effect=coroutine(lambda msg: "response"))):
        app = BaseApplication('app', loop=loop, CONFIG='config.tests')
        app.platforms = {"ubuntu-14.04-x64": 1}
        msg = ujson.dumps({
            "platform": "ubuntu-14.04-x64",
            "vmmaster_session": 1
        })

        qc = AsyncQueueConsumer(app)

        # mocks
        channel = Mock(channel_id=1)
        qc.messages["sessions"][1] = {}
        qc.channels[channel.channel_id] = {"mute": False, "type": "sessions", "channel": channel}
        channel.basic_client_ack = Mock(side_effect=coroutine(
            lambda delivery_tag: None
        ))
        qc.add_msg_to_queue = Mock(side_effect=coroutine(
            lambda _channel, correlation_id, queue_name, msg: None
        ))

        await qc.on_session_message(
            channel, msg, Mock(delivery_tag='dtag1.2134234'), Mock(correlation_id='6ivtyubhnj')
        )
        assert channel.basic_client_ack.called
        assert qc.add_msg_to_queue.called


async def test_on_service_message_with_CLIENT_DISCONNECTED(loop):
    with patch('worker.actions.make_service_command', Mock(side_effect=coroutine(lambda msg: "response"))):
        app = BaseApplication('app', loop=loop, CONFIG='config.tests')
        app.platforms = {"ubuntu-14.04-x64": 0}
        msg = ujson.dumps({
            "command": "CLIENT_DISCONNECTED",
            "platform": "ubuntu-14.04-x64",
            "vmmaster_session": 1
        })

        qc = AsyncQueueConsumer(app)

        # mocks
        service_channel = Mock(channel_id=1)
        session_channel = Mock(channel_id=2)
        platforms_channel = Mock(channel_id=3)
        qc.get_session_channel_by_id = Mock(return_value=session_channel)
        qc.get_platform_channel_by_platform = Mock(return_value=platforms_channel)
        qc.messages["sessions"] = {1: {}}
        qc.channels[service_channel.channel_id] = \
            {"mute": False, "type": "services", "channel": service_channel, "consumer_tag": "efwef1234r"}
        qc.channels[session_channel.channel_id] = \
            {"mute": False, "type": "sessions", "channel": session_channel, "consumer_tag": "efwef1234r"}
        qc.channels[platforms_channel.channel_id] = \
            {"mute": False, "type": "platforms", "channel": platforms_channel, "consumer_tag": "efwef1234r"}
        service_channel.basic_client_ack = Mock(side_effect=coroutine(
            lambda delivery_tag: None
        ))
        qc.delete_queue = Mock(side_effect=coroutine(
            lambda _channel, queue_name: None
        ))
        qc.mute_channel = Mock(side_effect=coroutine(
            lambda _channel, _ct: None
        ))

        await qc.on_service_message(
            service_channel, msg, Mock(delivery_tag='dtag1.2134234'), Mock(correlation_id='6ivtyubhnj')
        )
        assert service_channel.basic_client_ack.called
        assert qc.mute_channel.called
        assert qc.delete_queue.called
        assert app.platforms["ubuntu-14.04-x64"] == 1


async def test_on_service_message_with_SESSION_CLOSING(loop):
    with patch('worker.actions.make_service_command', Mock(side_effect=coroutine(lambda msg: "response"))):
        app = BaseApplication('app', loop=loop, CONFIG='config.tests')
        app.platforms = {"ubuntu-14.04-x64": 0}
        msg = ujson.dumps({
            "command": "SESSION_CLOSING",
            "platform": "ubuntu-14.04-x64",
            "vmmaster_session": 1
        })

        qc = AsyncQueueConsumer(app)

        # mocks
        service_channel = Mock(channel_id=1)
        session_channel = Mock(channel_id=2)
        platforms_channel = Mock(channel_id=3)
        qc.get_session_channel_by_id = Mock(return_value=session_channel)
        qc.get_platform_channel_by_platform = Mock(return_value=platforms_channel)
        qc.messages["sessions"] = {1: {}}
        qc.channels[service_channel.channel_id] = \
            {"mute": False, "type": "services", "channel": service_channel, "consumer_tag": "efwef1234r"}
        qc.channels[session_channel.channel_id] = \
            {"mute": False, "type": "sessions", "channel": session_channel, "consumer_tag": "efwef1234r"}
        qc.channels[platforms_channel.channel_id] = \
            {"mute": False, "type": "platforms", "channel": platforms_channel, "consumer_tag": "efwef1234r"}
        service_channel.basic_client_ack = Mock(side_effect=coroutine(
            lambda delivery_tag: None
        ))
        qc.delete_queue = Mock(side_effect=coroutine(
            lambda _channel, queue_name: None
        ))
        qc.mute_channel = Mock(side_effect=coroutine(
            lambda _channel, _ct: None
        ))

        await qc.on_service_message(
            service_channel, msg, Mock(delivery_tag='dtag1.2134234'), Mock(correlation_id='6ivtyubhnj')
        )
        assert service_channel.basic_client_ack.called
        assert qc.mute_channel.called
        assert qc.delete_queue.called
        assert app.platforms["ubuntu-14.04-x64"] == 1


async def test_on_service_message_with_channel_unmuting(loop):
    with patch('worker.actions.make_service_command', Mock(side_effect=coroutine(lambda msg: "response"))):
        app = BaseApplication('app', loop=loop, CONFIG='config.tests')
        app.platforms = {"ubuntu-14.04-x64": 0}
        msg = ujson.dumps({
            "command": "SESSION_CLOSING",
            "platform": "ubuntu-14.04-x64",
            "vmmaster_session": 1
        })

        qc = AsyncQueueConsumer(app)

        # mocks
        service_channel = Mock(channel_id=1)
        session_channel = Mock(channel_id=2)
        platforms_channel = Mock(channel_id=3)
        qc.get_session_channel_by_id = Mock(return_value=session_channel)
        qc.get_platform_channel_by_platform = Mock(return_value=platforms_channel)
        qc.messages["sessions"] = {1: {}}
        qc.channels[service_channel.channel_id] = \
            {"mute": False, "type": "services", "channel": service_channel, "consumer_tag": "efwef1234r"}
        qc.channels[session_channel.channel_id] = \
            {"mute": False, "type": "sessions", "channel": session_channel, "consumer_tag": "efwef1234r"}
        qc.channels[platforms_channel.channel_id] = \
            {"mute": True, "type": "platforms", "channel": platforms_channel, "consumer_tag": "efwef1234r"}
        service_channel.basic_client_ack = Mock(side_effect=coroutine(
            lambda delivery_tag: None
        ))
        qc.delete_queue = Mock(side_effect=coroutine(
            lambda _channel, queue_name: None
        ))
        qc.mute_channel = Mock(side_effect=coroutine(
            lambda _channel, _ct: None
        ))
        qc.unmute_channel = Mock(side_effect=coroutine(
            lambda _channel, _ct, pl: None
        ))

        await qc.on_service_message(
            service_channel, msg, Mock(delivery_tag='dtag1.2134234'), Mock(correlation_id='6ivtyubhnj')
        )
        assert service_channel.basic_client_ack.called
        assert qc.mute_channel.called
        assert qc.delete_queue.called
        assert app.platforms["ubuntu-14.04-x64"] == 1


async def test_on_service_message_with_unwnown_command(loop):
    with patch('worker.actions.make_service_command', Mock(side_effect=coroutine(lambda msg: "response"))):
        app = BaseApplication('app', loop=loop, CONFIG='config.tests')
        app.platforms = {"ubuntu-14.04-x64": 1}
        msg = ujson.dumps({
            "command": "bla bla",
            "platform": "ubuntu-14.04-x64",
            "vmmaster_session": 1
        })

        qc = AsyncQueueConsumer(app)

        # mocks
        service_channel = Mock(channel_id=1)
        session_channel = Mock(channel_id=2)
        platforms_channel = Mock(channel_id=3)
        qc.get_session_channel_by_id = Mock(return_value=session_channel)
        qc.get_platform_channel_by_platform = Mock(return_value=platforms_channel)
        service_channel.basic_client_ack = Mock(side_effect=coroutine(
            lambda delivery_tag: None
        ))

        await qc.on_service_message(
            service_channel, msg, Mock(delivery_tag='dtag1.2134234'), Mock(correlation_id='6ivtyubhnj')
        )
        assert service_channel.basic_client_ack.called
        assert app.platforms["ubuntu-14.04-x64"] == 1


async def test_on_service_message_for_other_consumers(loop):
    with patch('worker.actions.make_service_command', Mock(side_effect=coroutine(lambda msg: "response"))):
        app = BaseApplication('app', loop=loop, CONFIG='config.tests')
        app.platforms = {"ubuntu-14.04-x64": 1}
        msg = ujson.dumps({
            "command": "bla bla",
            "platform": "ubuntu-14.04-x64",
            "vmmaster_session": 1
        })

        qc = AsyncQueueConsumer(app)

        # mocks
        service_channel = Mock(channel_id=1)
        qc.get_session_channel_by_id = Mock(return_value=None)
        qc.get_platform_channel_by_platform = Mock(return_value=None)
        service_channel.basic_client_nack = Mock(side_effect=coroutine(
            lambda delivery_tag, multiple, requeue: None
        ))

        await qc.on_service_message(
            service_channel, msg, Mock(delivery_tag='dtag1.2134234'), Mock(correlation_id='6ivtyubhnj')
        )
        assert service_channel.basic_client_nack.called
        assert app.platforms["ubuntu-14.04-x64"] == 1


async def test_mute_channel(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    service_channel = Mock(channel_id=1)
    qc.channels[service_channel.channel_id] = \
            {"mute": False, "type": "services", "channel": service_channel, "consumer_tag": "efwef1234r"}
    service_channel.basic_cancel = Mock(side_effect=coroutine(
        lambda consumer_tag, no_wait, timeout: None
    ))

    await qc.mute_channel(service_channel, "efwef1234r", no_wait=False)
    assert service_channel.basic_cancel.called
    assert qc.channels[service_channel.channel_id]["mute"]


async def test_unmute_channel(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    service_channel = Mock(channel_id=1)
    qc.channels[service_channel.channel_id] = \
            {"mute": False, "type": "services", "channel": service_channel}
    qc.queue_consume = Mock(side_effect=coroutine(
        lambda consumer_tag, no_wait, timeout: "consumer_tag"
    ))

    await qc.unmute_channel(service_channel, Mock(), "queue_name")
    assert qc.queue_consume.called
    assert not qc.channels[service_channel.channel_id]["mute"]
    assert qc.channels[service_channel.channel_id]["consumer_tag"] == "consumer_tag"


async def test_queue_consume(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    service_channel = Mock(channel_id=1)
    qc.channels[service_channel.channel_id] = {
        "mute": False, "type": "services", "channel": service_channel
    }
    service_channel.basic_qos = Mock(side_effect=coroutine(
        lambda prefetch_count: None
    ))
    service_channel.basic_consume = Mock(side_effect=coroutine(
        lambda callback, queue_name, no_ack, timeout: "consumer_tag"
    ))

    consumer_tag = await qc.queue_consume(service_channel, "queue_name", lambda: None)
    assert service_channel.basic_qos.called
    assert service_channel.basic_consume.called
    assert consumer_tag == "consumer_tag"


async def test_get_platform_channel_by_platform(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    platforms_channel = Mock(channel_id=1)
    qc.channels[platforms_channel.channel_id] = {
        "mute": False, "type": "platforms", "channel": platforms_channel, "platform": "ubuntu-14.04-x64"
    }

    channel = qc.get_platform_channel_by_platform("ubuntu-14.04-x64")
    assert channel.channel_id == platforms_channel.channel_id


async def test_get_session_channel_by_id(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    sessions_channel = Mock(channel_id=1)
    qc.channels[sessions_channel.channel_id] = {
        "mute": False, "type": "sessions", "channel": sessions_channel, "session": 1
    }

    channel = qc.get_session_channel_by_id(1)
    assert channel.channel_id == sessions_channel.channel_id


async def test_make_channel(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    qc.connection = Mock()
    qc.connection.channel = Mock(side_effect=coroutine(
        lambda: Mock(channel_id=1)
    ))

    await qc.make_channel("sessions")
    assert qc.connection.channel.called
    assert qc.channels[1]["type"] == "sessions"


async def test_delete_channel(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    sessions_channel = Mock(channel_id=1)
    qc.channels[sessions_channel.channel_id] = {
        "mute": False, "type": "sessions", "channel": sessions_channel, "session": 1
    }
    sessions_channel.close = Mock(side_effect=coroutine(
        lambda: None
    ))

    await qc.delete_channel(sessions_channel)
    assert sessions_channel.close.called


async def test_create_queue_and_consume(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    qc.create_queue = Mock(side_effect=coroutine(
        lambda _channel, queue_name: None
    ))
    qc.queue_consume = Mock(side_effect=coroutine(
        lambda _channel, queue_name, on_message_method: "consumer_tag"
    ))

    queue_name, consumer_tag = await qc.create_queue_and_consume(Mock(), lambda: None, "queue_name")
    assert qc.create_queue.called
    assert qc.queue_consume.called
    assert queue_name, consumer_tag == ("queue_name", "consumer_tag")


async def test_create_queue_and_consume_with_autoname(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    qc.create_queue = Mock(side_effect=coroutine(
        lambda _channel: "queue_name"
    ))
    qc.queue_consume = Mock(side_effect=coroutine(
        lambda _channel, queue_name, on_message_method: "consumer_tag"
    ))

    queue_name, consumer_tag = await qc.create_queue_and_consume(Mock(), lambda: None)
    assert qc.create_queue.called
    assert qc.queue_consume.called
    assert queue_name, consumer_tag == ("queue_name", "consumer_tag")


async def test_delete_queue(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    sessions_channel = Mock(channel_id=1)
    sessions_channel.queue_delete = Mock(side_effect=coroutine(
        lambda queue_name, no_wait, timeout: None
    ))

    await qc.delete_queue(sessions_channel, "queue_name", no_wait=False)
    assert sessions_channel.queue_delete.called


async def test_create_queue(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    sessions_channel = Mock(channel_id=1)
    sessions_channel.queue_declare = Mock(side_effect=coroutine(
        lambda queue_name: {'queue': 'queue_name', 'message_count': 0, 'consumer_count': 0}
    ))

    queue_name = await qc.create_queue(sessions_channel, "queue_name")
    assert sessions_channel.queue_declare.called
    assert queue_name == "queue_name"


async def test_create_queue_with_autoname(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    sessions_channel = Mock(channel_id=1)
    sessions_channel.queue_declare = Mock(side_effect=coroutine(
        lambda exclusive: {'queue': 'queue_name', 'message_count': 0, 'consumer_count': 0}
    ))

    queue_name = await qc.create_queue(sessions_channel)
    assert sessions_channel.queue_declare.called
    assert queue_name == "queue_name"


async def test_start_consuming_for_commands(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    service_channel = Mock(channel_id=1)
    qc.make_channel = Mock(side_effect=coroutine(lambda _type: service_channel))
    qc.channels[service_channel.channel_id] = {
        "mute": False, "type": "services", "channel": service_channel
    }
    qc.create_queue_and_consume = Mock(side_effect=coroutine(
        lambda channel, on_message_method, queue_name: ("queue_name", "consumer_tag")
    ))

    queue_name = await qc.start_consuming_for_commands()
    assert qc.create_queue_and_consume.called
    assert queue_name == "queue_name"
    assert qc.channels[service_channel.channel_id]["consumer_tag"] == "consumer_tag"


async def test_start_consuming_for_session(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    qc = AsyncQueueConsumer(app)

    # mocks
    session_channel = Mock(channel_id=1)
    qc.make_channel = Mock(side_effect=coroutine(lambda _type: session_channel))
    qc.channels[session_channel.channel_id] = {
        "mute": False, "type": "sessions", "channel": session_channel
    }
    qc.create_queue_and_consume = Mock(side_effect=coroutine(
        lambda channel, on_message_method, queue_name: ("queue_name", "consumer_tag")
    ))

    queue_name = await qc.start_consuming_for_session(session_id=1)
    assert qc.create_queue_and_consume.called
    assert queue_name == "queue_name"
    assert qc.channels[session_channel.channel_id]["consumer_tag"] == "consumer_tag"
    assert qc.channels[session_channel.channel_id]["session"] == 1


async def test_start_consuming_for_platforms(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    app.platforms = {"ubuntu-14.04-x64": 1}
    qc = AsyncQueueConsumer(app)

    # mocks
    platform_channel = Mock(channel_id=1)
    qc.make_channel = Mock(side_effect=coroutine(lambda _type: platform_channel))
    qc.channels[platform_channel.channel_id] = {
        "mute": False, "type": "platforms", "channel": platform_channel
    }
    qc.create_queue_and_consume = Mock(side_effect=coroutine(
        lambda channel, on_message_method, queue_name: ("queue_name", "consumer_tag")
    ))

    await qc.start_consuming_for_platforms()
    assert qc.create_queue_and_consume.called
    assert qc.channels[platform_channel.channel_id]["consumer_tag"] == "consumer_tag"
    assert qc.channels[platform_channel.channel_id]["platform"] == "ubuntu-14.04-x64"


async def test_connect(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    app.platforms = {"ubuntu-14.04-x64": 1}
    qc = AsyncQueueConsumer(app)

    # mocks
    qc.make_connection = Mock(side_effect=coroutine(
        lambda params: (Mock(), Mock())
    ))
    qc.start_consuming_for_commands = Mock(side_effect=coroutine(
        lambda: "queue_name"
    ))
    qc.start_consuming_for_platforms = Mock(side_effect=coroutine(
        lambda: None
    ))

    await qc.connect()
    assert qc.make_connection.called
    assert qc.start_consuming_for_platforms.called
    assert qc.start_consuming_for_commands.called
    assert qc.service_queue
    assert qc.transport
    assert qc.connection


async def test_disconnect(loop):
    app = BaseApplication('app', loop=loop, CONFIG='config.tests')
    app.platforms = {"ubuntu-14.04-x64": 1}
    qc = AsyncQueueConsumer(app)

    # mocks
    qc.connection = Mock(close=Mock(side_effect=coroutine(lambda: None)))
    qc.transport = Mock(close=Mock(side_effect=coroutine(lambda: None)))

    await qc.disconnect()
    assert qc.connection.close.called
    assert qc.transport.close.called
