# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

from datetime import datetime
from typing import Dict, Mapping, Tuple, cast
from unittest.mock import Mock, patch

import pytest

from di_service_locator.config import DictionaryFactoryMap
from di_service_locator.definitions import FactoryDefinition
from di_service_locator.feature_defs.instrumentation import (
    BasicLogInstrument,
    instrument_counter,
    instrument_timer,
)
from di_service_locator.feature_defs.interfaces import Instrumentation


class StateInstrument(BasicLogInstrument):
    """
    Test instrument.

    Keeps a dict of reports for later inspection.
    """

    def __init__(self) -> None:
        super().__init__()
        self.state: Dict[str, Tuple[datetime, datetime]] = {}

    def report(self, report_id: str, start_time: datetime, end_time: datetime) -> None:
        self.state[report_id] = (start_time, end_time)

    @property
    def gauge_state(self) -> Mapping[str, float]:
        """Just give back the current gauge state"""
        return self._gauges

    @property
    def counter_state(self) -> Mapping[str, int]:
        """Just give back the current counter state"""
        return self._counters


EXAMPLE_FEATURES = {
    "test": FactoryDefinition(
        fqn_impl_factory="tests.feature_defs.test_instrumentation.StateInstrument",
        fqn_interface="di_service_locator.feature_defs.interfaces.Instrumentation",
        args=[],
        kwargs={},
    )
}
# Test instrumentation config


def test_instrument_timer_decorator(mock_service_locator):
    """Test instrument timer decorator without name"""
    with patch("di_service_locator.feature_defs.instrumentation.datetime") as mock_datetime:
        # mock up some start and end times and patch them onto datetime.today
        start_time = datetime(2021, 1, 1, 11, 0, 0)
        end_time = datetime(2021, 1, 1, 11, 5, 0)

        mock_datetime.today = Mock(side_effect=[start_time, end_time])

        with mock_service_locator(
            DictionaryFactoryMap(EXAMPLE_FEATURES)
        ) as TestServiceLocator:
            # have to keep test function in here or it configures the Features context
            # before we get a chance to mock it!
            @instrument_timer
            def a_function(a: int, b: int):
                return a + b

            # obtain the actual instrumentation implementation so we can inspect it
            test_instrument = cast(
                StateInstrument, TestServiceLocator.service(Instrumentation)
            )

            assert not test_instrument.state  # initial state should be empty
            # call the function that should be decorated for timing instrumentation
            ret = a_function(3, 4)
            assert (
                "tests.feature_defs.test_instrumentation.a_function" in test_instrument.state
            )  # ensure our func was instrumented
            assert (
                ret == 3 + 4
            )  # assert that our function took parameters and we got the result
            assert test_instrument.state[
                "tests.feature_defs.test_instrumentation.a_function"
            ] == (
                start_time,
                end_time,
            )  # assert start and end times


def test_instrument_timer_decorator_with_name(mock_service_locator):
    """Test instrument timer decorator with a given name"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        # have to keep test function in here or it configures the Features context
        # before we get a chance to mock it!
        @instrument_timer(name="my_test_name")
        def a_function(a: int, b: int):
            return a + b

        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))

        assert not test_instrument.state  # initial state should be empty
        # call the function that should be decorated for timing instrumentation
        ret = a_function(3, 4)
        assert "my_test_name" in test_instrument.state  # ensure our func was instrumented
        assert ret == 3 + 4  # assert that our function took parameters and we got the result


def test_instrument_counter_decorator(mock_service_locator):
    """Test instrument counter decorator without name"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        # have to keep test function in here or it configures the Features context
        # before we get a chance to mock it!
        @instrument_counter
        def a_function(a: int, b: int):
            return a + b

        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))

        assert not test_instrument.counter_state  # initial state should be empty
        # call the function that should be decorated for counting instrumentation
        ret = a_function(3, 4)
        assert (
            "tests.feature_defs.test_instrumentation.a_function"
            in test_instrument.counter_state
        )  # ensure our func was instrumented
        assert ret == 7  # assert that our function took parameters and we got the result
        assert (
            test_instrument.counter_state["tests.feature_defs.test_instrumentation.a_function"]
            == 1
        )  # assert count

        # call a few more times
        for _ in range(0, 5):
            a_function(3, 4)
        assert (
            test_instrument.counter_state["tests.feature_defs.test_instrumentation.a_function"]
            == 6
        )  # assert count


