# -*- coding: utf-8 -*-
"""
Flask Blueprint containing all behaviour related to the authentication and
authorization of users/clients
"""
from pathlib import Path
import re
import ipaddress
import datetime
import logging

from flask import Blueprint, request, abort, g
from flask.blueprints import BlueprintSetupState

from . import yaml, errors
from .logging import register_audit_event


bp = Blueprint('auth', __name__)

# Errors and audit events are registered with the errors and logging modules
# respectively
_ERRORS = [
    (
        429, 'auth-rate-limited',
        'Rate limited due to too many false auth attempts from this ip',
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
        "User '{user}' used from unauthorized IP {ip}",
    ),
    (
        'unauthorized-path', logging.WARNING,
        "User '{user}' tried to access {path} but is not authorized",
    ),
]


class _SCSUsersFileLoader(yaml.SCSYamlLoader):
    """
    Loader for the auth configuration file
    """
    pass


class _RateLimiter:
    """
    Tracks invalid authentication attempts for the current 15 minute interval
    and blacklists IPs when too many invalid authentication attempts were made.

    Ensures that passwords cannot be brute-forced
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
    global _auth_mapping, _rate_limiter

    # Get options
    opts = setup_state.options
    users_file_path = Path(opts['users_file'])
    private_only = opts['networks']['private_only']
    network_whitelist = opts['networks']['whitelist']
    secrets_dir = opts['directories']['secrets']
    max_auth_fails_per_15_min = opts['max_auth_fails_per_15_min']
    validate_dots = setup_state.app.config['SCS']['environments'][
        'reject_keys_containing_dots'
    ]

    # Initialize the rate limiter
    _rate_limiter = _RateLimiter(
        max_auth_fails_per_15_min=max_auth_fails_per_15_min
    )

    # Load the scs-ursers.yaml file
    secrets_constructor = yaml.SCSSecretConstructor(
        secrets_dir=secrets_dir,
        validate_dots=validate_dots
    )
    _SCSUsersFileLoader.add_constructor(
        secrets_constructor.tag, secrets_constructor.construct
    )
    scs_users = yaml.load_file(users_file_path, loader=_SCSUsersFileLoader)
    yaml.serialize_secrets(scs_users)

    # Parse whitelisted IP ranges:
    parsed_global_whitelist = [
        ipaddress.ip_network(network) for network in network_whitelist
    ]

    # Check if these are all private
    if private_only:
        for network in parsed_global_whitelist:
            if not network.is_private:
                raise ValueError(
                    'private_only enabled, but globally whitelisted '
                    f'{str(network)} is not private!'
                )

    # Create the mapping
    _auth_mapping = {}
    for user in scs_users['users']:
        _auth_mapping[user.pop('token')] = user
        parsed_whitelist = []
        for item in user['has_access']['from_networks']:
            network = ipaddress.ip_network(item)
            if not _is_whitelisted(network, parsed_global_whitelist):
                raise ValueError(
                    f"Network {str(network)} of user '{user['id']} "
                    "is not globally whitelisted!"
                )
            if private_only and not network.is_private:
                raise ValueError(
                    f"Network {str(network)} of user '{user['id']} "
                    "is not private, but private_only is enabled!"
                )
            parsed_whitelist.append(network)
        user['has_access']['from_networks'] = parsed_whitelist
        # Parse the path whitelist regexes
        parsed_allowed = []
        for item in user['has_access']['to_paths']:
            regex_str = '^' + re.escape(item).replace(r'\*', '(.*)') + '$'
            parsed_allowed.append(
                re.compile(regex_str)
            )
        user['has_access']['to_paths'] = parsed_allowed

    for error_args in _ERRORS:
        errors.register(*error_args)
    for audit_event_args in _AUDIT_EVENTS:
        register_audit_event(*audit_event_args)


def _is_whitelisted(
        network: ipaddress._BaseNetwork,
        whitelist: list[ipaddress._BaseNetwork]
        ) -> bool:
    """
    Checks if the network is in the given whitelist

    Args:
        network: The network to check
        whitelist: The whitelist the network should be within

    Returns:
        Whether the given network is a subnet of any of the networks in the
        whitelist
    """
    network_type = type(network)  # Ipv4 or Ipv6 network
    for wl_network in whitelist:
        if network_type is type(wl_network) and network.subnet_of(wl_network):
            return True
    else:
        return False


@bp.before_app_request
def check_auth():
    """
    Checks the authentication and authorization of users before the
    request
    """
    if _rate_limiter.is_limited(request.remote_addr):
        g.add_audit_event(event_type='rate-limited')
        abort(429, description={'id': 'auth-rate-limited'})

    # Get the bearer token, and check if it matches any accounts
    try:
        auth_header = request.headers['Authorization']
        token = auth_header.removeprefix('Bearer ')
        user = _auth_mapping[token]
        g.user_id = user['id']
    except KeyError:
        _rate_limiter.register_attempt(request.remote_addr)
        g.add_audit_event(event_type='unauthenticated')
        abort(401)

    # User is authenticated. Now check (1) if the ip is in the whitelist, (2)
    # if the url is authorized
    user_ip = ipaddress.ip_network(request.remote_addr)
    if not _is_whitelisted(user_ip, user['has_access']['from_networks']):
        g.add_audit_event(event_type='unauthorized-ip')
        abort(403, description={'id': 'unauthorized-ip'})

    # Check if the user is allowed to access the provided url
    for pattern in user['has_access']['to_paths']:
        if pattern.match(request.path):
            break
    else:
        g.add_audit_event(event_type='unauthorized-path')
        abort(403, description={'id': 'unauthorized-path'})
