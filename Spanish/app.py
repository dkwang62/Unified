# app.py (v13.0 - Streamlit Cloud Compatible)
# Browser-based storage with JSON download/upload for persistence

import streamlit as st
import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime

from spanish_core import (
    load_jehle_db, load_overrides, save_overrides,
    load_frequency_map, sorted_infinitives, search_verbs,
    get_verb_record, merge_usage, load_templates, render_prompt,
    get_taxonomy_map,
    # Browser storage functions
    init_user_data_in_session, toggle_favourite, is_favourite,
    export_user_data_json, import_user_data_from_json, merge_favourites
)
from spanish_state import PAGE_CONFIG, ensure_state, click_tile, back_to_grid
from spanish_ui import apply_styles, build_verb_card_html
from datafile_editor import render_datafile_editor

DB_JSON = "jehle_verb_database.json"
LOOKUP_JSON = "jehle_verb_lookup_index.json"
FREQ_JSON = "verb_frequency_rank.json" 
OVERRIDES_JSON = "verb_overrides.json"
VERBS_CAT_JSON = "verbs_categorized.json"

st.set_page_config(**PAGE_CONFIG)
apply_styles()
ensure_state()

verbs, lookup = load_jehle_db(DB_JSON, LOOKUP_JSON)
rank_map = load_frequency_map(FREQ_JSON)
overrides = load_overrides(OVERRIDES_JSON)
templates_map = load_templates(VERBS_CAT_JSON)

# Initialize user data in session (browser-based)
user_data = init_user_data_in_session()

# --- Helper to load Guide from the Main JSON ---
@st.cache_data
def load_guide_content(path: str):
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("reference_guide")

guide_content = load_guide_content(VERBS_CAT_JSON)

# Fetch state vars
mode = st.session_state.get("mode", "grid")
preview_inf = st.session_state.get("preview")
selected_inf = st.session_state.get("selected")

st.title("Spanish Verb Lab")

