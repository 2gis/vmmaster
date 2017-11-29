# coding: utf-8

import json
from datetime import datetime
from mock import Mock, patch, PropertyMock
from lode_runner import dataprovider

from tests.helpers import BaseTestCase, fake_home_dir, DatabaseMock
from core import constants


class TestVmmasterApi(BaseTestCase):
    def setUp(self):
        from core.config import setup_config
        setup_config('data/config_openstack.py')

        with patch(
            'core.utils.init.home_dir', Mock(return_value=fake_home_dir())
        ), patch(
            'core.video.start_vnc_proxy', Mock(return_value=(99999, 99999))
        ), patch(
            'core.utils.kill_process', Mock()
        ), patch(
            'core.db.Database', DatabaseMock()
        ):
            from vmmaster.server import create_app
            self.app = create_app()

        self.vmmaster_client = self.app.test_client()
        self.platform = 'origin_1'

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

    def test_get_vnc_proxy_port_if_session_is_waiting(self):
        from core.db.models import Session, Endpoint, Provider
        provider = Provider(name='noname', url='nourl')
        endpoint = Endpoint(Mock(), '', provider)
        endpoint.ip = '127.0.0.1'
        endpoint.name = 'test_endpoint'
        endpoint.ports = {'4455': 4455, '9000': 9000, '5900': 5900}
        session = Session("some_platform")
        session.name = "session1"
        session.id = 1
        session.status = "waiting"
        session.vnc_proxy_port = None
        session.vnc_proxy_pid = None
        session.created = session.modified = datetime.now()
        session.endpoint = endpoint

        with patch(
            'flask.current_app.sessions.get_session', Mock(return_value=session)
        ):
            response = self.vmmaster_client.get('/api/session/{}/vnc_info'.format(session.id))

        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({}, body['result'])
        self.assertEqual(500, body['metacode'])

    def test_start_new_proxy(self):
        from core.db.models import Session, Endpoint, Provider
        provider = Provider(name='noname', url='nourl')
        endpoint = Endpoint(Mock(), '', provider)
        endpoint.ip = '127.0.0.1'
        endpoint.name = 'test_endpoint'
        endpoint.ports = {'4455': 4455, '9000': 9000, '5900': 5900}
        session = Session("some_platform")
        session.id = 1
        session.name = "session1"
        session.status = "running"
        session.vnc_proxy_port = None
        session.vnc_proxy_pid = None
        session.created = session.modified = datetime.now()
        session.endpoint = endpoint
        session.stop_vnc_proxy = Mock()

        with patch(
            'flask.current_app.sessions.get_session', Mock(return_value=session)
        ):
            response = self.vmmaster_client.get('/api/session/{}/vnc_info'.format(session.id))
            session._close()

        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({'vnc_proxy_port': 99999}, body['result'])
        self.assertEqual(200, body['metacode'])
        self.assertTrue(session.stop_vnc_proxy.called)

    def test_when_during_proxy_starting_already_started_from_other_thread(self):
        from core.db.models import Session, Endpoint, Provider
        provider = Provider(name='noname', url='nourl')
        endpoint = Endpoint(Mock(), '', provider)
        endpoint.ip = '127.0.0.1'
        endpoint.name = 'test_endpoint'
        endpoint.ports = {'4455': 4455, '9000': 9000, '5900': 5900}
        session = Session("some_platform")
        session.id = 1
        session.name = "session1"
        session.status = "running"
        type(session).vnc_proxy_port = PropertyMock(side_effect=[None, 55555, 55555])
        session.vnc_proxy_pid = 55555
        session.created = session.modified = datetime.now()
        session.endpoint = endpoint
        session.stop_vnc_proxy = Mock()

        with patch(
            'flask.current_app.sessions.get_session', Mock(return_value=session)
        ):
            response = self.vmmaster_client.get('/api/session/{}/vnc_info'.format(session.id))
            session._close()

        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({'vnc_proxy_port': 55555}, body['result'])
        self.assertEqual(200, body['metacode'])
        self.assertTrue(session.stop_vnc_proxy.called)

    def test_when_during_proxy_starting_session_was_closed(self):
        from core.db.models import Session, Endpoint, Provider
        provider = Provider(name='noname', url='nourl')
        endpoint = Endpoint(Mock(), '', provider)
        endpoint.ip = '127.0.0.1'
        endpoint.name = 'test_endpoint'
        endpoint.ports = {'4455': 4455, '9000': 9000, '5900': 5900}
        session = Session("some_platform")
        session.id = 1
        session.name = "session1"
        session.status = "running"
        session.closed = True
        type(session).vnc_proxy_port = PropertyMock(side_effect=[None, 55555, 55555])
        session.vnc_proxy_pid = 55555
        session.created = session.modified = datetime.now()
        session.endpoint = endpoint
        session.stop_vnc_proxy = Mock()

        with patch(
            'flask.current_app.sessions.get_session', Mock(return_value=session)
        ):
            response = self.vmmaster_client.get('/api/session/%s/vnc_info' % session.id)

        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({}, body['result'])
        self.assertEqual(500, body['metacode'])

    def test_get_vnc_port_if_running_proxy(self):
        from core.db.models import Session, Endpoint, Provider
        provider = Provider(name='noname', url='nourl')
        endpoint = Endpoint(Mock(), '', provider)
        endpoint.ip = '127.0.0.1'
        endpoint.name = 'test_endpoint'
        endpoint.ports = {'4455': 4455, '9000': 9000, '5900': 5900}
        session = Session("some_platform")
        session.id = 1
        session.name = "session1"
        session.status = "running"
        session.vnc_proxy_port = 55555
        session.vnc_proxy_pid = 55555
        session.created = session.modified = datetime.now()
        session.endpoint = endpoint
        session.stop_vnc_proxy = Mock()

        with patch(
            'flask.current_app.sessions.get_session', Mock(return_value=session)
        ), patch(
            'core.utils.kill_process', Mock(return_value=True)
        ):
            response = self.vmmaster_client.get('/api/session/%s/vnc_info' % session.id)
            session._close()

        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({'vnc_proxy_port': 55555}, body['result'])
        self.assertEqual(200, body['metacode'])
        self.assertTrue(session.stop_vnc_proxy.called)

    def test_get_vnc_info_if_session_not_found(self):
        with patch(
            'flask.current_app.sessions.get_session', Mock(return_value=None)
        ):
            response = self.vmmaster_client.get('/api/session/1/vnc_info')

        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({}, body['result'])
        self.assertEqual(500, body['metacode'])

    def test_api_sessions(self):
        from core.db.models import Session
        session = Session(self.platform, "session1", self.desired_caps["desiredCapabilities"])
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

    def test_api_stop_session(self):
        from core.db.models import Session
        session = Session("some_platform")
        session.failed = Mock()

        with patch(
            'flask.current_app.sessions.get_session',
            Mock(return_value=session)
        ):
            response = self.vmmaster_client.get("/api/session/{}/stop".format(session.id))
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


