from vmmaster.core import commands
from config import Config
from vmmaster.utils import system_utils

CLONES_DIR = Config.CLONES_DIR
ORIGINS_DIR = Config.ORIGINS_DIR
ORIGIN_POSTFIX = Config.ORIGIN_POSTFIX


def convert_img_to_qcow2_origin(img_file, qcow2_origin_name):
    command = commands.convert_img_to_qcow2(
        img_file,
        "{origins_dir}/{qcow2_origin_name}-{origin_postfix}.qcow2".format(
            origins_dir=ORIGINS_DIR,
            qcow2_origin_name=qcow2_origin_name,
            origin_postfix=ORIGIN_POSTFIX
        )
    )
    system_utils.run_command(command)


def create_qcow2_clone(origin_name, clone_name):
    clone_path = "{clones_dir}/{clone_name}.qcow2".format(
        clones_dir=CLONES_DIR,
        clone_name=clone_name
    )
    origin_path = "{origins_dir}/{origin_name}-{postfix}.qcow2".format(
        origins_dir=ORIGINS_DIR,
        origin_name=origin_name,
        postfix=ORIGIN_POSTFIX
    )

    command = commands.clone_qcow2_image(
        origin_path,
        clone_path
    )
    system_utils.run_command(command)
    return clone_path


def create_img_clone(origin_name, clone_name):
    clone_path = "{clones_dir}/{clone_name}.img".format(
        clones_dir=CLONES_DIR,
        clone_name=clone_name
    )
    origin_path = "{origins_dir}/{origin_name}-{postfix}.img".format(
        origins_dir=ORIGINS_DIR,
        origin_name=origin_name,
        postfix=ORIGIN_POSTFIX
    )

    print "cloning {} into {}".format(origin_name, clone_name)
    #phrase = "hello {}!".format(machine)
    command = ["virt-clone", "-o", origin_name, "-n", clone_name, "-f", clone_path, "--connect=qemu:///system"]
    print command
    system_utils.run_command(command)
    return clone_path


def delete_clone_drive(drive_name):
    system_utils.run_command(
        ["rm",
         "{clones_dir}/{drive_name}".format(
             clones_dir=CLONES_DIR,
             drive_name=drive_name
         )]
    )


def write_xml_file(path, filename, xml):
    # saving to dir
    xmlfile = "{path}/{filename}.xml".format(
        path=path,
        filename=filename
    )
    file_handler = open(xmlfile, "w")
    xml.writexml(file_handler)
    return xmlfile