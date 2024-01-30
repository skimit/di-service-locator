# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Classes and functions to create factory maps from config."""
import json
import os
import pathlib
import sys
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple

from di_service_locator import logger
from di_service_locator.definitions import FactoryDefinition, FactoryMap
from di_service_locator.exceptions import (
    FeatureError,
    FeatureNotFound,
    MultipleFeatureDefaults,
)

VERSION = 1
""" Config schema version. """

PROPERTY_IDENTIFIER = "$"
PROPERTY_DEFAULT_SEPARATOR = "="


class FeatureConfigError(FeatureError):
    """Error rasied when there is problem with feature config."""


def _dot_env_file_property(property_name: str) -> Optional[str]:
    """
    Read a property from a .env file in the current directory.

    :param property_name: The name of the property
    :type property_name: str
    :return: the property value, or None if it doesn't exist
    :rtype: str
    """
    dot_env_file = pathlib.Path(".env").absolute()
    if dot_env_file.exists():
        with dot_env_file.open("rt", encoding="utf-8") as file:
            for line in file:
                bits = line.split("=")
                if len(bits) == 2:
                    if bits[0].strip() == property_name:
                        return bits[1].strip()
    return None


def _env_property(property_name: str) -> Optional[str]:
    """
    Read a property from the environment.

    :param property_name: The name of the property
    :type property_name: str
    :return: the property value, or None if it doesn't exist
    :rtype: str
    """
    return os.environ.get(property_name)


def _command_line_property(property_name: str) -> Optional[str]:
    """
    Read a property from the command line args.

    :param property_name: The name of the property
    :type property_name: str
    :return: the property value, or None if it doesn't exist
    :rtype: str
    """
    prop_key = f"--{property_name}="
    for sys_arg in sys.argv:
        if sys_arg.startswith(prop_key):
            return sys_arg.rsplit(prop_key, maxsplit=1)[-1]
    return None


class PropertyResolver:
    """Resolve properties by searching through an ordered list of property providers."""

    def __init__(self, providers: Sequence[Callable[[str], Optional[str]]]) -> None:
        self._providers = providers

    @staticmethod
    def _is_property(property_value: str) -> bool:
        return isinstance(property_value, str) and property_value.startswith(
            PROPERTY_IDENTIFIER
        )

    def _resolve_property(self, property_value: str) -> str:
        if PropertyResolver._is_property(property_value):
            property_name = property_value[len(PROPERTY_IDENTIFIER) :]
            property_default = None
            if PROPERTY_DEFAULT_SEPARATOR in property_name:
                property_name, property_default = property_name.split(
                    PROPERTY_DEFAULT_SEPARATOR, maxsplit=1
                )
            for resolver in self._providers:
                value = resolver(property_name)
                if value:
                    return value
            if property_default:
                property_value = property_default
            else:
                raise FeatureConfigError(f"No property value found for {property_value}")
        return property_value

    def resolve(self, factory_definition: FactoryDefinition) -> FactoryDefinition:
        """
        Take a `FactoryDefinition` and resolve any args or kwargs that are properties.

        Properties are values of the form $<property name>
        Note that property resolution is done in place and the factory definition is mutated
        rather than cloned.

        :param factory_definition: the factory definition to resolve
        :type factory_definition: FactoryDefinition
        :return: the factory definition with property values replaced in args & kwargs
        :rtype: FactoryDefinition
        """
        # fine to mutate in place
        factory_definition.args = [
            self._resolve_property(arg) if isinstance(arg, str) else arg
            for arg in factory_definition.args
        ]
        factory_definition.kwargs = {
            key: self._resolve_property(value) if isinstance(value, str) else value
            for key, value in factory_definition.kwargs.items()
        }
        return factory_definition


STANDARD_PROPERTY_RESOLVER = PropertyResolver(
    providers=[_command_line_property, _env_property, _dot_env_file_property]
)
"""
Standard property resolver specify priority order of command line args->environment->.env file.
"""


class DictionaryFactoryMap(FactoryMap):
    """A `FactoryMap` implementation sitting on top of a simple dictionary."""

    def __init__(self, config_dict: Mapping[str, FactoryDefinition]) -> None:
        self._config_dict = config_dict

        self._interface_map: Dict[str, Tuple[FactoryDefinition, str]] = {}
        for fd_name, factory_def in self._config_dict.items():
            _entry = self._interface_map.get(factory_def.fqn_interface, None)

            # If there is no definition or if a definition is not the default.
            if _entry is None or not _entry[0].default:
                self._interface_map[factory_def.fqn_interface] = (factory_def, fd_name)
            # If both definitions are trying to be the default.
            elif factory_def.default and _entry[0].default:
                raise MultipleFeatureDefaults(
                    f"Multiple definitions set as 'default' for {factory_def.fqn_interface}"
                )

    def get_by_type(self, fqn_type: str) -> Tuple[FactoryDefinition, str]:
        if fqn_type not in self._interface_map:
            raise FeatureNotFound(f"Feature {fqn_type} was not found in factory map")

        return self._interface_map[fqn_type]

    def get_by_name(self, name: str) -> FactoryDefinition:
        for k, value in self._config_dict.items():
            if k == name:
                return value

        raise FeatureNotFound(f"Feature {name} was not found in factory map")


# TODO: validation! schema?


def factory_definition_from_json(json_definition: Mapping) -> FactoryDefinition:
    """
    Convert a JSON object defining a `FactoryDefinition` into a python object.

    :param json_definition: json representation
    :returns: a `FactoryDefinition`
    """
    return STANDARD_PROPERTY_RESOLVER.resolve(
        FactoryDefinition(
            fqn_impl_factory=json_definition["factory"],
            fqn_interface=json_definition["implements"],
            args=json_definition["args"] if "args" in json_definition else [],
            kwargs=json_definition["kwargs"] if "kwargs" in json_definition else {},
            default=json_definition["default"] if "default" in json_definition else False,
        )
    )


def factory_map_from_json_dict(config_dict: Mapping) -> FactoryMap:
    """
    Build a factory map from a JSON dict.

    :param config_dict: json representation of a factory map
    :returns: a python `FactoryMap`
    """
    config_version = config_dict["version"] if "version" in config_dict else 0
    if config_version != VERSION:
        raise FeatureConfigError(
            f"Incorrect feature version in config {config_version}, but required {VERSION}"
        )

    return DictionaryFactoryMap(
        {
            key: factory_definition_from_json(value)
            for key, value in config_dict["features"].items()
        }
    )


def factory_map_from_json_file(path_to_json: pathlib.Path) -> FactoryMap:
    """
    Load a JSON file and convert it into a `FactoryMap`.

    :param path_to_json: the path to a valid json file
    :returns: a `FactoryMap` implementation
    """
    try:
        with path_to_json.open() as file_pointer:
            logger.info(f"Reading factory map file from {path_to_json}")
            json_dict = json.load(file_pointer)
            return factory_map_from_json_dict(json_dict)
    except FeatureConfigError as ex:
        raise FeatureConfigError(f"Problem with file '{str(path_to_json)}': {str(ex)}") from ex
