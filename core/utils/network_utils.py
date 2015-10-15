import netifaces
from . import system_utils
import socket


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


def get_socket(host, port):
    s = None

    addr_info = socket.getaddrinfo(
        host, port, socket.AF_UNSPEC, socket.SOCK_STREAM
    )
    for af, socktype, proto, canonname, sa in addr_info:
        try:
            s = socket.socket(af, socktype, proto)
        except socket.error:
            s = None
            continue
        try:
            s = socket.create_connection((host, port), timeout=0.1)
        except socket.error:
            s.close()
            s = None
            continue
        break

    return s


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def ping(ip, port):
    try:
        s = get_socket(ip, port)
    except Exception:
        return False
    if s:
        s.close()
        return True

    return False
