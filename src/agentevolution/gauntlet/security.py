"""Security Scanner — AST-based static analysis of submitted code.

Checks for dangerous patterns before code enters the sandbox.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any

from agentevolution.config import get_config
from agentevolution.storage.models import SecurityScanResult


# Dangerous built-in functions
DANGEROUS_BUILTINS = {
    "eval", "exec", "compile", "__import__",
    "globals", "locals", "getattr", "setattr", "delattr",
    "breakpoint", "exit", "quit",
}

# Dangerous modules
DANGEROUS_MODULES = {
    "subprocess", "shutil", "ctypes", "multiprocessing",
    "signal", "resource", "pty", "termios", "socket",
    "http.server", "xmlrpc", "pickle", "shelve",
    "webbrowser", "antigravity",
}

# Dangerous attribute access patterns
DANGEROUS_ATTRS = {
    "__subclasses__", "__bases__", "__mro__",
    "__globals__", "__code__", "__builtins__",
    "system", "popen", "rmtree", "unlink",
}


@dataclass
class SecurityIssue:
    """A security issue found during scanning."""
    severity: str  # "critical", "warning", "info"
    message: str
    line: int = 0
    column: int = 0


@dataclass
class SecurityReport:
    """Result of a security scan."""
    result: SecurityScanResult
    issues: list[SecurityIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.result == SecurityScanResult.PASS

    def summary(self) -> str:
        if not self.issues:
            return "No security issues found."
        lines = [f"Found {len(self.issues)} issue(s):"]
        for issue in self.issues:
            lines.append(f"  [{issue.severity.upper()}] Line {issue.line}: {issue.message}")
        return "\n".join(lines)


class SecurityScanner:
    """AST-based security scanner for submitted code."""

    def __init__(self) -> None:
        config = get_config().forge
        self.blocked_imports = set(config.blocked_imports) | DANGEROUS_MODULES

    def scan(self, code: str) -> SecurityReport:
        """Scan code for security issues.

        Returns a SecurityReport with PASS, WARNING, or FAIL result.
        """
        issues: list[SecurityIssue] = []

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return SecurityReport(
                result=SecurityScanResult.FAIL,
                issues=[SecurityIssue("critical", f"Syntax error: {e}", e.lineno or 0)],
            )

        # Walk the AST
        for node in ast.walk(tree):
            issues.extend(self._check_node(node))

        # Determine result
        has_critical = any(i.severity == "critical" for i in issues)
        has_warning = any(i.severity == "warning" for i in issues)

        if has_critical:
            result = SecurityScanResult.FAIL
        elif has_warning:
            result = SecurityScanResult.WARNING
        else:
            result = SecurityScanResult.PASS

        return SecurityReport(result=result, issues=issues)

    def _check_node(self, node: ast.AST) -> list[SecurityIssue]:
        """Check a single AST node for security issues."""
        issues: list[SecurityIssue] = []
        line = getattr(node, "lineno", 0)

        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in self.blocked_imports or alias.name.split(".")[0] in self.blocked_imports:
                    issues.append(SecurityIssue(
                        "critical",
                        f"Blocked import: '{alias.name}'",
                        line,
                    ))

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in self.blocked_imports or module.split(".")[0] in self.blocked_imports:
                issues.append(SecurityIssue(
                    "critical",
                    f"Blocked import from: '{module}'",
                    line,
                ))

        # Check dangerous function calls
        elif isinstance(node, ast.Call):
            func_name = self._get_call_name(node)
            if func_name in DANGEROUS_BUILTINS:
                issues.append(SecurityIssue(
                    "critical",
                    f"Dangerous built-in call: '{func_name}()'",
                    line,
                ))

            # Check os.system, os.popen, etc.
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in DANGEROUS_ATTRS:
                    issues.append(SecurityIssue(
                        "critical",
                        f"Dangerous attribute access: '.{node.func.attr}'",
                        line,
                    ))

        # Check dangerous attribute access
        elif isinstance(node, ast.Attribute):
            if node.attr in DANGEROUS_ATTRS:
                issues.append(SecurityIssue(
                    "warning",
                    f"Suspicious attribute access: '.{node.attr}'",
                    line,
                ))

        # Check file operations
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "open":
                # Check for write mode
                if len(node.args) >= 2:
                    mode_arg = node.args[1]
                    if isinstance(mode_arg, ast.Constant) and "w" in str(mode_arg.value):
                        issues.append(SecurityIssue(
                            "warning",
                            "File write operation detected",
                            line,
                        ))

        return issues

    def _get_call_name(self, node: ast.Call) -> str:
        """Extract the function name from a Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""
