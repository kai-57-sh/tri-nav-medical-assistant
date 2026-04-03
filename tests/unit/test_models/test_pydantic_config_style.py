"""Guard against deprecated Pydantic v1-style model config."""

from pathlib import Path


def test_models_do_not_use_class_config_block() -> None:
    """Pydantic v2 requires `model_config = ConfigDict(...)` instead of `class Config`."""
    models_dir = Path(__file__).resolve().parents[3] / "src" / "models"
    offending_files: list[str] = []

    for file_path in sorted(models_dir.glob("*.py")):
        source = file_path.read_text(encoding="utf-8")
        if "class Config:" in source:
            offending_files.append(str(file_path.relative_to(models_dir.parent.parent)))

    assert not offending_files, (
        "Replace deprecated `class Config` blocks with "
        "`model_config = ConfigDict(...)` in: "
        + ", ".join(offending_files)
    )
