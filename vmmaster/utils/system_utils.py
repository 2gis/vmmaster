import subprocess
import sys


def run_command(command, silent=False):
    process = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

    output = ""
    if not silent:
        while process.poll() is None:
            line = process.stdout.readline()
            sys.stdout.write(line)
            output += line

        sys.stdout.write('\n')

    return process.returncode, process.communicate()[0]
