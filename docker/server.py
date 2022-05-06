from cheroot.wsgi import Server as WSGIServer
from cheroot.wsgi import PathInfoDispatcher as WSGIPathInfoDispatcher
from cheroot.ssl.builtin import BuiltinSSLAdapter

from scs import create_app

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