# ==========================================
# 🛠️ SIDEBAR: NAVIGATION & CONTROLS
# ==========================================
with st.sidebar:
    st.header("Navigation")
    if mode == "grid":
        st.markdown("🏠 **Home / Grid**")
    elif mode == "editor":
        st.markdown("🏠 Home › **Data Editor**")
    else:
        st.markdown(f"🏠 Home › **{selected_inf}**")

    if mode == "grid":
        if preview_inf:
            if st.button(f"Open '{preview_inf}' Details ➡", use_container_width=True, type="primary"):
                st.session_state["selected"] = preview_inf
                st.session_state["mode"] = "detail"
                st.rerun()
        else:
            st.button("Select a verb to preview...", disabled=True, use_container_width=True)
            
    elif mode == "detail":
        if st.button("⬅ Back to Verb Grid", use_container_width=True, type="primary"):
            back_to_grid()
            st.rerun()
    elif mode == "editor":
        if st.button("⬅ Back to Verb Grid", use_container_width=True, type="primary"):
            st.session_state["mode"] = "grid"
            st.rerun()

    if mode != "editor":
        if st.button("🛠️ Open Data Editor", use_container_width=True):
            st.session_state["mode"] = "editor"
            st.rerun()

    st.divider()

    show_vos = True
    show_vosotros = True
    if mode != "editor":
        # ⭐ FAVOURITES MANAGEMENT SECTION
        st.subheader("⭐ My Favourites")
        fav_count = len(user_data.get("favourites", []))
        
        if fav_count > 0:
            st.caption(f"{fav_count} favourite{'s' if fav_count != 1 else ''} saved")
            
            # Download button
            json_data = export_user_data_json()
            st.download_button(
                label="📥 Download Favourites",
                data=json_data,
                file_name=f"spanish_verb_favourites_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True,
                help="Download your favourites as JSON to save permanently"
            )
            
            # Clear all favourites
            if st.button("🗑️ Clear All Favourites", use_container_width=True, type="secondary"):
                if st.session_state.get("confirm_clear"):
                    user_data["favourites"] = []
                    st.session_state["user_data"] = user_data
                    st.session_state["confirm_clear"] = False
                    st.toast("All favourites cleared!", icon="🗑️")
                    st.rerun()
                else:
                    st.session_state["confirm_clear"] = True
                    st.warning("⚠️ Click again to confirm")
                    st.rerun()
        else:
            st.caption("No favourites yet")
        
        # Upload favourites
        with st.expander("📤 Upload Favourites", expanded=False):
            st.caption("Upload a previously downloaded JSON file")
            uploaded_file = st.file_uploader(
                "Choose JSON file",
                type=["json"],
                label_visibility="collapsed",
                key="favourites_upload"
            )
            
            if uploaded_file is not None:
                try:
                    json_str = uploaded_file.read().decode("utf-8")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Replace", use_container_width=True, help="Replace all current favourites"):
                            if import_user_data_from_json(json_str):
                                st.success("✅ Favourites imported!")
                                st.rerun()
                            else:
                                st.error("❌ Invalid JSON file")
                    
                    with col2:
                        if st.button("Merge", use_container_width=True, help="Add to existing favourites"):
                            try:
                                data = json.loads(json_str)
                                new_favs = data.get("favourites", [])
                                merge_favourites(new_favs)
                                st.success("✅ Favourites merged!")
                                st.rerun()
                            except:
                                st.error("❌ Invalid JSON file")
                                
                except Exception as e:
                    st.error(f"Error reading file: {e}")
        
        st.divider()

        st.subheader("Search")
        if "search_query" not in st.session_state:
            st.session_state["search_query"] = ""
        if "search_input" not in st.session_state:
            st.session_state["search_input"] = ""

        search_cols = st.columns([0.85, 0.15])
        with search_cols[0]:
            search_text = st.text_input(
                "Search",
                value=st.session_state["search_input"],
                placeholder="hablar / speak",
                label_visibility="collapsed",
            )
        with search_cols[1]:
            if st.button("🔍", help="Search", use_container_width=True):
                st.session_state["search_query"] = search_text.strip()
                st.session_state["search_input"] = ""
                st.rerun()

        st.session_state["search_input"] = search_text

        if st.button("Clear search", use_container_width=True):
            st.session_state["search_query"] = ""
            st.rerun()

        st.divider()

        if mode == "grid":
            st.subheader("Preview")
            if preview_inf:
                v = get_verb_record(verbs, lookup, preview_inf)
                if v:
                    v = merge_usage(v, overrides)
                    rank = rank_map.get(preview_inf.lower())
                    st.markdown(build_verb_card_html(v, rating=None, freq_rank=rank), unsafe_allow_html=True)
                    
                    # ⭐ FAVOURITE TOGGLE IN PREVIEW
                    is_fav = is_favourite(preview_inf)
                    fav_label = "⭐ Remove from Favourites" if is_fav else "☆ Add to Favourites"
                    fav_help = "Click to remove this verb from your favourites" if is_fav else "Click to add this verb to your favourites"
                    
                    if st.button(fav_label, use_container_width=True, help=fav_help):
                        toggle_favourite(preview_inf)
                        action = "removed from" if is_fav else "added to"
                        st.toast(f"**{preview_inf}** {action} favourites!", icon="⭐" if not is_fav else "☆")
                        st.rerun()
            else:
                st.caption("Click a tile to preview.")
            st.divider()

        st.subheader("Display Settings")
        show_vos = st.checkbox("Show 'vos' (voseo)", value=True)
        show_vosotros = st.checkbox("Show 'vosotros'", value=True)


# ==========================================
# 🛠️ MAIN AREA
# ==========================================

if mode == "editor":
    render_datafile_editor(show_title=False, use_sidebar=False)
