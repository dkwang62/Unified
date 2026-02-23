# radix_core.py
# All non-UI logic, data loading, helpers and HTML generators for Radix

import json
import math
import html
import sqlite3
import unicodedata
import gc
import base64
import json as json_module  # for dumps in HTML
from typing import List, Dict, Optional
import copy
import re

# --- Optional: OpenCC for Traditional/Simplified Conversion ---
try:
    from opencc import OpenCC
    cc_t2s = OpenCC("t2s")
    cc_s2t = OpenCC("s2t")
except ImportError:
    cc_t2s = None
    cc_s2t = None

IDC_CHARS = {"⿰", "⿱", "⿲", "⿳", "⿴", "⿵", "⿶", "⿷", "⿸", "⿹", "⿺", "⿻"}
SCRIPT_FILTERS = ["Any", "Simplified", "Traditional"]

# --- Global SUBTLEX-CH frequency dict ---
SUBTLEX_FREQ: Dict[str, float] = {}  # simplified char -> freq per million

# --- SUBTLEX-CH Frequency Badge (Percentile-Based) ---
FREQ_PERCENTILES = {
    'p95': 8500,  # Top 5%
    'p75': 3200,  # Top 25%
    'p50': 800,   # Top 50%
    'p25': 150    # Bottom 25%
}

def load_subtlex_freq():
    global SUBTLEX_FREQ
    try:
        with open("SUBTLEX-CH-CHR.txt", "r", encoding="gbk") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("Character") or line.startswith("Total"):
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                char = parts[0].strip()
                try:
                    freq_per_million = float(parts[2])
                    if freq_per_million > 0:
                        SUBTLEX_FREQ[char] = freq_per_million
                except ValueError:
                    continue
        print(f"[Radix] Loaded {len(SUBTLEX_FREQ)} characters from SUBTLEX-CH frequency list")
    except FileNotFoundError:
        print("[Radix] SUBTLEX-CH-CHR.txt not found — frequency badges disabled")
    except Exception as e:
        print(f"[Radix] Error loading SUBTLEX-CH frequencies: {e}")

# Standard radical order based on Xinhua Zidian
XINHUA_RADICAL_ORDER = [
    '一', '丨', '丿', '丶', '乙', '二', '亠', '人', '儿', '入', '八', '冂', '冖', '冫', '几', '凵', '刀', '力', '勹', '匕', '匚', '卜', '卩', '厂', '厶', '又', '十', '讠', '阝', '刂',
    '口', '囗', '土', '士', '夂', '夊', '夕', '大', '女', '子', '宀', '寸', '小', '尢', '尸', '屮', '山', '川', '工', '己', '巾', '干', '幺', '广', '廴', '廾', '弋', '弓', '彐', '彡', '彳', '扌', '艹', '艸',
    '心', '戈', '戶', '手', '支', '攴', '文', '斗', '斤', '方', '无', '日', '曰', '月', '木', '欠', '止', '歹', '殳', '毋', '比', '毛', '氏', '气', '水', '火', '爪', '父', '爻', '片', '牙', '牛', '犬', '王', '玉', '田', '甘', '生', '用', '疋', '疒', '癶', '白', '皮', '皿', '目', '矛', '矢', '石', '示', '禸', '禾', '穴', '立',
    '竹', '米', '糸', '缶', '网', '羊', '羽', '老', '而', '耒', '耳', '聿', '肉', '臣', '自', '至', '臼', '舌', '舟', '艮', '色', '虍', '虫', '血', '行', '衣', '西',
    '臣', '見', '角', '言', '谷', '豆', '豕', '豸', '貝', '赤', '走', '足', '身', '車', '辛', '辰', '辵', '邑', '酉', '釆', '里',
    '金', '長', '門', '阜', '隶', '隹', '雨', '青', '非',
    '食', '首', '香', '馬', '骨', '高', '髟', '鬥', '鬯', '鬲', '鬼',
    '魚', '鳥', '鹵', '鹿', '麥', '麻',
    '黃', '黍', '黑', '黹', '黽', '鼎', '鼓', '鼠',
]

