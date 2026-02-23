"""Utility helpers for editable component-map JSON workflows used by app.py."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

PathLike = Union[str, Path]


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def default_copy_path(source_path: PathLike) -> str:
    source = Path(source_path)
    ext = source.suffix or ".json"
    return str(source.with_name(f"{source.stem}_editable_{timestamp()}{ext}"))


def _normalize_json_text(content: Union[str, Any]) -> str:
    if isinstance(content, str):
        parsed = json.loads(content)
    else:
        parsed = content
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def _is_single_char_key(value: str) -> bool:
    return isinstance(value, str) and len(value) == 1


def _default_download_filename(source_path: PathLike) -> str:
    source = Path(source_path)
    ext = source.suffix or ".json"
    return f"{source.stem}_editable_{timestamp()}{ext}"


def validate_component_map_structure(data: Any) -> list[str]:
    """
    Validate edited dataset against the minimum contract required by app.py/radix_core.py.
    Returns a list of errors; empty list means valid.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["Top-level JSON must be an object mapping single Hanzi keys to entry objects."]

    for char, entry in data.items():
        if not _is_single_char_key(char):
            errors.append(f"Key '{char}' is invalid: each top-level key must be exactly one character.")
            continue

        if not isinstance(entry, dict):
            errors.append(f"Entry '{char}' must be an object.")
            continue

        if "meta" not in entry or not isinstance(entry.get("meta"), dict):
            errors.append(f"Entry '{char}' must include a 'meta' object.")
            continue

        meta = entry["meta"]

        if "decomposition" in meta and not isinstance(meta["decomposition"], str):
            errors.append(f"Entry '{char}': 'meta.decomposition' must be a string.")

        if "radical" in meta and not isinstance(meta["radical"], str):
            errors.append(f"Entry '{char}': 'meta.radical' must be a string.")

        if "definition" in meta and not isinstance(meta["definition"], str):
            errors.append(f"Entry '{char}': 'meta.definition' must be a string.")

        if "pinyin" in meta and not isinstance(meta["pinyin"], (str, list)):
            errors.append(f"Entry '{char}': 'meta.pinyin' must be a string or list of strings.")
        elif isinstance(meta.get("pinyin"), list) and not all(isinstance(x, str) for x in meta["pinyin"]):
            errors.append(f"Entry '{char}': every item in 'meta.pinyin' must be a string.")

        if "compounds" in meta and not isinstance(meta["compounds"], list):
            errors.append(f"Entry '{char}': 'meta.compounds' must be a list of strings.")
        elif isinstance(meta.get("compounds"), list) and not all(isinstance(x, str) for x in meta["compounds"]):
            errors.append(f"Entry '{char}': every item in 'meta.compounds' must be a string.")

        if "strokes" in meta and not isinstance(meta["strokes"], (int, float, str)):
            errors.append(f"Entry '{char}': 'meta.strokes' must be a number or numeric string.")

        if "etymology" in meta and not isinstance(meta["etymology"], dict):
            errors.append(f"Entry '{char}': 'meta.etymology' must be an object.")
        elif isinstance(meta.get("etymology"), dict):
            ety = meta["etymology"]
            for ety_field in ("hint", "details"):
                if ety_field in ety and not isinstance(ety[ety_field], (str, list)):
                    errors.append(
                        f"Entry '{char}': 'meta.etymology.{ety_field}' must be a string or list of strings."
                    )
                elif isinstance(ety.get(ety_field), list) and not all(isinstance(x, str) for x in ety[ety_field]):
                    errors.append(
                        f"Entry '{char}': every item in 'meta.etymology.{ety_field}' must be a string."
                    )

        if "related_characters" in entry and not isinstance(entry["related_characters"], list):
            errors.append(f"Entry '{char}': 'related_characters' must be a list of single-character strings.")
        elif isinstance(entry.get("related_characters"), list):
            for rc in entry["related_characters"]:
                if not _is_single_char_key(rc):
                    errors.append(
                        f"Entry '{char}': 'related_characters' contains invalid value '{rc}' (must be one character)."
                    )

    return errors


def create_editable_copy(
    source_path: PathLike,
    output_path: Optional[PathLike] = None,
    persist: bool = False,
) -> dict:
    """Create an editable JSON copy. Defaults to in-memory (read-only safe)."""
    source = Path(source_path)
    if not source.exists() or not source.is_file():
        raise ValueError("Source file not found.")

    parsed = json.loads(source.read_text(encoding="utf-8"))
    errors = validate_component_map_structure(parsed)
    if errors:
        raise ValueError("Source JSON is incompatible with app.py:\n- " + "\n- ".join(errors[:20]))

    content = json.dumps(parsed, ensure_ascii=False, indent=2)
    target_path = None

    if persist:
        target_path = Path(output_path) if output_path else Path(default_copy_path(source))
        target_path.write_text(content, encoding="utf-8")

    return {
        "message": "Copy created in memory." if not persist else "Copy created.",
        "outputPath": str(target_path) if target_path else None,
        "suggestedFilename": _default_download_filename(source_path),
        "persisted": bool(target_path),
        "content": content,
    }


def save_json_copy(
    content: Union[str, Any],
    output_path: Optional[PathLike] = None,
    persist: bool = False,
) -> dict:
    """Validate edited JSON and optionally persist to disk."""
    if isinstance(content, str):
        parsed = json.loads(content)
    else:
        parsed = content

    errors = validate_component_map_structure(parsed)
    if errors:
        raise ValueError("Edited JSON is incompatible with app.py:\n- " + "\n- ".join(errors[:20]))

    normalized = json.dumps(parsed, ensure_ascii=False, indent=2)
    target = None

    if persist:
        if not output_path:
            raise ValueError("File path is required when persist=True.")
        target = Path(output_path)
        target.write_text(normalized, encoding="utf-8")

    return {
        "message": "Copy saved in memory." if not persist else "Copy saved successfully.",
        "outputPath": str(target) if target else None,
        "persisted": bool(target),
        "content": normalized,
    }


def build_download_payload(content: Union[str, Any], filename: str) -> dict:
    """Prepare bytes for Streamlit download_button in read-only deployments."""
    if isinstance(content, str):
        parsed = json.loads(content)
    else:
        parsed = content

    errors = validate_component_map_structure(parsed)
    if errors:
        raise ValueError("Download blocked because JSON is incompatible with app.py:\n- " + "\n- ".join(errors[:20]))

    normalized = json.dumps(parsed, ensure_ascii=False, indent=2)
    return {
        "filename": filename,
        "mime": "application/json",
        "bytes": normalized.encode("utf-8"),
        "content": normalized,
    }


__all__ = [
    "timestamp",
    "default_copy_path",
    "validate_component_map_structure",
    "create_editable_copy",
    "save_json_copy",
    "build_download_payload",
]
