# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

import abc
import contextlib
import importlib
from typing import Generator

import pytest

import di_service_locator
import di_service_locator.features
from di_service_locator.definitions import FactoryMap
from di_service_locator.features import ServiceLocator


class ITest(abc.ABC):
    """Test interface definition for a not very interesting service."""

    @abc.abstractmethod
    def add(self, a: int, b: int) -> int:
        """Add some things up."""
        raise NotImplementedError


class Test(ITest):
    """Test implementation of the test service."""

    def __init__(self, c: int) -> None:
        self._c = c

    def add(self, a: int, b: int) -> int:
        return a + b + self._c


@pytest.fixture(name="mock_service_locator")
def create_mock_service_locator():
    """
    Create a test `ServiceLocator` implementation.

    The test ServiceLocator implementation will unload its config and cached instances
    once it is finished with.
    """

    @contextlib.contextmanager
    def _f(test_factory_map: FactoryMap) -> Generator[ServiceLocator, None, None]:
        importlib.reload(di_service_locator.features)
        # configure the Features with the provided factory map
        features = ServiceLocator.configure(test_factory_map)
        try:
            yield features
        finally:
            # unload the Features to remove any caching and config
            importlib.reload(di_service_locator.features)

    # return a context manager wrapper for the test ServiceLocator implementation
    return _f


@pytest.fixture(
    name="namespace",
    params=[None, "namespace", "/namespace", "double/namespace"],
)
def _namespace(request):
    return request.param
