# -*- coding: utf-8 -*-
"""
Flask Blueprint containing all behaviour related to the authentication and
authorization of users/clients
"""
from pathlib import Path
import re
import ipaddress

from flask import Blueprint, request, abort

from .configs import load_yaml, serialize_secrets

bp = Blueprint('auth', __name__)

current_dir = Path(__file__).absolute().parent


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
    except KeyError:
        abort(401)

    # User is authenticated. Now check (1) if the ip is in the whitelist, (2)
    # if the url is authorized
    user_ip = ipaddress.ip_address(request.remote_addr)
    for network in user['whitelist']:
        if user_ip in network:
            break
    else:
        abort(403)

    # Check if the user is allowed to access the provided url
    for pattern in user['allowed']:
        if pattern.match(request.path):
            break
    else:
        abort(403)


def init():
    """
    Initializes the authentication module by loading the configuration files

    Args:
        scs_auth_loc:
            Location of the scs_auth.yaml file

        secrets_dir:
            The directory containing the secrets
    """
    # TODO: This should check at a later point if the given whitelist ips are
    # private ips, depending on the 'private only' value
    global auth_mapping

    auth_data = load_yaml(
        Path(current_dir, '../data/config_example/scs_auth.yaml')
    )
    serialize_secrets(auth_data)

    # Create the mapping
    auth_mapping = {}
    for account in auth_data['accounts']:
        auth_mapping[account.pop('token')] = account
        # Parse the IP whitelist
        if 'whitelist' in account:
            parsed_whitelist = []
            for item in account['whitelist']:
                network = ipaddress.ip_network(item)
                parsed_whitelist.append(network)
            account['whitelist'] = parsed_whitelist
        # Parse the path whitelist regexes
        if 'allowed' in account:
            parsed_allowed = []
            for item in account['allowed']:
                regex_str = '^' + re.escape(item).replace(r'\*', '(.*)') + '$'
                parsed_allowed.append(
                    re.compile(regex_str)
                )
            account['allowed'] = parsed_allowed
