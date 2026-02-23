# spanish_core.py (v12.0)
# Core: Jehle DB + Pronominal JSON + Prompts + Se Classification
# Updated: render_prompt() now detects if input is already reflexive to avoid 'hacersese'

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import streamlit as st

VERBS_CAT_JSON = "verbs_categorized.json"

@st.cache_data(show_spinner=False)
def load_jehle_db(db_json_path: str, lookup_json_path: str) -> Tuple[List[dict], Dict[str, int]]:
    with open(db_json_path, "r", encoding="utf-8") as f:
        verbs = json.load(f)
    with open(lookup_json_path, "r", encoding="utf-8") as f:
        lookup = json.load(f)
    lookup = {k.lower(): int(v) for k, v in lookup.items()}
    return verbs, lookup

@st.cache_data(show_spinner=False)
def load_se_catalog(path: str = VERBS_CAT_JSON) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

@st.cache_data(show_spinner=False)
def get_taxonomy_map(json_path: str = VERBS_CAT_JSON) -> Dict[str, Dict[str, str]]:
    data = load_se_catalog(json_path)
    taxonomy = data.get("verb_taxonomy", {})
    mapping = {}

    root_names = {
        "reflexive": "🪞 Reflexive (Self-directed)",
        "pronominal": "🔄 Pronominal (Meaning Shift)",
        "accidental_dative": "💥 Accidental Se (Se me...)",
        "experiencer": "🧠 Experiencer (Gustar-like)"
    }

    for root_key, root_data in taxonomy.items():
        root_label = root_names.get(root_key, root_key.title())
        categories = root_data.get("categories", {})
        
        for sub_key, sub_data in categories.items():
            sub_label = sub_key.replace("_", " ").title()
            verbs_dict = sub_data.get("verbs", {})
            for base, val in verbs_dict.items():
                if isinstance(val, dict):
                    pron = val.get("form", "") or val.get("related_pronominal", "")
                else:
                    pron = val
                
                if base:
                    mapping[base.lower()] = {"root": root_label, "sub": sub_label}
                if pron:
                    mapping[pron.lower()] = {"root": root_label, "sub": sub_label}
                    
    return mapping

@st.cache_data(show_spinner=False)
def load_verb_seeds(json_path: str = VERBS_CAT_JSON) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], List[str]]:
    data = load_se_catalog(json_path)
    taxonomy = data.get("verb_taxonomy", {})
    
    def _flatten_categories(root_key: str) -> Dict[str, str]:
        flat_map = {}
        cats = taxonomy.get(root_key, {}).get("categories", {})
        for cat_name, content in cats.items():
            for base, val in content.get("verbs", {}).items():
                if isinstance(val, dict):
                    pron = val.get("form", "")
                else:
                    pron = val
                if pron:
                    flat_map[base.lower()] = pron
        return flat_map

    reflexive_flat = _flatten_categories("reflexive")
    pronominal_flat = _flatten_categories("pronominal")
    accidental_flat = _flatten_categories("accidental_dative")
    
    experiencer_set = set()
    exp_cats = taxonomy.get("experiencer", {}).get("categories", {})
    for _, content in exp_cats.items():
        for base in content.get("verbs", {}).keys():
            experiencer_set.add(base.lower())
    
    return reflexive_flat, pronominal_flat, accidental_flat, list(experiencer_set)

@st.cache_data(show_spinner=False)
def load_templates(json_path: str = VERBS_CAT_JSON) -> Dict[str, dict]:
    data = load_se_catalog(json_path)
    raw_templates = data.get("templates", {})
    processed = {}
    for key, val in raw_templates.items():
        processed[key] = {
            "name": val.get("name", key),
            "prompt": "\n".join(val.get("prompt", [])) if isinstance(val.get("prompt"), list) else val.get("prompt", "")
        }
    return processed


def classify_se_type(infinitive: str, pronominal_infinitive: str | None, se_catalog: dict) -> str | None:
    inf = infinitive.lower()
    taxonomy = se_catalog.get("verb_taxonomy", {})
    
    def _get_set(root_key, use_values=True):
        s = set()
        cats = taxonomy.get(root_key, {}).get("categories", {})
        for _, content in cats.items():
            for val in content.get("verbs", {}).values():
                if isinstance(val, dict):
                    target = val.get("form", "") if use_values else val
                else:
                    target = val
                if use_values:
                    s.add(target.lower())
            if not use_values:
                for k in content.get("verbs", {}).keys():
                    s.add(k.lower())
        return s

    exp_all = _get_set("experiencer", use_values=False)
    if inf in exp_all:
        return "experiencer"

    if not pronominal_infinitive:
        return None

    pro = pronominal_infinitive.lower()
    acc_all = _get_set("accidental_dative", use_values=True)
    ref_all = _get_set("reflexive", use_values=True)
    pro_all = _get_set("pronominal", use_values=True)

    if pro in acc_all:
        return "accidental_dative"
    if pro in ref_all:
        return "reflexive"
    if pro in pro_all:
        return "pronominal"
    
    return None


