"""Performance Profiler — Measure execution time and memory usage."""

from __future__ import annotations

import time
import tracemalloc

from agentevolution.storage.models import PerformanceProfile


class Profiler:
    """Profiles code execution for performance metrics."""

    def __init__(self, max_memory_mb: int = 256):
        self.max_memory_mb = max_memory_mb

    def profile_execution(
        self,
        func: callable,
        *args,
        **kwargs,
    ) -> tuple[any, PerformanceProfile]:
        """Profile a function execution.

        Returns (result, PerformanceProfile).
        """
        tracemalloc.start()
        start_time = time.perf_counter()

        result = None
        error_message = ""
        test_passed = False

        try:
            result = func(*args, **kwargs)
            test_passed = True
        except Exception as e:
            error_message = f"{type(e).__name__}: {str(e)}"

        end_time = time.perf_counter()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        execution_time_ms = (end_time - start_time) * 1000
        memory_peak_mb = peak / (1024 * 1024)

        output_str = str(result) if result is not None else ""

        profile = PerformanceProfile(
            execution_time_ms=round(execution_time_ms, 2),
            memory_peak_mb=round(memory_peak_mb, 2),
            output_size_bytes=len(output_str.encode("utf-8")),
            test_passed=test_passed,
            test_output=output_str[:1000],  # Truncate output
            error_message=error_message,
        )

        return result, profile
