import os
import errno
import pwd
import grp

from vmmaster.core.config import config
from vmmaster.utils import system_utils, commands


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
    clone_path = "{clones_dir}/{clone_name}.qcow2".format(
        clones_dir=config.CLONES_DIR,
        clone_name=clone_name
    )
    origin_path = "{origins_dir}/{origin_name}.qcow2".format(
        origins_dir=config.ORIGINS_DIR,
        origin_name=origin_name,
    )

    command = commands.clone_qcow2_drive(
        origin_path,
        clone_path
    )
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


def delete_file(filename):
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
    if os.getuid() != 0:
        # We're not root so, like, whatever dude
        return

    # Get the uid/gid from the name
    try:
        running_uid = pwd.getpwnam(uid_name).pw_uid
    except KeyError:
        raise UserNotFound("User '%s' not found." % uid_name)

    try:
        running_gid = grp.getgrnam(gid_name).gr_gid
    except KeyError:
        raise GroupNotFound("Group '%s' not found." % gid_name)

    # Remove group privileges
    os.setgroups([])

    # Try setting the new uid/gid
    os.setgid(running_gid)
    os.setuid(running_uid)

    # Ensure a very conservative umask
    old_umask = os.umask(077)


def change_user_vmmaster():
    drop_privileges('vmmaster', 'libvirtd')