RADICAL_SORT_INDEX = {rad: idx for idx, rad in enumerate(XINHUA_RADICAL_ORDER)}

# --- Data Loading & Augmentation ---
def load_and_augment_map():
    try:
        filename = "enhanced_component_map_with_etymology.json"
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
            data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"\n[Radix Critical Error] JSON Syntax Error in {filename}")
        return {}
    except FileNotFoundError:
        return {}

    load_subtlex_freq()

    for char, info in data.items():
        meta = info.get("meta", {})
        rel = info.get("related_characters", [])
        info['usage_count'] = len({c for c in rel if isinstance(c, str) and len(c) == 1})

        s = meta.get("strokes")
        try:
            if isinstance(s, (int, float)) and s > 0:
                info['stroke_count'] = int(s)
            elif isinstance(s, str) and s.isdigit():
                info['stroke_count'] = int(s)
            else:
                info['stroke_count'] = None
        except:
            info['stroke_count'] = None

        lookup_char = cc_t2s.convert(char) if cc_t2s else char
        info['freq_per_million'] = SUBTLEX_FREQ.get(lookup_char, 0.0)

    gc.collect()
    return data

def get_component_stats(_component_map):
    r_groups = {}
    idc_counts = {}
    used_comps = set()

    for c, data in _component_map.items():
        r = data.get("meta", {}).get("radical")
        if r:
            gs = _component_map.get(r, {}).get('stroke_count') or 999
            r_groups.setdefault(gs, []).append(r)

        d = data.get("meta", {}).get("decomposition", "")
        if d and d[0] in IDC_CHARS:
            idc = d[0]
            idc_counts[idc] = idc_counts.get(idc, 0) + 1

        for ch in d:
            if ch not in IDC_CHARS:
                used_comps.add(ch)

    for gs in r_groups:
        r_groups[gs] = sorted(
            list(set(r_groups[gs])),
            key=lambda rad: (RADICAL_SORT_INDEX.get(rad, len(XINHUA_RADICAL_ORDER) + 1000), rad)
        )
    
    gc.collect()
    return {
        "rad_groups": r_groups,
        "idc_counts": idc_counts,
        "used_components": used_comps
    }

component_map = load_and_augment_map()
stats_cache = get_component_stats(component_map) if component_map else {}

# --- Database ---
def get_db_connection():
    try:
        conn = sqlite3.connect("phrases.db", check_same_thread=False)
        return conn
    except Exception:
        return None

def batch_get_phrase_details(words, conn):
    if not conn or not words:
        return {}
    try:
        placeholders = ",".join(["?"] * len(words))
        cursor = conn.cursor()
        query = f"SELECT word, pinyin, meanings FROM phrases WHERE word IN ({placeholders})"
        cursor.execute(query, list(words))
        results = cursor.fetchall()
        return {row[0]: {"pinyin": row[1], "meanings": row[2]} for row in results}
    except Exception:
        return {}

def search_phrases_by_definition(search_term: str, conn, limit: int = 50):
    if not conn or not search_term:
        return []
    try:
        cursor = conn.cursor()
        query = "SELECT word, pinyin, meanings FROM phrases WHERE meanings LIKE ? LIMIT ?"
        cursor.execute(query, (f"%{search_term}%", limit))
        results = cursor.fetchall()
        return [{"word": row[0], "pinyin": row[1], "meanings": row[2]} for row in results]
    except Exception:
        return []

# --- Pure Helpers ---
def get_stroke_count(char):
    return component_map.get(char, {}).get("stroke_count")

def component_usage_count(comp: str) -> int:
    return component_map.get(comp, {}).get("usage_count", 0)

