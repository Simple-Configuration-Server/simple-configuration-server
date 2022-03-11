# -*- coding: utf-8 -*-
"""
Contains the built-in YAML tag constructors for the SCS
"""
from abc import ABC, abstractmethod
from typing import Any
import re
import os
from pathlib import Path
import secrets

from yaml import Loader, Node, SafeLoader, dump


index_regex = re.compile(r'\[(\d+)\]')


class _ParsedFileCache:
    """
    Object to store the parsed contents of a YAML file during the construction
    of envdata for each path
    """
    def __init__(self):
        self.cache = {}
        self.disabled = False

    def clear(self):
        self.cache = {}

    def get_file(self, path: os.PathLike):
        if not self.disabled:
            abspath = Path(path).absolute().as_posix()
            return self.cache.get(abspath)

    def add_file(self, path: os.PathLike, data):
        if not self.disabled:
            abspath = Path(path).absolute().as_posix()
            self.cache[abspath] = data

    def disable(self):
        self.disabled = True


filecache = _ParsedFileCache()


class SCSYamlTagConstructor(ABC):
    """
    Base class for YAML tag constructors
    """
    @property
    @abstractmethod
    def tag(self):
        """The yaml tag to register the constructor for"""
        pass

    @abstractmethod
    def construct(self, loader: Loader, node: Node) -> Any:
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


def load(path: Path, loader: SCSYamlLoader) -> Any:
    """
    Load data from the given path, using the provided loader
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


class RelativePathMixin:
    """
    Constructor Mixin to get the data from a referenced relative path

    Attributes:
        validate_dots:
            Whether to validate that there are no dots in the key names, since
            these are unusable for references
    """
    @property
    @abstractmethod
    def loader(self):
        """The Loader Class (NOT: instance) to use"""
        pass

    def __init__(self, *args, validate_dots: bool = True, **kwargs):
        self.validate_dots = validate_dots
        super().__init__(*args, **kwargs)

    def _get_data(self, base_dir: Path, ref: str) -> Any:
        # Split the reference to (1) file path, (2) a property in a file (when
        # present)
        ref_parts = ref.split('#')

        if len(ref_parts) == 1:
            file_path = ref_parts
            attribute_loc = None
        else:
            file_path, attribute_loc = ref_parts

        # Resolve full path
        file_path = Path(base_dir, file_path)

        file_data = load(file_path, loader=self.loader)

        if self.validate_dots and self._contains_keys_with_dots(file_data):
            raise ValueError(
                f'The file {file_path.as_posix()} has variable names with dots'
            )

        if not attribute_loc:
            ref_data = file_data
        else:
            loc_levels = attribute_loc.split('.')
            level_data = file_data
            for level in loc_levels:
                if match := index_regex.match(level):
                    index = int(match.group(1))
                    level_data = level_data[index]
                else:
                    level_data = level_data[level]
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
    secret access can be logged.

    Attributes:
        id:
            A unique identifier describing the secrets. This will be logged in
            the access logs
        value:
            The value of the secret
    """
    def __init__(self, id_: str, value):
        self.id = id_
        self.value = value


# The default constructors used by SCS
class SCSSecretConstructor(SCSYamlTagConstructor, RelativePathMixin):
    """
    The default constructor for the 'scs-secret' tag
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


class SCSCommonConstructor(SCSYamlTagConstructor, RelativePathMixin):
    """
    The default constructor for the 'scs-common' tag
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


class SCSRelativeConstructor(SCSYamlTagConstructor, RelativePathMixin):
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
    The default constructor for the 'scs-relative' tag
    """
    tag = '!scs-expand-env'
    pattern = re.compile(r'\$\{([^}^{]+)\}')

    def _get_env_var(self, match):
        """
        Return the environment variable for the 'pattern' match
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
        return secrets.token_urlsafe(32)
