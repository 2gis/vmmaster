# coding: utf-8
from mock import Mock, patch
from tests.helpers import BaseTestCase

patch('core.utils.call_in_thread', lambda x: x).start()
app_context = Mock(return_value=Mock(__enter__=Mock(), __exit__=Mock()))


class TestEndpointRemover(BaseTestCase):
    def setUp(self):
        from core.config import setup_config
        setup_config('data/config_openstack.py')

    def test_remove_endpoint(self):
        from vmpool.virtual_machines_pool import EndpointRemover

        endpoint = Mock()
        endpoint_remover = EndpointRemover(
            platforms=Mock(), artifact_collector=Mock(),
            database=Mock(), app_context=app_context
        )
        endpoint_remover.remove_endpoint(endpoint)

        self.assertTrue(endpoint.service_mode_on.called)
        self.assertTrue(endpoint_remover.database.get_session_by_endpoint_id.called)

        self.assertTrue(endpoint_remover.artifact_collector.save_selenium_log.called)
        self.assertTrue(endpoint_remover.artifact_collector.wait_for_complete.called)

        self.assertTrue(endpoint.delete.called)
        self.assertTrue(endpoint.service_mode_off.called)

    def test_stop(self):
        from vmpool.virtual_machines_pool import EndpointRemover

        endpoint_remover = EndpointRemover(
            platforms=Mock(wait_for_service=[]), artifact_collector=Mock(),
            database=Mock(), app_context=app_context
        )
        endpoint_remover.remove_all = Mock()
        endpoint_remover.remove_endpoint = Mock()

        endpoint_remover.start()
        endpoint_remover.stop()

        self.assertTrue(endpoint_remover.remove_all.called)
