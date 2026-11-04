import sys
from pathlib import Path
from typing import Any

from sybil import Sybil
from sybil.evaluators.doctest import NUMBER
from sybil.parsers.myst import ClearNamespaceParser as MarkdownClearNamespaceParser
from sybil.parsers.myst import DocTestDirectiveParser as MarkdownDocTestParser
from sybil.parsers.myst import PythonCodeBlockParser as MarkdownPythonCodeBlockParser
from sybil.parsers.myst import SkipParser as MarkdownSkipParser
from sybil.parsers.rest import ClearNamespaceParser as ReSTClearNamespaceParser
from sybil.parsers.rest import DocTestParser as ReSTDocTestParser
from sybil.parsers.rest import PythonCodeBlockParser as ReSTPythonCodeBlockParser
from sybil.parsers.rest import SkipParser as ReSTSkipParser

markdown_examples = Sybil(
    parsers=[
        MarkdownDocTestParser(NUMBER),
        MarkdownPythonCodeBlockParser(doctest_optionflags=NUMBER),
        MarkdownSkipParser(),
        MarkdownClearNamespaceParser(),
    ],
    patterns=["*.md"],
)

rest_examples = Sybil(
    parsers=[
        ReSTDocTestParser(NUMBER),
        ReSTPythonCodeBlockParser(),
        ReSTSkipParser(),
        ReSTClearNamespaceParser(),
    ],
    patterns=["*.py", "*.rst"],
)

pytest_collect_file = (markdown_examples + rest_examples).pytest()


def _has_option(args: list[str], option: str) -> bool:
    return any(arg == option or arg.startswith(f"{option}=") for arg in args)


def _project_root() -> Path:
    return next(
        path for path in (Path.cwd(), *Path.cwd().parents) if (path / "pyproject.toml").is_file()
    )


def _package_path() -> Path | None:
    source_path = _project_root() / "src"
    if not source_path.is_dir():
        return None
    return next(
        path
        for path in source_path.iterdir()
        if path.is_dir() and not path.name.endswith(".egg-info")
    )


def _install_defaults(config: Any) -> Path | None:
    package_path = _package_path()
    if package_path is None:
        return None
    source_path = package_path.parent
    if str(source_path) not in sys.path:
        sys.path.insert(0, str(source_path))

    option = config.option
    option.verbose = max(getattr(option, "verbose", 0), 1)
    if not getattr(option, "pythonwarnings", None):
        option.pythonwarnings = ["once"]
    config.pluginmanager.set_blocked("doctest")
    if getattr(option, "no_cov", False) or config.pluginmanager.hasplugin("_cov"):
        return package_path
    option.cov_source = getattr(option, "cov_source", None) or [package_path.name]
    option.cov_config = getattr(option, "cov_config", None) or str(
        Path(__file__).with_name("coverage.ini")
    )
    option.cov_report = getattr(option, "cov_report", None) or {"term": None, "xml": None}
    try:
        from pytest_cov.plugin import CovPlugin  # noqa: PLC0415
    except ImportError:
        return package_path
    config.pluginmanager.register(CovPlugin(option, config.pluginmanager), "_cov")
    return package_path


def pytest_load_initial_conftests(early_config: Any, parser: Any, args: list[str]) -> None:
    """Install shared pytest defaults before initial conftest loading."""
    del parser
    package_path = _install_defaults(early_config)
    if package_path is None:
        return
    defaults = {
        "-v": ["-v"],
        "-Wonce": ["-Wonce"],
        "-p": ["-p", "no:doctest"],
        "--cov": [f"--cov={package_path.name}"],
        "--cov-config": [f"--cov-config={Path(__file__).with_name('coverage.ini')}"],
        "--cov-report": ["--cov-report=term", "--cov-report=xml"],
    }
    for option, values in defaults.items():
        if not _has_option(args, option):
            args.extend(values)
