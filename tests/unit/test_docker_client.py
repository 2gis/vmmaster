# coding: utf-8
from unittest import skip
from mock import patch, Mock
from tests.unit.helpers import BaseTestCase


class TestDockerClient(BaseTestCase):
    def setUp(self):
        with patch("docker.DockerClient", Mock()):
            from core.config import setup_config
            from core.clients.docker_client import DockerManageClient
            setup_config('data/config_openstack.py')
            self.docker_client = DockerManageClient()

    @skip
    def test_create_container(self):
        from core.clients.docker_client import DockerContainer
        container = self.docker_client.create_container("image")

        self.assertTrue(self.docker_client.client.containers.create.called)
        self.assertTrue(self.docker_client.client.containers.get.called)
        self.assertTrue(isinstance(container, DockerContainer))

    @skip
    def test_get_containers_list(self):
        self.docker_client.client.containers.list = Mock(return_value=[Mock()])

        containers_list = self.docker_client.containers()

        self.assertTrue(len(containers_list), 1)

    @skip
    def test_run_container(self):
        from core.clients.docker_client import DockerContainer

        container = self.docker_client.run_container("image")

        self.assertTrue(self.docker_client.client.containers.run.called)
        self.assertTrue(isinstance(container, DockerContainer))

    @skip
    def test_get_image(self):
        from vmpool.platforms import DockerImage

        container = self.docker_client.get_image("image")

        self.assertTrue(self.docker_client.client.images.get.called)
        self.assertTrue(isinstance(container, DockerImage))

    @skip
    def test_get_images_list(self):
        self.docker_client.client.images.list = Mock(return_value=[Mock(tags=["123"])])

        images_list = self.docker_client.images()

        self.assertTrue(self.docker_client.client.images.get.called)
        self.assertTrue(len(images_list), 1)

    @skip
    def test_create_network(self):
        self.docker_client.create_network("network")
        self.assertTrue(self.docker_client.client.networks.create.called)
