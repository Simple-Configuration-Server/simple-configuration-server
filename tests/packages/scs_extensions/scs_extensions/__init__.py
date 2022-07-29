"""
Contains SCS extensions used in the unit-tests
"""
from yaml import Loader, Node
from jinja2.ext import Extension
import functools

from scs.yaml import SCSYamlTagConstructor


class CapatilizeExtendPhraseConstructor(SCSYamlTagConstructor):
    """
    An example YAML tag constructor, that capitalizes a phrase and adds a
    suffix to it
    """
    tag = '!capitalize-extend-phrase'

    def __init__(self, *args, suffix: str, **kwargs):
        self.suffix = suffix
        super().__init__(*args, **kwargs)

    def construct(self, loader: Loader, node: Node) -> str:
        """
        Constructor method to construct the contents a node with the given tag
        """
        value = node.value
        if not isinstance(value, str):
            raise ValueError(
                'The value for the !capitalize-phrase constructor must be a '
                'string'
            )
        else:
            return value.upper() + self.suffix


def add_suffix(str_: str, *, suffix: str) -> str:
    """
    Add a suffix the end of a string
    """
    return str_ + suffix


class AddSuffixExtension(Extension):
    """
    Simple Extension that adds SCS to the end of a phrase
    """
    def __init__(self, environment):
        super().__init__(environment)
        suffix = environment.suffix_for_string
        environment.filters['add_suffix'] = functools.partial(
          add_suffix, suffix=suffix
        )
