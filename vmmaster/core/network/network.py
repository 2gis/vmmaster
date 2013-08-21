import virtinst.util
import libvirt

from vmmaster.core.network.network_xml import NetworkXml
from vmmaster.core.network.mac_ip_table import MacIpTable


class Network(MacIpTable):
    def __init__(self, conn):
        super(Network, self).__init__()

        self.name = "session_network"
        u = virtinst.util.randomUUID()
        self.uuid = virtinst.util.uuidToString(u)
        self.bridge_name = "virbr2"
        self.dumpxml_file = NetworkXml(self.name, self.uuid, self.bridge_name, self.free_table).xml.toprettyxml()
        self.conn = conn
        try:
            self.conn.networkDefineXML(self.dumpxml_file)
        except libvirt.libvirtError:
            net = self.conn.networkLookupByName(self.name)
            net.destroy()
            net.undefine()
            self.conn.networkDefineXML(self.dumpxml_file)

        net = self.conn.networkLookupByName(self.name)
        net.create()

    def __del__(self):
        print "destroying network: {}".format(self.name)
        net = self.conn.networkLookupByName(self.name)
        net.destroy()
        net.undefine()