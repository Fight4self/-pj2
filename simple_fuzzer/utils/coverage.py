import hashlib
import importlib
from typing import Any, Optional, Callable, List, Type, Set, Tuple
from types import FrameType, TracebackType

import sys
import inspect

Location = Tuple[str, int]


def path_id_from_trace(trace: List[Location]) -> str:
    """Derive a stable path identifier from an execution trace.

    Uses consecutive control-flow edges (prev_line, curr_line), which is the
    same intuition as edge-based coverage in AFL-style fuzzers: two inputs that
    traverse the same edges share one path bucket even if their full traces
    differ in length due to early termination.
    """
    if not trace:
        return hashlib.md5(b"<empty>").hexdigest()

    edges = tuple(zip(trace, trace[1:]))
    return hashlib.md5(repr(edges).encode()).hexdigest()


def path_id_from_coverage(coverage: Set[Location]) -> str:
    """Fallback path identifier when only coverage set is available."""
    if not coverage:
        return hashlib.md5(b"<empty>").hexdigest()
    return hashlib.md5(repr(tuple(sorted(coverage))).encode()).hexdigest()


def import_all_functions_from_module(module_name):
    module = importlib.import_module(module_name)
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        globals()[name] = obj


import_all_functions_from_module("samples.samples")


class Coverage:

    def __init__(self) -> None:
        """Constructor"""
        self._trace: List[Location] = []

    # Trace function
    def traceit(self, frame: FrameType, event: str, arg: Any) -> Optional[Callable]:
        """Tracing function. To be overloaded in subclasses."""
        if self.original_trace_function is not None:
            self.original_trace_function(frame, event, arg)

        if event == "line":
            function_name = frame.f_code.co_name
            lineno = frame.f_lineno
            if function_name != '__exit__':  # avoid tracing ourselves:
                self._trace.append((function_name, lineno))

        return self.traceit

    def __enter__(self) -> Any:
        """Start of `with` block. Turn on tracing."""
        self.original_trace_function = sys.gettrace()
        sys.settrace(self.traceit)
        return self

    def __exit__(self, exc_type: Type, exc_value: BaseException,
                 tb: TracebackType) -> Optional[bool]:
        """End of `with` block. Turn off tracing."""
        sys.settrace(self.original_trace_function)
        return None  # default: pass all exceptions

    def trace(self) -> List[Location]:
        """The list of executed lines, as (function_name, line_number) pairs"""
        return self._trace

    def coverage(self) -> Set[Location]:
        """The set of executed lines, as (function_name, line_number) pairs"""
        return set(self.trace())

    def function_names(self) -> Set[str]:
        """The set of function names seen"""
        return set(function_name for (function_name, line_number) in self.coverage())

    def __repr__(self) -> str:
        """Return a string representation of this object.
           Show covered (and uncovered) program code"""
        t = ""
        for function_name in self.function_names():
            # Similar code as in the example above
            try:
                fun = eval(function_name)
            except Exception as exc:
                t += f"Skipping {function_name}: {exc}"
                continue

            source_lines, start_line_number = inspect.getsourcelines(fun)
            for lineno in range(start_line_number, start_line_number + len(source_lines)):
                if (function_name, lineno) not in self.trace():
                    t += "# "
                else:
                    t += "  "
                t += "%2d  " % lineno
                t += source_lines[lineno - start_line_number]

        return t


def population_coverage(population: List[str], function: Callable) \
        -> Tuple[Set[Location], List[int]]:
    cumulative_coverage: List[int] = []
    all_coverage: Set[Location] = set()

    for s in population:
        with Coverage() as cov:
            try:
                function(s)
            except:
                pass
        all_coverage |= cov.coverage()
        cumulative_coverage.append(len(all_coverage))

    return all_coverage, cumulative_coverage
