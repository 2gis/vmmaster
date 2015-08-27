def get_name(xml):
    name_element = xml.getElementsByTagName('name')[0]
    return name_element.firstChild.nodeValue


def set_name(xml, name):
    name_element = xml.getElementsByTagName('name')[0]
    name_element.firstChild.nodeValue = name


def get_uuid(xml):
    uuid_element = xml.getElementsByTagName('uuid')[0]
    return uuid_element.firstChild.nodeValue


def set_uuid(xml, uuid):
    uuid_element = xml.getElementsByTagName('uuid')[0]
    uuid_element.firstChild.nodeValue = uuid


def get_mac(xml):
    mac_element = xml.getElementsByTagName('mac')[0]
    return mac_element.getAttribute('address')


def set_mac(xml, mac):
    mac_element = xml.getElementsByTagName('mac')[0]
    mac_element.setAttribute('address', mac)


def get_disk_file(xml):
    disk_element = xml.getElementsByTagName('disk')[0]
    source_element = disk_element.getElementsByTagName('source')[0]
    return source_element.getAttribute('file')


def set_disk_file(xml, filepath):
    disk_element = xml.getElementsByTagName('disk')[0]
    source_element = disk_element.getElementsByTagName('source')[0]
    source_element.setAttribute('file', filepath)


def get_interface_source(xml):
    interface_element = xml.getElementsByTagName('interface')[0]
    source_element = interface_element.getElementsByTagName('source')[0]
    return source_element.getAttribute('bridge')


def set_interface_source(xml, interface):
    interface_element = xml.getElementsByTagName('interface')[0]
    source_element = interface_element.getElementsByTagName('source')[0]
    source_element.setAttribute('bridge', interface)