def _starter_overrides() -> Dict[str, dict]:
    return {
        "lavar": {"is_pronominal": True, "pronominal_infinitive": "lavarse", "se_type": "reflexive", "meaning_shift": "subject washes self"},
        "ir": {"is_pronominal": True, "pronominal_infinitive": "irse", "se_type": "pronominal", "meaning_shift": "departure / leaving"},
        "caer": {"is_pronominal": True, "pronominal_infinitive": "caerse", "se_type": "accidental_dative", "meaning_shift": "fall/drop accidentally"},
        "gustar": {"is_pronominal": False, "se_type": "experiencer", "meaning_shift": "pleases (inverted subject)"}
    }


def load_overrides(overrides_path: str) -> Dict[str, dict]:
    starter = _starter_overrides()
    p = Path(overrides_path)
    if not p.exists():
        return starter
    try:
        with open(p, "r", encoding="utf-8") as f:
            user_overrides = json.load(f)
        if not isinstance(user_overrides, dict):
            return starter
        merged = dict(starter)
        for k, v in user_overrides.items():
            merged[str(k).lower()] = v
        return merged
    except Exception:
        return starter


def save_overrides(overrides_path: str, merged_overrides: Dict[str, dict]) -> None:
    starter_keys = set(_starter_overrides().keys())
    user_only = {k: v for k, v in merged_overrides.items() if k not in starter_keys}
    with open(overrides_path, "w", encoding="utf-8") as f:
        json.dump(user_only, f, ensure_ascii=False, indent=2)


@st.cache_data(show_spinner=False)
def load_frequency_map(freq_path: str) -> Dict[str, int]:
    p = Path(freq_path)
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            m = json.load(f)
        if not isinstance(m, dict):
            return {}
        out = {}
        for k, v in m.items():
            try:
                out[str(k).lower()] = int(v)
            except Exception:
                continue
        return out
    except Exception:
        return {}


def get_verb_record(verbs: List[dict], lookup: Dict[str, int], infinitive: str) -> Optional[dict]:
    idx = lookup.get(infinitive.lower())
    return verbs[idx] if idx is not None else None


def merge_usage(verb: dict, overrides: Dict[str, dict]) -> dict:
    base = (verb.get("infinitive") or "").lower()
    o = overrides.get(base, {})
    ref_seed, pron_seed, acc_seed, exp_seed_list = load_verb_seeds(VERBS_CAT_JSON)
    se_catalog = load_se_catalog(VERBS_CAT_JSON)
    
    seed_pron = pron_seed.get(base)
    seed_refl = ref_seed.get(base)

    is_pronominal = bool(o.get("is_pronominal", False))
    pronominal_inf = o.get("pronominal_infinitive")
    se_type = o.get("se_type")
    meaning_shift = o.get("meaning_shift")

    if not o:
        if seed_pron:
            is_pronominal = True
            pronominal_inf = seed_pron
            meaning_shift = "meaning shift (see category in json)"
        elif seed_refl:
            is_pronominal = True
            pronominal_inf = seed_refl
            meaning_shift = "reflexive (self-directed)"
    
    if is_pronominal and pronominal_inf:
        computed_type = classify_se_type(base, pronominal_inf, se_catalog)
        if computed_type:
            se_type = computed_type 
            if se_type == "experiencer":
                meaning_shift = "Psychological/Experiencer (IO construction)"
    elif classify_se_type(base, None, se_catalog) == "experiencer":
        se_type = "experiencer"
        meaning_shift = "Psychological/Experiencer (IO construction)"

    usage = {
        "is_pronominal": is_pronominal,
        "pronominal_infinitive": pronominal_inf,
        "se_type": se_type, 
        "meaning_shift": meaning_shift,
        "notes": o.get("notes", "")
    }

    verb2 = dict(verb)
    verb2["usage"] = usage
    if "infinitive_english" in verb2 and "gloss_en" not in verb2:
        verb2["gloss_en"] = verb2.get("infinitive_english")
    return verb2


