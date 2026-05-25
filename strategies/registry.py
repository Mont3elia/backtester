import importlib
import inspect
import pkgutil
import sys
from pathlib import Path

try:
    from .base_strategy import BaseStrategy
except ImportError:
    from strategies.base_strategy import BaseStrategy

_registry: dict[str, type] = {}


def discover():
    """
    Scan all modules inside the strategies package (including sub-packages)
    and register every class that:
      - inherits from BaseStrategy
      - is not BaseStrategy itself
      - has a `name` attribute different from "Base"
    """
    _registry.clear()

    strategies_dir = Path(__file__).parent
    package_name = _package_name(strategies_dir)

    _scan_package(strategies_dir, package_name)


def _package_name(strategies_dir: Path) -> str:
    """
    Resolve the importable package name for the strategies directory.
    Works both when strategies/ is imported as a package and when the
    project root is inserted directly into sys.path.
    """
    if "strategies" in sys.modules:
        return sys.modules["strategies"].__name__
    return "strategies"


def _scan_package(package_dir: Path, package_dotname: str):
    for finder, module_name, is_pkg in pkgutil.walk_packages(
        path=[str(package_dir)],
        prefix=package_dotname + ".",
        onerror=lambda name: None,
    ):
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                obj is not BaseStrategy
                and issubclass(obj, BaseStrategy)
                and getattr(obj, "name", "Base") != "Base"
                and obj.__module__ == module.__name__
            ):
                _registry[obj.name] = obj


def get_all() -> dict[str, type]:
    """Return a dict {strategy_name: strategy_class} of all registered strategies."""
    return dict(_registry)


def get(name: str) -> type:
    """Return the strategy class for the given name."""
    if name not in _registry:
        raise KeyError(f"Strategy '{name}' not found. Available: {list(_registry.keys())}")
    return _registry[name]
