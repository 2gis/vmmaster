# coding: utf-8
import json
import logging
from io import BytesIO
from tests.helpers import BaseTestCase
from lode_runner import dataprovider
from core.logger import LogstashFormatter


class LogStreamHandlerTest(BaseTestCase):
    def setUp(self):
        self.logger = logging.getLogger('logging-test')
        self.logger.setLevel(logging.DEBUG)
        self.buffer = BytesIO()
        self.logHandler = logging.StreamHandler(self.buffer)
        self.logger.addHandler(self.logHandler)

    @dataprovider([
        "test message",
        "{0}"
    ])
    def test_properties(self, msg):
        props = {
            "message": msg,
            "@version": "1",
            "level": "INFO"
        }
        self.logHandler.setFormatter(LogstashFormatter())
        self.logger.info(msg)
        log_json = json.loads(self.buffer.getvalue())
        self.assertEqual(log_json.get("@version"), props["@version"])
        self.assertEqual(log_json.get("tags"), list())
        self.assertTrue(isinstance(log_json.get("@timestamp"), unicode))
        self.assertEqual(log_json["message"], msg)

    @dataprovider([
        {"custom_field": 1},
        {"@1": "1"}
    ])
    def test_extra_properties(self, extra):
        self.logHandler.setFormatter(LogstashFormatter())
        self.logger.info("test message", extra=extra)
        log_json = json.loads(self.buffer.getvalue())
        key = extra.keys()[0]
        self.assertEqual(log_json.get(key), extra[key])
