from core.network.network_xml import NetworkXml
from core.network.mac_ip_table import MacIpTable

import virtinst.util


class Network(MacIpTable):
    def __init__(self, conn):
        super(Network, self).__init__()

        self.name = "session_network"
        u = virtinst.util.randomUUID()
        self.uuid = virtinst.util.uuidToString(u)
        self.bridge_name = "virbr2"
        self.dumpxml_file = NetworkXml(self.name, self.uuid, self.bridge_name, self.free_table).xml.toprettyxml()

        self.conn = conn
        self.conn.networkDefineXML(self.dumpxml_file)

        net = self.conn.networkLookupByName(self.name)
        net.create()

    def __del__(self):
        net = self.conn.networkLookupByName(self.name)
        net.destroy()
        net.undefine()