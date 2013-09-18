import os
import errno

from vmmaster.core.config import config
from vmmaster.utils import system_utils, commands


def convert_img_to_qcow2_origin(img_file, qcow2_origin_name):
    command = commands.convert_img_to_qcow2(
        img_file,
        "{origins_dir}/{qcow2_origin_name}-{origin_postfix}.qcow2".format(
            origins_dir=config.ORIGINS_DIR,
            qcow2_origin_name=qcow2_origin_name,
            origin_postfix=config.ORIGIN_POSTFIX
        )
    )
    system_utils.run_command(command)


def clone_qcow2_drive(origin_name, clone_name):
    clone_path = "{clones_dir}/{clone_name}.qcow2".format(
        clones_dir=config.CLONES_DIR,
        clone_name=clone_name
    )
    origin_path = "{origins_dir}/{origin_name}-{postfix}.qcow2".format(
        origins_dir=config.ORIGINS_DIR,
        origin_name=origin_name,
        postfix=config.ORIGIN_POSTFIX
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


def write_xml_file(path, filename, xml):
    # saving to dir
    xmlfile = "{path}/{filename}.xml".format(
        path=path,
        filename=filename
    )
    file_handler = open(xmlfile, "w")
    xml.writexml(file_handler)
    return xmlfile