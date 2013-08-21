import netifaces
from vmmaster.utils import system_utils
import time

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


def ping(ip, port, timeout):
    command = ['nc', '-z', ip, port]

    start = time.time()
    print "connecting"
    returncode, output = system_utils.run_command(command, True)
    while returncode:
        returncode, output = system_utils.run_command(command, True)
        if time.time() - start > timeout:
            return 1

    # time.sleep(5)
    return 0

