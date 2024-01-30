# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Features injector and service locator module."""
import os
import threading
from typing import Any, Optional, Type, TypeVar

from di_service_locator import logger
from di_service_locator.config import factory_map_from_json_file
from di_service_locator.definitions import FactoryDefinition, FactoryMap
from di_service_locator.exceptions import InvalidReturnType
from di_service_locator.files import CURRENT_OR_HOME, FileLocator
from di_service_locator.instantiator import instantiate, load_class

FeatureT = TypeVar("FeatureT")
# type variable for generics casting when retrieving services

# Filename for features config
FEATURES_CONFIG = (
    str(os.environ["FEATURES_CONFIG"]) if "FEATURES_CONFIG" in os.environ else "features.json"
)


class ServiceLocator:
    """
    Features service locatior class with threadlocal cache of services.

    This class is a singleton with a lazy, thread local cache of instantiated services.
    This means that config will only be read once and services only instantiated once per
    thread, hopefully making calls to ServiceLocator as efficient as possible.
    """

    _instance: Optional["ServiceLocator"] = None
    # Singleton instance
    _cache = None
    # thread local cache
    _factories: FactoryMap
    # factory map

    def __new__(cls, factories: FactoryMap) -> "ServiceLocator":
        if cls._instance is None:
            cls._instance = super(ServiceLocator, cls).__new__(cls)
            cls._instance._cache = threading.local()
            # thread local cache for lazy caching of instantiated services, per thread
            cls._instance._factories = factories
        return cls._instance

    @staticmethod
    def __instance() -> "ServiceLocator":
        """Singleton factory method."""
        if ServiceLocator._instance is None:
            logger.info("Creating ServiceLocator instance")
            ServiceLocator._instance = ServiceLocator(
                factory_map_from_json_file(FileLocator.find(CURRENT_OR_HOME, FEATURES_CONFIG))
            )
        return ServiceLocator._instance

    @staticmethod
    def configure(factory_map: FactoryMap) -> "ServiceLocator":
        """
        Manual configure method.

        Must be called before any other ServiceLocator methods.
        This is the way to configure the services in code.  Note that if services are to be
        used in a multi-process environment then it is the callers responsibility to ensure
        that this method is called when a new process is forked.  It is advisable to allow
        the ServiceLocator to use config in such a situation as then the injection context
        will configure itself, as required, across multiple threads and/or processes.

        :param factory_map: the factory map to use
        :returns: ServiceLocator instance
        """
        if ServiceLocator._instance is not None:
            logger.warning("ServiceLocator already configured.  Reconfiguration occurring.")
        ServiceLocator._instance = ServiceLocator(factory_map)
        return ServiceLocator._instance

    @staticmethod
    def _instantiate(factory_definition: FactoryDefinition) -> Any:
        """Dynamically instantiate a class from its factory definition."""
        logger.info(
            "Instantiating service with factory {factory}",
            factory=factory_definition.fqn_impl_factory,
        )
        # programmatically instantiate class from factory details
        clz = load_class(factory_definition.fqn_impl_factory)
        return instantiate(clz, *factory_definition.args, **factory_definition.kwargs)

    def get_instance_by_type(self, expected_type: Type[FeatureT]) -> FeatureT:
        """
        Dynamically instantiate a service by a type that it implements.

        :param expected_type: the type of service to instantiate
        :returns: thread specific instance of the service
        """
        type_name = f"{expected_type.__module__}.{expected_type.__name__}"
        entry = getattr(self._cache, type_name, None)
        if not entry:
            factory_def, name = self._factories.get_by_type(type_name)
            entry = self._instantiate(factory_def)
            setattr(self._cache, name, entry)
            setattr(self._cache, factory_def.fqn_interface, entry)

        if not isinstance(entry, expected_type):
            raise InvalidReturnType(
                f"Object type doesn't match the expected type {expected_type}"
            )
        return entry

    def get_instance_by_name(self, name: str, expected_type: Type[FeatureT]) -> FeatureT:
        """
        Instantiate a feature by name.

        :param name: the feature name
        :type name: str
        :param expected_type: the expected type/interface implementation of the feature
        :type expected_type: Type[FeatureType]
        :return: the instantiated feature
        :rtype: FeatureType
        """
        entry = getattr(self._cache, name, None)
        if not entry:
            factory_def = self._factories.get_by_name(name)
            entry = self._instantiate(factory_def)
            setattr(self._cache, name, entry)
            if not getattr(self._cache, factory_def.fqn_interface, None):
                setattr(self._cache, factory_def.fqn_interface, entry)

        if not isinstance(entry, expected_type):
            raise InvalidReturnType(
                f"Object type doesn't match the expected type {expected_type}"
            )
        return entry

    @staticmethod
    def service(expected_type: Type[FeatureT]) -> FeatureT:
        """
        Static method for retrieving services by type.

        :param expected_type: the type of service to retrieve
        :returns: thread specific instance of the service
        """
        self = ServiceLocator.__instance()
        return self.get_instance_by_type(expected_type)

    @staticmethod
    def service_by_name(name: str, expected_type: Type[FeatureT]) -> FeatureT:
        """
        Static method for retrieving services by name.

        :param expected_type: the type of service to retrieve
        :returns: thread specific instance of the service
        """
        self = ServiceLocator.__instance()
        return self.get_instance_by_name(name, expected_type)
