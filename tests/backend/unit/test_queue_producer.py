# coding: utf-8

from asyncio import coroutine
from mock import patch, Mock
from core.common import BaseApplication
from backend.queue_producer import AsyncQueueProducer


async def test_add_message_with_response(loop):
    app = BaseApplication('app', loop=loop, CONFIG='settings')
    with patch(
        'backend.queue_producer.AsyncQueueProducer.channel', new=Mock()
    ):
        qp = AsyncQueueProducer(app)
        qp.channel.basic_publish = Mock(side_effect=coroutine(
            lambda payload, exchange_name, routing_key, properties: None
        ))
        qp.channel.basic_client_ack = Mock(side_effect=coroutine(
            lambda delivery_tag: None
        ))

        correlation_id = await qp.add_msg_to_queue('queue1', '{"id": 1}')
        assert len(qp.messages) == 1
        await qp.on_message(qp.channel, "response", Mock(delivery_tag='1'), Mock(correlation_id=correlation_id))
        assert qp.messages[correlation_id]
        response = await qp.get_message_from_queue(correlation_id)
        assert response == "response"
        assert qp.channel.basic_publish.called
        assert qp.channel.basic_client_ack.called


async def test_create_queue_and_consume_with_autoname(loop):
    app = BaseApplication('app', loop=loop, CONFIG='settings')
    with patch(
        'backend.queue_producer.AsyncQueueProducer.channel', new=Mock()
    ):
        qp = AsyncQueueProducer(app)
        qp.channel.basic_consume = Mock(side_effect=coroutine(
            lambda callback, queue_name, no_ack: 'consumer_tag'
        ))
        qp.channel.queue_declare = Mock(side_effect=coroutine(
            lambda exclusive: {"queue": "queue_name", "message_count": 0, "consumer_count": 0}
        ))

        queue_name, consumer_tag = await qp.create_queue_and_consume()
        assert queue_name, consumer_tag == ('queue_name', 'consumer_tag')
        assert qp.channel.basic_consume.called
        assert qp.channel.queue_declare.called


async def test_create_queue_and_consume(loop):
    app = BaseApplication('app', loop=loop, CONFIG='settings')
    with patch(
        'backend.queue_producer.AsyncQueueProducer.channel', new=Mock()
    ):
        qp = AsyncQueueProducer(app)
        qp.channel.basic_consume = Mock(side_effect=coroutine(
            lambda callback, queue_name, no_ack: 'consumer_tag'
        ))
        qp.channel.queue_declare = Mock(side_effect=coroutine(
            lambda queue_name: {"queue": queue_name, "message_count": 0, "consumer_count": 0}
        ))

        queue_name, consumer_tag = await qp.create_queue_and_consume(queue_name='queue_name')
        assert queue_name, consumer_tag == ('queue_name', 'consumer_tag')
        assert qp.channel.basic_consume.called
        assert qp.channel.queue_declare.called


async def test_delete_queue(loop):
    app = BaseApplication('app', loop=loop, CONFIG='settings')
    with patch(
        'backend.queue_producer.AsyncQueueProducer.channel', new=Mock()
    ):
        qp = AsyncQueueProducer(app)
        qp.channel.queue_delete = Mock(side_effect=coroutine(
            lambda queue_name: None
        ))

        await qp.delete_queue(queue_name='queue_name')
        assert qp.channel.queue_delete.called


async def test_make_connection(loop):
    app = BaseApplication('app', loop=loop, CONFIG='settings')
    with patch(
        'aioamqp.connect', new=Mock(side_effect=coroutine(lambda: (Mock(), Mock())))
    ) as amqp_connect:
        qp = AsyncQueueProducer(app)
        await qp.make_connection({})
        assert amqp_connect.called


async def test_connect(loop):
    app = BaseApplication('app', loop=loop, CONFIG='settings')
    qp = AsyncQueueProducer(app)
    qp.make_connection = Mock(side_effect=coroutine(
        lambda queue_name: Mock(channel=Mock(side_effect=coroutine(lambda: None)))
    ))
    qp.create_queue_and_consume = Mock(side_effect=coroutine(
        lambda: ("queue_name", "consumer_tag")
    ))
    qp.create_queue = Mock(side_effect=coroutine(
        lambda queue_name: {"queue": queue_name, "message_count": 0, "consumer_count": 0}
    ))

    await qp.connect()
    assert qp.make_connection.called
    assert qp.create_queue_and_consume.called
    assert qp.create_queue.called


async def test_add_msg_w_response(loop):
    app = BaseApplication('app', loop=loop, CONFIG='settings')
    qp = AsyncQueueProducer(app)
    qp.add_msg_to_queue = Mock(side_effect=coroutine(
        lambda q, m: "24d8f597g8utr"
    ))
    qp.get_message_from_queue = Mock(side_effect=coroutine(
        lambda cid: "response"
    ))

    await qp.add_msg_to_queue_with_response('queue1', "qweqwe")
    assert qp.add_msg_to_queue.called
    assert qp.get_message_from_queue.called
