"""
Contains SCS extensions used in the unit-tests
"""
from yaml import Loader, Node
from jinja2.ext import Extension

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


def add_scs_suffix(str_: str) -> str:
    """
    Add ' SCS' to the end of a string
    """
    return str_ + ' SCS'


class AddSCSExtension(Extension):
    """
    Simple Extension that adds SCS to the end of a phrase
    """
    def __init__(self, environment):
        super().__init__(environment)
        environment.filters['add_scs_suffix'] = add_scs_suffix
