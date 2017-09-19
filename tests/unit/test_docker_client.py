# coding: utf-8
from mock import patch, Mock
from tests.helpers import BaseTestCase


class TestDockerClient(BaseTestCase):
    def setUp(self):
        with patch("docker.DockerClient", Mock(
            containers=Mock(
                create=Mock(),
                get=Mock()
            )
        )):
            from core.config import setup_config
            from core.clients.docker_client import DockerManageClient
            setup_config('data/config_openstack.py')
            self._docker_client = DockerManageClient()

    def test_create_container(self):
        from core.clients.docker_client import DockerContainer
        container = self._docker_client.create_container("image")

        self.assertTrue(self._docker_client.client.containers.create.called)
        self.assertTrue(self._docker_client.client.containers.get.called)
        self.assertTrue(isinstance(container, DockerContainer))

    def test_get_containers_list(self):
        self._docker_client.client.containers.list = Mock(return_value=[Mock()])

        containers_list = self._docker_client.containers()

        self.assertTrue(len(containers_list), 1)

    def test_run_container(self):
        from core.clients.docker_client import DockerContainer

        container = self._docker_client.run_container("image")

        self.assertTrue(self._docker_client.client.containers.run.called)
        self.assertTrue(isinstance(container, DockerContainer))

    def test_get_image(self):
        from vmpool.platforms import DockerImage

        container = self._docker_client.get_image("image")

        self.assertTrue(self._docker_client.client.images.get.called)
        self.assertTrue(isinstance(container, DockerImage))

    def test_get_images_list(self):
        self._docker_client.client.images.list = Mock(return_value=[Mock(tags=["123"])])

        images_list = self._docker_client.images()

        self.assertTrue(self._docker_client.client.images.list.called)
        self.assertTrue(len(images_list), 1)

    def test_create_network(self):
        self._docker_client.create_network("network")
        self.assertTrue(self._docker_client.client.networks.create.called)
