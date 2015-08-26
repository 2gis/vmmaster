#!/usr/bin/python
##
##  flvrec.py - VNC to FLV recording tool.
##
##  Copyright (c) 2009-2010 by Yusuke Shinyama
##

import threading
import sys
import time
import os
import os.path
import signal
from vnc2flv.flv import FLVWriter
from vnc2flv.rfb import RFBNetworkClient, RFBError, PWDFile, PWDCache
from vnc2flv.video import FLVVideoSink, str2clip, str2size

##  flvrec
##


class StoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, *args):
        super(StoppableThread, self).__init__(*args)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    @property
    def stopped(self):
        return self._stop.isSet()


class VNCRecoder(object):
    client = None
    writer = None
    fp = None

    def __init__(self, framerate=12, keyframe=120,
                 preferred_encoding=(0,), pwdfile=None,
                 blocksize=32, clipping=None,
                 cmdline=None,
                 debug=0, verbose=1):
        self.framerate = framerate
        self.keyframe = keyframe
        self.preferred_encoding = preferred_encoding
        self.pwdfile = pwdfile
        self.blocksize = blocksize
        self.clipping = clipping
        self.cmdline = cmdline
        self.debug = debug
        self.verbose = verbose

    def flvrec(self, filename, host='localhost', port=5900):
        self.fp = file(filename, 'wb')
        if self.pwdfile:
            pwdcache = PWDFile(self.pwdfile)
        else:
            pwdcache = PWDCache('%s:%d' % (host,port))
        self.writer = FLVWriter(self.fp, framerate=self.framerate, debug=self.debug)
        sink = FLVVideoSink(self.writer,
                            blocksize=self.blocksize, framerate=self.framerate, keyframe=self.keyframe,
                            clipping=self.clipping, debug=self.debug)
        self.client = RFBNetworkClient(host, port, sink, timeout=500/self.framerate,
                                       pwdcache=pwdcache, preferred_encoding=self.preferred_encoding,
                                       debug=self.debug)
        if self.verbose:
            print >>sys.stderr, 'start recording'
        self.pid = 0
        if self.cmdline:
            self.pid = os.fork()
            if self.pid == 0:
                os.setpgrp()
                os.execvp('sh', ['sh', '-c', cmdline])
                sys.exit(1)
        self.retval = 0
        self.client.open()

        self.thread = StoppableThread(target=self._run)
        self.thread.run()

    def _run(self):
        while not self.stopped:
            self.client.idle()

    def flvstop(self):
        self.thread.stop()
        self.thread.join()
        self.client.close()
        if self.pid:
            os.killpg(os.getpgid(self.pid), signal.SIGTERM)
        if self.verbose:
            print >>sys.stderr, 'stop recording'
        self.writer.close()
        self.fp.close()
        return self.retval

filename = 'out-%s.flv' % time.strftime('%Y%m%d%H%M%S')

args = sys.argv
if len(args) == 2:
    if args[1] in ['start', 'stop']:
        pass
    else:
        sys.exit("vnc_recorder [start, stop]")
else:
    sys.exit("vnc_recorder [start, stop]")


vncrec = VNCRecoder()
arg = sys.argv[1]
if arg == 'start':
    vncrec.flvrec(filename)
if arg == 'stop':
    vncrec.flvstop()
# (host, port) = ('localhost', 5900)
# try:
#     flvrec(filename)
# except KeyboardInterrupt:
#     flvstop()
# except socket.error, e:
#     print >>sys.stderr, 'Socket error:', e
#     retval = 1
# except RFBError, e:
#     print >>sys.stderr, 'RFB error:', e
#     retval = 1
    
