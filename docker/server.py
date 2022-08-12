"""
Main server for SCS, using the Cheroot HTTP server. This script is designed to
be used inside the simple-configuration-server docker image


Copyright 2022 Tom Brouwer

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import signal
import os

from cheroot.wsgi import Server as WSGIServer
from cheroot.wsgi import PathInfoDispatcher as WSGIPathInfoDispatcher
from cheroot.ssl.builtin import BuiltinSSLAdapter
from werkzeug.middleware.proxy_fix import ProxyFix

from scs import create_app


# The 'docker stop' command gives a SIGTERM signal, rather than SIGINT, so
# this should be caught
def sigterm_handler(*args):
    raise KeyboardInterrupt('Docker SIGTERM was sent')


def get_environment_config() -> dict:
    """
    Loads the part of the configuration that's stored in environment variables.

    The following environment variables are loaded:
        SCS_DISABLE_SSL:
            Set to 1 in case you want to disable HTTPS and use port 80 (
            default: 0)
        SCS_REVERSE_PROXY_COUNT:
            Set to >= 1 if you're using a reverse proxy that sets the
            X-Forwarded-For header. This means the 'X-Forwarded-For' header is
            used as the Remote Address, rather than the IP of the proxy itself.
            The count indicates how many values should be in the
            X-Forwarded-For headers. If you use multiple proxies, this may be
            higher than one. (default: 0)
    """
    return {
        'disable_ssl': bool(int(os.environ.get("SCS_DISABLE_SSL", "0"))),
        'reverse_proxy_count': int(
            os.environ.get("SCS_REVERSE_PROXY_COUNT", "0")
        ),
    }


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, sigterm_handler)
    flask_app = create_app()

    env_config = get_environment_config()
    if env_config['reverse_proxy_count'] > 0:
        app = ProxyFix(
            flask_app,
            x_for=env_config['reverse_proxy_count'],
        )
    else:
        app = flask_app

    cheroot_app = WSGIPathInfoDispatcher({'/': app})

    if env_config['disable_ssl']:
        message = (
            'SCS_DISABLE_SSL has been enabled, meaning INSECURE HTTP'
            ' connections are used. Use this only if you plan to have SSL'
            ' terminated by a proxy like NGINX.'
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
    try:
        message = 'Simple Configuration Server Started'
        print(message, flush=True)
        flask_app.logger.info(message)
        server.start()
    except KeyboardInterrupt:
        server.stop()
