import netifaces
from . import system_utils
import time
import socket


from vmmaster.core.logger import log


def get_interface_subnet(inteface):
    ip = netifaces.ifaddresses(inteface)[2][0]["addr"]
    split_ip = ip.split(".")
    split_ip[-1] = "0"
    ip = ".".join(split_ip)
    return ip + "/24"


def nmap_ping_scan(subnet):
    return system_utils.run_command(["nmap", "-sP", "-T4", subnet])


def arp_numeric():
    return system_utils.run_command(["arp", "--numeric"])


def get_ip_by_mac(mac):
    subnet = get_interface_subnet("br0")
    nmap_ping_scan(subnet)
    code, output = arp_numeric()
    split_output = output.split("\n")

    for line in split_output:
        if mac in line:
            break

    if line == "":
        return None

    return line.split(" ")[0]


def ping(session, port, timeout=180):
    def get_socket(host, port):
        s = None

        for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
            af, socktype, proto, canonname, sa = res
            try:
                s = socket.socket(af, socktype, proto)
            except socket.error as msg:
                s = None
                continue
            try:
                s = socket.create_connection(sa, timeout=0.1)
            except socket.error as msg:
                s.close()
                s = None
                continue
            break

        return s

    ip = session.virtual_machine.ip
    session.timer.restart()
    log.info("starting ping: {ip}:{port}".format(ip=ip, port=port))
    start = time.time()

    s = get_socket(ip, port)
    while not s:
        session.timer.restart()
        time.sleep(0.1)
        s = get_socket(ip, port)
        if time.time() - start > timeout:
            log.info("ping failed: timeout {ip}:{port}".format(ip=ip, port=port))
            return 1

    log.info("ping successful: {ip}:{port}".format(ip=ip, port=port))
    return 0