def test_instrument_counter_decorator_with_name(mock_service_locator):
    """Test instrument counter decorator with a given name"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        # have to keep test function in here or it configures the Features context
        # before we get a chance to mock it!
        @instrument_counter(name="my_test_name")
        def a_function(a: int, b: int):
            return a + b

        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))

        assert not test_instrument.counter_state  # initial state should be empty
        # call the function that should be decorated for timing instrumentation
        ret = a_function(3, 4)
        assert (
            "my_test_name" in test_instrument.counter_state
        )  # ensure our func was instrumented
        assert ret == 7  # assert that our function took parameters and we got the result
        assert test_instrument.counter_state["my_test_name"] == 1  # assert count


def test_nested_decorators(mock_service_locator):
    """Test nesting of decorators"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        # have to keep test function in here or it configures the Features context
        # before we get a chance to mock it!
        @instrument_timer
        @instrument_counter
        def a_function(a: int, b: int):
            return a + b

        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))

        ret = a_function(3, 4)
        assert ret == 7
        assert "tests.feature_defs.test_instrumentation.a_function" in test_instrument.state
        assert (
            test_instrument.counter_state["tests.feature_defs.test_instrumentation.a_function"]
            == 1
        )

        @instrument_counter
        @instrument_timer
        def b_function(a: int, b: int):
            return a + b

        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))

        ret = b_function(3, 4)
        assert ret == 7
        assert "tests.feature_defs.test_instrumentation.b_function" in test_instrument.state
        assert (
            test_instrument.counter_state["tests.feature_defs.test_instrumentation.b_function"]
            == 1
        )


def test_nested_decorators_with_name(mock_service_locator):
    """Test nesting of decorators with given names"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        # have to keep test function in here or it configures the Features context
        # before we get a chance to mock it!
        @instrument_timer(name="my_test_timer_1")
        @instrument_counter(name="my_test_counter_1")
        def a_function(a: int, b: int):
            return a + b

        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))

        ret = a_function(3, 4)
        assert ret == 7
        assert "my_test_timer_1" in test_instrument.state
        assert test_instrument.counter_state["my_test_counter_1"] == 1

        @instrument_counter(name="my_test_counter_2")
        @instrument_timer(name="my_test_timer_2")
        def b_function(a: int, b: int):
            return a + b

        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))

        ret = b_function(3, 4)
        assert ret == 7
        assert "my_test_timer_2" in test_instrument.state
        assert test_instrument.counter_state["my_test_counter_2"] == 1


def test_nested_decorators_with_one_name(mock_service_locator):
    """Test nesting decorators with/without names"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        # have to keep test function in here or it configures the Features context
        # before we get a chance to mock it!
        @instrument_timer()
        @instrument_counter(name="my_test_counter_1")
        def a_function(a: int, b: int):
            return a + b

        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))

        ret = a_function(3, 4)
        assert ret == 7
        assert "tests.feature_defs.test_instrumentation.a_function" in test_instrument.state
        assert test_instrument.counter_state["my_test_counter_1"] == 1

        @instrument_timer(name="my_test_timer_2")
        @instrument_counter()
        def b_function(a: int, b: int):
            return a + b

        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))

        ret = b_function(3, 4)
        assert ret == 7
        assert "my_test_timer_2" in test_instrument.state
        assert (
            test_instrument.counter_state["tests.feature_defs.test_instrumentation.b_function"]
            == 1
        )


def test_instrument_report(mock_service_locator):
    """Test instrument reporting"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))
        assert not test_instrument.state  # initial state should be empty

        time_1 = datetime.today()
        time_2 = datetime.today()

        TestServiceLocator.service(Instrumentation).report("test_report", time_1, time_2)

        assert "test_report" in test_instrument.state  # ensure our report was instrumented
        assert test_instrument.state["test_report"] == (time_1, time_2)


def test_instrument_update_gauge(mock_service_locator):
    """Test instrument update guage"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))
        assert not test_instrument.gauge_state  # initial state should be empty

        TestServiceLocator.service(Instrumentation).update_gauge("test_report", 4.0)

        assert (
            "test_report" in test_instrument.gauge_state
        )  # ensure our report was instrumented
        assert test_instrument.gauge_state["test_report"] == 4.0

        # ensure we can go both up and down
        TestServiceLocator.service(Instrumentation).update_gauge("test_report", -2.0)
        assert test_instrument.gauge_state["test_report"] == 2.0
        TestServiceLocator.service(Instrumentation).update_gauge("test_report", 1.5)
        assert test_instrument.gauge_state["test_report"] == 3.5


def test_instrument_increase_counter(mock_service_locator):
    """Test instrument counter"""
    with mock_service_locator(DictionaryFactoryMap(EXAMPLE_FEATURES)) as TestServiceLocator:
        # obtain the actual instrumentation implementation so we can inspect it
        test_instrument = cast(StateInstrument, TestServiceLocator.service(Instrumentation))
        assert not test_instrument.counter_state  # initial state should be empty

        TestServiceLocator.service(Instrumentation).increase_counter("test_report", 4)

        assert (
            "test_report" in test_instrument.counter_state
        )  # ensure our report was instrumented
        assert test_instrument.counter_state["test_report"] == 4

        # ensure we can only go up
        TestServiceLocator.service(Instrumentation).increase_counter("test_report", 2)
        assert test_instrument.counter_state["test_report"] == 6
        with pytest.raises(ValueError, match="positive"):
            TestServiceLocator.service(Instrumentation).increase_counter("test_report", -3)
            assert test_instrument.counter_state["test_report"] == 6
