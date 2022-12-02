"""
Flask Blueprint containing all behaviour related to the authentication and
authorization of users/clients


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
from pathlib import Path
import ipaddress
import datetime
import logging

from flask import Blueprint, request, abort, g, current_app
from flask.blueprints import BlueprintSetupState
import fastjsonschema

from . import yaml, tools


bp = Blueprint('auth', __name__)

_ERRORS = [
    (
        429, 'auth-rate-limited',
        'Rate limited because of too many false auth attempts from this ip',
    ),
    (
        403, 'unauthorized-ip',
        'You are not authorized to access the server from this IP',
    ),
    (
        403, 'unauthorized-path',
        'You are not authorized to access this path on the server',
    ),
]
_AUDIT_EVENTS = [
    (
        'unauthenticated', logging.WARNING,
        'Unauthenticated request to {path} from {ip}',
    ),
    (
        'rate-limited', logging.WARNING,
        'Requests from {ip} are rate limited by the auth module',
    ),
    (
        'unauthorized-ip', logging.WARNING,
        "User '{user}' connected from unauthorized IP {ip}",
    ),
    (
        'unauthorized-path', logging.WARNING,
        "User '{user}' tried to access unauthorized path: {path}",
    ),
]

# Load the schema to validate the users file against
module_dir = Path(__file__).absolute().parent
_users_schema = yaml.safe_load_file(
    Path(module_dir, 'schemas/scs-users.yaml'),
)
validate_user_configuration = fastjsonschema.compile(_users_schema)


class _RateLimiter:
    """
    Tracks invalid authentication attempts for the current 15 minute interval
    and blacklists IPs when too many invalid authentication attempts were made.
    """
    def __init__(self, *, max_auth_fails_per_15_min: int):
        self._current_window = self._get_window_id()
        self._invalid_auth_attempts = {}
        self.max_auth_fails = max_auth_fails_per_15_min

    def register_attempt(self, ip: str):
        invalid_auth_attempts = self.invalid_auth_attempts

        if ip not in invalid_auth_attempts:
            invalid_auth_attempts[ip] = 0

        invalid_auth_attempts[ip] += 1

    def is_limited(self, ip: str) -> bool:
        return self.invalid_auth_attempts.get(ip, 0) >= self.max_auth_fails

    @property
    def invalid_auth_attempts(self) -> dict:
        window_id = self._get_window_id()

        # Reset attempts if a new window is reached
        if self._current_window != window_id:
            self._current_window = window_id
            self._invalid_auth_attempts = {}

        return self._invalid_auth_attempts

    def _get_window_id(self) -> str:
        """
        Get the id of the current 15 minute window
        """
        now = datetime.datetime.utcnow()
        minute_rounded = now.minute - (now.minute % 15)
        return f'{now.year}{now.month}{now.day}{now.hour}{minute_rounded}'


class NetworkWhitelist:
    """
    A network whitelist with a method to check if another network is included
    in the whitelist
    """
    def __init__(self, networks: list[str], private_only: bool = False):
        """
        Initialzes the NetworkWhitelist instance

        Args:
            networks:
                List with specific IPs, Subnet CIDR notations or both. All
                items are passed to the ipaddress.ip_network() function.

            private_only:
                If True, the networks must contain only private subnets
        """
        self.ipv4_networks = []
        self.ipv6_networks = []
        for network in networks:
            ip_network = ipaddress.ip_network(network)
            if private_only and not ip_network.is_private:
                raise ValueError(
                    f'private_only enabled, but network {network} is not private!'  # noqa:E501
                )
            if isinstance(ip_network, ipaddress.IPv4Network):
                self.ipv4_networks.append(ip_network)
            else:
                self.ipv6_networks.append(ip_network)

    def contains(self, network: str) -> bool:
        """
        Check if the whitelist contains the provided network

        Args:
            network:
                A specific IP or CIDR notation
        """
        ip_network = ipaddress.ip_network(network)
        if isinstance(ip_network, ipaddress.IPv4Network):
            whitelist = self.ipv4_networks
        else:
            whitelist = self.ipv6_networks

        for whitelisted_network in whitelist:
            if ip_network.subnet_of(whitelisted_network):
                return True

        return False

    def issubset(self, other_network_whitelist) -> bool:
        """
        Checks if this whitelist is fully covered by another whitelist

        Args:
            network_whitelist:
                Another NetworkWhitelist instance
        """
        network_types = ['ipv4_networks', 'ipv6_networks']
        for network_type in network_types:
            networks = getattr(self, network_type)
            other_networks = getattr(other_network_whitelist, network_type)
            for network in networks:
                is_subnet_of_other = False
                for other_network in other_networks:
                    if network.subnet_of(other_network):
                        is_subnet_of_other = True
                        break
                if not is_subnet_of_other:
                    return False

        return True


@bp.record
def init(setup_state: BlueprintSetupState):
    """
    Initializes the authentication module and loads the user data

    Args:
        setup_state:
            The .options attribute (options parameter passed to
            register_blueprint) should be a dict with the key/value pairs:
                users_file: pathlib.Path
                directories: dict
                    secrets: string
                networks: dict
                    private_only: bool
                    whitelist: list[str]
                max_auth_fails_per_15_min: bool
    """
    options = setup_state.options
    users_file_path = Path(options['users_file'])
    private_networks_only = options['networks']['private_only']
    network_whitelist = options['networks']['whitelist']
    secrets_dir = options['directories']['secrets']
    max_auth_fails_per_15_min = options['max_auth_fails_per_15_min']
    validate_dots = setup_state.app.config['SCS']['environments'][
        'reject_keys_containing_dots'
    ]

    setup_state.app.scs._auth_rate_limiter = _RateLimiter(
        max_auth_fails_per_15_min=max_auth_fails_per_15_min
    )

    secrets_constructor = yaml.SCSSecretConstructor(
        secrets_dir=secrets_dir,
        validate_dots=validate_dots
    )

    class SCSUsersFileLoader(yaml.SCSYamlLoader):
        """
        Loader for the user configuration file

        Local class used to prevent re-use accross multiple apps
        """
        pass

    SCSUsersFileLoader.add_constructor(
        secrets_constructor.tag, secrets_constructor.construct
    )
    scs_users = yaml.SecretsSerializedList(
        yaml.load_file(users_file_path, loader=SCSUsersFileLoader)
    )
    scs_users = validate_user_configuration(scs_users.data)

    global_whitelist = NetworkWhitelist(
        network_whitelist, private_only=private_networks_only,
    )

    setup_state.app.scs._auth_global_whitelist = global_whitelist

    _auth_mapping = {}
    for user in scs_users:
        _auth_mapping[user.pop('token')] = user
        parsed_whitelist = NetworkWhitelist(
            user['has_access']['from_networks']
        )
        if not parsed_whitelist.issubset(global_whitelist):
            raise ValueError(
                f'Network whitelist of user {user["id"]} not fully covered'
                ' by global whitelist'
            )
        user['has_access']['from_networks'] = parsed_whitelist
        user['has_access']['to_paths'] = [
            tools.build_pattern_from_path(p)
            for p in user['has_access']['to_paths']
        ]
    setup_state.app.scs._auth_mapping = _auth_mapping

    for error_args in _ERRORS:
        setup_state.app.scs.register_error(*error_args)
    for audit_event_args in _AUDIT_EVENTS:
        setup_state.app.scs.register_audit_event(*audit_event_args)


@bp.before_app_request
def check_auth():
    """
    Validates if user authentication credentials are valid, and if the given
    user is authorized to make the request.
    """
    if not current_app.scs._auth_global_whitelist.contains(request.remote_addr):  # noqa:E501
        # Check the global whitelist before hitting the rate-limiter, so
        # non-whitelisted IPs cannot be used to reduce the changes of rate
        # limiting. The failed attempt is not logs, since otherwise attackers
        # could flood the logs
        abort(403, description={'id': 'unauthorized-ip'})

    if current_app.scs._auth_rate_limiter.is_limited(request.remote_addr):
        g.add_audit_event(event_type='rate-limited')
        abort(429, description={'id': 'auth-rate-limited'})

    try:
        auth_header = request.headers['Authorization']
        token = auth_header.removeprefix('Bearer ')
        user = current_app.scs._auth_mapping[token]
        g.user_id = user['id']
    except KeyError:
        current_app.scs._auth_rate_limiter.register_attempt(
            request.remote_addr
        )
        g.add_audit_event(event_type='unauthenticated')
        abort(401)

    if not user['has_access']['from_networks'].contains(request.remote_addr):
        g.add_audit_event(event_type='unauthorized-ip')
        abort(403, description={'id': 'unauthorized-ip'})

    for pattern in user['has_access']['to_paths']:
        if pattern.match(request.path):
            break
    else:
        g.add_audit_event(event_type='unauthorized-path')
        abort(403, description={'id': 'unauthorized-path'})
