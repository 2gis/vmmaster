from xml.dom import minidom
from vmmaster.core.config import config
from vmmaster.core.utils import utils


class NetworkXml(object):
    def __init__(self, name, uuid, bridge_name, table):
        self.template = """\
<network>
    <name>test_network</name>
    <uuid>1cb43310-d10d-9853-f541-ba3efc9c7a3c</uuid>
    <forward mode='nat'/>
    <bridge name='virbr1' stp='on' delay='0' />
    <mac address='52:54:00:35:6C:24'/>
    <ip address='192.168.201.1' netmask='255.255.255.0'>
        <dhcp>
            <range start='192.168.201.2' end='192.168.201.254' />
        </dhcp>
    </ip>
</network> \
"""
        self.name = name
        self.uuid = uuid
        self.bridge_name = bridge_name
        self.table = table
        self.xml = self.createNetworkXml()

    def createNetworkXml(self):
        xml = minidom.parseString(self.template)

        name_element = xml.getElementsByTagName('name')[0]
        name_element.firstChild.nodeValue = self.name

        uuid_element = xml.getElementsByTagName('uuid')[0]
        uuid_element.firstChild.nodeValue = self.uuid

        bridge_element = xml.getElementsByTagName('bridge')[0]
        bridge_element.setAttribute('name', self.bridge_name)

        dhcp_element = xml.getElementsByTagName('dhcp')[0]
        for raw in self.table:
            host = xml.createElement('host')
            # host.setAttribute('name', str(raw["name"]))
            host.setAttribute('mac', str(raw["mac"]))
            host.setAttribute('ip', str(raw["ip"]))
            dhcp_element.appendChild(host)

        return xml

    def saveXml(self):
        return utils.write_xml_file(config.SESSION_DIR, self.name, self.xml)
