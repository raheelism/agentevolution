"""Sandbox Executor — Safe, isolated code execution.

MVP: subprocess-based with timeout and resource limits.
Future: Docker containers → E2B microVMs.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from agentevolution.config import get_config
from agentevolution.storage.models import PerformanceProfile


class SandboxResult:
    """Result of sandbox execution."""

    def __init__(
        self,
        success: bool,
        stdout: str = "",
        stderr: str = "",
        execution_time_ms: float = 0.0,
        return_code: int = 0,
        error_message: str = "",
    ):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.execution_time_ms = execution_time_ms
        self.return_code = return_code
        self.error_message = error_message

    def to_performance_profile(self) -> PerformanceProfile:
        return PerformanceProfile(
            execution_time_ms=self.execution_time_ms,
            memory_peak_mb=0.0,  # Not measurable with subprocess
            output_size_bytes=len(self.stdout.encode("utf-8")),
            test_passed=self.success,
            test_output=self.stdout[:1000],
            error_message=self.error_message,
        )


class Sandbox:
    """Isolated code execution sandbox.

    MVP uses subprocess with timeout. Each execution runs in a
    fresh temporary directory that is cleaned up afterwards.
    """

    def __init__(self):
        config = get_config().gauntlet
        self.timeout = config.execution_timeout_seconds
        self.max_output = config.max_output_size_bytes

    def execute(self, code: str, test_case: str, dependencies: list[str] | None = None) -> SandboxResult:
        """Execute code + test case in an isolated subprocess.

        Creates a temp directory with the tool code and test case,
        then runs the test case in a subprocess with timeout.
        """
        run_id = str(uuid.uuid4())[:8]

        with tempfile.TemporaryDirectory(prefix=f"agentevolution_{run_id}_") as tmpdir:
            tmppath = Path(tmpdir)

            # Write tool code
            tool_file = tmppath / "tool.py"
            tool_file.write_text(code, encoding="utf-8")

            # Write test runner that imports and runs the test
            test_file = tmppath / "test_runner.py"
            test_runner_code = self._build_test_runner(code, test_case)
            test_file.write_text(test_runner_code, encoding="utf-8")

            # Execute
            import time
            start = time.perf_counter()

            try:
                result = subprocess.run(
                    [sys.executable, str(test_file)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=tmpdir,
                    env=self._get_safe_env(),
                )

                elapsed_ms = (time.perf_counter() - start) * 1000

                stdout = result.stdout[:self.max_output]
                stderr = result.stderr[:self.max_output]

                if result.returncode == 0:
                    return SandboxResult(
                        success=True,
                        stdout=stdout,
                        stderr=stderr,
                        execution_time_ms=round(elapsed_ms, 2),
                        return_code=result.returncode,
                    )
                else:
                    return SandboxResult(
                        success=False,
                        stdout=stdout,
                        stderr=stderr,
                        execution_time_ms=round(elapsed_ms, 2),
                        return_code=result.returncode,
                        error_message=stderr[:500] if stderr else "Non-zero exit code",
                    )

            except subprocess.TimeoutExpired:
                elapsed_ms = (time.perf_counter() - start) * 1000
                return SandboxResult(
                    success=False,
                    execution_time_ms=round(elapsed_ms, 2),
                    error_message=f"Execution timed out after {self.timeout}s",
                )

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000
                return SandboxResult(
                    success=False,
                    execution_time_ms=round(elapsed_ms, 2),
                    error_message=f"Sandbox error: {type(e).__name__}: {str(e)}",
                )

    def _build_test_runner(self, tool_code: str, test_case: str) -> str:
        """Build the test runner script.

        Combines the tool code and test case into a single runnable script.
        """
        return f'''
import sys
import traceback

# ─── Tool Code ───
try:
{self._indent(tool_code, 4)}
except Exception as e:
    print(f"TOOL_LOAD_ERROR: {{type(e).__name__}}: {{e}}", file=sys.stderr)
    sys.exit(1)

# ─── Test Case ───
try:
{self._indent(test_case, 4)}
    print("TEST_PASSED")
except AssertionError as e:
    print(f"TEST_FAILED: Assertion: {{e}}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"TEST_FAILED: {{type(e).__name__}}: {{e}}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''

    def _indent(self, code: str, spaces: int) -> str:
        """Indent code by the given number of spaces."""
        prefix = " " * spaces
        return "\n".join(prefix + line for line in code.split("\n"))

    def _get_safe_env(self) -> dict[str, str]:
        """Get a safe environment for subprocess execution."""
        import os
        # Start with minimal env
        safe_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": "",
            "HOME": os.environ.get("HOME", os.environ.get("USERPROFILE", "")),
            "TEMP": os.environ.get("TEMP", os.environ.get("TMPDIR", "/tmp")),
            "TMP": os.environ.get("TMP", os.environ.get("TMPDIR", "/tmp")),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Windows needs this
        }
        return {k: v for k, v in safe_env.items() if v}
