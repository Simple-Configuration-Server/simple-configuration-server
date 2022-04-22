# -*- coding; utf-8 -*-
"""
Flask Blueprint containing the code for the configs/ endpoints, that loads the
configuration data and returns the formatted data
"""
from pathlib import Path
import copy
import logging
import os

from flask import (
    Blueprint, request, g, make_response, abort, current_app, Response
)
from flask.blueprints import BlueprintSetupState
import fastjsonschema
from jinja2 import TemplateError
from yaml import YAMLError

from . import yaml, errors
from .tools import get_object_from_name
from .logging import register_audit_event

bp = Blueprint('configs', __name__, url_prefix='/configs')

# These are registered with the logging module in the init function
_AUDIT_EVENTS = [
    (
        'config-loaded', logging.INFO,
        "User '{user}' has loaded {path}",
    ),
    (
        'secrets-loaded', logging.INFO,
        "User '{user}' has loaded the following secrets: {secrets}",
    ),
]

# Load the schema, and use this to populate the default values of the ENV
_env_file_schema_path = Path(
    Path(__file__).absolute().parent,
    'schemas/scs-env.yaml'
)
_env_file_schema = yaml.safe_load_file(_env_file_schema_path)
_validate_env_file = fastjsonschema.compile(_env_file_schema)
_DEFAULT_ENV = _validate_env_file({})


@bp.record
def init(setup_state: BlueprintSetupState):
    """
    Initializes the configs/* endpoints

    Args:
        setup_state:
            The .options attribute of this (options passed to
            register_blueprint function) should contain the following dict
            data:
                directories: dict; containing:
                    common, config, secrets: str


    """
    global _config_basepath

    scs_config = setup_state.app.config['SCS']

    _config_basepath = Path(scs_config['directories']['config']).absolute()
    common_basepath = Path(scs_config['directories']['common']).absolute()
    secrets_basepath = Path(scs_config['directories']['secrets']).absolute()
    add_constructors = scs_config['extensions']['constructors']
    check_templates = scs_config['templates']['validate_on_startup']
    default_rendering_options = scs_config['templates']['rendering_options']
    validate_dots = scs_config['environments']['reject_keys_containing_dots']
    enable_env_cache = scs_config['environments']['cache']

    _configure_yaml_loaders(
        common_dir=common_basepath,
        secrets_dir=secrets_basepath,
        add_constructors=add_constructors,
        validate_dots=validate_dots
    )

    # Configure template rendering options
    setup_state.app.jinja_options.update(default_rendering_options)

    bp.template_folder = _config_basepath

    # Register all exceptions and audit events with the errors and logging
    # modules, to make sure pre-defined json messages are returned when errors
    # occur, and specific audit events can be logged from within this
    # bluetprint
    for exc_class, error_id, error_msg in _EXCEPTIONS:
        errors.register_exception(
            exc_class, error_id,
            message=error_msg
        )
    for audit_event_args in _AUDIT_EVENTS:
        register_audit_event(*audit_event_args)

    if enable_env_cache or check_templates:
        relative_config_template_paths = _get_relative_config_template_paths()
        for relative_url in relative_config_template_paths:
            env = _load_env(relative_url.lstrip('/'))
            if check_templates:
                yaml.serialize_secrets(env)
                template = setup_state.app.jinja_env.get_template(
                    relative_url.lstrip('/')
                )
                template.render(**env)


def _configure_yaml_loaders(
        *, common_dir: Path, secrets_dir: Path, add_constructors: list[dict],
        validate_dots: bool,
        ):
    """
    Configure the YAML loaders used by the configs module, to use the right
    constructors for YAML tags

    Args:
        common_dir:
            The base directory used to resolve !scs-common tags

        secrets_dir:
            The base directory used to resolve !scs-secret tags

        add_constructors:
            List of custom constructers to add on top of the default ones

        validate_dots:
            Whether errors should be generated if dots are in keys
    """
    ENV_FILE_CONSTRUCTORS = [
        yaml.SCSRelativeConstructor(
            validate_dots=validate_dots,
        ),
        yaml.SCSSecretConstructor(
            secrets_dir=secrets_dir,
            validate_dots=validate_dots,
        ),
        yaml.SCSCommonConstructor(
            common_dir=common_dir,
            validate_dots=validate_dots,
        ),
        yaml.SCSExpandEnvConstructor(),
    ]

    if add_constructors:
        for constructor_config in add_constructors:
            constructor_name = constructor_config['name']
            constructor_class = get_object_from_name(constructor_name)
            if not isinstance(constructor_class, yaml.SCSYamlTagConstructor):
                raise ValueError(
                    f"The constructor '{constructor_name}' is not a "
                    "SCSYamlTagConstructor subclass"
                )
            options = constructor_config.get('options', {})
            ENV_FILE_CONSTRUCTORS.append(
                constructor_class(**options)
            )

    SECRET_FILE_CONSTRUCTORS = [
        yaml.SCSGenSecretConstructor(),
    ]

    for constructor in ENV_FILE_CONSTRUCTORS:
        yaml.SCSEnvFileLoader.add_constructor(
            constructor.tag, constructor.construct
        )

    for constructor in SECRET_FILE_CONSTRUCTORS:
        yaml.SCSSecretFileLoader.add_constructor(
            constructor.tag, constructor.construct
        )


class EnvFileFormatException(Exception):
    """Raised if JSON schema validation fails on an env-file"""