def render_prompt(template_id: str, verb: dict) -> str:
    templates = load_templates(VERBS_CAT_JSON)
    t = templates.get(template_id)
    if not t:
        return ""
    usage = verb.get("usage", {}) or {}
    
    raw_infinitive = verb.get("infinitive", "VERB")
    usage_pron = usage.get("pronominal_infinitive")
    
    # ----------------------------------------------------
    # SMART LOGIC: Handle "hacerse" -> "hacer" vs "hacerse"
    # ----------------------------------------------------
    if usage_pron:
        pronominal = usage_pron
        # If user selected 'hacerse' (so infinitive='hacerse') and DB agrees...
        if raw_infinitive == pronominal and raw_infinitive.endswith("se"):
            # Strip 'se' to get true base for the prompt
            base_infinitive = raw_infinitive[:-2]
        else:
            base_infinitive = raw_infinitive
    else:
        # No usage data, but verb ends in 'se'?
        if raw_infinitive.endswith("se"):
            pronominal = raw_infinitive
            base_infinitive = raw_infinitive[:-2]
        else:
            base_infinitive = raw_infinitive
            pronominal = f"{raw_infinitive}se"
            
    shift = usage.get("meaning_shift") or "Standard usage"

    return t["prompt"].format(
        infinitive=base_infinitive, # Passes 'hacer' even if 'hacerse' was clicked
        pronominal_infinitive=pronominal, # Passes 'hacerse'
        meaning_shift=shift,
    )


def _matches_english(v: dict, q: str) -> bool:
    gloss = (v.get("infinitive_english") or v.get("gloss_en") or "")
    if gloss and q in gloss.lower():
        return True
    for c in (v.get("conjugations") or []):
        ve = (c.get("verb_english") or "")
        if ve and q in ve.lower():
            return True
    return False


def search_verbs(verbs: List[dict], query: str, limit: int = 2000) -> List[dict]:
    q = (query or "").strip().lower()
    if not q:
        return []
    out = []
    for v in verbs:
        inf = (v.get("infinitive") or "")
        if inf.lower().startswith(q) or _matches_english(v, q):
            out.append(v)
        if len(out) >= limit:
            break
    return out


def sorted_infinitives(verbs: List[dict], rank_map: Dict[str, int]) -> List[str]:
    infinitives = [v.get("infinitive") for v in verbs if v.get("infinitive")]
    infinitives.sort(key=lambda inf: (rank_map.get(inf.lower(), 10_000_000), inf))
    return infinitives

# ==========================================
# BROWSER-BASED USER DATA (for Streamlit Cloud)
# ==========================================

def get_default_user_data() -> dict:
    """Return default user data structure"""
    return {
        "version": 1,
        "ratings": {},
        "history": [],
        "favourites": [],
        "notes": {},
        "last_updated": None
    }


def init_user_data_in_session() -> dict:
    """
    Initialize user data in session state.
    For Streamlit Cloud: data lives only in session state (browser session)
    """
    if "user_data" not in st.session_state:
        st.session_state["user_data"] = get_default_user_data()
    return st.session_state["user_data"]


def toggle_favourite(infinitive: str) -> dict:
    """
    Add or remove a verb from favourites in session state.
    Returns updated user_data dict.
    """
    user_data = st.session_state.get("user_data", get_default_user_data())
    favourites = user_data.get("favourites", [])
    
    if infinitive in favourites:
        favourites.remove(infinitive)
    else:
        favourites.append(infinitive)
    
    user_data["favourites"] = favourites
    user_data["last_updated"] = datetime.now().isoformat()
    st.session_state["user_data"] = user_data
    return user_data


def is_favourite(infinitive: str) -> bool:
    """Check if a verb is in favourites"""
    user_data = st.session_state.get("user_data", {})
    return infinitive in user_data.get("favourites", [])


def export_user_data_json() -> str:
    """Export user data as JSON string for download"""
    user_data = st.session_state.get("user_data", get_default_user_data())
    user_data["last_updated"] = datetime.now().isoformat()
    return json.dumps(user_data, ensure_ascii=False, indent=2)


def import_user_data_from_json(json_str: str) -> bool:
    """
    Import user data from JSON string.
    Returns True if successful, False otherwise.
    """
    try:
        data = json.loads(json_str)
        
        # Validate structure
        if not isinstance(data, dict):
            return False
        
        # Ensure required keys exist
        required_keys = ["favourites", "ratings", "history", "notes"]
        for key in required_keys:
            if key not in data:
                data[key] = [] if key in ["favourites", "history"] else {}
        
        data["version"] = data.get("version", 1)
        data["last_updated"] = datetime.now().isoformat()
        
        st.session_state["user_data"] = data
        return True
        
    except json.JSONDecodeError:
        return False
    except Exception:
        return False


def merge_favourites(new_favourites: list) -> dict:
    """
    Merge new favourites with existing ones (no duplicates).
    Useful for importing favourites from GitHub without losing session data.
    """
    user_data = st.session_state.get("user_data", get_default_user_data())
    current_favs = set(user_data.get("favourites", []))
    
    for fav in new_favourites:
        current_favs.add(fav)
    
    user_data["favourites"] = sorted(list(current_favs))
    user_data["last_updated"] = datetime.now().isoformat()
    st.session_state["user_data"] = user_data
    return user_data