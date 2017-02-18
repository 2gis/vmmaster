# coding: utf-8

import logging

from core.config import config
from core.utils import exception_handler
from core.clients.docker_client import DockerManageClient

log = logging.getLogger(__name__)


class DockerNetwork:
    network = None

    def __init__(self):
        self.name = config.DOCKER_NETWORK_NAME
        self.client = DockerManageClient()
        self.network = self.create()

    def create(self):
        """

        :rtype: DNetwork
        """
        self.delete(self.name)
        return self.client.create_network(self.name)

    @exception_handler()
    def delete(self, name=None):
        if not name and self.network and self.network.id:
            name = self.network.id
        if name:
            self.client.delete_network(name)
        else:
            log.error("Can't delete network with name equals None")

    def connect_container(self, container_id):
        self.network.connect(container_id)

    def disconnect_container(self, container_id):
        self.network.disconnect(container_id)
