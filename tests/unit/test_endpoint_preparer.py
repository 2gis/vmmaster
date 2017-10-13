# coding: utf-8
from lode_runner import dataprovider
from mock import Mock, patch
from tests.helpers import BaseTestCase

patch('core.utils.call_in_thread', lambda x: x).start()
app_context = Mock(return_value=Mock(__enter__=Mock(), __exit__=Mock()))


def get_endpoint_mock(*args, **kwargs):
    yield Mock(id=1)


class TestEndpointPreparer(BaseTestCase):
    def setUp(self):
        from core.config import setup_config
        setup_config('data/config_openstack.py')

    @dataprovider([
        (True, False, True, False, False, True),
        (False, False, True, True, True, False),
    ])
    def test_run_preparer(self, is_running, screencast_started, take_screencast, is_waiting, pec, ssc):
        from vmpool.endpoint import EndpointPreparer
        sessions = Mock(active=Mock(return_value=[
            Mock(
                is_running=is_running, screencast_started=screencast_started,
                take_screencast=take_screencast, is_waiting=is_waiting
            )
        ]))
        endpoint_preparer = EndpointPreparer(
            sessions=sessions, artifact_collector=Mock(), app_context=app_context
        )
        endpoint_preparer.start_screencast = Mock()
        endpoint_preparer.prepare_endpoint = Mock()

        endpoint_preparer._run_tasks()

        self.assertEqual(endpoint_preparer.prepare_endpoint.called, pec)
        self.assertEqual(endpoint_preparer.start_screencast.called, ssc)

    @patch('vmpool.endpoint.get_endpoint', get_endpoint_mock)
    def test_prepare_endpoint(self):
        from vmpool.endpoint import EndpointPreparer
        session = Mock()
        endpoint_preparer = EndpointPreparer(
            sessions=Mock(), artifact_collector=Mock(), app_context=app_context
        )

        endpoint_preparer.prepare_endpoint(session)

        self.assertTrue(session.set_status.called)
        self.assertTrue(session.set_endpoint_id.called)

    @patch('vmpool.endpoint.get_endpoint', get_endpoint_mock)
    def test_prepare_endpoint_with_exception(self):
        from vmpool.endpoint import EndpointPreparer
        session = Mock(set_status=Mock(side_effect=Exception("Error")))
        endpoint_preparer = EndpointPreparer(
            sessions=Mock(), artifact_collector=Mock(), app_context=app_context
        )

        endpoint_preparer.prepare_endpoint(session)

        self.assertTrue(session.set_status.called)
        self.assertFalse(session.set_endpoint_id.called)

    def test_start_screencast(self):
        from vmpool.endpoint import EndpointPreparer
        session = Mock()
        endpoint_preparer = EndpointPreparer(
            sessions=Mock(), artifact_collector=Mock(), app_context=app_context
        )

        endpoint_preparer.start_screencast(session)

        self.assertTrue(session.set_screencast_started.called)
        self.assertTrue(session.restore.called)
        self.assertTrue(endpoint_preparer.artifact_collector.record_screencast.called)