def sort_key_usage_primary(ch: str):
    info = component_map.get(ch, {})
    use = info.get('usage_count', 0)
    freq = info.get('freq_per_million', 0.0)
    strokes = info.get('stroke_count') or 999
    group = 0 if use >= 5 else 1
    if group == 0:
        return (group, -use, -freq, strokes, ch)
    else:
        return (group, -freq, strokes, ch)

def sort_key_frequency_primary(ch: str):
    info = component_map.get(ch, {})
    freq = info.get('freq_per_million', 0.0)
    use = info.get('usage_count', 0)
    strokes = info.get('stroke_count') or 999
    return (-freq, -use, strokes, ch)

def apply_script_filter(chars: List[str], script_filter: str) -> List[str]:
    if script_filter == "Any":
        return chars
    if script_filter == "Simplified":
        return [c for c in chars if not cc_t2s or cc_t2s.convert(c) == c]
    return [c for c in chars if not cc_s2t or cc_s2t.convert(c) == c]

def clean_field(field):
    return field[0] if isinstance(field, list) and field else field or "—"

def get_etymology_text(meta):
    etymology = meta.get("etymology", {})
    hint = clean_field(etymology.get("hint", ""))
    if not hint or hint.lower() == "no hint":
        hint = ""
    details = clean_field(etymology.get("details", ""))
    if details == "—":
        details = ""
    parts = [p for p in [hint, details] if p]
    return "; ".join(parts) if parts else None

def format_decomposition(char):
    d = component_map.get(char, {}).get("meta", {}).get("decomposition", "")
    return "—" if not d or "?" in d else d

def normalize_single_hanzi(raw: str) -> str:
    if not raw:
        return ""
    s = unicodedata.normalize("NFC", raw)
    chars = [ch for ch in s.strip() if not ch.isspace() and unicodedata.category(ch) != "Cf"]
    return chars[0] if len(chars) == 1 else ""

def resolve_to_known_variant(ch: str) -> str:
    if not ch:
        return ""
    if ch in component_map:
        return ch
    if cc_s2t:
        t = cc_s2t.convert(ch)
        if t in component_map:
            return t
    if cc_t2s:
        s = cc_t2s.convert(ch)
        if s in component_map:
            return s
    return ""

def get_char_definition_en(char: str) -> str:
    char = (char or "").strip()[:1]
    meta = component_map.get(char, {}).get("meta", {})
    return clean_field(meta.get("definition", ""))

# --- PHONETIC & SEMANTIC ANALYSIS ---

def analyze_component_structure(char: str) -> dict:
    """
    Analyze character to identify Semantic (Radical) and Phonetic components.
    RESTRICTION: Only analyzes Left-Right (⿰) or Top-Bottom (⿱) structures 
    to avoid false positives in complex or single-body characters.
    """
    info = component_map.get(char, {})
    meta = info.get("meta", {})
    
    # 1. VALIDATE STRUCTURE FIRST
    # We only want to guess logic for clear binary compounds.
    # ⿰ = Left-Right, ⿱ = Top-Bottom
    ALLOWED_IDCS = {'⿰', '⿱'}
    decomp_str = meta.get("decomposition", "")
    
    # If decomposition is missing or doesn't start with allowed IDC, skip analysis.
    if not decomp_str or decomp_str[0] not in ALLOWED_IDCS:
        return {
            "char": char,
            "semantic": None,
            "phonetic": None,
            "phonetic_pinyin": None,
            "is_sound_match": False
        }
    
    # 2. Identify Semantic (Radical)
    radical = clean_field(meta.get("radical", ""))
    if radical == "—": radical = None
    
    # 3. Identify Phonetic Candidate
    parts = [c for c in decomp_str if c not in IDC_CHARS and c != char]
    
    phonetic = None
    phonetic_pinyin = ""
    is_match = False
    
    if radical and parts:
        # Try to find the part that ISN'T the radical
        potential_phonetics = [p for p in parts if p != radical]
        
        # Heuristic: If multiple parts remain, take the one with highest stroke count or first one
        if potential_phonetics:
            phonetic = potential_phonetics[0] 
            
            # Check for sound similarity
            char_pinyin = clean_field(meta.get("pinyin", ""))
            phonetic_data = component_map.get(phonetic, {})
            phonetic_pinyin = clean_field(phonetic_data.get("meta", {}).get("pinyin", ""))
            
            if char_pinyin and phonetic_pinyin and char_pinyin != "—" and phonetic_pinyin != "—":
                # Clean tones for comparison
                import re
                cp_plain = re.sub(r'[0-9]', '', char_pinyin).lower()
                pp_plain = re.sub(r'[0-9]', '', phonetic_pinyin).lower()
                if cp_plain == pp_plain:
                    is_match = True
    
    return {
        "char": char,
        "semantic": radical,
        "phonetic": phonetic,
        "phonetic_pinyin": phonetic_pinyin,
        "is_sound_match": is_match
    }

