# coding: utf-8

import os
import sys
import time
import signal
import logging
import os.path
import websockify
import multiprocessing

from core.config import config
from vnc2flv import flv, rfb, video
from core.utils.network_utils import get_free_port

log = logging.getLogger(__name__)


class VNCVideoHelper:
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
                debug=0):
        fp = file(filename, 'wb')
        pwdcache = rfb.PWDCache('%s:%d' % (host, port))
        writer = flv.FLVWriter(fp, framerate=framerate, debug=debug)
        sink = video.FLVVideoSink(
            writer,
            blocksize=blocksize, framerate=framerate, keyframe=keyframe,
            clipping=clipping, debug=debug)
        client = rfb.RFBNetworkClient(
            host, port, sink, timeout=500/framerate,
            pwdcache=pwdcache, preferred_encoding=preferred_encoding,
            debug=debug)
        log.debug('Start vnc recording to %s' % filename)
        return_code = 0
        try:
            def sigterm_handler(sig, frame):
                log.debug("%s %s" % (sig, frame))
                raise SystemExit
            signal.signal(signal.SIGTERM, sigterm_handler)
            client.open()
            try:
                current_time = time.time()
                max_duration = getattr(config, "SCREENCAST_RECORDER_MAX_DURATION", 1800)
                while True:
                    if time.time() - current_time > max_duration:
                        log.warning("VNC recorder for {} has been stopped "
                                    "because max duration({}) was exceeded".format(filename, max_duration))
                        raise SystemExit
                    client.idle()
            finally:
                client.close()
        except Exception as e:
            if isinstance(e, SystemExit):
                log.info("VNC recorder process({}): Got SIGTERM. stopping...".format(filename))
            else:
                log.exception("Error in VNC recorder process({})".format(filename))
                return_code = 1
        finally:
            writer.close()
            fp.close()
            exit(return_code)
            log.info('Stopped vnc recording to %s' % filename)

    def delete_source_video(self):
        if self.__filepath and os.path.isfile(self.__filepath):
            os.remove(self.__filepath)
            log.debug('Source video %s was deleted' % self.__filepath)
            self.delete_vnc_log()

    def delete_vnc_log(self):
        vnc_log = os.sep.join([self.dir_path, 'vnc_video.log'])
        if os.path.isfile(vnc_log):
            os.remove(vnc_log)
            log.debug('File %s was deleted' % vnc_log)

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
            'debug': 1
        }
        self.recorder = multiprocessing.Process(
            target=self._flvrec,
            args=(self.__filepath, self.host, self.port),
            kwargs=kwargs
        )
        self.recorder.daemon = True
        self.recorder.start()
        log.info(
            "Started screencast recording(pid:{}) for {}:{} to {}".format(
                self.recorder.pid, self.host, self.port, self.dir_path
            )
        )

    def stop_recording(self):
        if self.recorder and self.recorder.is_alive():
            self.recorder.terminate()
            log.info(
                "Stopped screencast recording(pid:{}) for {}:{} to {}".format(
                    self.recorder.pid, self.host, self.port, self.dir_path
                )
            )
