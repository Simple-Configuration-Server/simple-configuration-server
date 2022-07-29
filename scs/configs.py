# -*- coding; utf-8 -*-
"""
Flask Blueprint containing the code for the configs/ endpoints, that loads the
configuration data and returns the formatted data
"""
from pathlib import Path
import copy
import logging
import os
import inspect

from flask import (
    Blueprint, request, g, make_response, abort, current_app, Response,
    send_from_directory,
)
from flask.blueprints import BlueprintSetupState
import fastjsonschema
from jinja2 import TemplateError, Environment
from yaml import YAMLError

from . import yaml, errors
from .tools import get_object_from_name
from .logging import register_audit_event

bp = Blueprint('configs', __name__, url_prefix='/configs')
native_rendering_options = set(
    inspect.getfullargspec(Environment.__init__).args
)
native_rendering_options.difference_update([
    'loader', 'extensions', 'undefined',
])

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

_ERRORS = [
    (
        400, 'request-body-invalid',
        'Your request body doesn\'t match the configured schema',
    )
]

# Load the schema, and use this to populate the default values of the ENV
_env_file_schema_path = Path(
    Path(__file__).absolute().parent,
    'schemas/scs-env.yaml'
)
_env_file_schema = yaml.safe_load_file(_env_file_schema_path)
_validate_env_file = fastjsonschema.compile(_env_file_schema)
_DEFAULT_ENV = _validate_env_file({})


def split_jinja_env_options(options: dict) -> tuple[dict, dict]:
    """
    Split the provided jinja environment options into (1) options that are
    natively supported, and can therefore be provided at environment init,
    and (2) other options that are not officially supported, and should be
    added after init using the .extend method
    """
    native_options = {}
    non_native_options = {}
    for key, value in options.items():
        if key in native_rendering_options:
            native_options[key] = value
        else:
            non_native_options[key] = value

    return (native_options, non_native_options)


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
    global _config_basepath, default_rendering_options, jinja_extensions

    scs_config = setup_state.app.config['SCS']

    _config_basepath = Path(scs_config['directories']['config']).absolute()
    common_basepath = Path(scs_config['directories']['common']).absolute()
    if not _config_basepath.is_dir():
        raise ValueError(
            'The provided directories.config path does not exist!'
        )
    if not common_basepath.is_dir():
        raise ValueError(
            'The provided directories.common path does not exist!'
        )
    if 'secrets' in scs_config['directories']:
        secrets_basepath = Path(
            scs_config['directories']['secrets']
        ).absolute()
    else:
        secrets_basepath = None
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

    # Native env options should be passed at init, non-native ones should be
    # applied using extend to ensure no built-in properties are overriden
    native_env_options, extend_env_options = split_jinja_env_options(
        default_rendering_options
    )
    setup_state.app.jinja_options.update(native_env_options)
    setup_state.app.jinja_env.extend(**extend_env_options)

    jinja_extensions = scs_config['extensions']['jinja2']
    for jinja_extension in jinja_extensions:
        setup_state.app.jinja_env.add_extension(jinja_extension['name'])

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
    for error_args in _ERRORS:
        errors.register(*error_args)

    if enable_env_cache or check_templates:
        relative_config_template_paths = get_relative_config_template_paths()
        for relative_url in relative_config_template_paths:
            env = _load_env(relative_url.lstrip('/'))
            # If request.schema is defined, check if it's able to parse
            if env['request']['schema']:
                fastjsonschema.compile(env['request']['schema'])
            if check_templates and env['template']['enabled']:
                yaml.serialize_secrets(env)
                template = setup_state.app.jinja_env.get_template(
                    relative_url.lstrip('/')
                )
                template.render(**env['template']['context'])


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
    env_file_constructors = [
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
            options = constructor_config.get('options', {})
            constructor_instance = constructor_class(**options)
            if not isinstance(constructor_instance, yaml.SCSYamlTagConstructor):  # noqa:E501
                raise ValueError(
                    f"The constructor '{constructor_name}' is not a "
                    "SCSYamlTagConstructor subclass"
                )
            env_file_constructors.append(
                constructor_instance
            )

    SECRET_FILE_CONSTRUCTORS = [
        yaml.SCSGenSecretConstructor(),
    ]

    for constructor in env_file_constructors:
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
        for pkey, pvalue in data.items():
            for ckey, cvalue in pvalue.items():
                if isinstance(cvalue, dict):
                    combined_env[pkey][ckey].update(cvalue)
                else:
                    combined_env[pkey][ckey] = cvalue

    return combined_env


def get_relative_config_template_paths() -> list[str]:
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

    if request.method not in env['request']['methods']:
        abort(405)

    if request.method == 'POST':
        body = request.get_json(force=True)
        if env['request']['schema']:
            try:
                body = fastjsonschema.validate(env['request']['schema'], body)
            except fastjsonschema.JsonSchemaValueException:
                abort(400, description={'id': 'request-body-invalid'})

        env['template']['context'].update(request.get_json(force=True))

    secret_ids = yaml.serialize_secrets(env)

    if env['template']['enabled']:
        if additional_options := env['template']['rendering_options']:
            # Since it should be supported to override properties that are
            # initially set using .extend, create a completely new environment
            # with the existing loader, because .extend cannot be used twice
            combined_options = copy.copy(default_rendering_options)
            combined_options.update(additional_options)
            native_env_options, extend_env_options = split_jinja_env_options(
                combined_options
            )
            native_env_options['loader'] = current_app.jinja_env.loader
            jinja_env = Environment(**native_env_options)
            jinja_env.extend(**extend_env_options)
            for jinja_extension in jinja_extensions:
                jinja_env.add_extension(jinja_extension['name'])
        else:
            jinja_env = current_app.jinja_env

        template = jinja_env.get_template(path.lstrip('/'))
        rendered_template = template.render(env['template']['context'])

        response = make_response(rendered_template)
        response.headers.clear()  # Remove the default 'html' content type
    else:
        response = send_from_directory(_config_basepath, path)

    response.headers.update(env['response']['headers'])
    response.status = env['response']['status']

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