def get_pronunciation_family(char: str, limit: int = 8) -> list:
    """Find other characters that share the same phonetic component."""
    analysis = analyze_component_structure(char)
    phonetic = analysis.get("phonetic")
    
    if not phonetic:
        return []
        
    family = []
    for c, info in component_map.items():
        if c == char: continue
        d = info.get("meta", {}).get("decomposition", "")
        if phonetic in d:
            family.append(c)
            
    family.sort(key=lambda x: component_map.get(x, {}).get("freq_per_million", 0), reverse=True)
    return family[:limit]

def get_semantic_family(char: str, limit: int = 8) -> list:
    """Find other characters with the same radical."""
    radical = component_map.get(char, {}).get("meta", {}).get("radical")
    if not radical or radical == "—":
        return []
        
    family = []
    for c, info in component_map.items():
        if c == char: continue
        if info.get("meta", {}).get("radical") == radical:
            family.append(c)
            
    family.sort(key=lambda x: component_map.get(x, {}).get("freq_per_million", 0), reverse=True)
    return family[:limit]

# --- PROMPT GENERATION ---

def get_default_prompt_config() -> dict:
    return {
        "version": 1,
        "preamble": "You are a bilingual Chinese dictionary editor and teacher.\n\nExplain a single Chinese character in depth for language learners.\n\n⸻\n\n",
        "tasks": [
            {
                "id": "task1",
                "title": "Task 1 — Character Analysis",
                "template": (
                    "Task 1 — Character Analysis\n\n"
                    "For the Hanzi below, provide:\n"
                    "\t1.\tOriginal meaning\n"
                    "\t2.\tCore semantic concept\n"
                    "\t3.\tWhy it is used in compound characters\n"
                    "\t4.\tThree example words\n"
                    "\t5.\tOne modern usage sentence\n\n"
                    "⸻\n\n"
                ),
            },
            {
                "id": "task2",
                "title": "Task 2 — Example Sentences and Images",
                "template": (
                    "Task 2 — Example Sentences and Images\n\n"
                    "Provide two example sentences that best illustrate modern usage.\n\n"
                    "⸻\n\n"
                ),
            },
            {
                "id": "task3",
                "title": "Task 3 — Conceptual Contrast",
                "template": (
                    "Task 3 — Conceptual Contrast\n\n"
                    "Compare this character with 2–3 other characters of similar meaning.\n\n"
                    "⸻\n\n"
                ),
            },
            {
                "id": "task4",
                "title": "Task 4 — Logic & Pattern Tutor",
                "template": """Task 4 — Logic & Pattern Tutor

You are a Chinese character structure tutor. Your job is to explain Radix’s “Character Logic & Patterns” panel clearly and conservatively (do not invent etymology; if uncertain, say so).

INPUT (fields provided by the app):
- char: {char}
- def_en: {def_en}
- decomposition: {decomposition}
- semantic: {semantic}
- phonetic: {phonetic}
- phonetic_pinyin: {phonetic_pinyin}
- is_sound_match: {is_sound_match}
- pronunciation_family: {pronunciation_family}
- semantic_family: {semantic_family}

TASK:
Explain (1) why semantic vs phonetic were assigned, and (2) what the two families mean, INCLUDING checking for false friends in the pronunciation_family list.

OUTPUT REQUIREMENTS:

1) Component Roles
- If semantic exists: explain what semantic/radical contributes conceptually.
- If phonetic exists: explain what phonetic contributes (sound hint).
- Interpret is_sound_match:
  - If True: strong phonetic cue.
  - If False: phonetic candidate but sound does not match; give reasons if confident.

2) Pronunciation Family (share {phonetic})
For each character in pronunciation_family, produce ONE line:
- Character: Classification (Likely true member / Visual only / Simplification artefact / Uncertain) - Short Reason.
Add 1 summary sentence on if this is a "Sound family" or "Component family".

3) Meaning Family (share {semantic})
- Provide a 1-2 sentence “theme” for {semantic}.
- For each char, give ONE short line describing how the theme applies.

4) Learner Takeaway (2 bullets max)
- Rule-of-thumb about radicals
- Rule-of-thumb about phonetics

5) UI Tooltip Copy
- Tooltip for “Meaning (Radical)” (<= 18 words)
- Tooltip for “Sound Match / Sound Component” (<= 18 words)

⸻
"""
            }
        ],
        "epilogue": "Hanzi: {char}\n- English definition: {def_en}\n",
    }

