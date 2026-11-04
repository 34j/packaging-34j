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


def _project_paths() -> tuple[Path, Path]:
    project_root = _project_root()
    source_path = project_root / "src"
    package_path = next(
        path
        for path in source_path.iterdir()
        if path.is_dir() and not path.name.endswith(".egg-info")
    )
    return source_path, package_path


def _install_defaults(config: Any) -> None:
    source_path, package_path = _project_paths()
    if str(source_path) not in sys.path:
        sys.path.insert(0, str(source_path))

    option = config.option
    option.verbose = max(getattr(option, "verbose", 0), 1)
    if not getattr(option, "pythonwarnings", None):
        option.pythonwarnings = ["once"]
    config.pluginmanager.set_blocked("doctest")

    if getattr(option, "no_cov", False) or config.pluginmanager.hasplugin("_cov"):
        return

    option.cov_source = getattr(option, "cov_source", None) or [package_path.name]
    option.cov_config = getattr(option, "cov_config", None) or str(
        Path(__file__).with_name("coverage.ini")
    )
    option.cov_report = getattr(option, "cov_report", None) or {"term": None, "xml": None}

    try:
        from pytest_cov.plugin import CovPlugin  # noqa: PLC0415
    except ImportError:
        return
    config.pluginmanager.register(CovPlugin(option, config.pluginmanager), "_cov")


def pytest_configure(config: Any) -> None:
    """Install shared pytest defaults for source-layout projects."""
    _install_defaults(config)


def pytest_load_initial_conftests(early_config: Any, parser: Any, args: list[str]) -> None:
    """Install shared pytest defaults before initial conftest loading."""
    del parser
    _install_defaults(early_config)
    defaults = [
        ("-v", "-v"),
        ("-Wonce", "-Wonce"),
        ("-p", "-p", "no:doctest"),
        ("--cov", f"--cov={_project_paths()[1].name}"),
        ("--cov-config", f"--cov-config={Path(__file__).with_name('coverage.ini')}"),
        ("--cov-report", "--cov-report=term", "--cov-report=xml"),
    ]
    for options in defaults:
        if not any(_has_option(args, option) for option in options if option.startswith("-")):
            args.extend(options[1:])
