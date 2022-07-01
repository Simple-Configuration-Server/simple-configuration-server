# -*- coding: utf-8 -*-
"""
Contains the built-in YAML Loaders, loading functions, and constructors. A
file cache is implemented to cache loaded content when required.
"""
from abc import ABC, abstractmethod
from typing import Any
import re
import os
from pathlib import Path
import secrets
import copy
from random import randint

from yaml import Loader, Node, SafeLoader, dump, safe_load


class _ParsedFileCache:
    """
    Object to store parsed contents of YAML files. If enabled, this means
    YAML files only have to be loaded and parsed once. Use the disable() method
    to disable the caching of YAML files
    """
    def __init__(self):
        self._cache = {}
        self.disabled = False

    def clear(self):
        """Clears the parsed file cache"""
        self._cache = {}

    def get_file(self, path: os.PathLike) -> Any:
        """
        Get the contents of the file with the given path from the cache
        """
        if not self.disabled:
            abspath = Path(path).absolute().as_posix()
            data = self._cache.get(abspath)
            if data is not None:
                return copy.deepcopy(data)

    def add_file(self, path: os.PathLike, data):
        """
        Adds the parsed data (contents) of the file at the given file path to
        the cache
        """
        if not self.disabled:
            abspath = Path(path).absolute().as_posix()
            self._cache[abspath] = copy.deepcopy(data)

    def disable(self):
        """
        Disables the cache
        """
        self.clear()
        self.disabled = True


filecache = _ParsedFileCache()


class SCSYamlTagConstructor(ABC):
    """
    Base class for YAML tag constructors

    Any constructors configured under extensions.constructors in the
    scs-configuration file should inherit from this class
    """
    def __init__(self):
        """
        Validates if the 'tag' attribute is defined
        """
        if not hasattr(self, 'tag'):
            raise AttributeError('.tag attribute of YAML constructor missing!')

    @abstractmethod
    def construct(self, loader: Loader, node: Node) -> Any:
        """
        Constructor method to construct the contents a node with the given tag
        """
        pass


class SCSYamlLoader(SafeLoader):
    """
    The base loader used to load SCS Yaml files, which tracks the file path of
    the file that's loaded, and whether the contents have changed.
    """
    def __init__(self, *args, filepath: Path, **kwargs):
        self.filepath = filepath
        # The 'resave' option can be set from constructors to indicate to the
        # 'load' function that the file has changed (e.g values were added) and
        # should be resaved
        self.resave = False
        super().__init__(*args, **kwargs)


# Seperate classes are defined for each type of loader. Different constructors
# are added to them during server initialization
class SCSAppConfigLoader(SCSYamlLoader):
    """Used to load the App configuration files"""
    pass


class SCSSecretFileLoader(SCSYamlLoader):
    """Used to load secret files"""
    pass


class SCSEnvFileLoader(SCSYamlLoader):
    """Used to load the scs-env.yaml files"""
    pass


def load_file(path: Path, loader: type) -> Any:
    """
    Load data from the given path, using the provided loader

    Args:
        path: The path of the yaml file to load

        loader: A loader class that inherits from SCSYamlLoader

    Returns:
        The data loaded from the YAML file
    """
    path = path.absolute()
    if (data := filecache.get_file(path)) is not None:
        return data

    with open(path, 'r', encoding='utf8') as yamlfile:
        yaml_loader = loader(yamlfile, filepath=path)
        data = yaml_loader.get_single_data()

    if yaml_loader.resave:
        with open(path, 'w', encoding='utf8') as yamlfile:
            dump(data, yamlfile, sort_keys=False)

    filecache.add_file(path, data)

    return data


def safe_load_file(path: Path) -> Any:
    """
    Use the default pyyaml SafeLoader to load a file (uncached)

    Args:
        path: The full path of the YAML file

    Returns:
        The parsed contents of the given YAML file
    """
    with open(path, 'r', encoding='utf8') as yamlfile:
        return safe_load(yamlfile)


class RelativePathMixin:
    """
    Constructor Mixin to get the data from a referenced relative path

    Attributes:
        validate_dots:
            Whether to validate that there are no dots in the key names, since
            these are unusable for references
    """
    # Regex to match a list index inside a scs-ref tag contents
    index_regex = re.compile(r'\[(\d+)\]')

    @property
    @abstractmethod
    def loader(self) -> type:
        """The Loader Class (NOT: instance) to use"""
        pass

    def __init__(self, *args, validate_dots: bool = True, **kwargs):
        self.validate_dots = validate_dots
        super().__init__(*args, **kwargs)

    def _get_data(self, base_dir: Path, ref: str) -> Any:
        """
        Get the data from the referenced location and attribute

        Args:
            base_dir:
                The directory the reference is relative to
            ref:
                The reference given in the YAML file

        Returns:
            The data that's loaded from the referenced location
        """
        # Split the reference to (1) file path, (2) a property in a file (when
        # present)
        ref_parts = ref.split('#')

        if len(ref_parts) == 1:
            file_path = ref_parts[0]
            attribute_loc = None
        else:
            file_path, attribute_loc = ref_parts

        file_path = Path(base_dir, file_path)

        file_data = load_file(file_path, loader=self.loader)

        if self.validate_dots and self._contains_keys_with_dots(file_data):
            raise ValueError(
                f'The file {file_path.as_posix()} has variable names with dots'
            )

        if not attribute_loc:
            ref_data = file_data
        else:
            loc_levels = attribute_loc.split('.')
            level_data = file_data
            try:
                for level in loc_levels:
                    if match := self.index_regex.match(level):
                        index = int(match.group(1))
                        level_data = level_data[index]
                    else:
                        level_data = level_data[level]
            except (KeyError, IndexError):
                raise ValueError(
                    f'The reference {ref} in file {file_path.as_posix()} '
                    'could not be resolved!'
                )
            ref_data = level_data

        return ref_data

    def _contains_keys_with_dots(self, data: Any) -> bool:
        """
        Verify that there are no dots in the keynames of dicts embedded in the
        data, since this doesn't work in combination with references

        Arguments:
            data: The data to validate

        Returns:
            Whether there are any 'keys' in the data that contain dots
        """
        if isinstance(data, dict):
            for key, value in data.items():
                if '.' in key:
                    return True
                if self._contains_keys_with_dots(value):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._contains_keys_with_dots(item):
                    return True

        return False