def normalize_prompt_config(cfg: dict | None) -> dict:
    base = get_default_prompt_config()
    if not isinstance(cfg, dict):
        return base
    out = {
        "version": base.get("version", 1),
        "preamble": base.get("preamble", ""),
        "epilogue": base.get("epilogue", ""),
        "tasks": list(base.get("tasks", [])),
    }
    if isinstance(cfg.get("preamble"), str): out["preamble"] = cfg["preamble"]
    if isinstance(cfg.get("epilogue"), str): out["epilogue"] = cfg["epilogue"]
    if isinstance(cfg.get("tasks"), list):
        cleaned = []
        seen = set()
        for t in cfg.get("tasks"):
            if isinstance(t, dict) and t.get("id") and t.get("id") not in seen:
                seen.add(t.get("id"))
                cleaned.append(t)
        if cleaned: out["tasks"] = cleaned
    return out

def render_combined_prompt(char: str, prompt_config: dict | None, selected_task_ids: list[str] | None, definition_en: str = "") -> str:
    cfg = normalize_prompt_config(prompt_config)
    char = (char or "").strip()[:1]
    
    # Analyze data for Task 4
    analysis = analyze_component_structure(char)
    semantic = analysis.get("semantic") or "None"
    phonetic = analysis.get("phonetic") or "None"
    phonetic_pinyin = analysis.get("phonetic_pinyin") or "None"
    is_sound_match = str(analysis.get("is_sound_match", False))
    decomposition = component_map.get(char, {}).get("meta", {}).get("decomposition", "None")
    
    p_fam = get_pronunciation_family(char)
    p_fam_str = ", ".join(p_fam) if p_fam else "None"
    
    s_fam = get_semantic_family(char)
    s_fam_str = ", ".join(s_fam) if s_fam else "None"

    # Build prompt parts
    parts = []
    selected_set = set(selected_task_ids or [])
    for t in cfg.get("tasks", []):
        if t.get("id") in selected_set:
            parts.append(t.get("template", ""))

    full = cfg.get("preamble", "") + "".join(parts) + cfg.get("epilogue", "")
    
    return full.format(
        char=char, 
        def_en=definition_en or "",
        decomposition=decomposition,
        semantic=semantic,
        phonetic=phonetic,
        phonetic_pinyin=phonetic_pinyin,
        is_sound_match=is_sound_match,
        pronunciation_family=p_fam_str,
        semantic_family=s_fam_str
    )

