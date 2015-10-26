# coding: utf-8

from Queue import Queue
import json
import os
import errno
import pwd
import grp
import requests
import time
import sys


from twisted.internet import threads
from threading import Thread

from core.config import config
from core.utils import system_utils, commands
from core.logger import log


class UserNotFound(Exception):
    pass


class GroupNotFound(Exception):
    pass


class NoPermission(Exception):
    pass


def convert_img_to_qcow2_origin(img_file, qcow2_origin_name):
    command = commands.convert_img_to_qcow2(
        img_file,
        "{origins_dir}/{qcow2_origin_name}.qcow2".format(
            origins_dir=config.ORIGINS_DIR,
            qcow2_origin_name=qcow2_origin_name,
        )
    )
    system_utils.run_command(command)


def clone_qcow2_drive(origin_name, clone_name):
    clone_path = os.path.join(config.CLONES_DIR, "%s.qcow2" % clone_name)
    origin_path = os.path.join(config.ORIGINS_DIR, origin_name, "drive.qcow2")

    command = commands.clone_qcow2_drive(origin_path, clone_path)
    system_utils.run_command(command)
    return clone_path


def write_clone_dumpxml(clone_name, xml):
    # saving to dir
    dumpxml_path = "{clones_dir}/{clone_name}.xml".format(
        clones_dir=config.CLONES_DIR,
        clone_name=clone_name
    )
    file_handler = open(dumpxml_path, "w")
    xml.writexml(file_handler)
    return dumpxml_path


def rm(files):
    command = ["rm", "-f"]
    command += files
    code, text = system_utils.run_command(command)
    if code:
        raise Exception(text)


def delete_file(filename):
    if filename is None:
        return
    try:
        os.remove(filename)
    # this would be "except OSError as e:" in python 3.x
    except OSError, e:
        # errno.ENOENT = no such file or directory
        if e.errno != errno.ENOENT:
            # re-raise exception if a different error occured
            raise


def write_file(path, content):
    basedir = os.path.dirname(path)
    if not os.path.exists(basedir):
        os.makedirs(basedir)

    os.chmod(basedir, 0777)

    with open(path, "w") as f:
        f.write(content)
        f.close()

    os.chmod(path, 0777)


def write_xml_file(path, filename, xml):
    # saving to dir
    xmlfile = "{path}/{filename}.xml".format(
        path=path,
        filename=filename
    )
    file_handler = open(xmlfile, "w")
    xml.writexml(file_handler)
    return xmlfile


def drop_privileges(uid_name='vmmaster', gid_name='vmmaster'):
    # Get the uid/gid from the name
    try:
        running_uid = pwd.getpwnam(uid_name).pw_uid
    except KeyError:
        raise UserNotFound("User '%s' not found." % uid_name)

    try:
        running_gid = grp.getgrnam(gid_name).gr_gid
    except KeyError:
        raise GroupNotFound("Group '%s' not found." % gid_name)

    if os.getuid() == running_uid:
        return

    if os.getuid() != 0:
        # We're not root so, like, whatever dude
        raise Exception("Need to be a root, to change user")

    # Remove group privileges
    os.setgroups([])

    # Try setting the new uid/gid
    os.setgid(running_gid)
    os.setuid(running_uid)

    # Ensure a very conservative umask
    # old_umask = os.umask(077)


def change_user_vmmaster():
    drop_privileges('vmmaster', 'libvirtd')
    log.info('Changed privileges by default for application directory')


def to_thread(f):
    def wrapper(*args, **kwargs):
        return threads.deferToThread(f, *args, **kwargs)
    return wrapper


def wait_for(condition, timeout=5):
    start = time.time()
    while not condition() and time.time() - start < timeout:
        time.sleep(0.1)

    return condition()


def generator_wait_for(condition, timeout=5):
    start = time.time()
    while not condition() and time.time() - start < timeout:
        time.sleep(0.1)
        yield None

    yield condition()


class BucketThread(Thread):
    def __init__(self, bucket, *args, **kwargs):
        Thread.__init__(self, *args, **kwargs)
        self.bucket = bucket

    def run(self):
        try:
            super(BucketThread, self).run()
        except:
            self.bucket.put(sys.exc_info())


def getresponse(req, q):
    try:
        q.put(req())
    except Exception as e:
        q.put(e)


def to_json(result):
    try:
        return json.loads(result)
    except ValueError:
        log.info("Couldn't parse response content <%s>" % repr(result))
        return {}


def make_request(request, host, port):
        """ Make http request to some port
            and return the response. """

        # log.debug('Request: %s' % request)
        q = Queue()
        url = "http://%s:%s%s" % (host,
                                  port,
                                  request.url)

        req = lambda: requests.request(method=request.method,
                                       url=url,
                                       headers=request.headers,
                                       data=request.body)

        t = Thread(target=getresponse, args=(req, q))
        t.daemon = True
        t.start()

        response = None
        while not response:
            if not t.isAlive():
                response = q.get()
                if isinstance(response, Exception):
                    log.info('Exception in thread '
                             'during request: %s' % str(response))
                break
            elif t is not None:
                t.join(0.1)

        return response


def remove_base64_screenshot(response_data):
    content_json = to_json(response_data)

    if content_json.get("screenshot", None):
        content_json["screenshot"] = ""

    if isinstance(content_json.get("value", None), dict):
        content_json["value"]["screen"] = ""

    return json.dumps(content_json)
