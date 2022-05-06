import signal

from cheroot.wsgi import Server as WSGIServer
from cheroot.wsgi import PathInfoDispatcher as WSGIPathInfoDispatcher
from cheroot.ssl.builtin import BuiltinSSLAdapter

from scs import create_app


# The 'docker stop' command gives a SIGTERM signal, rather than SIGINT, so
# this should be caught
def sigterm_handler(*args):
    raise KeyboardInterrupt('Docker SIGTERM was sent')


signal.signal(signal.SIGTERM, sigterm_handler)

my_app = WSGIPathInfoDispatcher({'/': create_app()})
server = WSGIServer(('0.0.0.0', 443), my_app)

ssl_cert = "/etc/ssl/certs/scs.crt"
ssl_key = "/etc/ssl/private/scs.key"
server.ssl_adapter = BuiltinSSLAdapter(ssl_cert, ssl_key, None)

if __name__ == '__main__':
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