def build_chatgpt_prompt(char: str) -> str:
    char = (char or "").strip()[:1]
    cfg = get_default_prompt_config()
    selected = [t.get("id") for t in cfg.get("tasks", []) if t.get("id")]
    def_en = get_char_definition_en(char)
    return render_combined_prompt(char, cfg, selected, definition_en=def_en)

# --- Stroke Order & HTML ---

def get_stroke_order_view_html(primary_char: str, display_mode: str) -> tuple[str, Optional[str]]:
    primary_char = (primary_char or "").strip()[:1]
    if not primary_char:
        return "<p>No character selected.</p>", None

    s_char = cc_t2s.convert(primary_char) if cc_t2s else primary_char
    t_char = cc_s2t.convert(primary_char) if cc_s2t else primary_char
    chars_to_show = list(dict.fromkeys([c for c in [s_char, t_char] if c]))
    BOX_SIZE = 280
    
    container_html = ""
    for i, c in enumerate(chars_to_show):
        label_text = ""
        if s_char != t_char:
            label_text = "Simplified" if c == s_char else "Traditional"
        label_html = f"<div style='text-align:center; font-weight:bold; color:#555; margin-bottom:5px;'>{label_text}</div>" if label_text else ""
        pinyin = clean_field(component_map.get(c, {}).get("meta", {}).get("pinyin", ""))
        container_html += f"""
        <div style="display:flex; flex-direction:column; align-items:center;">
            {label_html}
            <div style="font-size:2.5rem; color:#e67e22; font-weight:bold; margin-bottom:10px;">{pinyin}</div>
            <div id="hw-target-{i}" style="width:{BOX_SIZE}px;height:{BOX_SIZE}px;border:1px solid #e0e0e0;border-radius:12px; background:white;"></div>
        </div>
        """

    phrases_html = None
    if display_mode != "Single Character" and primary_char:
        n = {"2-Characters": 2, "3-Characters": 3, "4-Characters": 4}.get(display_mode, 0)
        
        # 1. Try primary character compounds
        meta_compounds = component_map.get(primary_char, {}).get("meta", {}).get("compounds", [])
        
        # 2. Fallback to simplified compounds if primary has none
        if not meta_compounds and cc_t2s:
            s_char = cc_t2s.convert(primary_char)
            if s_char != primary_char:
                meta_compounds = component_map.get(s_char, {}).get("meta", {}).get("compounds", [])

        relevant = [w for w in (meta_compounds or []) if isinstance(w, str) and len(w) == n]
        if relevant:
            db_conn = get_db_connection()
            if db_conn:
                phrases_map = batch_get_phrase_details(sorted(relevant), db_conn)
                items = []
                for word in sorted(relevant):
                    entry = phrases_map.get(word)
                    if entry:
                        pinyin = entry.get("pinyin", "")
                        meanings = html.escape(entry.get("meanings", "")[:100] + ("..." if len(entry.get("meanings", "")) > 100 else ""))
                        items.append(f"<div class='compound-item'><span class='cp-word'>{word}</span><span class='cp-pinyin'>{pinyin}</span><span class='cp-mean'>{meanings}</span></div>")
                    else:
                        items.append(f"<div class='compound-item'><span class='cp-word'>{word}</span></div>")
                phrases_html = f"<div style='padding:15px; background:#f1f8e9; border-radius:8px; margin:10px auto; border:1px solid #dcedc8; max-width:800px; max-height:400px; overflow-y:auto;'><div style='font-weight:bold; margin-bottom:10px; color:#2e7d32; border-bottom:2px solid #a5d6a7; padding-bottom:5px; text-align:center;'>{display_mode} containing {primary_char}</div>{''.join(items)}</div>"

    full_html = f"""
    <div style="display:flex; gap:15px; align-items:flex-start; flex-wrap:wrap; justify-content:center;">{container_html}</div>
    <div style="display:flex; justify-content:center; margin-top:15px; gap:8px;">
         <button id="hw-reset">Reset</button><button id="hw-animate">Replay Animation</button>
    </div>
    <div id="hw-error" style="margin-top:10px; color:#b00020; text-align:center;"></div>
    <script>
    (function() {{
        const chars = {json_module.dumps(chars_to_show, ensure_ascii=False)};
        const boxSize = {BOX_SIZE};
        const errEl = document.getElementById('hw-error');
        function speak(text) {{
            if ('speechSynthesis' in window) {{
                window.speechSynthesis.cancel();
                const u = new SpeechSynthesisUtterance(text); u.lang = 'zh-CN';
                const voices = window.speechSynthesis.getVoices();
                const zhVoice = voices.find(v => v.lang.replace('_', '-').toLowerCase().startsWith('zh'));
                if (zhVoice) u.voice = zhVoice;
                window.speechSynthesis.speak(u);
            }}
        }}
        function loadScript(src) {{ return new Promise((resolve, reject) => {{
            const s = document.createElement('script'); s.src = src; s.async = true;
            s.onload = () => resolve(src); s.onerror = () => reject();
            document.head.appendChild(s);
        }}); }}
        async function ensureLibLoaded() {{
            if (window.HanziWriter) return;
            const sources = ['https://cdn.jsdelivr.net/npm/hanzi-writer@3/dist/hanzi-writer.min.js', 'https://unpkg.com/hanzi-writer@3/dist/hanzi-writer.min.js'];
            for (const src of sources) {{ try {{ await loadScript(src); if (window.HanziWriter) return; }} catch (e) {{}} }}
        }}
        const writers = [];
        async function init() {{
            try {{
                await ensureLibLoaded();
                for (let idx = 0; idx < chars.length; idx++) {{
                    const char = chars[idx]; const targetId = 'hw-target-' + idx;
                    const dataUrls = [`https://cdn.jsdelivr.net/npm/hanzi-writer-data@2.0.1/${{char}}.json`, `https://unpkg.com/hanzi-writer-data@2.0.1/${{char}}.json`];
                    let hasData = false;
                    for (const url of dataUrls) {{ try {{ const res = await fetch(url); if (res.ok) {{ hasData = true; break; }} }} catch (e) {{}} }}
                    if(hasData) {{
                        const writer = window.HanziWriter.create(targetId, char, {{ width: boxSize, height: boxSize, padding: 10, showOutline: true, showCharacter: false, strokeAnimationSpeed: 1, delayBetweenStrokes: 60 }});
                        writers.push({{w: writer, c: char}});
                    }} else {{ document.getElementById(targetId).innerHTML = `<div style="line-height:${{boxSize}}px; text-align:center; font-size:${{boxSize/2}}px; color:#ddd;">${{char}}</div>`; }}
                }}
                autoAnimateAll(true);
            }} catch (e) {{ errEl.textContent = e.message || String(e); }}
        }}
        async function playSequence(item, silent) {{ const writer = item.w; const char = item.c; for (let k = 0; k < 30; k++) {{ if (!silent) speak(char); writer.hideCharacter(); await writer.animateCharacter(); await new Promise(r => setTimeout(r, 800)); }} writer.showCharacter(); }}
        function autoAnimateAll(silent = false) {{ writers.forEach(item => {{ playSequence(item, silent); }}); }}
        function resetAll() {{ writers.forEach(item => {{ item.w.hideCharacter(); }}); }}
        document.getElementById('hw-reset').addEventListener('click', resetAll);
        document.getElementById('hw-animate').addEventListener('click', () => autoAnimateAll(false));
        init();
    }})();
    </script>
    """
    return full_html, phrases_html