elif mode == "grid":
    st.info("💡 **Tip:** Click a tile to **preview** in the sidebar. Click the **same tile again** (or the sidebar button) to open details.", icon="ℹ️")

    sort_option = st.radio(
        "Sort Order",
        options=["Alphabetical", "ar/er/ir/se", "By Category", "Popularity", "⭐ Favourites"], 
        index=0, 
        horizontal=True,
        label_visibility="collapsed"
    )

    def _rank(inf: str) -> int:
        return rank_map.get(inf.lower(), 10_000_000)

    def build_list() -> list[str]:
        q = st.session_state.get("search_query", "")
        if q.strip():
            results = search_verbs(verbs, q, limit=5000)
            base = [r["infinitive"] for r in results if r.get("infinitive")]
        else:
            base = [v["infinitive"] for v in verbs if v.get("infinitive")]
        base = list(dict.fromkeys(base))
        if sort_option == "Popularity":
            base.sort(key=lambda inf: (_rank(inf), inf))
            return base
        return sorted(base, key=lambda x: x.lower())

    base_list = build_list()

    def render_tiles(infs: list[str], per_row: int = 6, max_items: int = 240):
        """Render verb tiles with ⭐ indicator for favourites"""
        infs = infs[:max_items]
        for i in range(0, len(infs), per_row):
            row = infs[i:i+per_row]
            cols = st.columns(per_row)
            for j, inf in enumerate(row):
                # Add ⭐ to favourites
                is_fav = is_favourite(inf)
                label = f"⭐ {inf}" if is_fav else inf
                
                is_preview = (st.session_state.get("preview") == inf)
                btn_type = "primary" if is_preview else "secondary"
                cols[j].button(
                    label,
                    key=f"tile_{inf}",
                    use_container_width=True,
                    type=btn_type,
                    on_click=click_tile,
                    args=(inf,),
                )

    # ⭐ FAVOURITES VIEW
    if sort_option == "⭐ Favourites":
        favourites = user_data.get("favourites", [])
        if favourites:
            # Filter to only favourites that exist in current search/base list
            fav_verbs = [inf for inf in favourites if inf in base_list]
            
            if fav_verbs:
                st.subheader(f"⭐ Your Favourites ({len(fav_verbs)} verb{'s' if len(fav_verbs) != 1 else ''})")
                
                # Show tip with download reminder
                st.info("💡 **Tip:** Download your favourites using the sidebar button to save them permanently!", icon="💾")
                
                render_tiles(fav_verbs, max_items=600)
                
                # Show removed favourites if search is active
                if st.session_state.get("search_query", "").strip():
                    removed = [inf for inf in favourites if inf not in base_list]
                    if removed:
                        with st.expander(f"🔍 {len(removed)} favourite{'s' if len(removed) != 1 else ''} hidden by search"):
                            st.caption(", ".join(removed))
            else:
                st.warning("Your favourites are not in the current search results. Clear your search to see all favourites.")
        else:
            st.info("⭐ **You haven't added any favourites yet!**\n\n**To add favourites:**\n1. Click a verb tile to preview it\n2. Click the '☆ Add to Favourites' button in the sidebar\n\n**To save permanently:**\n- Use the '📥 Download Favourites' button in the sidebar\n- Save the JSON file to your computer or GitHub\n- Upload it later using '📤 Upload Favourites'", icon="💡")

    elif sort_option == "ar/er/ir/se":
        ar = sorted([inf for inf in base_list if inf.lower().endswith("ar")], key=lambda x: x.lower())
        er = sorted([inf for inf in base_list if inf.lower().endswith("er")], key=lambda x: x.lower())
        ir = sorted([inf for inf in base_list if inf.lower().endswith(("ir", "ír"))], key=lambda x: x.lower())
        other = sorted([inf for inf in base_list if not inf.lower().endswith(("ar", "er", "ir", "ír"))], key=lambda x: x.lower())

        st.subheader("-ar verbs")
        render_tiles(ar)
        st.divider()
        st.subheader("-er verbs")
        render_tiles(er)
        st.divider()
        st.subheader("-ir verbs")
        render_tiles(ir)
        if other:
            st.divider()
            st.subheader("Other")
            render_tiles(other)

    elif sort_option == "By Category":
        taxonomy_map = get_taxonomy_map()
        grouped = defaultdict(lambda: defaultdict(list))
        standard = []
        
        for inf in base_list:
            meta = taxonomy_map.get(inf.lower())
            if meta:
                grouped[meta['root']][meta['sub']].append(inf)
            else:
                standard.append(inf)
        
        root_order = [
            "🧠 Experiencer (Gustar-like)",
            "💥 Accidental Se (Se me...)",
            "🪞 Reflexive (Self-directed)",
            "🔄 Pronominal (Meaning Shift)"
        ]
        
        for root in root_order:
            if root in grouped:
                st.header(root)
                sub_groups = grouped[root]
                for sub in sorted(sub_groups.keys()):
                    st.markdown(f"#### {sub}")
                    render_tiles(sorted(sub_groups[sub]))
                st.divider()
                del grouped[root]
        
        for root, sub_groups in grouped.items():
            st.header(root)
            for sub in sorted(sub_groups.keys()):
                st.markdown(f"#### {sub}")
                render_tiles(sorted(sub_groups[sub]))
            st.divider()
            
        if standard:
            st.header("Standard / Other")
            render_tiles(standard)

    else:
        # Alphabetical or Popularity
        render_tiles(base_list, max_items=600)

