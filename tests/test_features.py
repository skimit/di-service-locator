# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

import contextlib
import importlib
import os
from pathlib import Path

import pytest

import di_service_locator
import di_service_locator.features
from di_service_locator.config import DictionaryFactoryMap
from di_service_locator.definitions import FactoryDefinition
from di_service_locator.exceptions import FeatureNotFound
from di_service_locator.feature_defs.interfaces import BlobStorage
from tests.conftest import ITest

EXAMPLE_FEATURES = {
    "test": FactoryDefinition(
        fqn_impl_factory="tests.conftest.Test",
        fqn_interface="tests.conftest.ITest",
        args=[2],
        kwargs={},
    )
}


@pytest.fixture(name="mock_feature_json")
def _feature_json_definition(mock_service_locator):
    @contextlib.contextmanager
    def features_file_location(features_file: str):
        os.environ["FEATURES_CONFIG"] = features_file
        importlib.reload(di_service_locator.features)

        try:
            yield
        finally:
            del os.environ["FEATURES_CONFIG"]

    return features_file_location


def test_nonexistent_features_json(mock_feature_json):
    """Test non-existent features raise expected error"""
    with mock_feature_json("dummy.json"):
        with pytest.raises(FileNotFoundError):
            from di_service_locator.feature_defs.interfaces import BlobStorage
            from di_service_locator.features import ServiceLocator

            # Dummy service call
            ServiceLocator.service(BlobStorage)


def test_existent_features_json(mock_feature_json):
    """Test that features specified in JSON that do not exist raise expected error"""
    feature_json_path = str(Path(__file__).parent / "test_features.json")

    with mock_feature_json(feature_json_path):
        # Found the file but the feature is not in the factory map
        with pytest.raises(FeatureNotFound):
            from di_service_locator.features import ServiceLocator

            # Dummy service call
            ServiceLocator.service(BlobStorage)


def test_instance(mock_service_locator):
    """Test that we get the type of feature we expect"""
    with mock_service_locator(DictionaryFactoryMap({})) as TestServiceLocator:
        from di_service_locator.features import ServiceLocator

        assert isinstance(TestServiceLocator, ServiceLocator)


def test_example_feature(mock_service_locator):
    """Test that returned feature works"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        test = TestServiceLocator.service(ITest)
        assert test.add(3, 4) == 3 + 4 + 2


def test_mock_features_not_persisted(mock_service_locator):
    """Test mock features not persisted"""
    with mock_service_locator(DictionaryFactoryMap({})) as TestServiceLocator:
        with pytest.raises(FeatureNotFound):
            _ = TestServiceLocator.service(ITest)


def test_get_by_name(mock_service_locator):
    """Test that getting features by name works as expected"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        test = TestServiceLocator.service_by_name("test", ITest)
        assert test.add(3, 4) == 3 + 4 + 2


def test_get_by_non_existent_name(mock_service_locator):
    """Test that getting non-existent features by name raises expected error"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        with pytest.raises(FeatureNotFound):
            _ = TestServiceLocator.service_by_name("non-existent", ITest)


# TODO: test different threads + event loop
