import ast
from pathlib import Path

import pytest

from nullforge.runes import RUNES_DIR, discover_runes, rune_summary


FOUNDRY_DIR = RUNES_DIR.parent / "foundry"
SMITHY_DIR = RUNES_DIR.parent / "smithy"

OP_NAMESPACES = frozenset({"files", "server", "systemd", "git", "apt", "dnf", "python", "local", "pm"})
"""Names operations are called on; a call on any of these adds a node to pyinfra's ordering DAG."""


def test_discover_runes_skips_private_and_sorts(tmp_path: Path) -> None:
    (tmp_path / "_private.py").write_text('"""Private."""\n')
    (tmp_path / "beta.py").write_text('"""Beta rune.\n\nLonger description."""\n')
    (tmp_path / "alpha.py").write_text('"""Alpha rune."""\n')

    infos = discover_runes(tmp_path)

    assert [info.name for info in infos] == ["alpha", "beta"]
    assert infos[0].summary == "Alpha rune."
    assert infos[1].summary == "Beta rune."


def test_discover_runes_missing_directory(tmp_path: Path) -> None:
    assert discover_runes(tmp_path / "gone") == ()


def test_rune_summary_never_imports_the_module(tmp_path: Path) -> None:
    rune = tmp_path / "explosive.py"
    rune.write_text('"""Explosive rune."""\n\nraise AssertionError("executed")\n')

    assert rune_summary(rune) == "Explosive rune."


def test_rune_summary_handles_missing_docstring_and_file(tmp_path: Path) -> None:
    bare = tmp_path / "bare.py"
    bare.write_text("x = 1\n")

    assert rune_summary(bare) == ""
    assert rune_summary(tmp_path / "gone.py") == ""


def _emits_operations(node: ast.AST, emitting_functions: set[str]) -> bool:
    """Whether this subtree calls a pyinfra operation, directly or via a function in the same module."""

    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in OP_NAMESPACES:
            return True
        if isinstance(func, ast.Name) and func.id in emitting_functions:
            return True
    return False


def _emitting_functions(tree: ast.Module) -> set[str]:
    """Names of module-level functions that emit operations, resolved transitively."""

    functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    emitting: set[str] = set()

    while True:
        found = {name for name, node in functions.items() if name not in emitting and _emits_operations(node, emitting)}
        if not found:
            return emitting
        emitting |= found


def _is_host_loop(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "loop"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "host"
    )


@pytest.mark.parametrize(
    "module_path",
    sorted(RUNES_DIR.glob("*.py")) + sorted(FOUNDRY_DIR.glob("*.py")),
    ids=lambda path: f"{path.parent.name}/{path.name}",
)
def test_operation_loops_use_host_loop(module_path: Path) -> None:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    emitting_functions = _emitting_functions(tree)

    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.For) and _emits_operations(node, emitting_functions) and not _is_host_loop(node.iter)
    ]

    assert not offenders, f"{module_path.name} emits operations in a plain loop at line(s) {offenders}; use host.loop()"


def _direct_breaks(node: ast.AST) -> list[int]:
    """Line numbers of `break`s whose nearest enclosing loop is `node`."""

    lines: list[int] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Break):
            lines.append(child.lineno)
        elif not isinstance(child, ast.For | ast.While | ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            lines.extend(_direct_breaks(child))
    return lines


@pytest.mark.parametrize(
    "module_path",
    sorted(RUNES_DIR.glob("*.py")) + sorted(FOUNDRY_DIR.glob("*.py")),
    ids=lambda path: f"{path.parent.name}/{path.name}",
)
def test_host_loops_never_break(module_path: Path) -> None:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    offenders = [
        line
        for node in ast.walk(tree)
        if isinstance(node, ast.For) and _is_host_loop(node.iter)
        for line in _direct_breaks(node)
    ]

    assert not offenders, f"{module_path.name} breaks out of host.loop() at line(s) {offenders}"


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def _curl_args_for_src(value: ast.expr | None, src: ast.expr | None) -> bool:
    if not (isinstance(value, ast.Call) and value.args and src is not None):
        return False
    func = value.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
    return name in {"curl_args", "release_curl_args"} and ast.dump(value.args[0]) == ast.dump(src)


@pytest.mark.parametrize(
    "module_path",
    sorted(RUNES_DIR.glob("*.py")) + sorted(SMITHY_DIR.rglob("*.py")),
    ids=lambda path: str(path.relative_to(RUNES_DIR.parent)),
)
def test_downloads_pass_their_own_url(module_path: Path) -> None:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "download"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "files"
        and not _curl_args_for_src(_keyword(node, "extra_curl_args"), _keyword(node, "src"))
    ]

    assert not offenders, f"{module_path.name} downloads without curl_args(src) at line(s) {offenders}"
