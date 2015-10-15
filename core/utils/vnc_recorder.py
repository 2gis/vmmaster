##
##  flvrec.py - VNC to FLV recording tool.
##
##  Copyright (c) 2009-2010 by Yusuke Shinyama
##

import multiprocessing

from core.config import config
from core.logger import log

import sys, socket, os, os.path, subprocess, signal
from vnc2flv import flv, rfb, video


class VNCRecorder():
    recorder = None

    def __init__(self, host, filename, port=5900, framerate=5, size=(800, 600)):
        sys.stderr = sys.stdout = open(os.sep.join([
            config.LOG_DIR, str(filename) + '_vnc_recorder.log'
        ]), 'w')
        debug = 0
        verbose = 0
        dir_path = os.sep.join([config.SCREENSHOTS_DIR, str(filename)])

        if not os.path.isdir(dir_path):
            os.mkdir(dir_path)
        self.filepath = os.sep.join([dir_path, str(filename) + '.flv'])

        if config.LOG_LEVEL == "DEBUG":
            debug = 1
            verbose = 1

        args = (
            self.filepath,
            host,
            port
        )

        kwargs = {
            'framerate': framerate,
            'clipping': video.str2clip("%sx%s+0-0" % (size[0], size[1])),
            'debug': debug,
            'verbose': verbose
        }

        self.recorder = multiprocessing.Process(target=self.flvrec,
                                                args=args,
                                                kwargs=kwargs)

    @staticmethod
    def flvrec(filename, host='localhost', port=5900,
               framerate=12, keyframe=120,
               preferred_encoding=(0,),
               blocksize=32, clipping=None,
               debug=0, verbose=0):
        fp = file(filename, 'wb')
        pwdcache = rfb.PWDCache('%s:%d' % (host,port))
        writer = flv.FLVWriter(fp, framerate=framerate, debug=debug)
        sink = video.FLVVideoSink(writer,
                            blocksize=blocksize, framerate=framerate, keyframe=keyframe,
                            clipping=clipping, debug=debug)
        client = rfb.RFBNetworkClient(host, port, sink, timeout=500/framerate,
                                  pwdcache=pwdcache, preferred_encoding=preferred_encoding,
                                  debug=debug)
        if verbose:
            log.debug('Start vnc recording to %s' % filename)
        retval = 0
        try:
            def sigint_handler(sig, frame):
                raise KeyboardInterrupt
            signal.signal(signal.SIGINT, sigint_handler)
            client.open()
            try:
                while 1:
                    client.idle()
            finally:
                client.close()
        except KeyboardInterrupt:
            pass
        except socket.error, e:
            log.debug('Socket error: %s' % str(e))
            retval = 1
        except rfb.RFBError, e:
            log.debug('RFB error: %s' % str(e))
            retval = 1
        if verbose:
            log.debug('Stop vnc recording to %s' % filename)
        writer.close()
        fp.close()
        return retval

    def flv2webm(self):
        args = [
            "/usr/bin/avconv",
            "-v", "quiet",
            "-i", "%s" % self.filepath,
            "%s.webm" % self.filepath.split(".flv")[0]
        ]
        subprocess.Popen(args, stdin=subprocess.PIPE)

    def start(self):
        self.recorder.start()

    def stop(self):
        if self.recorder.is_alive():
            self.recorder.terminate()

        self.flv2webm()