class TestProviderApi(BaseTestCase):
    def setUp(self):
        from core.config import setup_config
        setup_config('data/config_openstack.py')

        with patch(
            'core.utils.init.home_dir', Mock(return_value=fake_home_dir())
        ), patch(
            'core.db.Database', DatabaseMock()
        ), patch(
            'vmpool.virtual_machines_pool.VirtualMachinesPool', Mock()
        ):
            from vmpool.server import create_app
            from vmpool.virtual_machines_pool import VirtualMachinesPool
            self.app = create_app()
            self.app.pool = VirtualMachinesPool(
                self.app, 'unnamed', platforms_class=Mock(), preloader_class=Mock(),
                artifact_collector_class=Mock(), endpoint_preparer_class=Mock(), endpoint_remover_class=Mock()
            )

        self.vmmaster_client = self.app.test_client()
        self.platform = 'origin_1'

        self.ctx = self.app.app_context()
        self.ctx.push()

    @patch('vmpool.api.helpers.get_platforms', Mock(return_value=['origin_1']))
    def test_api_platforms(self):
        response = self.vmmaster_client.get('/api/platforms')
        body = json.loads(response.data)
        platforms = body['result']['platforms']

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(platforms))

        names = [platform for platform in platforms]

        self.assertEqual(names[0], self.platform)
        self.assertEqual(200, body['metacode'])

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
            'vmpool.api.helpers.get_active_sessions', Mock(return_value=fake_pool)
        ):
            response = self.vmmaster_client.delete("/api/pool")

            body = json.loads(response.data)
            self.assertEqual(200, body['metacode'])
            self.assertEqual("This endpoints were deleted from pool: {}".format([vm_name_1]), body['result'])
