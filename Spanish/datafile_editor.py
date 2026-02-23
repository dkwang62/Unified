from __future__ import annotations

import copy
import datetime as dt
import difflib
import json
from pathlib import Path
from typing import Any

import streamlit as st

DEFAULT_DATA_FILE = "jehle_verb_database.json"
DEFAULT_LOOKUP_FILE = "jehle_verb_lookup_index.json"


def _json_pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _load_json_from_path(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dict_key_paths(value: Any, base_path: str = "$") -> set[tuple[str, tuple[str, ...]]]:
    paths: set[tuple[str, tuple[str, ...]]] = set()
    if isinstance(value, dict):
        keys = tuple(sorted(str(k) for k in value.keys()))
        paths.add((base_path, keys))
        for key, val in value.items():
            paths |= _dict_key_paths(val, f"{base_path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths |= _dict_key_paths(item, f"{base_path}[{idx}]")
    return paths


def _normalize_indexed_path(path: str) -> str:
    out = []
    i = 0
    while i < len(path):
        if path[i] == "[":
            while i < len(path) and path[i] != "]":
                i += 1
            out.append("[]")
            if i < len(path):
                i += 1
            continue
        out.append(path[i])
        i += 1
    return "".join(out)


def _shape_signature(value: Any) -> set[tuple[str, tuple[str, ...]]]:
    raw = _dict_key_paths(value)
    normalized: dict[tuple[str, tuple[str, ...]], None] = {}
    for pth, keys in raw:
        normalized[(_normalize_indexed_path(pth), keys)] = None
    return set(normalized.keys())


def _validate_json_compatible(candidate: Any, baseline: Any) -> list[str]:
    errors: list[str] = []

    if type(candidate) is not type(baseline):
        errors.append(
            f"Top-level type changed: expected {type(baseline).__name__}, got {type(candidate).__name__}."
        )
        return errors

    baseline_shape = _shape_signature(baseline)
    candidate_shape = _shape_signature(candidate)

    missing = baseline_shape - candidate_shape
    extra = candidate_shape - baseline_shape

    if missing:
        errors.append(f"Missing key-shape paths detected (sample): {sorted(missing)[:5]}")
    if extra:
        errors.append(f"Unexpected key-shape paths detected (sample): {sorted(extra)[:5]}")

    return errors


def _build_lookup_index(candidate: Any) -> tuple[dict[str, int], list[str]]:
    errors: list[str] = []
    lookup: dict[str, int] = {}

    if not isinstance(candidate, list):
        return {}, ["Lookup generation requires top-level list data."]

    for idx, row in enumerate(candidate):
        if not isinstance(row, dict):
            errors.append(f"Row {idx} is not an object.")
            continue

        inf_raw = row.get("infinitive", "")
        inf = str(inf_raw).strip().lower()
        if not inf:
            errors.append(f"Row {idx} has empty infinitive.")
            continue
        if inf in lookup:
            errors.append(f"Duplicate infinitive '{inf}' at row {idx}.")
            continue
        lookup[inf] = idx

    return lookup, errors


def _build_diff(before: str, after: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="loaded",
            tofile="edited",
            lineterm="",
        )
    )


def _matches_english(row: dict[str, Any], query: str) -> bool:
    inf_en = str(row.get("infinitive_english", "")).lower()
    if inf_en and query in inf_en:
        return True
    for conj in row.get("conjugations", []) or []:
        if not isinstance(conj, dict):
            continue
        verb_en = str(conj.get("verb_english", "")).lower()
        if verb_en and query in verb_en:
            return True
    return False


def _search_loaded_verbs(rows: list[Any], query: str, limit: int = 300) -> list[tuple[int, dict[str, Any]]]:
    q = (query or "").strip().lower()
    out: list[tuple[int, dict[str, Any]]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        inf = str(row.get("infinitive", ""))
        if not inf:
            continue
        if not q or inf.lower().startswith(q) or _matches_english(row, q):
            out.append((idx, row))
        if len(out) >= limit:
            break
    return out


def _blank_like(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _blank_like(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_blank_like(v) for v in value]
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0
    if isinstance(value, float):
        return 0.0
    if value is None:
        return None
    return ""


def _widget_key(path: str) -> str:
    return f"editor_field::{path}"


def _list_item_label(path: str, index: int, item: Any) -> str:
    if path.endswith(".conjugations") and isinstance(item, dict):
        mood = str(item.get("mood", "")).strip()
        tense = str(item.get("tense", "")).strip()
        mood_en = str(item.get("mood_english", "")).strip()
        tense_en = str(item.get("tense_english", "")).strip()

        left = f"{mood} · {tense}".strip(" ·")
        right = f"{mood_en} · {tense_en}".strip(" ·")
        if left and right:
            return f"{index}: {left} ({right})"
        if left:
            return f"{index}: {left}"
        if right:
            return f"{index}: {right}"
    return f"{index}: item"


def _render_value_editor(value: Any, path: str, label: str) -> Any:
    if isinstance(value, dict):
        st.markdown(f"**{label}**")
        out: dict[str, Any] = {}
        for key, val in value.items():
            out[key] = _render_value_editor(val, f"{path}.{key}", str(key))
        return out

    if isinstance(value, list):
        st.markdown(f"**{label}** ({len(value)} items)")
        out_list: list[Any] = []
        for i, item in enumerate(value):
            item_label = _list_item_label(path, i, item)
            with st.expander(item_label, expanded=False):
                out_list.append(_render_value_editor(item, f"{path}[{i}]", item_label))
        return out_list

    key = _widget_key(path)
    if isinstance(value, bool):
        return st.checkbox(label, value=value, key=key)
    if isinstance(value, int) and not isinstance(value, bool):
        return int(st.number_input(label, value=value, step=1, key=key))
    if isinstance(value, float):
        return float(st.number_input(label, value=value, key=key))
    if value is None:
        txt = st.text_input(f"{label} (blank keeps null)", value="", key=key)
        return None if txt.strip() == "" else txt

    text_value = str(value)
    if "\n" in text_value or len(text_value) > 120:
        return st.text_area(label, value=text_value, height=120, key=key)
    return st.text_input(label, value=text_value, key=key)


def _candidate_data() -> Any:
    return st.session_state.get("editor_working_data")


def _editor_validation_errors() -> list[str]:
    candidate = _candidate_data()
    errors = _validate_json_compatible(candidate, st.session_state["editor_loaded_data"])
    _, lookup_errors = _build_lookup_index(candidate)
    errors.extend(lookup_errors)
    return errors


def _set_loaded_data(data: Any, source_path: str) -> None:
    st.session_state["editor_loaded_data"] = data
    st.session_state["editor_working_data"] = copy.deepcopy(data)
    st.session_state["editor_loaded_json_text"] = _json_pretty(data)
    st.session_state["editor_loaded_from_path"] = source_path
    st.session_state["editor_selected_row_index"] = 0
    st.session_state["editor_delete_confirm"] = False


def _init_editor_state() -> None:
    st.session_state.setdefault("editor_loaded_data", None)
    st.session_state.setdefault("editor_working_data", None)
    st.session_state.setdefault("editor_loaded_json_text", "")
    st.session_state.setdefault("editor_loaded_from_path", "")
    st.session_state.setdefault("editor_lookup_data", None)
    st.session_state.setdefault("editor_selected_row_index", 0)
    st.session_state.setdefault("editor_delete_confirm", False)
    st.session_state.setdefault("editor_autoload_done", False)


def render_datafile_editor(*, show_title: bool = True, use_sidebar: bool = True) -> None:
    _init_editor_state()

    workspace_root = Path(".")
    default_data_path = workspace_root / DEFAULT_DATA_FILE
    default_lookup_path = workspace_root / DEFAULT_LOOKUP_FILE
    if not st.session_state.get("editor_autoload_done", False):
        if st.session_state.get("editor_loaded_data") is None and default_data_path.exists():
            try:
                _set_loaded_data(_load_json_from_path(default_data_path), str(default_data_path))
            except Exception:
                pass
        if st.session_state.get("editor_lookup_data") is None and default_lookup_path.exists():
            try:
                lookup_obj = _load_json_from_path(default_lookup_path)
                if isinstance(lookup_obj, dict):
                    st.session_state["editor_lookup_data"] = {str(k).lower(): int(v) for k, v in lookup_obj.items()}
            except Exception:
                pass
        st.session_state["editor_autoload_done"] = True

    if show_title:
        st.title("Safe Data File Editor")
        st.caption("Controlled form editing with validation, diff, add/delete, and backup-first overwrite.")
    else:
        st.subheader("Safe Data File Editor")
        st.caption("Controlled editor for verb records. Raw JSON editing is disabled.")

    controls = st.sidebar if use_sidebar else st.container()
    with controls:
        st.subheader("Load")
        data_path_input = st.text_input(
            "Data file path",
            value=st.session_state.get("editor_loaded_from_path") or str(default_data_path),
            key="editor_data_path_input",
            help="Relative or absolute path to JSON data file.",
        )
        if st.button("Load from disk", use_container_width=True, type="primary", key="editor_load_disk"):
            try:
                src_path = Path(data_path_input)
                data = _load_json_from_path(src_path)
                _set_loaded_data(data, str(src_path))
                st.success(f"Loaded: {src_path}")
            except Exception as exc:
                st.error(f"Failed to load file: {exc}")

        uploaded = st.file_uploader("Or upload JSON", type=["json"], key="editor_upload_json")
        if uploaded is not None:
            try:
                raw = uploaded.read().decode("utf-8")
                data = json.loads(raw)
                _set_loaded_data(data, "")
                st.success("Uploaded JSON loaded into editor.")
            except Exception as exc:
                st.error(f"Invalid uploaded JSON: {exc}")

        st.divider()
        st.subheader("Lookup Check")
        lookup_path_input = st.text_input(
            "Lookup file path (optional)",
            value=str(default_lookup_path),
            key="editor_lookup_path_input",
            help="Used for compatibility checks when editing Jehle DB.",
        )
        if st.button("Load lookup", use_container_width=True, key="editor_load_lookup"):
            try:
                lookup_obj = _load_json_from_path(Path(lookup_path_input))
                if not isinstance(lookup_obj, dict):
                    st.error("Lookup file must be a JSON object of infinitive->index.")
                else:
                    st.session_state["editor_lookup_data"] = {str(k).lower(): int(v) for k, v in lookup_obj.items()}
                    st.success(f"Lookup loaded ({len(lookup_obj)} entries).")
            except Exception as exc:
                st.error(f"Failed to load lookup file: {exc}")

    loaded_data = st.session_state.get("editor_loaded_data")
    working_data = st.session_state.get("editor_working_data")
    if loaded_data is None or working_data is None:
        st.info("Load a file from disk or upload JSON to begin.")
        return

    if not (isinstance(working_data, list) and working_data and isinstance(working_data[0], dict)):
        st.error("This controlled editor currently supports list-of-object JSON files.")
        return

    st.subheader("Locate Verb")
    st.caption("Use search or grid to select a verb, then edit all nested fields below.")

    locate_mode = st.radio(
        "Locate mode",
        options=["Search", "Row list"],
        horizontal=True,
        key="editor_locate_mode",
    )

    if locate_mode == "Search":
        query = st.text_input(
            "Search verb",
            value=st.session_state.get("editor_locate_query", ""),
            placeholder="hablar / speak",
            key="editor_locate_query",
        )
        matches = _search_loaded_verbs(working_data, query, limit=300)
        if matches:
            options = [idx for idx, _ in matches]
            selected_idx = st.selectbox(
                "Search results",
                options=options,
                key="editor_search_result_idx",
                format_func=lambda i: f"{i}: {working_data[i].get('infinitive', '')} — {working_data[i].get('infinitive_english', '')}",
            )
            st.session_state["editor_selected_row_index"] = selected_idx
        else:
            st.info("No matches found.")

    else:
        labels = [f"{i}: {row.get('infinitive', '')}" for i, row in enumerate(working_data)]
        chosen_label = st.selectbox("Select row", labels, index=0, key="editor_select_row")
        st.session_state["editor_selected_row_index"] = int(chosen_label.split(":", 1)[0])

    chosen_index = int(st.session_state.get("editor_selected_row_index", 0))
    if chosen_index < 0 or chosen_index >= len(working_data):
        chosen_index = 0
        st.session_state["editor_selected_row_index"] = 0

    action_col1, action_col2, action_col3 = st.columns([1, 1, 1])
    with action_col1:
        if st.button("Add New Verb", use_container_width=True, key="editor_add_verb"):
            template = working_data[0]
            new_row = _blank_like(template)
            if isinstance(new_row, dict):
                new_row["infinitive"] = "new_verb"
            working_data.append(new_row)
            st.session_state["editor_selected_row_index"] = len(working_data) - 1
            st.session_state["editor_delete_confirm"] = False
            st.success("Added new verb record. Edit it below.")
            st.rerun()

    with action_col2:
        st.session_state["editor_delete_confirm"] = st.checkbox(
            "Confirm delete",
            value=bool(st.session_state.get("editor_delete_confirm", False)),
            key="editor_delete_confirm_checkbox",
        )

    with action_col3:
        if st.button("Delete Selected Verb", use_container_width=True, key="editor_delete_verb"):
            if not st.session_state.get("editor_delete_confirm", False):
                st.error("Enable 'Confirm delete' before deleting.")
            elif len(working_data) <= 1:
                st.error("Cannot delete the only remaining verb record.")
            else:
                del working_data[chosen_index]
                st.session_state["editor_selected_row_index"] = max(0, chosen_index - 1)
                st.session_state["editor_delete_confirm"] = False
                st.success("Selected verb deleted.")
                st.rerun()

    selected_row = copy.deepcopy(working_data[chosen_index])
    current_inf = str(selected_row.get("infinitive", "")) if isinstance(selected_row, dict) else ""
    st.markdown(f"### Editing: `{chosen_index}: {current_inf}`")

    with st.form(f"editor_verb_form_{chosen_index}", clear_on_submit=False):
        edited_row = _render_value_editor(selected_row, f"verb[{chosen_index}]", "verb")
        submitted = st.form_submit_button("Apply Selected Verb Changes")

    if submitted:
        working_data[chosen_index] = edited_row
        st.success("Selected verb changes applied.")

    st.subheader("Validation")
    if st.button("Validate", use_container_width=True, key="editor_validate"):
        errs = _editor_validation_errors()
        if errs:
            st.error("Validation failed:")
            for err in errs:
                st.write(f"- {err}")
        else:
            st.success("Validation passed.")

    st.subheader("Diff")
    diff_text = _build_diff(
        st.session_state["editor_loaded_json_text"],
        _json_pretty(working_data),
    )
    if diff_text.strip():
        st.code(diff_text, language="diff")
    else:
        st.caption("No changes.")

    st.subheader("Save")
    col_save_1, col_save_2 = st.columns([1, 1])
    with col_save_1:
        save_new_path = st.text_input(
            "Save as new file",
            value="edited_output.json",
            key="editor_save_new_path",
            help="Writes data + regenerated lookup only if validation passes.",
        )
        save_new_lookup_path = st.text_input(
            "Save new lookup file",
            value="edited_lookup_index.json",
            key="editor_save_new_lookup_path",
        )
        if st.button("Save New", use_container_width=True, key="editor_save_new"):
            errs = _editor_validation_errors()
            if errs:
                st.error("Save blocked due to validation errors.")
                for err in errs:
                    st.write(f"- {err}")
            else:
                lookup_map, _ = _build_lookup_index(working_data)
                out_path = Path(save_new_path)
                out_lookup_path = Path(save_new_lookup_path)
                out_path.write_text(_json_pretty(working_data) + "\n", encoding="utf-8")
                out_lookup_path.write_text(_json_pretty(lookup_map) + "\n", encoding="utf-8")
                st.session_state["editor_lookup_data"] = lookup_map
                st.success(f"Saved data: {out_path}")
                st.success(f"Saved lookup: {out_lookup_path}")

    with col_save_2:
        overwrite_path = st.text_input(
            "Overwrite target",
            value=st.session_state.get("editor_loaded_from_path") or str(default_data_path),
            key="editor_overwrite_path",
            help="Creates timestamped backup before overwriting data + lookup.",
        )
        overwrite_lookup_path = st.text_input(
            "Overwrite lookup target",
            value=st.session_state.get("editor_lookup_path_input", str(default_lookup_path)),
            key="editor_overwrite_lookup_path",
        )
        if st.button("Overwrite (with backup)", use_container_width=True, type="primary", key="editor_overwrite"):
            errs = _editor_validation_errors()
            if errs:
                st.error("Overwrite blocked due to validation errors.")
                for err in errs:
                    st.write(f"- {err}")
            else:
                lookup_map, _ = _build_lookup_index(working_data)
                target = Path(overwrite_path)
                lookup_target = Path(overwrite_lookup_path)
                if not target.exists() or not lookup_target.exists():
                    st.error("Data or lookup overwrite target does not exist. Use Save New instead.")
                else:
                    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup = target.with_name(f"{target.name}.backup_{stamp}")
                    backup_lookup = lookup_target.with_name(f"{lookup_target.name}.backup_{stamp}")
                    backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
                    backup_lookup.write_text(lookup_target.read_text(encoding="utf-8"), encoding="utf-8")
                    target.write_text(_json_pretty(working_data) + "\n", encoding="utf-8")
                    lookup_target.write_text(_json_pretty(lookup_map) + "\n", encoding="utf-8")
                    st.session_state["editor_lookup_data"] = lookup_map
                    st.success(f"Overwrite complete. Data backup: {backup}")
                    st.success(f"Overwrite complete. Lookup backup: {backup_lookup}")


def main() -> None:
    st.set_page_config(page_title="Data File Editor", page_icon="🛠️", layout="wide")
    render_datafile_editor(show_title=True, use_sidebar=True)


if __name__ == "__main__":
    main()