else:
    # --- DETAIL VIEW ---
    if not selected_inf:
        st.warning("No verb selected.")
        st.stop()

    v = get_verb_record(verbs, lookup, selected_inf)
    if not v:
        st.error("Verb not found.")
        st.stop()

    v = merge_usage(v, overrides)
    
    # ⭐ HEADER WITH FAVOURITE TOGGLE
    col1, col2 = st.columns([0.88, 0.12])
    with col1:
        st.markdown(f"## 🔹 Verb: **{selected_inf.upper()}**")
    with col2:
        is_fav = is_favourite(selected_inf)
        fav_icon = "⭐" if is_fav else "☆"
        fav_help = "Remove from favourites" if is_fav else "Add to favourites"
        
        if st.button(fav_icon, help=fav_help, use_container_width=True, type="primary" if is_fav else "secondary"):
            toggle_favourite(selected_inf)
            action = "removed from" if is_fav else "added to"
            st.toast(f"**{selected_inf}** {action} favourites!", icon=fav_icon)
            st.rerun()
    
    tabs = st.tabs(["Conjugations", "Prompt generator", "📘 Guide"])
    
    with tabs[0]:
        from spanish_ui import render_conjugation_dashboard
        render_conjugation_dashboard(v, show_vos=show_vos, show_vosotros=show_vosotros)

    with tabs[1]:
        template_id = st.selectbox(
            "Template",
            options=list(templates_map.keys()),
            format_func=lambda k: f"{templates_map[k]['name']} ({k})"
        )
        prompt = render_prompt(template_id, v)
        st.subheader("Generated AI Prompt")
        st.code(prompt, language="text")

    with tabs[2]:
        if guide_content:
            st.header(guide_content.get("title", "Guide"))
            st.info(guide_content.get("summary", ""))
            
            for section in guide_content.get("sections", []):
                with st.expander(section.get("heading", "Section"), expanded=False):
                    
                    for point in section.get("points", []):
                        st.markdown(f"- {point}")
                    
                    if "rule" in section:
                        st.markdown(f"**Rule:** {section['rule']}")

                    examples = section.get("examples") or section.get("mini_examples")
                    if examples:
                        st.markdown("---")
                        st.markdown("**Examples:**")
                        for ex in examples:
                            if "base" in ex:
                                st.markdown(f"- **{ex['base']}** → **{ex['with_se']}**: {ex.get('se_meaning_en', '')}")
                            elif "paraphrase" in ex:
                                st.markdown(f"- *{ex['spanish']}* → {ex['paraphrase']} ({ex.get('note', '')})")
                            elif "spanish" in ex:
                                st.markdown(f"- {ex['spanish']} ({ex.get('en', '')})")
        else:
            st.warning("Guide content not found in verbs_categorized.json.")
