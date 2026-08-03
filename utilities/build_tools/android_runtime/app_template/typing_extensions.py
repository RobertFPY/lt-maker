"""Minimal Android runtime compatibility surface used by Lex Talionis.

The engine only imports Protocol and override from typing_extensions. Keeping
this tiny pure-Python shim in the APK avoids invoking p4a's cross-build pip for
a dependency whose runtime behavior is otherwise provided by Python 3.11.
"""

from typing import Protocol

try:
    from typing import override
except ImportError:
    def override(method):
        return method


__all__ = ["Protocol", "override"]

