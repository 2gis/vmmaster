##
##  flvrec.py - VNC to FLV recording tool.
##
##  Copyright (c) 2009-2010 by Yusuke Shinyama
##

import multiprocessing
from twisted.internet import threads
import websockify

from core.config import config
from core.logger import log

import sys, socket, os, os.path, subprocess, signal
from vnc2flv import flv, rfb, video
from core.utils.network_utils import get_free_port


class VNCVideoHelper():
    recorder = None
    proxy = None
    __proxy_port = None
    __filepath = None

    def __init__(self, host, port=5900, filename_prefix='vnc'):
        self.filename_prefix = filename_prefix
        self.dir_path = os.sep.join([config.SCREENSHOTS_DIR,
                                     str(self.filename_prefix)])
        if not os.path.isdir(self.dir_path):
            os.mkdir(self.dir_path)
        self.host = host
        self.port = port


    @staticmethod
    def _flvrec(filename, host='localhost', port=5900,
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

    def _flv2webm(self):
        args = [
            "/usr/bin/avconv",
            "-v", "quiet",
            "-i", "%s" % self.__filepath,
            "%s.webm" % self.__filepath.split(".flv")[0]
        ]
        converter = subprocess.Popen(args, stdin=subprocess.PIPE)

        if converter.pid:
            cpulimiter = subprocess.Popen([
                "/usr/bin/cpulimit",
                "-z",
                "-b",
                "-l", "15",
                "-p", "%s" % converter.pid
            ], stdin=subprocess.PIPE)

            cpulimiter.wait()
            converter.communicate()
            self.delete_source_video()

    def delete_source_video(self):
        if os.path.isfile('%s.webm' % self.__filepath.split('.flv')[0]):
            os.remove(self.__filepath)
            log.debug('Source video %s was deleted' % self.__filepath)

    def start_proxy(self):
        self.__proxy_port = get_free_port()
        sys.argv = [
            "--daemon",
            "--wrap-mode=ignore",
            "--record=%s/proxy_vnc_%s.log" % (self.dir_path, self.port),
            "0.0.0.0:%d" % self.__proxy_port,
            "%s:%s" % (self.host, self.port)
        ]

        self.proxy = multiprocessing.Process(
            target=websockify.websocketproxy.websockify_init
        )

        self.proxy.start()

    def get_proxy_port(self):
        return self.__proxy_port

    def stop_proxy(self):
        if self.proxy and self.proxy.is_alive():
            self.proxy.terminate()

    def start_recording(self, framerate=5, size=(800, 600)):
        sys.stderr = sys.stdout = open(os.sep.join([
            self.dir_path, 'vnc_video.log'
        ]), 'w')
        self.__filepath = os.sep.join([self.dir_path,
                                       str(self.filename_prefix) + '.flv'])

        kwargs = {
            'framerate': framerate,
            'clipping': video.str2clip("%sx%s+0-0" % (size[0], size[1])),
            'debug': 1,
            'verbose': 1
        }
        self.recorder = multiprocessing.Process(target=self._flvrec,
                                                args=(self.__filepath,
                                                      self.host,
                                                      self.port),
                                                kwargs=kwargs)
        self.recorder.start()

    def stop_recording(self):
        if self.recorder and self.recorder.is_alive():
            self.recorder.terminate()

            d = threads.deferToThread(self._flv2webm)
            d.addBoth(lambda s: None)