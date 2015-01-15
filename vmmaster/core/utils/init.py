import subprocess
import crypt
import os
from os.path import expanduser

from .print_utils import cin, cout, OKGREEN, WARNING, FAIL

from vmmaster import package_dir
from .system_utils import run_command
from .utils import change_user_vmmaster


def files(path):
    for path, subdirs, filenames in os.walk(path):
        for filename in filenames:
            yield os.path.join(path, filename)


def useradd(home):
    password = 'vmmaster'
    encrypted_password = crypt.crypt(password, "22")
    shell = '/bin/bash'
    group = 'libvirtd'

    subprocess.call(
        ["sudo", "/usr/sbin/useradd",
            "--create-home", "--home-dir=%s" % home,
            "--groups=%s" % group,
            "--shell=%s" % shell,
            "-p", encrypted_password,
            "vmmaster"]
    )


def copy_files_to_home(home):
    copy = ["/bin/cp", "-r", package_dir() + "home" + os.sep + ".", home]
    change_user_vmmaster()
    return_code, output = run_command(copy)
    if return_code != 0:
        cout("\nFailed to copy files to home dir: %s\n" % home_dir(), color=FAIL)
        exit(output)


def home_dir():
    user_path = "~%s" % "vmmaster"
    home = expanduser(user_path)
    if user_path == home:
        return None
    return home


def init():
    home = '/var/lib/vmmaster'
    cout("Please input absolute path to home directory for 'vmmaster'\n")
    cout("[default:%s]:" % home, color=WARNING)
    abspath = cin()
    abspath = abspath.strip()
    if abspath:
        home = abspath

    useradd(home)
    copy_files_to_home(home)
    cout("\nvmmaster successfully inited in %s\n" % home_dir(), color=OKGREEN)