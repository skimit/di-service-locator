# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Contains concrete instrumentation implementations."""
import functools
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
from typing import Callable, Dict, Generator, Optional, TypeVar

from typing_extensions import ParamSpec

from di_service_locator import logger
from di_service_locator.feature_defs.interfaces import Instrumentation
from di_service_locator.features import ServiceLocator


def _name_extractor(func: Callable, name: Optional[str]) -> str:
    return name if name else f"{func.__module__}.{func.__name__}"


P = ParamSpec("P")
R = TypeVar("R")


# Note: this typing is still less than ideal, but hopefully it is good enough for now
def instrument_timer(
    func: Optional[Callable[P, R]] = None, *, name: Optional[str] = None
) -> Callable[P, R]:
    """
    Decorator to add execution timing instrumentation to a function or method.

    It is recommended to instrument potentially expensive methods on service implementations.
    Instrumenting all of our service methods, such as those that access cloud services, will
    give us insights into overall product performance.

    Example:
        This decorator can be used on any method to provide instrumentation reports::

        @instrument_timer
        def method_that_wants_instrumenting(*args, **kwargs) -> Any:
            ...


        An optional name can be specified when decorating a method and this will be used
        as the report id instead of the fully qualified name of the function::

        @instrument_timer(name="my.unique.name.for.reporting")
        def method_that_wants_instrumenting(*args, **kwargs) -> Any:
            ...

    :param name: Optional override for report name
    """

    if func is None:
        return functools.partial(instrument_timer, name=name)  # type: ignore

    name_to_use = _name_extractor(func, name)
    instrumentation = ServiceLocator.service(Instrumentation)
    instrumentation.register_report(name_to_use)

    @functools.wraps(func)
    def _w(*args: P.args, **kwargs: P.kwargs):
        with timed_instrumentation(name_to_use):
            return func(*args, **kwargs)

    return _w


@contextmanager
def timed_instrumentation(name: str) -> Generator[None, None, None]:
    """
    Context manager to add execution timing instrumentation to a block of code.

    :param name: Report name
    :type name: str
    """
    instrumentation = ServiceLocator.service(Instrumentation)
    start_time = datetime.today()
    yield
    end_time = datetime.today()
    instrumentation.report(
        report_id=name,
        start_time=start_time,
        end_time=end_time,
    )


def instrument_counter(
    func: Optional[Callable[P, R]] = None, *, name: Optional[str] = None
) -> Callable[P, R]:
    """
    Decorator to add execution count instrumentation to a function or method.

    It is recommended to instrument potentially expensive methods on service implementations.
    Instrumenting all of our service methods, such as those that access cloud services, will
    give us insights into how used functionality is.

    Example:
        This decorator can be used on any method to provide instrumentation reports::

        @instrument_counter
        def method_that_wants_instrumenting(*args, **kwargs) -> Any:
            ...


        An optional name can be specified when decorating a method and this will be used
        as the gauge id instead of the fully qualified name of the function::

        @instrument_counter(name="my.unique.name.for.reporting")
        def method_that_wants_instrumenting(*args, **kwargs) -> Any:
            ...

    :param name: Optional override for report name
    """

    if func is None:
        return functools.partial(instrument_counter, name=name)  # type: ignore

    name_to_use = _name_extractor(func, name)
    instrumentation = ServiceLocator.service(Instrumentation)
    instrumentation.register_counter(name_to_use)

    @functools.wraps(func)
    def _w(*args: P.args, **kwargs: P.kwargs):
        with counted_instrumentation(name_to_use):
            return func(*args, **kwargs)

    return _w


@contextmanager
def counted_instrumentation(name: str) -> Generator[None, None, None]:
    """
    Context manager to add execution count instrumentation to a block of code.

    :param name: Report name
    :type name: str
    """
    instrumentation = ServiceLocator.service(Instrumentation)
    yield
    instrumentation.increase_counter(counter_id=name, increase=1)


class BasicLogInstrument(Instrumentation):
    """
    A basic log instrument.

    Uses a logger to log execution times, counters and gauges.
    Logs execution times, counter increases and gauge updates as they occur.
    """

    def __init__(self):
        self._gauges: Dict[str, float] = defaultdict(float)
        self._counters: Dict[str, int] = defaultdict(int)

    def register_report(self, report_id: str) -> None:
        """We don't need to do anything in this basic implementation"""
        pass

    def register_gauge(self, gauge_id: str) -> None:
        """We don't need to do anything in this basic implementation"""
        pass

    def register_counter(self, counter_id: str) -> None:
        """We don't need to do anything in this basic implementation"""
        pass

    def report(self, report_id: str, start_time: datetime, end_time: datetime) -> None:
        """Basic report"""
        if start_time > end_time:
            logger.warning("Instrumentation: start time is after end time")
        logger.info(
            "Instrumentation: [{report_id}] took {time}s",
            report_id=report_id,
            time=(end_time - start_time).total_seconds(),
        )

    def update_gauge(self, gauge_id: str, delta: float) -> None:
        """Basic update"""
        self._gauges[gauge_id] += delta
        logger.info(
            "Instrumentation: {gauge_id} updated to {gauge_value}",
            gauge_id=gauge_id,
            gauge_value=self._gauges[gauge_id],
        )

    def increase_counter(self, counter_id: str, increase: int) -> None:
        """Basic counter increase"""
        if increase < 0:
            raise ValueError(f"Increase must be a positive integer, not {increase}")

        self._counters[counter_id] += increase
        logger.info(
            "Instrumentation: {counter_id} increased to {counter_value}",
            counter_id=counter_id,
            counter_value=self._counters[counter_id],
        )
