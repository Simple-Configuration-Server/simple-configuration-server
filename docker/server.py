import signal
import os

from cheroot.wsgi import Server as WSGIServer
from cheroot.wsgi import PathInfoDispatcher as WSGIPathInfoDispatcher
from cheroot.ssl.builtin import BuiltinSSLAdapter

from scs import create_app


# The 'docker stop' command gives a SIGTERM signal, rather than SIGINT, so
# this should be caught
def sigterm_handler(*args):
    raise KeyboardInterrupt('Docker SIGTERM was sent')


signal.signal(signal.SIGTERM, sigterm_handler)
flask_app = create_app()
cheroot_app = WSGIPathInfoDispatcher({'/': flask_app})

disable_scs_ssl = bool(int(os.environ.get("DISABLE_SCS_SSL", "0")))
if disable_scs_ssl:
    message = (
        'DISABLE_SCS_SSL has been enabled, meaning INSECURE HTTP connections '
        'are used. Use this only if you plan to have SSL terminated by a proxy'
        ' like NGINX.'
    )
    flask_app.logger.warning(message)
    print(f'WARNING: {message}', flush=True)
    server = WSGIServer(('0.0.0.0', 80), cheroot_app)
else:
    server = WSGIServer(('0.0.0.0', 443), cheroot_app)
    server.ssl_adapter = BuiltinSSLAdapter(
        certificate='/etc/ssl/certs/scs.crt',
        private_key='/etc/ssl/private/scs.key',
    )

if __name__ == '__main__':
    try:
        message = 'Simple Configuration Server Started'
        print(message, flush=True)
        flask_app.logger.info(message)
        server.start()
    except KeyboardInterrupt:
        server.stop()
