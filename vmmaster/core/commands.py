def convert_img_to_qcow2(img_name, qcow2_name):
    command = ["qemu-img", "convert", "-O", "qcow2", img_name, qcow2_name]
    return command


def clone_qcow2_image(qcow2_origin_name, qcow2_clone_name):
    command = ["qemu-img", "create", "-f", "qcow2", "-b", qcow2_origin_name, qcow2_clone_name]
    return command


    # clone_name = "temp_ubuntu"
    # clone_drive_name = clone_name + ".img"
    #
    # print "cloning {} into {}".format(standard_machine, clone_name)
    # system_utils.run_command(
    #     ["virt-clone",
    #      "-o", standard_machine,
    #      "-n", clone_name,
    #      "-f", clone_drive_name,
    #      "--connect={hypervisor}".format(hypervisor=hypervisor),
    #      "--mac=de:af:de:af:00:02"])