class SCSSecret:
    """
    A secret class, used to track which secrets end-up in the final Env, so
    secret access can be logged

    Attributes:
        id:
            A unique identifier describing the secrets. This will be logged in
            the audit logs
        value:
            The value of the secret
    """
    def __init__(self, id_: str, value: Any):
        self.id = id_
        self.value = value


def serialize_secrets(data: dict | list) -> list[str]:
    """
    Serialize all secrets in the data (In-place)

    Args:
        env_data:
            The environment data, possible containg SCSSecret objects. This
            will be serialized IN PLACE

    Returns:
        The id's of the secrets that were serialized
    """
    secret_ids = set()
    if isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, SCSSecret):
                secret_ids.add(item.id)
                data[i] = item.value
            else:
                serialize_secrets(item)
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                serialized_secrets = serialize_secrets(value)
                secret_ids.update(serialized_secrets)
            elif isinstance(value, SCSSecret):
                secret_ids.add(value.id)
                data[key] = value.value

    return secret_ids


# The default constructors used by SCS
class SCSSecretConstructor(RelativePathMixin, SCSYamlTagConstructor):
    """
    The default constructor for the 'scs-secret' tag

    Attributes:
        secrets_dir: The directory containing the yaml files with secrets
    """
    tag = '!scs-secret'
    loader = SCSSecretFileLoader

    def __init__(self, *args, secrets_dir: Path, **kwargs):
        self.secrets_dir = secrets_dir
        super().__init__(*args, **kwargs)

    def construct(self, loader: Loader, node: Node) -> Any:
        ref = node.value
        base_dir = self.secrets_dir
        ref_data = self._get_data(base_dir, ref)

        return SCSSecret(ref, ref_data)


class SCSCommonConstructor(RelativePathMixin, SCSYamlTagConstructor):
    """
    The default constructor for the 'scs-common' tag

    Attributes:
        common_dir: The directory containing the yaml files with common data
    """
    tag = '!scs-common'
    loader = SCSEnvFileLoader

    def __init__(self, *args, common_dir: Path, **kwargs):
        self.common_dir = common_dir
        super().__init__(*args, **kwargs)

    def construct(self, loader: Loader, node: Node) -> Any:
        ref = node.value
        base_dir = self.common_dir
        return self._get_data(base_dir, ref)


class SCSRelativeConstructor(RelativePathMixin, SCSYamlTagConstructor):
    """
    The default constructor for the 'scs-relative' tag
    """
    tag = '!scs-relative'
    loader = SCSEnvFileLoader

    def construct(self, loader: Loader, node: Node) -> Any:
        ref = node.value
        base_dir = loader.filepath.parent
        return self._get_data(base_dir, ref)


class SCSExpandEnvConstructor(SCSYamlTagConstructor):
    """
    The default constructor for the 'scs-expand-env' tag
    """
    tag = '!scs-expand-env'
    pattern = re.compile(r'\$\{([^}^{]+)\}')

    def _get_env_var(self, match: re.Match) -> str:
        """
        Return the environment variable for the 'pattern' match

        Args:
            match: A match to the SCSExpandEnvConstructor.pattern

        Returns:
            The contents of the environment variable

        Raises:
            KeyError in case the parsed environment variable does not exist
        """
        env_var_name = match.group(1)
        try:
            return os.environ[env_var_name]
        except KeyError:
            raise KeyError(
                f'Environment Variable {env_var_name} not defined!'
            ) from None

    def construct(self, loader: Loader, node: Node) -> str:
        return self.pattern.sub(self._get_env_var, node.value)


class SCSGenSecretConstructor(SCSYamlTagConstructor):
    """
    The default constructor for the 'scs-gen-secret' tag. If this tag is
    encountered, a secret is generated, and the contents of the file are
    re-saved.
    """
    tag = '!scs-gen-secret'

    def construct(self, loader: Loader, node: Node) -> str:
        loader.resave = True
        return secrets.token_urlsafe(randint(32, 64))


class SCSSimpleValueConstructor(SCSYamlTagConstructor):
    """
    A YAML tag constructor that can be used multiple times to replace a
    specific tag (passed as init variable) with a fixed value. The main
    use-case for this is for testing configuration files, in which case
    advanced configuration parameters are not available.

    Attributes:
        tag: The tag to which this constructor should be applied

        value: The value to use when parsing this tag
    """
    def __init__(self, *args, tag: str, value: Any, **kwargs):
        self.tag = tag
        self.value = value
        super().__init__(*args, **kwargs)

    def construct(self, loader: Loader, node: Node) -> Any:
        return self.value