def _load_env_file(relative_path: str) -> dict:
    """
    Load the data from the given env file, if it exists

    Args:
        relative_path: The path of env file, relative to the config directory

    Raises:
        EnvFileFormatException in case the env file does not pass JSON-schema
        validation
    """
    path = Path(_config_basepath, relative_path)
    if not path.is_file():
        return {}

    env_data = yaml.load_file(path, loader=yaml.SCSEnvFileLoader)

    try:
        # Ignore the return, since we don't want to fill defaults
        _validate_env_file(env_data)
    except fastjsonschema.JsonSchemaValueException as e:
        raise EnvFileFormatException(
            f'The env file {path.as_posix()} failed validation: {e.message}'
        )

    return env_data


def _get_env_file_hierarchy(relative_path: str) -> list[str]:
    """
    Get all possible paths of the env-files belonging to the file under the
    given relative path

    Args:
        relative_path:
            The path of the template to get the env files for, relative to the
            config directory

    Returns:
        A list of the possible relative paths of scs-env files
    """
    path_parts = relative_path.split('/')

    ordered_envfiles = ['scs-env.yaml']
    envfile_basepath = ''
    for part in path_parts[:-1]:
        envfile_basepath += f'{part}/'
        ordered_envfiles.append(envfile_basepath + '/scs-env.yaml')
    ordered_envfiles.append(relative_path + '.scs-env.yaml')

    return ordered_envfiles


def _load_env(relative_path: str):
    """
    Load the combined env data for the template with the given relative_path

    Args:
        relative_path:
            The path of the template, relative to the config directory
    Returns:
        The combined environment data of all environment files applicable to
        the template
    """
    combined_env = copy.deepcopy(_DEFAULT_ENV)
    rel_env_file_paths = _get_env_file_hierarchy(relative_path)

    for rel_path in rel_env_file_paths:
        data = _load_env_file(rel_path)
        for key, value in data.items():
            if isinstance(value, dict):
                combined_env[key].update(value)
            else:
                combined_env[key] = value

        combined_env.update(data)

    return combined_env


def _get_relative_config_template_paths() -> list[str]:
    """
    Gets the relative paths of all config templates

    Returns:
        List of all relative paths of available templates under the config
        directory
    """
    config_template_paths = []
    for path in _config_basepath.rglob('*'):
        if path.is_file() and not path.name.endswith('scs-env.yaml'):
            relative_template_path = \
                path.as_posix().removeprefix(_config_basepath.as_posix())
            config_template_paths.append(relative_template_path)

    return config_template_paths


def _resource_exists(path: str) -> bool:
    """
    Checks if a template exists that matches the given path

    Args:
        path: The path of the template

    Returns:
        True if the path is valid and the template exists. Otherwise returns
        False
    """
    # Prevent path traversal
    # Note that this is later more extensively checked by the jinja loader
    references_parent = any([p == os.path.pardir for p in path.split('/')])
    if references_parent:
        return False

    # Prevent exposing env files
    if path.endswith('scs-env.yaml'):
        return False

    full_path = Path(_config_basepath, path)

    return full_path.is_file()


# These seem to erroneously not be supported on the overlay function
# https://github.com/pallets/jinja/issues/1645
# Test the removal of this after jinja2>=3.1.2 is released
_MISSING_OVERLAY_OPTIONS = [
    'newline_sequence',
    'keep_trailing_newline'
]


@bp.route('/<path:path>', methods=('GET', 'POST'))
def view_config_file(path: str) -> Response:
    """
    Flask view function that returns the rendered template at the given path

    Args:
        path:
            The path in the URL of the request, relative to the configs/
            endpoint

    Returns:
        Flask response object containing the rendered template

    Raises:
        werkzeug.exceptions.HTTPException in case (1) an invalid path is
        provided (404) or an unsupported method is used (405)
    """
    if not _resource_exists(path):
        abort(404)

    env = _load_env(path)

    if request.method not in env['methods']:
        abort(405)

    if request.method == 'POST':
        env['context'].update(request.get_json(force=True))

    secret_ids = yaml.serialize_secrets(env)

    if rendering_options := env['rendering_options']:
        # Since some options seem to erroneously not be supported, these are
        # applied later
        # https://github.com/pallets/jinja/issues/1645
        # Test the removal of this after jinja2>=3.1.2 is released
        unsupported_options = {}
        for key in _MISSING_OVERLAY_OPTIONS:
            if key in rendering_options:
                unsupported_options[key] = rendering_options.pop(key)
        jinja_env = current_app.jinja_env.overlay(**rendering_options)
        for key, value in unsupported_options.items():
            setattr(jinja_env, key, value)
    else:
        jinja_env = current_app.jinja_env

    template = jinja_env.get_template(path.lstrip('/'))
    rendered_template = template.render(env['context'])

    response = make_response(rendered_template)
    response.headers.clear()  # Remove the default 'html' content type
    response.headers.update(env['headers'])
    response.status = env['status']

    g.add_audit_event(event_type='config-loaded')
    if secret_ids:
        g.add_audit_event(
            event_type='secrets-loaded', secrets=list(secret_ids),
        )

    return response


# These are registered with the 'errors' module, to ensure correct error
# messages are returned if these occur
_EXCEPTIONS = [
    (
        YAMLError, 'env-syntax-error',
        'The YAML syntax in an env file could not be parsed',
    ),
    (
        TemplateError, 'template-rendering-error',
        'An error occured while trying to render the template',
    ),
    (
        EnvFileFormatException, 'env-format-error',
        'An env file was provided in an invalid format',
    ),
]
