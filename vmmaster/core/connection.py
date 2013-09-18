import libvirt


class Virsh(object):
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, 'instance'):
            # cls.instance = super(Connection, cls).__new__(cls, *args, **kwargs)
            hypervisor = 'qemu:///system'
            cls.instance = libvirt.open(hypervisor)
        return cls.instance