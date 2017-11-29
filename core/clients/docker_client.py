# coding: utf-8
import logging

from core.config import config
from core.utils import exception_handler, api_exception_handler


log = logging.getLogger(__name__)


class DockerContainer:
    def __init__(self, origin):
        """

        :type origin: Container
        """
        self.origin = origin

    @property
    @exception_handler(return_on_exc="")
    def id(self):
        return self.origin.id

    @property
    def short_id(self):
        return self.origin.short_id

    @property
    @exception_handler(return_on_exc="")
    def name(self):
        return self.origin.name

    @property
    @exception_handler(return_on_exc="")
    def status(self):
        return self.origin.status

    @property
    def ip(self):
        if config.BIND_LOCALHOST_PORTS:
            return config.PUBLIC_IP
        else:
            networks = self.origin.attrs["NetworkSettings"]["Networks"]
            return networks.get("vmmaster", {}).get("IPAddress", "")

    @property
    def ports(self):
        _ports = {}
        try:
            for original_port, bind_port in self.origin.attrs["NetworkSettings"]["Ports"].items():
                original_port = str(original_port.replace("/tcp", ""))
                _ports[original_port] = str(bind_port[0]["HostPort"])
        except:
            log.debug("Network settings isn't available")
        return _ports

    @exception_handler()
    def exec_run(self, cmd, *args, **kwargs):
        return self.origin.exec_run(cmd=cmd, detach=True, *args, **kwargs)

    @exception_handler()
    def export(self):
        raise NotImplementedError

    @exception_handler()
    def get_archive(self):
        raise NotImplementedError

    @exception_handler()
    def kill(self, signal=None):
        return self.origin.kill(signal=signal)

    @exception_handler()
    def logs(self, **kwargs):
        return self.origin.logs(**kwargs)

    @api_exception_handler()
    def remove(self, **kwargs):
        kwargs["force"] = True
        return self.origin.remove(**kwargs)

    @exception_handler()
    def rename(self):
        raise NotImplementedError

    @exception_handler()
    def restart(self, **kwargs):
        return self.origin.restart(**kwargs)

    @exception_handler()
    def stop(self, **kwargs):
        return self.origin.stop(**kwargs)

    @exception_handler()
    def pause(self):
        raise NotImplementedError

    @exception_handler()
    def unpause(self):
        raise NotImplementedError


class DockerManageClient:
    def __init__(self):
        from docker import DockerClient
        self.client = DockerClient(
            base_url=config.DOCKER_BASE_URL,
            timeout=config.DOCKER_TIMEOUT,
            num_pools=config.DOCKER_NUM_POOLS
        )

    @api_exception_handler()
    def containers(self, all=None, before=None, filters=None, limit=-1, since=None):
        return [
            DockerContainer(container) for container in self.client.containers.list(
                all=all, before=before, filters=filters, limit=limit, since=since
            )
        ]

    @exception_handler()
    def get_container(self, container_id):
        return DockerContainer(
            self.client.containers.get(container_id)
        )

    @exception_handler()
    def create_container(self, image, command=None):
        return self.get_container(
            self.client.containers.create(image=image, command=command)
        )

    def run_container(self, image, ports, name=None, env_vars=None, *args, **kwargs):
        """

        :type image: str
        :type ports: list
        :type name: str
        :type env_vars: dict
        :rtype: DockerContainer
        """
        if config.BIND_LOCALHOST_PORTS:
            kwargs["ports"] = {"%s/tcp" % port: None for port in ports}
        if name:
            kwargs["name"] = name
        if env_vars:
            kwargs["environment"] = env_vars

        kwargs.update({
            "dns": config.DNS_LIST,
            "dns_search": config.DNS_SEARCH_LIST,
            "image": image,
            "privileged": True,
            "mem_limit": config.DOCKER_CONTAINER_MEMORY_LIMIT,
            "cpu_period": config.DOCKER_CONTAINER_CPU_PERIOD,
            "cpu_quota": config.DOCKER_CONTAINER_CPU_QUOTA,
            "detach": True,
            "publish_all_ports": True,
            "volumes": config.DOCKER_CONTAINER_VOLUMES,
        })
        return DockerContainer(self.client.containers.run(*args, **kwargs))

    @exception_handler()
    def get_image(self, name):
        from vmpool.platforms import DockerImage
        return DockerImage(self.client.images.get(name=name))

    @exception_handler()
    def images(self, name=None, all=None, filters=None):
        from vmpool.platforms import DockerImage
        return [
            DockerImage(image) for image in self.client.images.list(
                name=name, all=all, filters=filters) if len(image.tags)
        ]

    def create_network(self, network_name):
        """

        :rtype: Network
        """
        import docker
        ipam_pool = docker.types.IPAMPool(
            subnet=config.DOCKER_SUBNET,
            gateway=config.DOCKER_GATEWAY
        )
        ipam_config = docker.types.IPAMConfig(
            pool_configs=[ipam_pool]
        )
        return self.client.networks.create(
            network_name,
            check_duplicate=True,
            ipam=ipam_config
        )

    @exception_handler()
    def delete_network(self, network_id):
        network = self.client.networks.get(network_id)
        if network:
            network.remove()
