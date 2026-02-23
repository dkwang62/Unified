# app.py
# Main Streamlit app for Radix - WITH AUTO-LOAD OF radix_user_data.json

import streamlit as st
from streamlit.components.v1 import html as st_html
import math
import html as pyhtml
import uuid
import re
import unicodedata
import os
import json
import radix_core as rc
from radix_core import (
    component_map, get_db_connection, batch_get_phrase_details,
    search_phrases_by_definition, get_stroke_count, component_usage_count,
    apply_script_filter, get_char_definition_en, render_combined_prompt,
    get_stroke_order_view_html, SCRIPT_FILTERS, IDC_CHARS,
    sort_key_usage_primary, sort_key_frequency_primary, stats_cache,
    cc_t2s, cc_s2t, analyze_component_structure
)
from radix_state import (
    StateManager, ConfigManager, InputValidator,
    PAGE_CONFIG, PAGE_SIZE, GRID_COLUMNS, PROFILE_FILENAME, PROFILE_SCHEMA_VERSION
)
from radix_ui import (
    apply_styles, generate_clean_card_html, render_ipad_safe_download_html,
    render_copy_to_clipboard, get_stroke_order_sidebar_html,
    render_learning_insights_html
)
from server import create_editable_copy, save_json_copy, build_download_payload


# Configure Streamlit
st.set_page_config(**PAGE_CONFIG)
apply_styles()

# Initialize managers
state = StateManager()
config = ConfigManager(state)
DEFAULT_COMPONENT_MAP_FILE = "enhanced_component_map_with_etymology.json"


# ==================== HELPERS ====================

def normalize_pinyin(pinyin_str):
    """Remove tone marks from pinyin for fuzzy search (e.g., 'nǐ' -> 'ni')."""
    if not isinstance(pinyin_str, str):
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', pinyin_str) if unicodedata.category(c) != 'Mn').lower()


