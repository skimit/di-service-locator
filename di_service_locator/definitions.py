# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Feature dataclasses and types."""
import abc
import dataclasses
from typing import Collection, Mapping, Sequence, Tuple, Union

Primitives = Union[str, bool, int, float, Collection[str], Collection[int], Collection[float]]
# Type def for supported primitives
# TODO: dates? timestamps?


@dataclasses.dataclass
class FactoryDefinition:
    """
    Dataclass to hold all necessary factory information.

    Contains all the things necessary to instantiate a class dynamically and register it
    with the Features injector.
    """

    fqn_impl_factory: str
    fqn_interface: str
    args: Sequence[Primitives]
    kwargs: Mapping[str, Primitives]
    default: bool = False


class FactoryMap(abc.ABC):
    """
    Interface definition for a factory map.

    Provides factory definitions by type and name.
    """

    @abc.abstractmethod
    def get_by_type(self, fqn_type: str) -> Tuple[FactoryDefinition, str]:
        """
        Retrieve a `FactoryDefinition` by type name.

        :param fqn_type: the fully qualified name of the feature type
        :type fqn_type: str
        :return: the found factory definition and factory name
        :rtype: Tuple of FactoryDefinition and FactoryName
        """
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def get_by_name(self, name: str) -> FactoryDefinition:
        """
        Retrieve a `FactoryDefinition` by type name.

        :param name: the name of the feature type
        :type name: str
        :return: the found factory definition
        :rtype: FactoryDefinition
        """
        raise NotImplementedError  # pragma: no cover
