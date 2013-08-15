from BaseHTTPServer import HTTPServer
from BaseHTTPServer import BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import httplib


class RequestHandler(BaseHTTPRequestHandler):
    def transparent(self, method):
        """Transparent request."""
        if self.headers.getheader('Content-Length') is None:
            request_body = None
        else:
            content_length = int(self.headers.getheader('Content-Length'))
            request_body = self.rfile.read(content_length)#.decode('utf-8')

        # get response from selenium-server
        conn = httplib.HTTPConnection("127.0.0.1:4455")
        conn.request(method=method, url=self.path, body=request_body, headers=self.headers.dict)

        response = conn.getresponse()
        conn.close()

        # reply code
        self.send_response(response.status)

        # reply headers
        for keyword, value in response.getheaders():
            self.send_header(keyword, value)
        self.end_headers()

        # reply body
        response_length = response.getheader('Content-Length')
        response_body = response.read(response_length)
        self.wfile.write(response_body)
        return

    def do_GET(self):
        """GET request."""
        self.transparent("GET")
        return


    def do_POST(self):
        """POST request."""
        self.transparent("POST")
        return

    def do_DELETE(self):
        """DELETE request."""
        self.transparent("DELETE")
        return

        # def log_request(self, code=None, size=None):
        #     print('Request')
        #
        # def log_message(self, format, *args):
        #     print('Message')


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


server_address = ('', 9000)
handler = RequestHandler

server = ThreadedHTTPServer(server_address, handler)
server.serve_forever()
