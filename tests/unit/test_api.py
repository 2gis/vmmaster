# coding: utf-8

import json
from datetime import datetime
from mock import Mock, patch, PropertyMock
from multiprocessing import Process
from helpers import BaseTestCase, fake_home_dir, DatabaseMock, wait_for, custom_wait
from lode_runner import dataprovider
from core import constants


@patch.multiple(
    'core.utils.openstack_utils',
    nova_client=Mock(return_value=Mock())
)
@patch.multiple(
    'vmpool.clone.OpenstackClone',
    _wait_for_activated_service=custom_wait,
    ping_vm=Mock(return_value=True)
)
class TestApi(BaseTestCase):
    def setUp(self):
        from core.config import setup_config
        setup_config('data/config_openstack.py')

        self.mocked_image = Mock(
            id=1, status='active',
            get=Mock(return_value='snapshot'),
            min_disk=20,
            min_ram=2,
            instance_type_flavorid=1,
        )
        type(self.mocked_image).name = PropertyMock(
            return_value='test_origin_1')

        with patch(
            'core.utils.init.home_dir', Mock(return_value=fake_home_dir())
        ), patch(
            'core.logger.setup_logging', Mock(return_value=Mock())
        ), patch(
            'core.db.Database', DatabaseMock()
        ), patch.multiple(
            'vmpool.platforms.OpenstackPlatforms',
            images=Mock(return_value=[self.mocked_image]),
            flavor_params=Mock(return_value={'vcpus': 1, 'ram': 2}),
            limits=Mock(return_value={
                'maxTotalCores': 10, 'maxTotalInstances': 10,
                'maxTotalRAMSize': 100, 'totalCoresUsed': 0,
                'totalInstancesUsed': 0, 'totalRAMUsed': 0}),
        ):
            from vmmaster.server import create_app
            self.app = create_app()

        self.vmmaster_client = self.app.test_client()
        self.platforms = self.app.pool.platforms.platforms
        self.platform = sorted(self.app.pool.platforms.platforms.keys())[0]

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.platform
            }
        }

        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.app.sessions.kill_all()
        self.ctx.pop()
        self.app.cleanup()
        del self.app

    def test_api_sessions(self):
        from core.sessions import Session
        session = Session("session1", self.desired_caps["desiredCapabilities"])
        session.created = session.modified = datetime.now()

        with patch('flask.current_app.sessions.active',
                   Mock(return_value=[session])):
            response = self.vmmaster_client.get('/api/sessions')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        sessions = body['result']['sessions']
        self.assertEqual(1, len(sessions))
        self.assertEqual(self.platform, session.platform)
        self.assertEqual(200, body['metacode'])

        session.failed()

    def test_api_platforms(self):
        response = self.vmmaster_client.get('/api/platforms')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        platforms = body['result']['platforms']
        self.assertEqual(1, len(platforms))
        names = [platform for platform in self.platforms]
        self.assertEqual(names, platforms)
        self.assertEqual(200, body['metacode'])

    def test_api_stop_session(self):
        from core.sessions import Session
        session = Session()
        session.failed = Mock()

        with patch(
            'flask.current_app.sessions.get_session',
            Mock(return_value=session)
        ):
            response = self.vmmaster_client.post("/api/session/%s/stop"
                                                 % session.id)
        body = json.loads(response.data)
        self.assertEqual(200, body['metacode'])

        session.failed.assert_any_call(
            reason=constants.SESSION_CLOSE_REASON_API_CALL)

    def test_get_screenshots(self):
        steps = [
            Mock(screenshot=None),
            Mock(screenshot="/vmmaster/screenshots/1/1.png")
        ]

        with patch('flask.current_app.database.get_log_steps_for_session',
                   Mock(return_value=steps)):
            response = self.vmmaster_client.get('/api/session/1/screenshots')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        screenshots = body['result']['screenshots']
        self.assertEqual(1, len(screenshots))
        self.assertEqual(200, body['metacode'])

    @dataprovider([
        ("/vmmaster/screenshots/1/1.png", 1),
        (None, 0)
    ])
    def test_get_screenshot_for_step(self, screenshot_path, screenshots_count):

        steps = Mock(screenshot=screenshot_path)

        with patch('flask.current_app.database.get_step_by_id',
                   Mock(return_value=steps)):
            response = self.vmmaster_client.get(
                '/api/session/1/step/1/screenshots')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        screenshots = body['result']['screenshots']
        self.assertEqual(screenshots_count, len(screenshots))
        self.assertEqual(200, body['metacode'])

    def test_get_screenshots_for_label(self):

        steps = [
            Mock(control_line="POST /wd/hub/session/23/element HTTP/1.0",
                 id=2,
                 screenshot="/vmmaster/screenshots/1/1.png"),
            Mock(control_line="POST /wd/hub/session/23/vmmasterLabel HTTP/1.0",
                 id=1,
                 screenshot=None)
        ]

        with patch('flask.current_app.database.get_log_steps_for_session',
                   Mock(return_value=steps)):
            response = \
                self.vmmaster_client.get('/api/session/1/label/1/screenshots')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        screenshots = body['result']['screenshots']
        self.assertEqual(1, len(screenshots))
        self.assertEqual(200, body['metacode'])

    def test_failed_get_vnc_info_with_create_proxy(self):
        from core.sessions import Session
        endpoint = Mock(ip='127.0.0.1')
        session = Session()
        session.name = "session1"
        session.created = session.modified = datetime.now()

        expected = 5901

        with patch(
            'flask.current_app.sessions.active',
            Mock(return_value=[session])
        ), patch(
                'websockify.websocketproxy.websockify_init', Mock()
        ):
            session.run(endpoint)
            response = self.vmmaster_client.get(
                '/api/session/%s/vnc_info' % session.id)

        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        vnc_proxy_port = body['result']['vnc_proxy_port']
        self.assertEqual(type(expected), type(vnc_proxy_port))
        self.assertEqual(200, body['metacode'])
        self.assertTrue(isinstance(session.vnc_helper.proxy, Process))

        session.close()
        self.assertTrue(wait_for(
            lambda: not session.vnc_helper.proxy.is_alive()))

    def test_get_vnc_info_for_running_proxy(self):
        from core.sessions import Session
        endpoint = Mock(ip='127.0.0.1')
        session = Session()
        session.name = "session1"
        session.created = session.modified = datetime.now()
        session.run(endpoint)
        session.vnc_helper = Mock(proxy=Mock(),
                                  get_proxy_port=Mock(return_value=5900))

        expected = {
            'vnc_proxy_port': 5900
        }

        response = self.vmmaster_client.get(
            '/api/session/%s/vnc_info' % session.id)

        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        vnc_proxy_port = body['result']
        self.assertDictEqual(expected, vnc_proxy_port)
        self.assertEqual(200, body['metacode'])
        session.close()

    def test_get_vnc_info_if_session_not_found(self):
        with patch(
                'flask.current_app.sessions.active',
                Mock(return_value=[])
        ), patch(
                'websockify.websocketproxy.websockify_init', Mock()
        ), patch(
                'core.utils.network_utils.get_free_port',
                Mock(side_effect=5900)
        ):
            response = self.vmmaster_client.get('/api/session/1/vnc_info')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        vnc_proxy_port = body['result']
        self.assertDictEqual({}, vnc_proxy_port)
        self.assertEqual(500, body['metacode'])

    def test_api_success_delete_endpoint(self):
        vm_for_delete = Mock(name='test_vm_1', delete=Mock())
        success_answer = "Endpoint %s was deleted" % vm_for_delete.name

        with patch(
            'flask.current_app.pool.get_by_name',
            Mock(return_value=vm_for_delete)
        ):
            response = self.vmmaster_client.delete("/api/pool/%s"
                                                   % vm_for_delete.name)

            body = json.loads(response.data)
            self.assertEqual(200, body['metacode'])
            self.assertEqual(success_answer, body['result'])

    def test_api_failed_delete_endpoint(self):
        error = 'Failed'
        vm_for_delete = Mock(
            name='test_vm_1', delete=Mock(side_effect=Exception(error))
        )
        failed_answer = 'Got error during deleting vm %s. ' \
                        '\n\n %s' % (vm_for_delete.name, error)

        with patch(
            'flask.current_app.pool.get_by_name',
            Mock(return_value=vm_for_delete)
        ):
            response = self.vmmaster_client.delete("/api/pool/%s"
                                                   % vm_for_delete.name)

            body = json.loads(response.data)
            self.assertEqual(200, body['metacode'])
            self.assertEqual(failed_answer, body['result'])

    def test_api_success_and_failed_delete_all_endpoints(self):
        vm_name_1 = "test_vm_1"

        class VM:
            def __repr__(self):
                return "test_vm_1"

            def __init__(self, name):
                self.name = name

            def delete(self):
                pass

        fake_pool = [
            VM(vm_name_1),
            Mock(name='test_vm_2', delete=Mock(side_effect=Exception))
        ]

        with patch(
            'flask.current_app.pool.pool', fake_pool
        ), patch(
            'flask.current_app.pool.using', []
        ):
            response = self.vmmaster_client.delete("/api/pool")

            body = json.loads(response.data)
            self.assertEqual(200, body['metacode'])
            self.assertEqual("This endpoints were deleted from pool: "
                             "%s" % [vm_name_1], body['result'])
