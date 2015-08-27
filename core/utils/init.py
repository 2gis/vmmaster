import subprocess
import crypt
import os

from .print_utils import cout, FAIL

from vmmaster import package_dir
from .system_utils import run_command
from .utils import change_user_vmmaster


def files(path):
    for path, subdirs, filenames in os.walk(path):
        for filename in filenames:
            yield os.path.join(path, filename)


def useradd():
    password = 'vmmaster'
    encrypted_password = crypt.crypt(password, "22")
    shell = '/bin/bash'
    group = 'libvirtd'
    user_add = subprocess.Popen(
        ["sudo", "useradd",
         "--create-home", "--home-dir=/home/vmmaster",
         "--groups=%s" % group,
         "--shell=%s" % shell,
         "-p", encrypted_password,
         "vmmaster"], stdin=subprocess.PIPE
    )
    output, err = user_add.communicate()
    if err:
        cout(repr(err), color=FAIL)
        exit(1)


def copy_files_to_home(home):
    copy = ["/bin/cp", "-r", package_dir() + "home" + os.sep + ".", home]
    return_code, output = run_command(copy)
    if return_code != 0:
        cout(
            "\nFailed to copy files to home dir: %s\n" % home_dir(),
            color=FAIL
        )
        exit(output)
    chown = ["/bin/chown", "-R", "vmmaster:vmmaster", home]
    return_code, output = run_command(chown)
    if return_code != 0:
        cout("\nFailed to change owner for: %s\n" % home_dir(), color=FAIL)
        exit(output)
    change_user_vmmaster()


def home_dir():
    return os.path.abspath(os.curdir)
