import ast
from pathlib import Path


def test_domain_packages_do_not_import_frameworks_or_other_modules() -> None:
    modules_root = Path(__file__).resolve().parents[2]
    forbidden_roots = {"django", "rest_framework", "celery"}
    violations: list[str] = []
    for source in modules_root.glob("*/domain/**/*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            for name in imported:
                root = name.split(".", 1)[0]
                if root in forbidden_roots or name.startswith("modules."):
                    violations.append(f"{source}: {name}")
    assert not violations, "\n".join(violations)