def auto_load_user_data():
    """
    Automatically load radix_user_data.json on startup if it exists.
    This replaces the manual upload process with automatic loading.
    """
    # Only load once per session
    if state.get("auto_load_attempted"):
        return
    
    state.set("auto_load_attempted", True)
    
    # Check if file exists
    if not os.path.exists(PROFILE_FILENAME):
        return
    
    try:
        with open(PROFILE_FILENAME, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Validate schema
        if not isinstance(data, dict) or data.get("schema_version") != PROFILE_SCHEMA_VERSION:
            st.warning(f"⚠️ Found {PROFILE_FILENAME} but schema version mismatch. Skipping auto-load.")
            return
        
        # Import the data
        config.import_profile_dict(data)
        
        # Show success message
        favs_count = len(data.get("favourites_list", []))
        if favs_count > 0:
            st.toast(f"✅ Auto-loaded profile: {favs_count} favourites restored", icon="💾")
        else:
            st.toast(f"✅ Auto-loaded profile from {PROFILE_FILENAME}", icon="💾")
            
    except json.JSONDecodeError:
        st.error(f"❌ Error: {PROFILE_FILENAME} contains invalid JSON")
    except Exception as e:
        st.error(f"❌ Error loading {PROFILE_FILENAME}: {e}")


def _augment_component_map(data: dict) -> dict:
    """Recompute derived fields required by the runtime after dataset edits."""
    if not rc.SUBTLEX_FREQ:
        rc.load_subtlex_freq()

    for char, info in data.items():
        meta = info.get("meta", {})
        rel = info.get("related_characters", [])
        info["usage_count"] = len({c for c in rel if isinstance(c, str) and len(c) == 1})

        s = meta.get("strokes")
        try:
            if isinstance(s, (int, float)) and s > 0:
                info["stroke_count"] = int(s)
            elif isinstance(s, str) and s.isdigit():
                info["stroke_count"] = int(s)
            else:
                info["stroke_count"] = None
        except Exception:
            info["stroke_count"] = None

        lookup_char = cc_t2s.convert(char) if cc_t2s else char
        info["freq_per_million"] = rc.SUBTLEX_FREQ.get(lookup_char, 0.0)

    return data


def _apply_dataset_to_runtime(content) -> int:
    """Validate and hot-apply edited dataset into the running app."""
    validated = save_json_copy(content=content, persist=False)
    parsed = json.loads(validated["content"])
    _augment_component_map(parsed)
    component_map.clear()
    component_map.update(parsed)
    stats_cache.clear()
    stats_cache.update(rc.get_component_stats(component_map))
    return len(component_map)


def _default_entry_template() -> dict:
    return {
        "meta": {
            "definition": "",
            "pinyin": "",
            "decomposition": "",
            "radical": "",
            "strokes": "",
            "compounds": [],
            "etymology": {"hint": "", "details": ""},
        },
        "related_characters": [],
    }


def _load_dataset_working_copy(source_path: str) -> None:
    payload = create_editable_copy(source_path=source_path, persist=False)
    st.session_state["dataset_working_map"] = json.loads(payload["content"])
    st.session_state["dataset_editor_filename"] = payload.get("suggestedFilename", "component_map_editable.json")
    st.session_state["dataset_entry_loaded_for"] = ""


def _load_entry_into_editor(char_key: str) -> None:
    wm = st.session_state.get("dataset_working_map", {})
    entry = wm.get(char_key, _default_entry_template())
    st.session_state["dataset_entry_raw"] = json.loads(json.dumps(entry, ensure_ascii=False))
    st.session_state["dataset_entry_loaded_for"] = char_key

    meta = entry.get("meta", {}) if isinstance(entry, dict) else {}

    def _to_text_list(value):
        if isinstance(value, list):
            return "\n".join([str(x) for x in value if isinstance(x, str)])
        if isinstance(value, str):
            return value
        return ""

    pinyin_value = meta.get("pinyin", "")
    if isinstance(pinyin_value, list):
        st.session_state["dataset_form_pinyin_type"] = "List"
        st.session_state["dataset_form_pinyin"] = "\n".join([x for x in pinyin_value if isinstance(x, str)])
    else:
        st.session_state["dataset_form_pinyin_type"] = "String"
        st.session_state["dataset_form_pinyin"] = pinyin_value if isinstance(pinyin_value, str) else ""

    ety = meta.get("etymology", {}) if isinstance(meta.get("etymology"), dict) else {}
    st.session_state["dataset_form_definition"] = meta.get("definition", "") if isinstance(meta.get("definition"), str) else ""
    st.session_state["dataset_form_decomposition"] = meta.get("decomposition", "") if isinstance(meta.get("decomposition"), str) else ""
    st.session_state["dataset_form_radical"] = meta.get("radical", "") if isinstance(meta.get("radical"), str) else ""
    st.session_state["dataset_form_strokes"] = str(meta.get("strokes", "") or "")
    st.session_state["dataset_form_compounds"] = _to_text_list(meta.get("compounds", []))
    st.session_state["dataset_form_etym_hint"] = _to_text_list(ety.get("hint", ""))
    st.session_state["dataset_form_etym_details"] = _to_text_list(ety.get("details", ""))
    st.session_state["dataset_form_related"] = _to_text_list(entry.get("related_characters", []))


def _split_lines_csv(raw: str) -> list[str]:
    if not isinstance(raw, str):
        return []
    out = []
    for part in re.split(r"[\n,]+", raw):
        token = part.strip()
        if token:
            out.append(token)
    return out


def _build_entry_from_form() -> dict:
    original = st.session_state.get("dataset_entry_raw", {})
    entry = json.loads(json.dumps(original if isinstance(original, dict) else {}, ensure_ascii=False))

    meta = entry.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    entry["meta"] = meta

    meta["definition"] = st.session_state.get("dataset_form_definition", "")
    pinyin_raw = st.session_state.get("dataset_form_pinyin", "")
    if st.session_state.get("dataset_form_pinyin_type", "String") == "List":
        meta["pinyin"] = _split_lines_csv(pinyin_raw)
    else:
        meta["pinyin"] = pinyin_raw
    meta["decomposition"] = st.session_state.get("dataset_form_decomposition", "")
    meta["radical"] = st.session_state.get("dataset_form_radical", "")

    strokes_raw = st.session_state.get("dataset_form_strokes", "").strip()
    if strokes_raw.isdigit():
        meta["strokes"] = int(strokes_raw)
    else:
        meta["strokes"] = strokes_raw

    meta["compounds"] = _split_lines_csv(st.session_state.get("dataset_form_compounds", ""))

    ety = meta.get("etymology")
    if not isinstance(ety, dict):
        ety = {}
    ety["hint"] = st.session_state.get("dataset_form_etym_hint", "")
    ety["details"] = st.session_state.get("dataset_form_etym_details", "")
    meta["etymology"] = ety

    entry["related_characters"] = _split_lines_csv(st.session_state.get("dataset_form_related", ""))
    return entry


def dataset_pick_char(c: str):
    """Select a character and immediately load its dataset entry into the editor."""
    state.set("preview_comp", c)
    st.session_state["dataset_edit_char"] = c
    _load_entry_into_editor(c)


def open_dataset_editor():
    state.set("dataset_editor_mode", True)


def close_dataset_editor():
    state.set("dataset_editor_mode", False)


def go_to_search_root():
    state.set("dataset_editor_mode", False)
    state.go_to_root()


def _promote_selection_for_navigation(target_char: str):
    """Promote previewed char into selected state before explicit nav actions."""
    if not target_char:
        return
    selected = state.get_selected_component()
    if selected and selected != target_char:
        history = state.get_history()
        history.append(selected)
        state.set("history", history)
    state.set("selected_comp", target_char)
    state.set("last_valid_selected_comp", target_char)
    state.set("text_input_comp", target_char)
    state.set("preview_comp", None)


def _search_pick_char(c: str, key_prefix: str = "", on_pick=None, collapse_after_pick: bool = False):
    """Handle character selection from shared search UI."""
    if on_pick:
        on_pick(c)
    else:
        # Search picks should stay in Search and only update sidebar preview.
        state.set("preview_comp", c)

    if collapse_after_pick:
        st.session_state[f"{key_prefix}selected_char"] = c
        st.rerun()


def render_dataset_editor():
    """Character-focused dataset editor integrated with app search/selection."""
    st.caption("Search/select a character, then edit it with strict fields (key names are fixed).")
    st.markdown("### Character Search")
    render_smart_search("dataset_", on_pick=dataset_pick_char, collapse_after_pick=True)
    st.markdown("---")
    st.markdown("### Entry Editor")

    if "dataset_source_path" not in st.session_state:
        st.session_state["dataset_source_path"] = DEFAULT_COMPONENT_MAP_FILE
    if "dataset_working_map" not in st.session_state:
        try:
            _load_dataset_working_copy(st.session_state["dataset_source_path"])
        except Exception:
            st.session_state["dataset_working_map"] = json.loads(json.dumps(component_map, ensure_ascii=False))
            st.session_state["dataset_editor_filename"] = "component_map_editable.json"
            st.session_state["dataset_entry_loaded_for"] = ""
    if "dataset_edit_char" not in st.session_state:
        st.session_state["dataset_edit_char"] = ""
    if "dataset_editor_filename" not in st.session_state:
        st.session_state["dataset_editor_filename"] = "component_map_editable.json"
    if "dataset_output_path" not in st.session_state:
        st.session_state["dataset_output_path"] = ""
    if "dataset_entry_raw" not in st.session_state:
        st.session_state["dataset_entry_raw"] = {}

    source_path = st.text_input("Source JSON path", key="dataset_source_path")
    if st.button("Reload Working Copy From Source", key="dataset_load_copy", use_container_width=True):
        try:
            _load_dataset_working_copy(source_path)
            st.success(f"Loaded {source_path} into memory.")
        except Exception as e:
            st.error(str(e))

    selected_char = state.get_preview_component() or state.get_selected_component()
    if selected_char:
        if st.session_state.get("dataset_edit_char") != selected_char:
            st.session_state["dataset_edit_char"] = selected_char
            _load_entry_into_editor(selected_char)
        st.caption(f"Current search selection: `{selected_char}` (auto-loaded)")

    st.text_input("Character key to edit", key="dataset_edit_char", max_chars=1)
    e1, e2 = st.columns(2)
    with e1:
        if st.button("Load Character Entry", key="dataset_load_char", use_container_width=True):
            char_key = (st.session_state["dataset_edit_char"] or "").strip()
            if len(char_key) != 1:
                st.error("Enter exactly one character key.")
            else:
                _load_entry_into_editor(char_key)
    with e2:
        if st.button("New Entry Template", key="dataset_new_entry", use_container_width=True):
            char_key = (st.session_state["dataset_edit_char"] or "").strip()
            if len(char_key) != 1:
                st.error("Enter exactly one character key.")
            else:
                st.session_state["dataset_entry_raw"] = _default_entry_template()
                _load_entry_into_editor(char_key)

    char_key = (st.session_state["dataset_edit_char"] or "").strip()
    wm = st.session_state.get("dataset_working_map", {})
    if len(char_key) == 1 and char_key in wm:
        st.markdown("**Current entry snapshot (read-only full data):**")
        st.json(wm[char_key], expanded=False)

    st.markdown("### Edit Fields (Strict Schema)")
    st.text_input("meta.definition", key="dataset_form_definition")
    st.radio("meta.pinyin type", options=["String", "List"], horizontal=True, key="dataset_form_pinyin_type")
    st.text_area("meta.pinyin", key="dataset_form_pinyin", height=90, help="String or newline/comma separated list.")
    st.text_input("meta.decomposition", key="dataset_form_decomposition")
    st.text_input("meta.radical", key="dataset_form_radical")
    st.text_input("meta.strokes", key="dataset_form_strokes")
    st.text_area("meta.compounds (newline/comma separated)", key="dataset_form_compounds", height=90)
    st.text_area("meta.etymology.hint", key="dataset_form_etym_hint", height=70)
    st.text_area("meta.etymology.details", key="dataset_form_etym_details", height=90)
    st.text_area("related_characters (newline/comma separated)", key="dataset_form_related", height=90)

    a1, a2 = st.columns(2)
    with a1:
        if st.button("Save Entry To Working Copy", key="dataset_save_entry", use_container_width=True):
            try:
                char_key = (st.session_state["dataset_edit_char"] or "").strip()
                if len(char_key) != 1:
                    raise ValueError("Character key must be exactly one character.")

                parsed_entry = _build_entry_from_form()
                updated = dict(st.session_state["dataset_working_map"])
                updated[char_key] = parsed_entry
                validated = save_json_copy(content=updated, persist=False)
                normalized_map = json.loads(validated["content"])
                st.session_state["dataset_working_map"] = normalized_map
                _load_entry_into_editor(char_key)
                st.success(f"Entry '{char_key}' saved to working copy.")
            except Exception as e:
                st.error(str(e))
    with a2:
        if st.button("Delete Entry", key="dataset_delete_entry", use_container_width=True):
            try:
                char_key = (st.session_state["dataset_edit_char"] or "").strip()
                if len(char_key) != 1:
                    raise ValueError("Character key must be exactly one character.")
                updated = dict(st.session_state["dataset_working_map"])
                if char_key not in updated:
                    raise ValueError(f"Entry '{char_key}' not found.")
                del updated[char_key]
                validated = save_json_copy(content=updated, persist=False)
                st.session_state["dataset_working_map"] = json.loads(validated["content"])
                st.success(f"Entry '{char_key}' deleted from working copy.")
            except Exception as e:
                st.error(str(e))

    st.markdown("---")
    st.text_input("Download filename", key="dataset_editor_filename")
    full_dataset = st.session_state.get("dataset_working_map", {})

    o1, o2 = st.columns(2)
    with o1:
        if st.button("Validate Full Dataset", key="dataset_validate_all", use_container_width=True):
            try:
                save_json_copy(content=full_dataset, persist=False)
                st.success("Full dataset is valid and app-compatible.")
            except Exception as e:
                st.error(str(e))
    with o2:
        if st.button("Apply Full Dataset To App", key="dataset_apply_runtime", use_container_width=True, type="primary"):
            try:
                count = _apply_dataset_to_runtime(full_dataset)
                st.success(f"Applied dataset to runtime ({count} characters).")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    try:
        download_payload = build_download_payload(
            content=full_dataset,
            filename=st.session_state["dataset_editor_filename"],
        )
        st.download_button(
            "Download Full Edited JSON",
            data=download_payload["bytes"],
            file_name=download_payload["filename"],
            mime=download_payload["mime"],
            use_container_width=True,
            key="dataset_download_btn",
        )
    except Exception as e:
        st.error(str(e))

    st.caption("Optional: save full edited dataset to disk (writable environments only).")
    st.text_input("Output path", key="dataset_output_path")
    if st.button("Save Full Dataset To Disk", key="dataset_save_disk", use_container_width=True):
        try:
            result = save_json_copy(
                content=full_dataset,
                output_path=st.session_state["dataset_output_path"].strip(),
                persist=True,
            )
            st.success(f"Saved: {result.get('outputPath')}")
        except Exception as e:
            st.error(str(e))


# ==================== CALLBACKS ====================

def tile_click(c):
    """Handle click on a grid tile."""
    if state.is_showing_inputs() and state.get_preview_component() == c:
        state.enter_character_view(c)
    else:
        state.set("preview_comp", c)

def list_tile_click(c):
    """Handle click on a list/lineage tile."""
    if state.get_preview_component() == c:
        if state.get_selected_component():
            history = state.get_history()
            history.append(state.get_selected_component())
            state.set("history", history)
        state.enter_character_view(c)
    else:
        state.set("preview_comp", c)

def toggle_favourite(char):
    """Toggle favourite status via checkbox."""
    if state.get(f"fav_chk_{char}", False):
        state.add_to_favourites(char)
    else:
        state.remove_from_favourites(char)

def search_by_definition():
    """Execute search for English definitions (Legacy/Sidebar version)."""
    query = state.get("sidebar_def_search", "").strip()
    is_valid, error_msg = InputValidator.validate_definition_search(query)
    
    if not is_valid:
        st.toast(error_msg)
        return
    
    # 1. Search Characters
    char_results = []
    query_lower = query.lower()
    for char, info in component_map.items():
        definition = info.get("meta", {}).get("definition", "")
        if isinstance(definition, str) and query_lower in definition.lower():
            char_results.append(char)
    
    # 2. Search Phrases
    db_conn = get_db_connection()
    phrase_results = search_phrases_by_definition(query, db_conn, limit=200) if db_conn else []
    
    # 3. Update State
    state.update(
        definition_search_mode=True,
        definition_search_query=query,
        definition_search_results={"characters": char_results[:120], "phrases": phrase_results[:200]},
        show_inputs=False,
        selected_comp="",
        preview_comp=None
    )


# ==================== HTML HELPERS ====================

def _render_phrase_html(c: str) -> str:
    """Render phrases containing the character."""
    n_map = {"Single Character": 1, "2-Characters": 2, "3-Characters": 3, "4-Characters": 4}
    n = n_map.get(state.get_display_mode(), 2)
    
    raw_compounds = component_map.get(c, {}).get("meta", {}).get("compounds", [])
    
    if not raw_compounds and cc_t2s:
        s_c = cc_t2s.convert(c)
        if s_c != c:
            raw_compounds = component_map.get(s_c, {}).get("meta", {}).get("compounds", [])
            
    compounds = [w for w in (raw_compounds or []) if len(w) == n]
    
    if compounds and (db := get_db_connection()):
        phrases = batch_get_phrase_details(sorted(compounds), db)
        items_html_list = []
        for word in sorted(compounds):
            entry = phrases.get(word)
            if entry:
                p_mean = pyhtml.escape(entry.get('meanings', '')[:130] + ('...' if len(entry.get('meanings', '')) > 130 else ''))
                items_html_list.append(f"<div style='display:flex; align-items:baseline; padding:5px 8px; border-bottom:1px solid #eee;'><span style='font-weight:700; font-size:1.0rem; min-width:65px;'>{word}</span><span style='color:#d35400; font-size:0.85rem; font-family:monospace; margin-right:12px; font-weight:600;'>{entry.get('pinyin', '')}</span><span style='color:#444; font-size:0.85rem; flex:1; line-height:1.2;'>{p_mean}</span></div>")
        
        if items_html_list:
            return f"<div style='padding:12px; background:#f1f8e9; border-radius:8px; margin-top:10px; border:1px solid #dcedc8; max-height:400px; overflow-y:auto;'><div style='font-weight:bold; font-size:0.8rem; margin-bottom:8px; color:#2e7d32; text-transform:uppercase;'>{state.get_display_mode()} containing {c}</div>{''.join(items_html_list)}</div>"
    return ""

def render_radix_row(c, is_static=False, minimal=False):
    """Render a standard list row for a character."""
    col_char, col_details = st.columns([2, 10])
    is_preview = state.get_preview_component() == c
    is_active_focus = is_preview or (state.get_preview_component() is None and c == state.get_selected_component())
    
    uid = str(uuid.uuid4())[:8]

    with col_char:
        if is_static:
            st.markdown(f"<div class='char-static-box'>{c}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='char-btn-wrap'>", unsafe_allow_html=True)
            st.button(
                c,
                key=f"char_{c}_{uid}",
                type="primary" if is_preview else "secondary",
                help="Previewing..." if is_preview else "Click to preview",
                on_click=list_tile_click,
                args=(c,),
                use_container_width=True
            )
            st.markdown(f"<div class='char-btn-hint {'previewing' if is_preview else ''}'>{'Click again to drill down' if is_preview else 'Click once to preview'}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        
    with col_details:
        st.markdown(generate_clean_card_html(c, usage_count=component_usage_count(c), is_static=is_static, minimal=minimal), unsafe_allow_html=True)
        
        if not is_static and is_active_focus:
            current_mode_str = state.get_display_mode()
            try:
                current_int = int(current_mode_str[0])
            except:
                current_int = 2
            
            if current_int not in [2, 3, 4]:
                current_int = 2

            def update_phrase_len():
                val = st.session_state[f"ph_len_{c}_{uid}"]
                state.set("display_mode", f"{val}-Characters")

            st.radio(
                "Phrase Length",
                options=[2, 3, 4],
                index=[2, 3, 4].index(current_int),
                key=f"ph_len_{c}_{uid}",
                horizontal=True,
                label_visibility="collapsed",
                on_change=update_phrase_len
            )

            if html := _render_phrase_html(c):
                st.markdown(html, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 15px'></div>", unsafe_allow_html=True)


# ==================== VIEW RENDERERS ====================

def render_sidebar():
    with st.sidebar:
        st.markdown("# 🈳 Radix")
        
        # 1. Breadcrumbs
        current_char = state.get("stroke_view_char") if state.is_stroke_view_active() else state.get_selected_component()
        if current_char:
            path_items = ["🏠 Search"] + state.get_history()
            if state.is_stroke_view_active():
                path_items.append(f"<i>{current_char}</i> (AI)")
            else:
                path_items.append(f"<b>{current_char}</b>")
            st.markdown(f"<div style='font-size:0.85em; margin:0 0 12px 0; padding:10px; color:#fff; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius:8px; text-align:center; font-weight:600; box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);'>{' → '.join(path_items)}</div>", unsafe_allow_html=True)
        
        # 2. Navigation
        if not state.is_showing_inputs() or state.is_stroke_view_active() or state.get("dataset_editor_mode", False):
            nav_col1, nav_col2 = st.columns(2)
            with nav_col1:
                if state.get("dataset_editor_mode", False):
                    st.button("← Back", on_click=close_dataset_editor, use_container_width=True, type="primary")
                elif state.is_stroke_view_active():
                    st.button("← Lineage", on_click=state.exit_stroke_view, use_container_width=True, type="primary")
                else:
                    st.button("← Back", on_click=state.go_back, use_container_width=True, type="primary")
            with nav_col2:
                st.button("🔍 Search", on_click=go_to_search_root, use_container_width=True)

        st.button("🧩 Dataset Editor", on_click=open_dataset_editor, use_container_width=True)

        # 3. Action Buttons & Character Details
        current_char_for_sidebar = state.get("stroke_view_char") if state.is_stroke_view_active() else (state.get_preview_component() or state.get_selected_component())

        if current_char_for_sidebar:
            # Action Buttons
            show_lineage = state.is_showing_inputs() or state.is_stroke_view_active() or (current_char_for_sidebar != state.get_selected_component())
            show_ai_link = not state.is_stroke_view_active()

            if show_lineage or show_ai_link:
                if show_lineage and show_ai_link:
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("🌳 Lineage", key="sb_btn_lin", use_container_width=True, type="primary"):
                            state.set("dataset_editor_mode", False)
                            _promote_selection_for_navigation(current_char_for_sidebar)
                            state.enter_character_view(current_char_for_sidebar)
                            st.rerun()
                    with b2:
                        if st.button("🧠 AI Link", key="sb_btn_ai", use_container_width=True):
                            state.set("dataset_editor_mode", False)
                            _promote_selection_for_navigation(current_char_for_sidebar)
                            state.enter_stroke_view(current_char_for_sidebar)
                            st.rerun()
                else:
                    if show_lineage:
                        if st.button("🌳 Lineage", key="sb_btn_lin_full", use_container_width=True, type="primary"):
                            state.set("dataset_editor_mode", False)
                            _promote_selection_for_navigation(current_char_for_sidebar)
                            state.enter_character_view(current_char_for_sidebar)
                            st.rerun()
                    if show_ai_link:
                        if st.button("🧠 AI Link", key="sb_btn_ai_full", use_container_width=True):
                            state.set("dataset_editor_mode", False)
                            _promote_selection_for_navigation(current_char_for_sidebar)
                            state.enter_stroke_view(current_char_for_sidebar)
                            st.rerun()

            # Visuals
            sidebar_html, sidebar_height = get_stroke_order_sidebar_html(current_char_for_sidebar, size=140)
            if sidebar_html:
                st_html(sidebar_html, height=sidebar_height)
            
            card_html = generate_clean_card_html(current_char_for_sidebar, usage_count=component_usage_count(current_char_for_sidebar), is_static=True)
            st.markdown(f"<div style='margin-top: 15px;'>{card_html}</div>", unsafe_allow_html=True)

            # Logic Breakdown
            analysis = analyze_component_structure(current_char_for_sidebar)
            if analysis['semantic'] or analysis['phonetic']:
                s_txt = f"💡 <b>{analysis['semantic']}</b> = Meaning" if analysis['semantic'] else ""
                p_txt = f"📊 <b>{analysis['phonetic']}</b> = Sound" if analysis['phonetic'] else ""
                st.markdown(f"""
                <div style='background-color: #f0f2f6; padding: 12px; border-radius: 10px; margin-top: 15px; border: 1px solid #dce0e6;'>
                    <div style='font-weight:bold; margin-bottom:6px; color: #31333F; font-size: 0.9em;'>🧠 Logic Breakdown</div>
                    <div style='font-size: 0.85em; color: #31333F; margin-bottom: 4px; line-height: 1.4;'>{s_txt}</div>
                    <div style='font-size: 0.85em; color: #31333F; line-height: 1.4;'>{p_txt}</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.checkbox("⭐ Favourite", value=(current_char_for_sidebar in state.get_favourites()), key=f"fav_chk_{current_char_for_sidebar}", on_change=toggle_favourite, args=(current_char_for_sidebar,))
        
        st.markdown("---")
        
        # 4. User Data (Manual Upload/Download)
        with st.expander("💾 User Data", expanded=False):
            st.info(f"💡 {PROFILE_FILENAME} auto-loads on startup if present in the app directory")
            st.markdown(render_ipad_safe_download_html(config.export_profile_str(), PROFILE_FILENAME, "📥 Download Profile"), unsafe_allow_html=True)
            
            st.caption("---")
            st.caption("**Manual Upload:**")
            if uf := st.file_uploader("📤 Upload JSON", type=["json"], key="sidebar_uploader", label_visibility="collapsed"):
                import hashlib
                hash_val = hashlib.sha256(uf.getvalue()).hexdigest()
                if hash_val != state.get('_last_upload_hash', ''):
                    st.warning("⚠️ New file detected")
                    if st.button("✅ Apply Now", use_container_width=True, type="primary", key="apply_upload"):
                        state.set("_last_upload_hash", hash_val)
                        config.import_profile_bytes(uf.getvalue())
                        st.rerun()
                else:
                    st.success("✓ Current file active")

def render_grid():
    """Render the main grid view with tabs."""
    tab1, tab2, tab3 = st.tabs(["🔍 Smart Search", "📊 Filter", "⭐ Favourites"])
    
    with tab1:
        render_smart_search()
    
    with tab2:
        render_all_components_grid()

    with tab3:
        render_favourites_grid()

def render_smart_search(key_prefix: str = "", on_pick=None, collapse_after_pick: bool = False):
    """Render the combined Fuzzy Pinyin + Meaning search tab."""
    selected_key = f"{key_prefix}selected_char"
    input_key = f"{key_prefix}smart_search_input"
    committed_key = f"{key_prefix}smart_search_committed"

    if committed_key not in st.session_state:
        st.session_state[committed_key] = ""

    if collapse_after_pick and st.session_state.get(selected_key):
        chosen = st.session_state.get(selected_key)
        st.success(f"Selected character: {chosen}")
        if st.button("Change character", key=f"{key_prefix}change_char", use_container_width=False):
            st.session_state[selected_key] = ""
            st.session_state[input_key] = ""
            st.session_state[committed_key] = ""
            st.rerun()
        return

    st.info("💡 Search by **Character** (e.g., '水'), **Phrase** (e.g., '你好'), **Pinyin** (e.g., 'ma' or 'tan lan'), OR **English Meaning** (e.g., 'fire'). Results show pinyin matches first, then English matches.")

    with st.form(key=f"{key_prefix}smart_search_form", clear_on_submit=False):
        st.text_input(
            "Enter Character, Phrase, Pinyin or Meaning",
            key=input_key,
            placeholder="e.g. 水, 你好, tan lan, ma, horse, water",
        )
        submitted = st.form_submit_button("Search", use_container_width=False)

    if submitted:
        st.session_state[committed_key] = st.session_state.get(input_key, "").strip()

    query = st.session_state.get(committed_key, "")

    if query:
        query = query.strip()
        if len(query) < 1:
            st.warning("Please enter at least 1 character.")
            return

        # Check if query is a single Chinese character - if so, show it directly
        if len(query) == 1 and query in component_map:
            if on_pick or collapse_after_pick:
                _search_pick_char(query, key_prefix=key_prefix, on_pick=on_pick, collapse_after_pick=collapse_after_pick)
            else:
                state.set("preview_comp", query)
            return
        
        # Check if query is a multi-character Chinese phrase
        # If all characters are Chinese, try to look it up as a phrase
        if len(query) > 1 and all('\u4e00' <= c <= '\u9fff' for c in query):
            db_conn = get_db_connection()
            if db_conn:
                phrase_data = batch_get_phrase_details([query], db_conn)
                if query in phrase_data:
                    # Found the phrase! Show its details and the characters
                    entry = phrase_data[query]
                    st.success(f"📖 Found phrase: **{query}**")
                    st.markdown(f"**Pinyin:** {entry.get('pinyin', '')}")
                    st.markdown(f"**Meaning:** {entry.get('meanings', '')}")
                    st.markdown("---")
                    st.markdown("### Characters in this phrase:")
                    
                    # Show each character from the phrase
                    chars_in_phrase = [c for c in query if c in component_map]
                    
                    if chars_in_phrase:
                        st.markdown("<div class='comp-grid'>", unsafe_allow_html=True)
                        cols = st.columns(GRID_COLUMNS)
                        for i, ch in enumerate(chars_in_phrase):
                            with cols[i % GRID_COLUMNS]:
                                st.button(
                                    ch,
                                    key=f"{key_prefix}phrase_char_{ch}_{i}",
                                    type="primary" if state.get_preview_component() == ch else "secondary",
                                    on_click=_search_pick_char,
                                    args=(ch,),
                                    kwargs={
                                        "key_prefix": key_prefix,
                                        "on_pick": on_pick,
                                        "collapse_after_pick": collapse_after_pick,
                                    },
                                    use_container_width=True,
                                )
                        st.markdown("</div>", unsafe_allow_html=True)
                    return

        # If not a phrase match, proceed with regular search
        # Separate results: pinyin matches first, then English matches
        pinyin_results = []
        english_results = []
        phrase_results = []
        
        # Normalize the query for pinyin comparison (e.g. "jiong")
        query_norm = normalize_pinyin(query)
        query_lower = query.lower()

        # Iterate through all components
        for char, info in component_map.items():
            meta = info.get("meta", {})
            
            # 1. Pinyin Match (Fuzzy)
            # 'pinyin' in meta can be a list ["kān"] or string "kān"
            pinyin_data = meta.get("pinyin", [])
            pinyin_match = False
            
            if isinstance(pinyin_data, list):
                # Check if ANY pronunciation matches
                for p in pinyin_data:
                    if normalize_pinyin(p) == query_norm:
                        pinyin_match = True
                        break
            elif isinstance(pinyin_data, str):
                if normalize_pinyin(pinyin_data) == query_norm:
                    pinyin_match = True
            
            if pinyin_match:
                pinyin_results.append(char)
                continue # Matched pinyin, skip checking definition to avoid duplicates in list

            # 2. Definition Match (English) - Strict word boundary matching
            definition = meta.get("definition", "")
            if isinstance(definition, str):
                # Use word boundaries to match whole words only
                # This ensures "car" doesn't match "carve" or "carriage"
                pattern = r'\b' + re.escape(query_lower) + r'\b'
                if re.search(pattern, definition.lower()):
                    english_results.append(char)
                    continue

        # 3. Search phrases (if query is likely NOT Chinese characters)
        if not all('\u4e00' <= c <= '\u9fff' for c in query):
            db_conn = get_db_connection()
            if db_conn:
                # Check if query looks like pinyin (contains spaces or latin letters)
                is_pinyin_query = ' ' in query or any(c.isalpha() for c in query)
                
                if is_pinyin_query:
                    # Search for phrases by pinyin
                    # Use SQL LIKE for more efficient searching
                    try:
                        cursor = db_conn.cursor()
                        # Search for phrases where pinyin might contain the query
                        # This is more efficient than loading all phrases
                        cursor.execute("SELECT word, pinyin, meanings FROM phrases WHERE pinyin IS NOT NULL")
                        all_phrases = cursor.fetchall()
                        
                        for word, pinyin, meanings in all_phrases:
                            if pinyin:
                                # Normalize both query and phrase pinyin for comparison
                                phrase_pinyin_norm = normalize_pinyin(pinyin)
                                
                                # Check if query matches the phrase pinyin
                                # Handle both exact matches and substring matches
                                if query_norm in phrase_pinyin_norm or query_norm.replace(' ', '') in phrase_pinyin_norm.replace(' ', ''):
                                    phrase_results.append({
                                        'word': word,
                                        'pinyin': pinyin,
                                        'meanings': meanings
                                    })
                    except Exception as e:
                        st.warning(f"Pinyin search error: {str(e)}")
                
                # Also search phrases by English meaning (with strict word boundary matching)
                all_phrase_results = search_phrases_by_definition(query, db_conn, limit=200) or []
                
                # Filter to only include phrases where the query matches as a whole word
                pattern = r'\b' + re.escape(query_lower) + r'\b'
                for phrase_data in all_phrase_results:
                    meanings = phrase_data.get('meanings', '')
                    if isinstance(meanings, str) and re.search(pattern, meanings.lower()):
                        # Avoid duplicates from pinyin search
                        if not any(p.get('word') == phrase_data.get('word') for p in phrase_results):
                            phrase_results.append(phrase_data)
                    if isinstance(meanings, str) and re.search(pattern, meanings.lower()):
                        # Avoid duplicates from pinyin search
                        if not any(p.get('word') == phrase_data.get('word') for p in phrase_results):
                            phrase_results.append(phrase_data)

        # Combine results: pinyin matches first, then English matches
        results = pinyin_results + english_results

        # Display Results
        if not results and not phrase_results:
            st.info(f"No matches found for '{query}'.")
        else:
            # Show character results
            if results:
                st.success(f"Found {len(results)} character matches.")
                st.markdown("<div class='comp-grid'>", unsafe_allow_html=True)
                
                # Pagination for search results if too many (limit to first 100 for speed)
                display_results = results[:100]
                
                cols = st.columns(GRID_COLUMNS)
                for i, ch in enumerate(display_results):
                    with cols[i % GRID_COLUMNS]:
                        st.button(
                            ch,
                            key=f"{key_prefix}smart_res_{ch}_{i}",
                            type="primary" if state.get_preview_component() == ch else "secondary",
                            on_click=_search_pick_char,
                            args=(ch,),
                            kwargs={
                                "key_prefix": key_prefix,
                                "on_pick": on_pick,
                                "collapse_after_pick": collapse_after_pick,
                            },
                            use_container_width=True,
                        )
                st.markdown("</div>", unsafe_allow_html=True)
                
                if len(results) > 100:
                    st.caption(f"Showing first 100 of {len(results)} results.")
            
            # Show phrase results
            if phrase_results:
                st.markdown("---")
                st.success(f"Found {len(phrase_results)} phrase matches.")
                st.markdown("<div style='max-width:900px; margin:0 auto;'>", unsafe_allow_html=True)
                for phrase_data in phrase_results[:50]:  # Limit to 50 phrases
                    phrase_word = phrase_data['word']
                    st.markdown(f"<div class='compound-item' style='margin-bottom:15px; cursor:pointer;'><span class='cp-word' style='font-size:1.4em;'>{phrase_word}</span><span class='cp-pinyin'>{phrase_data['pinyin']}</span><span class='cp-mean'>{pyhtml.escape(phrase_data['meanings'][:200] + ('...' if len(phrase_data['meanings']) > 200 else ''))}</span></div>", unsafe_allow_html=True)
                    
                    # Show clickable characters from this phrase
                    chars_in_phrase = [c for c in phrase_word if c in component_map]
                    if chars_in_phrase:
                        cols = st.columns(len(chars_in_phrase) if len(chars_in_phrase) <= 8 else 8)
                        for i, ch in enumerate(chars_in_phrase[:8]):
                            with cols[i]:
                                st.button(
                                    ch,
                                    key=f"{key_prefix}phrase_result_{phrase_word}_{ch}_{i}",
                                    type="secondary",
                                    on_click=_search_pick_char,
                                    args=(ch,),
                                    kwargs={
                                        "key_prefix": key_prefix,
                                        "on_pick": on_pick,
                                        "collapse_after_pick": collapse_after_pick,
                                    },
                                    use_container_width=True,
                                )
                
                st.markdown("</div>", unsafe_allow_html=True)
                if len(phrase_results) > 50:
                    st.caption(f"Showing first 50 of {len(phrase_results)} phrase results.")

def render_all_components_grid():
    st.markdown("<div style='background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 25px;'>", unsafe_allow_html=True)
    
    # Row 1: Sort and Script
    col_sort, col_script = st.columns([1, 1])
    with col_sort:
        sort_choice = st.radio("Sort by", options=["Component frequency", "Character frequency"], index=0 if state.get_grid_sort_mode() == "usage" else 1, horizontal=True, key="grid_sort_radio")
        state.set("grid_sort_mode", "usage" if "Component" in sort_choice else "frequency")
    
    with col_script:
        if state.get_grid_sort_mode() == "frequency":
            gsf = state.get("grid_script_filter", "Any")
            script_choice = st.radio("Script", options=["Simplified", "Traditional", "Any"], index=["Simplified", "Traditional", "Any"].index(gsf), horizontal=True, key="grid_script_radio")
            state.set("grid_script_filter", script_choice)
    
    # Row 2: Filters
    col_stroke, col_radical, col_idc = st.columns([2, 2, 2])
    
    with col_stroke:
        stroke_range = st.slider("Strokes", 1, 30, value=state.get_stroke_range(), key="grid_stroke_slider")
        state.set("stroke_range", stroke_range)
    
    with col_radical:
        rad_groups = stats_cache.get("rad_groups", {})
        radical_options = ["none"]
        for stroke_count in sorted(rad_groups.keys()):
            rads_in_group = rad_groups[stroke_count]
            if rads_in_group:
                for rad in rads_in_group:
                    radical_options.append(rad)
        
        def format_radical(rad):
            if rad == "none": return "none"
            rad_info = component_map.get(rad, {})
            strokes = rad_info.get('stroke_count')
            if strokes: return f"{rad} ({strokes} strokes)"
            return rad
        
        current_rad = state.get("radical", "none")
        current_index = radical_options.index(current_rad) if current_rad in radical_options else 0
        radical_choice = st.selectbox("Radical", options=radical_options, format_func=format_radical, index=current_index, key="grid_radical_select")
        state.set("radical", radical_choice)
    
    with col_idc:
        idcs = sorted(stats_cache.get("idc_counts", {}).keys())
        idc = state.get("component_idc", "none")
        idc_choice = st.selectbox("Structure", options=["none"] + idcs, index=(["none"] + idcs).index(idc) if idc in idcs else 0, key="grid_idc_select")
        state.set("component_idc", idc_choice)
    
    st.markdown("</div>", unsafe_allow_html=True)

    # Filter Logic
    cur_min, cur_max = state.get_stroke_range()
    
    filtered = [c for c in component_map if (s := get_stroke_count(c)) is not None and cur_min <= s <= cur_max]
    
    if state.get("radical") != "none":
        filtered = [c for c in filtered if component_map[c]["meta"].get("radical") == state.get("radical")]
    
    if state.get("component_idc") != "none":
        filtered = [c for c in filtered if component_map[c]["meta"].get("decomposition", "").startswith(state.get("component_idc"))]
    
    if state.get_grid_sort_mode() == "usage":
         filtered = [c for c in filtered if c in stats_cache["used_components"]]
    
    if state.get_grid_sort_mode() == "frequency":
        filtered = apply_script_filter(filtered, state.get("grid_script_filter"))
    
    sorted_comps = sorted(filtered, key=sort_key_frequency_primary if state.get_grid_sort_mode() == "frequency" else sort_key_usage_primary)

    if not sorted_comps:
        st.info("No components match filters.")
        return

    # Pagination
    total = len(sorted_comps)
    max_page = max(1, math.ceil(total / PAGE_SIZE))
    page = max(1, min(state.get_current_page(), max_page))
    state.set("page", page)
    
    p1, p2, p3 = st.columns([1, 3, 1])
    with p1:
        if st.button("◀ Prev", disabled=page <= 1, use_container_width=True, key="grid_prev"):
            state.set("page", page - 1)
            st.rerun()
    with p2:
        st.markdown(f"<div style='text-align:center; padding:10px 0; color:#555;'><div style='font-size:1.1em; font-weight:bold;'>{(page - 1) * PAGE_SIZE + 1}–{min(page * PAGE_SIZE, total)} of {total}</div></div>", unsafe_allow_html=True)
    with p3:
        if st.button("Next ▶", disabled=page >= max_page, use_container_width=True, key="grid_next"):
            state.set("page", page + 1)
            st.rerun()

    # Tiles
    st.markdown("<div class='comp-grid'>", unsafe_allow_html=True)
    cols = st.columns(GRID_COLUMNS)
    for i, ch in enumerate(sorted_comps[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]):
        with cols[i % GRID_COLUMNS]:
            st.button(ch, key=f"grid_{ch}_{page}", type="primary" if state.get_preview_component() == ch else "secondary", on_click=tile_click, args=(ch,), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_favourites_grid():
    favs = state.get_favourites()
    if not favs:
        st.info("No favourites yet. Click the ⭐ button in the sidebar to add characters.")
        return

    st.markdown(f"### {len(favs)} Favourites")
    
    with st.expander("📝 Edit Favourites List", expanded=False):
        fav_txt = st.text_area("Edit (space/newline separated)", value=" ".join(favs), height=90, key="fav_bulk_editor")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Apply", use_container_width=True, key="fav_apply"):
                tokens = [t for t in re.split(r"\s+", (fav_txt or "").strip()) if t]
                cleaned = []
                seen = set()
                for c in [t for t in tokens if len(t) == 1]:
                    if c not in seen:
                        cleaned.append(c)
                        seen.add(c)
                state.set("favourites_list", cleaned)
                st.toast("Favourites updated.", icon="✅")
                st.rerun()
        with c2:
            if st.button("Clear All", use_container_width=True, key="fav_clear"):
                state.set("favourites_list", [])
                st.toast("Cleared.", icon="✅")
                st.rerun()

    st.markdown("<div class='comp-grid'>", unsafe_allow_html=True)
    cols = st.columns(GRID_COLUMNS)
    for i, ch in enumerate(favs):
        with cols[i % GRID_COLUMNS]:
            st.button(ch, key=f"fav_{ch}_{i}", type="primary" if state.get_preview_component() == ch else "secondary", on_click=tile_click, args=(ch,), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_definition_search_results():
    """Render the results of an English definition search (Legacy Sidebar)."""
    results = state.get("definition_search_results")
    if not results:
        st.error("No results state found.")
        return

    st.markdown(f"<div style='font-size:1.2em; font-weight:700; margin-bottom:20px;'>Search Results for \"{pyhtml.escape(state.get('definition_search_query'))}\"</div><div style='font-size:0.85em; color:#666; margin-bottom:20px;'>Found {len(results['characters'])} characters and {len(results['phrases'])} phrases</div>", unsafe_allow_html=True)
    
    if results['characters']:
        st.markdown("<div class='lineage-header'>📖 Characters</div>", unsafe_allow_html=True)
        for char in results['characters'][:30]:
            render_radix_row(char)
    
    if results['phrases']:
        st.markdown("<div class='lineage-header'>💬 Phrases</div>", unsafe_allow_html=True)
        st.markdown("<div style='max-width:900px; margin:0 auto;'>", unsafe_allow_html=True)
        for phrase_data in results['phrases']:
            st.markdown(f"<div class='compound-item' style='margin-bottom:15px;'><span class='cp-word' style='font-size:1.4em;'>{phrase_data['word']}</span><span class='cp-pinyin'>{phrase_data['pinyin']}</span><span class='cp-mean'>{pyhtml.escape(phrase_data['meanings'][:200] + ('...' if len(phrase_data['meanings']) > 200 else ''))}</span></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    if not results['characters'] and not results['phrases']:
        st.info(f"No results found for '{state.get('definition_search_query')}'. Try different search terms.")

def render_lineage():
    """Render the lineage/list view."""
    sel = state.get_selected_component()
    info = component_map.get(sel, {})
    
    # Filter
    st.markdown("<div style='background: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    script_choice = st.radio("Filter Results", options=SCRIPT_FILTERS, index=SCRIPT_FILTERS.index(state.get_script_filter()), horizontal=True, key="lineage_script_filter")
    state.set("script_filter", script_choice)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Parents
    decomp = info.get("meta", {}).get("decomposition", "")
    parents = [p for p in decomp if p in component_map and p not in IDC_CHARS and p not in ["?", "—"] and p != sel]
    parents = apply_script_filter(parents, state.get_script_filter())
    
    if parents:
        st.markdown("<div class='lineage-header'>🧱 Components (How it's built)</div>", unsafe_allow_html=True)
        for p in parents:
            render_radix_row(p)

    # Current
    st.markdown("<div class='lineage-header'>🎯 Current Selection</div>", unsafe_allow_html=True)
    focus_group = [sel]
    if cc_t2s and cc_s2t:
        s_cand, t_cand = cc_t2s.convert(sel), cc_s2t.convert(sel)
        variant = s_cand if s_cand != sel else t_cand
        if variant != sel and variant in component_map:
            focus_group.append(variant)
    for f in apply_script_filter(focus_group, state.get_script_filter()):
        render_radix_row(f)

    # Children
    rel = info.get("related_characters", [])
    children = [c for c in rel if isinstance(c, str) and len(c) == 1 and c in component_map and c != sel]

    if children:
        visible_children = apply_script_filter(sorted(children, key=sort_key_usage_primary), state.get_script_filter())
        unique_visible = list(dict.fromkeys(visible_children))
        BATCH_SIZE, total_derivs = 25, len(unique_visible)
        
        current_page = min(state.get("derivative_page", 0), max(0, math.ceil(total_derivs / BATCH_SIZE) - 1))
        start_idx = current_page * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total_derivs)
        current_batch = unique_visible[start_idx:end_idx]

        st.markdown(f"<div class='lineage-header'>🌲 Derivatives (Used in {total_derivs} characters)</div>", unsafe_allow_html=True)
        
        nav_c1, nav_c2, nav_c3 = st.columns([1, 2, 1])
        with nav_c1:
            if current_page > 0:
                if st.button("⬅️ Prev 25", key="deriv_prev", use_container_width=True):
                    state.set("derivative_page", current_page - 1)
                    st.rerun()
        with nav_c2:
            st.markdown(f"<div style='text-align:center; padding:8px; font-weight:600; color:#666;'>Batch {current_page + 1} · {start_idx + 1}–{end_idx}</div>", unsafe_allow_html=True)
        with nav_c3:
            if end_idx < total_derivs:
                if st.button("Next 25 ➡️", key="deriv_next", use_container_width=True):
                    state.set("derivative_page", current_page + 1)
                    st.rerun()
        
        chars_html = "".join([f"<span style='display:inline-block; margin: 2px 6px; font-size: 1.4em; font-weight: bold; color: #444;'>{c}</span>" for c in current_batch])
        st.markdown(f"""<div style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 12px; padding: 15px; margin-bottom: 20px; text-align: center;"><div style="font-size: 0.85em; color: #888; margin-bottom: 8px; text-transform: uppercase; font-weight: 700;">Visible in this batch</div><div style="line-height: 1.6;">{chars_html}</div></div>""", unsafe_allow_html=True)
        
        for child in current_batch:
            render_radix_row(child, minimal=True)

def render_ai_link():
    """Render the AI Link / Stroke View."""
    char = state.get("stroke_view_char")
    
    st.markdown("### Stroke Order Animation")
    main_html, _ = get_stroke_order_view_html(char, state.get_display_mode())
    st_html(main_html, height=450)
    
    # Insights
    insights_result = render_learning_insights_html(char)
    if isinstance(insights_result, tuple):
        if len(insights_result) == 3:
            insights_html, insights_height, prompt_text = insights_result
        elif len(insights_result) == 2:
            insights_html, insights_height = insights_result
            prompt_text = None
        else:
            insights_html, insights_height, prompt_text = None, 0, None
            
        if insights_html:
            st_html(insights_html, height=insights_height)
        if prompt_text:
            st.markdown("---")
            st.markdown("**🤖 Verify Logic & Patterns with AI**")
            render_copy_to_clipboard(prompt_text, f"verify_{char}")
    
    # Phrases
    if state.get_display_mode() != "Single Character":
        if phrase_html := _render_phrase_html(char):
            st.markdown(phrase_html, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ChatGPT Prompt")
    
    # Prompt Config
    config.normalize_prompt_state()
    cfg = state.get("prompt_config")
    tasks = cfg.get("tasks", []) or []
    all_task_ids = [t.get("id") for t in tasks if t.get("id")]
    
    cur_sel = [tid for tid in (state.get("prompt_selected_task_ids") or []) if tid in all_task_ids]
    if not cur_sel:
        cur_sel = list(state.get("prompt_ui").get("default_selected_task_ids", all_task_ids)) or list(all_task_ids)
    state.set("prompt_selected_task_ids", cur_sel)

    with st.expander("Prompt tasks (choose what to include)", expanded=False):
        if st.button("Select all tasks", key="select_all_prompt_tasks"):
            state.set("prompt_selected_task_ids", list(all_task_ids))
            for tid in all_task_ids:
                state.state[f"prompt_task_cb_{tid}"] = True
            st.rerun()
        sel = []
        for t in tasks:
            tid = t.get("id", "")
            if tid and st.checkbox(t.get("title", tid), key=f"prompt_task_cb_{tid}"):
                sel.append(tid)
        state.set("prompt_selected_task_ids", sel)

    prompt_text = render_combined_prompt(
        char=char,
        prompt_config=state.get("prompt_config"),
        selected_task_ids=state.get("prompt_selected_task_ids"),
        definition_en=get_char_definition_en(char)
    )
    st.text_area("Copy this prompt into ChatGPT", value=prompt_text, height=320, label_visibility="collapsed")
    render_copy_to_clipboard(prompt_text, str(hash(char)))


# ==================== MAIN ====================

def main():
    if not component_map:
        st.error("Component dataset not loaded.")
        st.stop()

    # Initialize
    state.initialize()
    config.load_server_data()
    config.initialize_prompt_config()
    
    # AUTO-LOAD user data file if present (NEW!)
    auto_load_user_data()

    # Layout
    render_sidebar()

    # Routing
    if state.get("dataset_editor_mode", False):
        render_dataset_editor()
    elif state.is_stroke_view_active():
        render_ai_link()
    elif state.is_definition_search_active():
        render_definition_search_results()
    elif state.is_showing_inputs():
        render_grid()
    else:
        render_lineage()
    
if __name__ == "__main__":
    main()
