# coding: utf-8

from mock import patch, Mock
from tests.helpers import BaseTestCase, DatabaseMock, wait_for


class TestVNCVideoHelper(BaseTestCase):
    def setUp(self):
        from core.config import setup_config
        setup_config('data/config_openstack.py')

    def test_run_recorder(self):
        """
        - call session.run()
        - call session.succeed()

        Expected: vnc_recorder was started and stopped
        """
        with patch(
            'core.video.VNCVideoHelper._flvrec', Mock()
        ), patch(
            'core.video.VNCVideoHelper.start_recording', Mock()
        ) as start_rec_mock, patch(
            'core.video.VNCVideoHelper.stop', Mock()
        ) as stop_rec_mock, patch(
            'core.video.VNCVideoHelper.is_alive', Mock(return_value=True)
        ):
            from vmpool.artifact_collector import ArtifactCollector

            session = Mock(endpoint=Mock(prefix="ondemand", ip='127.0.0.1'), closed=False)
            artifact_collector = ArtifactCollector(database=DatabaseMock())
            artifact_collector.record_screencast(session)

            wait_for(lambda: artifact_collector.in_queue, timeout=5)

            session.closed = True

            wait_for(lambda: not artifact_collector.in_queue, timeout=5)
            self.assertTrue(start_rec_mock.called)
            self.assertTrue(stop_rec_mock.called)
