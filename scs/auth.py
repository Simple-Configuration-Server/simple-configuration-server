# -*- coding: utf-8 -*-
"""
Flask Blueprint containing all behaviour related to the authentication and
authorization of users/clients
"""
from pathlib import Path
import re
import ipaddress

from flask import Blueprint, request, abort, g
from flask.blueprints import BlueprintSetupState

from .configs import serialize_secrets
from . import yaml


bp = Blueprint('auth', __name__)

current_dir = Path(__file__).absolute().parent


class SCSAuthFileLoader(yaml.SCSYamlLoader):
    """
    Loader for the auth configuration file
    """
    pass


@bp.record
def init(setup_state: BlueprintSetupState):
    """
    Initializes the authentication module by loading the configuration files

    Args:
        setup_state:
            The .options attribute (options parameter passed to
            register_blueprint) should be a dict with the key/value pairs:
                scs_auth_path: pathlib.Path
                private_only: bool
                ip_whitelist: list[str]
    """
    global auth_mapping

    # Get options
    opts = setup_state.options
    scs_auth_path = Path(opts['users_file'])
    private_only = opts['networks']['private_only']
    network_whitelist = opts['networks']['whitelist']
    secrets_dir = opts['directories']['secrets']
    validate_dots = setup_state.app.config['SCS']['environments']\
        ['reject_keys_containing_dots']

    # Load the scs_auth.yaml file
    secrets_constructor = yaml.SCSSecretConstructor(
        secrets_dir=secrets_dir,
        validate_dots=validate_dots
    )
    SCSAuthFileLoader.add_constructor(
        secrets_constructor.tag, secrets_constructor.construct
    )
    scs_auth = yaml.load_file(scs_auth_path, loader=SCSAuthFileLoader)
    serialize_secrets(scs_auth)

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
    auth_mapping = {}
    for user in scs_auth['users']:
        auth_mapping[user.pop('token')] = user
        parsed_whitelist = []
        for item in user['has_access']['from_networks']:
            network = ipaddress.ip_network(item)
            if not is_whitelisted(network, parsed_global_whitelist):
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


def is_whitelisted(
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
    Check the authentication and authorization of the given user
    """
    # Get the bearer token, and check if it matches any accounts
    try:
        auth_header = request.headers['Authorization']
        token = auth_header.removeprefix('Bearer ')
        user = auth_mapping[token]
        g.user = user
    except KeyError:
        g.add_audit_event(event_type='unauthenticated')
        abort(401)

    # User is authenticated. Now check (1) if the ip is in the whitelist, (2)
    # if the url is authorized
    user_ip = ipaddress.ip_network(request.remote_addr)
    if not is_whitelisted(user_ip, user['has_access']['from_networks']):
        event_type = 'unauthorized-ip'
        g.add_audit_event(event_type=event_type)
        abort(403, description={'id': event_type})

    # Check if the user is allowed to access the provided url
    for pattern in user['has_access']['to_paths']:
        if pattern.match(request.path):
            break
    else:
        event_type = 'unauthorized-path'
        g.add_audit_event(event_type=event_type)
        abort(403, description={'id': event_type})
