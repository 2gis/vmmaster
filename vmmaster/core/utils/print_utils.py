HEADER = '\033[95m'
OKBLUE = '\033[94m'
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'

from sys import stdout, stdin


def cin():
    return stdin.readline()


def cout(text, color=None):
    if color:
        stdout.write(color + text + ENDC)
    else:
        stdout.write(text)
    stdout.flush()