# coding: utf-8
import os
import json
import logging
import requests
from Queue import Queue
from threading import Thread
from core.logger import setup_logging
from core.config import setup_config, config
from core.utils.init import home_dir


setup_config('%s/config.py' % home_dir())


from core.utils import openstack_utils


setup_logging(
    log_type=getattr(config, "LOG_TYPE", None),
    log_level=getattr(config, "LOG_LEVEL", None)
)
log = logging.getLogger(__name__)


class RequestHelper(object):
    method = None
    url = None
    headers = None
    data = None

    def __init__(self, method, url="/", headers=None, data=""):
        _headers = {}
        if headers:
            for key, value in headers.items():
                if value:
                    _headers[key] = value
        _headers["Content-Length"] = str(len(data))
        self.headers = _headers
        self.method = method
        self.url = url
        self.data = data

    def __repr__(self):
        return "<RequestHelper method:%s url:%s headers:%s body:%s>" % (
            self.method, self.url, self.headers, self.data)


def getresponse(req, q):
    try:
        q.put(req())
    except Exception as e:
        q.put(e)


class Remover:
    def __init__(self):
        self.nova_client = openstack_utils.nova_client()

    def make_request(self, request, timeout=180):
        q = Queue()
        url = "{}".format(request.url)

        def req():
            return requests.request(method=request.method,
                                    url=url,
                                    headers=request.headers,
                                    data=request.data,
                                    timeout=timeout)

        t = Thread(target=getresponse, args=(req, q))
        t.daemon = True
        t.start()

        while t.isAlive():
            yield None, None, None

        response = q.get()
        if isinstance(response, Exception):
            raise response

        yield response.status_code, response.headers, response.content

    def get_endpoints_from_openstack(self):
        return self.nova_client.servers.list()

    def get_endpoints_from_vmmaster(self):
        body = None
        for code, headers, body in self.make_request(
            request=RequestHelper(
                method="GET", url=os.environ.get("API_URL")
            )
        ):
            pass
        results = json.loads(body)["result"]["pool"]
        endpoints = results["pool"]["list"]
        endpoints.extend(results["using"]["list"])
        endpoints.extend(results["on_service"]["list"])
        endpoints.extend(results["wait_for_service"]["list"])
        return endpoints

    def run(self):
        os_endpoints = self.get_endpoints_from_openstack()
        vm_endpoints = self.get_endpoints_from_vmmaster()
        vm_endpoints = [ep.get("name", None) for ep in vm_endpoints]

        self.remove_not_in_vmmaster_from_openstack(vm_endpoints, os_endpoints)
        self.remove_not_existing_from_vmmaster(vm_endpoints)

    @staticmethod
    def remove_not_in_vmmaster_from_openstack(vm_endpoints, os_endpoints):
        not_delete = {}
        for_delete = {}

        for os_endpoint in os_endpoints:
            if os.environ.get("ENDPOINTS_PREFIX", "unprefix") in os_endpoint.name:
                if os_endpoint.name in vm_endpoints:
                    not_delete[os_endpoint.name] = os_endpoint
                else:
                    for_delete[os_endpoint.name] = os_endpoint

        for endpoint in for_delete.values():
            log.info("Removing %s" % endpoint.name)
            try:
                endpoint.delete()
                log.info("Endpoint %s was successful deleted" % endpoint.name)
            except:
                log.exception("Can't delete endpoint %s" % endpoint.name)
        log.warn("Endpoints %s(for delete) and %s(not delete)" % (len(for_delete), len(not_delete)))

    def remove_not_existing_from_vmmaster(self, vm_endpoints):
        not_delete = {}
        for_delete = {}
        for endpoint in vm_endpoints:
            try:
                exist = self.nova_client.servers.find(name=endpoint)
                if exist.status == "SHUTOFF":
                    raise
                log.info("Endpoint %s is exist %s" % (endpoint, exist.status))
                not_delete[endpoint] = endpoint
            except:
                resp_code = None
                for code, headers, body in self.make_request(
                    request=RequestHelper(
                        method="DELETE", url="{}/{}".format(os.environ.get("API_URL"), endpoint)
                    )
                ):
                    resp_code = code
                for_delete[endpoint] = endpoint
                log.info("Removed %s" % endpoint)

        log.warn("Endpoints %s(for delete) and %s(not delete)" % (len(for_delete), len(not_delete)))


if __name__ == "__main__":
    remover = Remover()
    remover.run()
