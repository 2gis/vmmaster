import netifaces
from vmmaster.utils import system_utils
import time


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


def ping(ip, port, timeout=180):
    command = ['nc', '-z', ip, port]

    start = time.time()
    log.info("starting ping: {ip}:{port}".format(ip=ip, port=port))
    returncode, output = system_utils.run_command(command, True)
    while returncode:
        time.sleep(0.1)
        returncode, output = system_utils.run_command(command, True)
        if time.time() - start > timeout:
            log.info("ping failed: timeout {ip}:{port}".format(ip=ip, port=port))
            return 1

    log.info("ping successful: {ip}:{port}".format(ip=ip, port=port))

    ### @todo: add some more tools to define, if virtual machine is ready (selenium status?)
    time.sleep(1)
    log.debug("sleep 1 more second instead of normal selenium status check")
    return 0
