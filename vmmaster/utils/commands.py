def convert_img_to_qcow2(img_name, qcow2_name):
    command = ["qemu-img", "convert", "-O", "qcow2", img_name, qcow2_name]
    return command


def clone_qcow2_image(qcow2_origin_name, qcow2_clone_name):
    command = ["qemu-img", "create", "-f", "qcow2", "-b", qcow2_origin_name, qcow2_clone_name]
    return command