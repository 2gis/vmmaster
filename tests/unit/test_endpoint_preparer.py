# coding: utf-8

from lode_runner import dataprovider
from mock import Mock, patch, PropertyMock, MagicMock
from tests.helpers import BaseTestCase
from core.exceptions import CreationException

patch('core.utils.call_in_thread', lambda x: x).start()
app_context = Mock(return_value=Mock(__enter__=Mock(), __exit__=Mock()))


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
            pool=Mock(), sessions=sessions, artifact_collector=Mock(), app_context=app_context
        )
        endpoint_preparer.start_screencast = Mock()
        endpoint_preparer.prepare_endpoint = Mock()

        endpoint_preparer._run_tasks()

        self.assertEqual(endpoint_preparer.prepare_endpoint.called, pec)
        self.assertEqual(endpoint_preparer.start_screencast.called, ssc)

    def test_prepare_endpoint_was_successful(self):
        """
        - call OpenstackClone.prepare_endpoint

        Expected:
        - session wasn't closed
        - session was refreshed
        - endpoint was set set_endpoint_id method
        """
        from vmpool.endpoint import EndpointPreparer
        session = Mock(closed=False, endpoint=None)
        endpoint = Mock()
        pool = Mock(get_vm=Mock(return_value=endpoint))
        endpoint_preparer = EndpointPreparer(
            pool=pool, sessions=Mock(), artifact_collector=Mock(), app_context=app_context
        )
        type(endpoint_preparer).running = PropertyMock(return_value=True)
        endpoint_preparer.prepare_endpoint(session)

        self.assertTrue(session.refresh.called)
        self.assertTrue(session.set_status.called)
        self.assertTrue(session.set_endpoint.called)

    def test_prepare_endpoint_if_session_closed(self):
        """
        - session was closed during starting preparing
        - call OpenstackClone.prepare_endpoint

        Expected:
        - session was refreshed
        - endpoint wasn't set by set_endpoint_id method
        - session status wasn't changed
        """
        from vmpool.endpoint import EndpointPreparer
        session = Mock(closed=True, endpoint=None)
        endpoint = Mock()
        pool = Mock(get_vm=Mock(return_value=endpoint))
        endpoint_preparer = EndpointPreparer(
            pool=pool, sessions=Mock(), artifact_collector=Mock(), app_context=app_context
        )
        type(endpoint_preparer).running = PropertyMock(return_value=True)

        endpoint_preparer.prepare_endpoint(session)

        self.assertTrue(session.refresh.called)
        self.assertTrue(session.set_status.called)
        self.assertFalse(session.set_endpoint_id.called)

    def test_prepare_endpoint_if_endpoint_id_was_existed(self):
        """
        - session.endpoint_id was set and session wasn't closed
        - call OpenstackClone.prepare_endpoint

        Expected:
        - session was refreshed
        - session status wasn't changed
        - endpoint wasn't set set_endpoint_id method
        """
        from vmpool.endpoint import EndpointPreparer
        session = Mock(closed=False, is_preparing=PropertyMock(return_value=True))
        endpoint = Mock()
        pool = Mock(get_vm=Mock(return_value=endpoint))
        endpoint_preparer = EndpointPreparer(
            pool=pool, sessions=Mock(), artifact_collector=Mock(), app_context=app_context
        )
        type(endpoint_preparer).running = PropertyMock(return_value=True)

        endpoint_preparer.prepare_endpoint(session)

        self.assertTrue(session.refresh.called)
        self.assertTrue(session.set_status.called)
        self.assertFalse(session.set_endpoint.called)

    def test_endpoint_was_prepared_but_app_was_stopped(self):
        """
        - session.endpoint_id wasn't set and session wasn't closed
        - call OpenstackClone.prepare_endpoint

        Expected:
        - session was refreshed
        - session status was changed to "preparing"
        - endpoint was deleted
        """
        from vmpool.endpoint import EndpointPreparer
        session = Mock(closed=False, endpoint=None)
        endpoint = Mock()
        pool = Mock(get_vm=Mock(return_value=endpoint))
        endpoint_preparer = EndpointPreparer(
            pool=pool, sessions=Mock(), artifact_collector=Mock(), app_context=app_context
        )
        type(endpoint_preparer).running = PropertyMock(side_effect=[True, False, False])

        endpoint_preparer.prepare_endpoint(session)

        self.assertTrue(endpoint.delete.called)
        self.assertTrue(session.refresh.called)
        self.assertTrue(session.set_status.called)

    def test_if_got_no_endpoint(self):
        """
        - session.endpoint_id wasn't set and session wasn't closed
        - call OpenstackClone.prepare_endpoint

        Expected:
        - session was refreshed
        - session status was changed to "preparing"
        - get_vm returns none
        - session status was changed to "waiting"
        """
        from vmpool.endpoint import EndpointPreparer
        session = Mock(closed=False, endpoint_id=None, is_preparing=PropertyMock(return_value=True))
        endpoint = Mock()
        pool = Mock(get_vm=Mock(return_value=endpoint))
        endpoint_preparer = EndpointPreparer(
            pool=pool, sessions=Mock(), artifact_collector=Mock(), app_context=app_context
        )
        type(endpoint_preparer).running = PropertyMock(return_value=True)

        endpoint_preparer.prepare_endpoint(session, get_endpoint_attempts=2)

        self.assertTrue(session.refresh.called)
        self.assertTrue(session.set_status.called)
        self.assertEqual(session.set_status.call_count, 2)

    def test_if_got_exception_during_getting_endpoint(self):
        """
        - session.endpoint_id wasn't set and session wasn't closed
        - call OpenstackClone.prepare_endpoint with 2 attempts

        Expected:
        - session status was changed to "preparing"
        - session was refreshed
        - exception was raised in get_vm method
        - session status was changed to "waiting"
        """
        from vmpool.endpoint import EndpointPreparer
        session = MagicMock(closed=False, endpoint_id=None, is_preparing=PropertyMock(return_value=True))
        pool = Mock(get_vm=Mock(side_effect=CreationException))
        endpoint_preparer = EndpointPreparer(
            pool=pool, sessions=Mock(), artifact_collector=Mock(), app_context=app_context
        )
        type(endpoint_preparer).running = PropertyMock(return_value=True)

        endpoint_preparer.prepare_endpoint(session, get_endpoint_attempts=2)

        self.assertTrue(session.refresh.called)
        self.assertTrue(session.set_status.called)
        self.assertEqual(session.set_status.call_count, 2)

    def test_prepare_endpoint_with_exception(self):
        from vmpool.endpoint import EndpointPreparer
        session = Mock(set_status=Mock(side_effect=Exception("Error")), closed=False,
                       endpoint=None, is_preparing=PropertyMock(return_value=True))
        endpoint_preparer = EndpointPreparer(
            pool=Mock(), sessions=Mock(), artifact_collector=Mock(), app_context=app_context
        )

        endpoint_preparer.prepare_endpoint(session, get_endpoint_attempts=2)

        self.assertTrue(session.set_status.called)
        self.assertFalse(session.set_endpoint.called)

    def test_start_screencast(self):
        from vmpool.endpoint import EndpointPreparer
        session = Mock()
        endpoint_preparer = EndpointPreparer(
            pool=Mock(), sessions=Mock(), artifact_collector=Mock(), app_context=app_context
        )

        endpoint_preparer.start_screencast(session)

        self.assertTrue(session.set_screencast_started.called)
        self.assertTrue(session.restore.called)
        self.assertTrue(endpoint_preparer.artifact_collector.record_screencast.called)
