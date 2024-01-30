# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Reusable functions for dynamically loading and instantiating classes."""
import importlib
from typing import Type, TypeVar

InstanceT = TypeVar("InstanceT")


def load_class(fqn: str) -> Type:
    """
    Load a class using the fully qualified name.

    :param fqn: the fully qualified name of the class to load
    :returns: the loaded class
    """
    # TODO: validation and error handling
    bits = fqn.split(".")
    module = importlib.import_module(".".join(bits[0:-1]))
    return getattr(module, bits[-1])


def instantiate(clz: Type[InstanceT], *args, **kwargs) -> InstanceT:
    """
    Instantiate a given class.

    Eventually this could do runtime checking of types and
    also recursively handle other factory type instantiations.

    :param clz: the class to instantiate
    :param args: the args to pass to the constructor
    :param kwargs: the kwargs to pass to the constructor
    """
    # TODO: runtime check arg types
    # TODO: recursive instantiation if required!
    return clz(*args, **kwargs)


def build_fqn(clz: Type) -> str:
    """
    Get the fully qualified name of a given class.

    :param clz: the class to retrieve the fqn from
    """
    return clz.__module__ + "." + clz.__name__
