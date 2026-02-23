# radix_ui.py
# Consolidated UI components, HTML builders, and styles

import streamlit as st
from streamlit.components.v1 import html as st_html
import json
import html as pyhtml
import base64
import hashlib
import uuid
from radix_core import (
    component_map, clean_field, format_decomposition, get_etymology_text,
    cc_t2s, cc_s2t, get_char_definition_en, component_usage_count, analyze_component_structure, get_pronunciation_family, get_semantic_family
)


# ==================== STYLES ====================

def apply_styles():
    """Apply all CSS styles."""
    st.markdown("""
    <style>
    .main .block-container {padding-top: 2rem; padding-bottom: 3rem;}
    .char-card {background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); padding: 24px; border-radius: 16px; margin-bottom: 0px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e9ecef; transition: all 0.3s ease;}
    .char-card:hover {box-shadow: 0 6px 20px rgba(0,0,0,0.1); transform: translateY(-2px);}
    .meta-row {font-size: 0.95em; color: #555; margin-bottom: 12px; display: flex; align-items: center; flex-wrap: wrap; gap: 12px;}
    .meta-pinyin {font-weight: 700; font-size: 2.4em; color: #d35400; text-shadow: 0 2px 4px rgba(211, 84, 0, 0.1);}
    .meta-tag {background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 4px 12px; border-radius: 8px; font-size: 0.85em; color: #495057; font-weight: 600; box-shadow: 0 2px 4px rgba(0,0,0,0.04); margin-bottom: 6px; display: inline-block;}
    .meta-tag-trad {background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%); color: #856404; border: 1px solid #ffd54f;}
    .meta-tag-simp {background: linear-gradient(135deg, #d1e7dd 0%, #a3cfbb 100%); color: #0f5132; border: 1px solid #81c784;}
    .def-row {font-size: 1.15em; line-height: 1.6; color: #2c3e50; margin-bottom: 10px; font-weight: 500;}
    .ety-row {font-size: 0.92em; color: #666; font-style: italic; border-top: 2px solid #e9ecef; padding-top: 12px; margin-top: 8px; line-height: 1.5;}
    section[data-testid="stSidebar"] .meta-pinyin {font-size: 2.0em !important;}
    section[data-testid="stSidebar"] .char-card {padding: 16px !important;}
    section[data-testid="stSidebar"] .def-row {font-size: 1.05em !important;}
    .comp-grid .stButton > button {width: 100% !important; font-size: 2.2em !important; height: 85px !important; background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%) !important; border: 2px solid #dee2e6 !important; border-radius: 14px !important; box-shadow: 0 3px 8px rgba(0,0,0,0.08) !important; padding: 0 !important; line-height: 85px !important; font-weight: 600 !important; transition: all 0.2s ease !important;}
    .comp-grid .stButton > button:hover {background: linear-gradient(135deg, #fff5f5 0%, #ffe8e8 100%) !important; border-color: #f2c6c6 !important; color: #c0392b !important; transform: translateY(-3px) !important; box-shadow: 0 6px 16px rgba(192, 57, 43, 0.15) !important;}
    .char-btn-wrap .stButton > button {width: 100% !important; font-size: 3.8em !important; font-weight: 700 !important; background: linear-gradient(135deg, #ffffff 0%, #f0f4f8 100%) !important; border: 3px solid #dee2e6 !important; padding: 10px !important; min-height: 90px !important; border-radius: 16px !important; box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important; transition: all 0.25s ease !important;}
    .char-btn-wrap .stButton > button:hover {background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%) !important; border-color: #3b82f6 !important; transform: scale(1.02) !important; box-shadow: 0 6px 20px rgba(59, 130, 246, 0.2) !important;}
    .pen-btn-wrap .stButton > button {width: 100% !important; font-size: 1.6em !important; border: 2px solid #dee2e6 !important; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%) !important; margin-top: 8px !important; height: 45px !important; line-height: 1 !important; color: #555 !important; font-weight: 600 !important; border-radius: 12px !important; transition: all 0.2s ease !important;}
    .pen-btn-wrap .stButton > button:hover {background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%) !important; border-color: #64b5f6 !important; color: #1565c0 !important; transform: translateY(-2px) !important; box-shadow: 0 4px 12px rgba(100, 181, 246, 0.2) !important;}
    .char-static-box {font-size: 3.8em; font-weight: 700; background: linear-gradient(135deg, #fafafa 0%, #f0f0f0 100%); color: #bbb; border: 2px solid #e0e0e0; border-radius: 16px; padding: 10px; min-height: 90px; display: flex; align-items: center; justify-content: center; width: 100%; cursor: default; box-shadow: 0 2px 8px rgba(0,0,0,0.04);}
    .status-line {font-size: 1.1em; font-weight: 600; color: #0f5132; background: linear-gradient(135deg, #d1e7dd 0%, #c3e6cb 100%); border: 2px solid #95d5b2; padding: 18px; border-radius: 12px; margin: 20px 0 30px 0; box-shadow: 0 3px 10px rgba(15, 81, 50, 0.08);}
    .status-tag {background: linear-gradient(135deg, #ffffff 0%, #f1f3f5 100%); color: #2c3e50; padding: 6px 14px; border-radius: 8px; font-weight: 700; font-size: 0.9em; border: 2px solid #dee2e6; display: inline-flex; align-items: center; box-shadow: 0 2px 6px rgba(0,0,0,0.06);}
    .lineage-header {font-size: 1.4em; font-weight: 800; color: #2c3e50; margin: 30px 0 20px 0; padding: 12px 20px; background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-left: 5px solid #1976d2; border-radius: 8px; box-shadow: 0 2px 8px rgba(25, 118, 210, 0.1);}
    .compound-item {display: flex; align-items: baseline; margin-bottom: 10px; padding: 12px; border-bottom: 2px solid #e9ecef; border-radius: 8px; background: #ffffff; transition: all 0.2s ease;}
    .compound-item:hover {background: #f8f9fa; transform: translateX(4px);}
    .cp-word {font-weight: 700; font-size: 1.2em; color: #2c3e50; min-width: 85px; margin-right: 15px;}
    .cp-pinyin {color: #d35400; font-family: 'Monaco', 'Menlo', monospace; margin-right: 15px; font-weight: 600; font-size: 1.5em;}
    .cp-mean {color: #495057; font-size: 1em; flex: 1; line-height: 1.5;}
    .char-btn-hint {margin-top: 6px; text-align: center; font-size: 0.86em; color: #6c757d; font-weight: 700;}
    .char-btn-hint.previewing {color: #c0392b;}
    .splash-wrap {max-width: 850px; margin: 0 auto; padding: 60px 20px 20px 20px;}
    .splash-card {background: #ffffff; border: 1px solid #e0e0e0; border-radius: 40px; padding: 60px; box-shadow: 0 15px 50px rgba(0,0,0,0.05); text-align: center;}
    .splash-title {font-size: 3.0em; font-weight: 800; color: #1a1a1a; margin-bottom: 10px;}
    .splash-sub {font-size: 1.3em; color: #666;}
    .palace-entrance-container {text-align: center; margin: 60px 0;}
    .grand-torii {font-size: 250px !important; line-height: 1; filter: drop-shadow(0 10px 20px rgba(0,0,0,0.1));}
    .entrance-text {color: #2c3e50; font-size: 24px; font-weight: 700; margin-top: 20px; margin-bottom: 30px; letter-spacing: 2px;}
    .radix-tooltip {position: relative; display: inline-block; cursor: help;}
    .radix-tooltip .radix-tooltiptext {visibility: hidden; width: 240px; background-color: #262626; color: #fff; text-align: left; border-radius: 6px; padding: 12px; position: absolute; z-index: 1000; bottom: 125%; left: 50%; margin-left: -120px; opacity: 0; transition: opacity 0.3s; font-size: 0.8rem; font-weight: normal; line-height: 1.4; box-shadow: 0 4px 12px rgba(0,0,0,0.3); pointer-events: none;}
    .radix-tooltip .radix-tooltiptext::after {content: ""; position: absolute; top: 100%; left: 50%; margin-left: -5px; border-width: 5px; border-style: solid; border-color: #262626 transparent transparent transparent;}
    .radix-tooltip:hover .radix-tooltiptext {visibility: visible; opacity: 1;}
    .radix-tooltiptext strong {color: #ffb74d;}
    .insight-box {background: #fff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px; margin-top: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.03);}
    .insight-title {font-weight: 800; color: #37474f; font-size: 1.1em; margin-bottom: 15px; display: flex; align-items: center; gap: 8px;}
    .role-badge {display: inline-flex; align-items: center; padding: 6px 12px; border-radius: 8px; font-size: 0.9em; font-weight: 600; margin-right: 10px; margin-bottom: 8px;}
    .role-semantic {background: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9;}
    .role-phonetic {background: #e3f2fd; color: #1565c0; border: 1px solid #bbdefb;}
    .family-list {display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px;}
    .family-char {font-size: 1.4em; color: #333; cursor: pointer; padding: 2px 8px; background: #f5f5f5; border-radius: 6px; border: 1px solid #eee;}
    </style>
    """, unsafe_allow_html=True)

# ==================== HTML BUILDERS ====================

FREQ_PERCENTILES = {'p95': 8500, 'p75': 3200, 'p50': 800, 'p25': 150}

def build_frequency_badge(freq: float, minimal: bool = False) -> str:
    """Build frequency badge HTML."""
    if freq > 0:
        if freq >= FREQ_PERCENTILES['p95']:
            label, color = "Top 5%", "#2e7d32"
        elif freq >= FREQ_PERCENTILES['p75']:
            label, color = "Top 25%", "#558b2f"
        elif freq >= FREQ_PERCENTILES['p50']:
            label, color = "Above Average", "#ff8f00"
        elif freq >= FREQ_PERCENTILES['p25']:
            label, color = "Below Average", "#f57c00"
        else:
            label, color = "Bottom 25%", "#c62828"
        
        if minimal:
            return f"<span class='meta-tag' title='Frequency: {label} ({freq:,.0f}/M)' style='background: linear-gradient(135deg, {color}15 0%, {color}25 100%); color: {color}; border: 1px solid {color}40; font-weight:700; cursor: help;'>Freq: {label}</span>"
        else:
            legend = "<strong>📊 Frequency Guide</strong><br><br><strong>Top 5% (Essential):</strong> Core survival vocabulary.<br><strong>Top 25% (Common):</strong> Standard for news & business.<br><strong>Above Average:</strong> Topic-specific (e.g. Science).<br><strong>Below Average:</strong> Literary & enrichment words.<br><strong>Bottom 25%:</strong> Rare, archaic, or very specific names."
            return f"<div class='radix-tooltip'><span class='meta-tag' style='background: linear-gradient(135deg, {color}15 0%, {color}25 100%); color: {color}; border: 1px solid {color}40; font-weight:700; cursor: help;'>Frequency: {label} ({freq:,.0f}/M)</span><span class='radix-tooltiptext' style='width:250px;'>{legend}</span></div>"
    else:
        if minimal:
            return "<span class='meta-tag' style='color:#999;'>Freq: No Data</span>"
        else:
            return "<div class='radix-tooltip'><span class='meta-tag' style='color:#999;'>Freq: No Data</span><span class='radix-tooltiptext'>No frequency data available in SUBTLEX-CH for this character.</span></div>"

def build_usage_badge(count: int, char: str, is_static: bool, minimal: bool) -> str:
    """Build usage badge with tooltip."""
    if count <= 0:
        return ""
    
    if minimal:
        return f"<span class='meta-tag' title='Used in {count} characters. Click to drill down.'>Used in {count} chars</span>"
    else:
        if is_static:
            tip = f"💡 <strong>Static View:</strong> Copy and paste <strong>{char}</strong> into the search box to explore related chars."
        else:
            tip = f"✨ <strong>Interactive Tip:</strong><br>1. Click <strong>{char}</strong> once to preview in sidebar.<br>2. Click <strong>{char}</strong> again to drill down into the {count} related characters."
        return f"<div class='radix-tooltip'><span class='meta-tag' style='border-bottom: 2px dotted #aaa;'>Used in {count} chars</span><span class='radix-tooltiptext'>{tip}</span></div>"

def generate_clean_card_html(c: str, usage_count: int = None, is_static: bool = False, minimal: bool = False) -> str:
    """Generate character card HTML."""
    if not c:
        return ""
    
    info = component_map.get(c, {})
    meta = info.get("meta", {})
    
    # Build meta items
    meta_items = []
    
    # Pinyin
    pinyin = clean_field(meta.get("pinyin", ""))
    if pinyin and pinyin != "—":
        meta_items.append(f"<span class='meta-pinyin'>{pinyin}</span>")
    
    # Strokes
    strokes = info.get('stroke_count')
    if strokes:
        meta_items.append(f"<span class='meta-tag'>{strokes} strokes</span>")
    
    # Radical
    radical = clean_field(meta.get("radical", ""))
    if radical and radical != "—":
        meta_items.append(f"<span class='meta-tag'>Rad. {radical}</span>")
    
    # Decomposition
    decomp = format_decomposition(c)
    if decomp and decomp != "—":
        meta_items.append(f"<span class='meta-tag'>{decomp}</span>")
    
    # Usage badge
    if usage_count is not None and usage_count > 0:
        meta_items.append(build_usage_badge(usage_count, c, is_static, minimal))
    
    # Frequency badge
    freq = info.get('freq_per_million', 0.0)
    meta_items.append(build_frequency_badge(freq, minimal))
    
    # Script variants
    if cc_t2s:
        simplified = cc_t2s.convert(c)
        if simplified != c:
            meta_items.append(f"<span class='meta-tag meta-tag-trad'>Trad. → {simplified}</span>")
    if cc_s2t:
        traditional = cc_s2t.convert(c)
        if traditional != c:
            meta_items.append(f"<span class='meta-tag meta-tag-simp'>Simp. → {traditional}</span>")
    
    meta_html = f"<div class='meta-row' style='display:flex; flex-wrap:wrap; gap:8px; align-items:center;'>{''.join(meta_items)}</div>"
    
    # Definition and etymology
    definition = clean_field(meta.get("definition", ""))
    def_html = f"<div class='def-row'>{definition}</div>" if definition and definition != "—" else ""
    
    etymology = get_etymology_text(meta)
    ety_html = f"<div class='ety-row'>{etymology}</div>" if etymology else ""
    
    return f"<div class='char-card'>{meta_html}{def_html}{ety_html}</div>"

def render_ipad_safe_download_html(data_str: str, filename: str, label: str) -> str:
    """Build iPad-safe download link."""
    b64 = base64.b64encode(data_str.encode()).decode()
    href = f'data:application/octet-stream;base64,{b64}'
    return f'<div style="text-align:center; margin: 10px 0;"><a href="{href}" download="{filename}" target="_self" style="text-decoration: none; color: white; background-color: #d35400; padding: 12px 24px; border-radius: 12px; font-weight: 700; display: inline-block; box-shadow: 0 4px 12px rgba(211, 84, 0, 0.2); -webkit-appearance: none;">{label}</a></div>'

def render_copy_to_clipboard(prompt_text: str, widget_id: str):
    """Render copy-to-clipboard button."""
    safe_text = json.dumps(prompt_text, ensure_ascii=False)
    st_html(
        f"""<div style="display:flex; justify-content:center; margin:10px 0 0 0;"><button id="copy-btn-{widget_id}" style="padding:10px 14px; border-radius:10px; border:1px solid #ddd; background:#fff; cursor:pointer; font-weight:700;">Copy Prompt to Clipboard</button></div><div id="copy-msg-{widget_id}" style="text-align:center; margin-top:8px; color:#2e7d32; font-weight:600;"></div><script>(function() {{const text = {safe_text}; const btn = document.getElementById("copy-btn-{widget_id}"); const msg = document.getElementById("copy-msg-{widget_id}"); if (!btn) return; async function copy() {{try {{await navigator.clipboard.writeText(text); msg.textContent = "Copied. Paste into ChatGPT.";}} catch (e) {{msg.textContent = "Copy failed.";}} setTimeout(() => {{msg.textContent = "";}}, 2500);}} btn.addEventListener("click", copy);}})();</script>""",
        height=90,
    )

def get_stroke_order_sidebar_html(char: str, size: int = 140) -> tuple[str, int]:
    """Build sidebar stroke order HTML with infinite animation."""
    char = (char or "").strip()[:1]
    if not char:
        return "", 0
    
    pinyin = clean_field(component_map.get(char, {}).get("meta", {}).get("pinyin", ""))
    h = size + 80
    
    html_content = f"""<div style="display:flex; flex-direction:column; align-items:center; margin:20px 0;"><div style="text-align:center; font-size:2.5rem; font-weight:bold; color:#e67e22; margin-bottom:10px;">{pinyin}</div><div id="sb-hw-{hash(char)}" style="width:{size}px; height:{size}px;"></div><div style="font-size:11px; color:#666; text-align:center; margin-top:5px;">🔄 Continuous animation (keeps session alive)</div></div><script>(function() {{const char = {json.dumps(char, ensure_ascii=False)}; const target = "sb-hw-{hash(char)}"; async function loadScript(src) {{return new Promise((resolve, reject) => {{const s = document.createElement('script'); s.src = src; s.async = true; s.onload = resolve; s.onerror = reject; document.head.appendChild(s);}});}} async function ensureLib() {{if (window.HanziWriter) return; const sources = ['https://cdn.jsdelivr.net/npm/hanzi-writer@3/dist/hanzi-writer.min.js','https://unpkg.com/hanzi-writer@3/dist/hanzi-writer.min.js']; for (const src of sources) {{try {{await loadScript(src); if (window.HanziWriter) return;}} catch(e) {{}}}}}} function speak(text) {{if ('speechSynthesis' in window) {{window.speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); u.lang = 'zh-CN'; const voices = window.speechSynthesis.getVoices(); const zhVoice = voices.find(v => v.lang.replace('_', '-').toLowerCase().startsWith('zh')); if (zhVoice) u.voice = zhVoice; window.speechSynthesis.speak(u);}}}} async function init() {{try {{await ensureLib(); const writer = window.HanziWriter.create(target, char, {{width: {size}, height: {size}, padding: 8, showOutline: true, showCharacter: false, strokeAnimationSpeed: 1.5, delayBetweenStrokes: 80}}); async function continuousAnimation() {{while (true) {{writer.hideCharacter(); await writer.animateCharacter(); writer.showCharacter(); if (Math.random() < 0.2) {{speak(char);}} await new Promise(r => setTimeout(r, 2000));}}}} continuousAnimation().catch(console.error); const el = document.getElementById(target); el.style.cursor = 'pointer'; const trigger = (e) => {{e.preventDefault(); speak(char); writer.hideCharacter(); writer.animateCharacter();}}; el.addEventListener('click', trigger); el.addEventListener('touchend', trigger);}} catch(e) {{console.error("HanziWriter init failed:", e); document.getElementById(target).innerHTML = `<div style="font-size:${{size*0.7}}px; line-height:${{size}}px; text-align:center;">${{char}}</div>`;}}}};init();}})();</script>"""
    
    return html_content, h

def render_learning_insights_html(char: str) -> tuple[str, int, str]:
    """Render the Logic/Analysis box. Returns (html, height, prompt_text)."""
    if not char: 
        return "", 0, ""
    
    analysis = analyze_component_structure(char)
    sem = analysis.get("semantic")
    pho = analysis.get("phonetic")
    pho_pinyin = analysis.get("phonetic_pinyin", "")
    is_match = analysis.get("is_sound_match")
    
    if not sem and not pho:
        return "", 0, ""

    # Get data for prompt
    decomposition = component_map.get(char, {}).get("meta", {}).get("decomposition", "None")
    def_en = get_char_definition_en(char) or "None"
    p_fam = get_pronunciation_family(char)
    s_fam = get_semantic_family(char)
    
    unique_id = hashlib.md5(char.encode()).hexdigest()[:8]

    # Build HTML components piece by piece
    html_parts = []
    
    # 1. Component Roles section
    html_parts.append('<div style="margin-bottom:20px;">')
    if sem:
        html_parts.append(f'<div class="role-badge role-semantic">💡 {pyhtml.escape(sem)} : Meaning (Radical)</div>')
    if pho:
        match_icon = "📊" if is_match else "🗣️"
        match_text = "Sound Match" if is_match else "Sound Component"
        pinyin_display = f" ({pyhtml.escape(pho_pinyin)})" if pho_pinyin else ""
        html_parts.append(f'<div class="role-badge role-phonetic">{match_icon} {pyhtml.escape(pho)}{pinyin_display} : {match_text}</div>')
    html_parts.append('</div>')
    
    # 2. Sound Family section
    if pho and p_fam:
        html_parts.append('<div style="margin-bottom:15px;">')
        html_parts.append(f'<div style="font-size:0.85em; font-weight:bold; color:#666; margin-bottom:5px;">📊 SOUND FAMILY (share {pyhtml.escape(pho)}):</div>')
        html_parts.append('<div class="family-list">')
        for c in p_fam:
            html_parts.append(f'<span class="family-char">{pyhtml.escape(c)}</span>')
        html_parts.append('</div>')
        html_parts.append('</div>')
    
    # 3. Meaning Family section
    if sem and s_fam:
        html_parts.append('<div style="margin-bottom:15px;">')
        html_parts.append(f'<div style="font-size:0.85em; font-weight:bold; color:#666; margin-bottom:5px;">💡 MEANING FAMILY (share {pyhtml.escape(sem)}):</div>')
        html_parts.append('<div class="family-list">')
        for c in s_fam:
            html_parts.append(f'<span class="family-char">{pyhtml.escape(c)}</span>')
        html_parts.append('</div>')
        html_parts.append('</div>')

    # Build prompt text  
    lines = [
        "Task 4 — Logic & Pattern Tutor (From App Fields)",
        "",
        "You are a Chinese character structure tutor. Explain Radix's \"Character Logic & Patterns\" panel clearly and conservatively.",
        "Do not invent etymology; if uncertain, say so. Do not assume any prior tasks have been run.",
        "",
        "INPUT (fields provided by the app):",
        f"- char: {char}",
        f"- def_en: {def_en}",
        f"- decomposition: {decomposition}",
        f"- semantic: {sem or 'None'}",
        f"- phonetic: {pho or 'None'}",
        f"- phonetic_pinyin: {pho_pinyin or 'None'}",
        f"- is_sound_match: {is_match}",
        f"- pronunciation_family: {', '.join(p_fam) if p_fam else 'None'}",
        f"- semantic_family: {', '.join(s_fam) if s_fam else 'None'}",
        "",
        "TASK:",
        "Explain (1) why semantic vs phonetic were assigned, and (2) what the two families mean,",
        "INCLUDING checking for false friends in pronunciation_family (e.g., visual matches caused by simplification).",
        "",
        "OUTPUT:",
        "",
        "1) Component Roles",
        "- If semantic exists: what meaning cue it suggests (1–2 lines).",
        "- If phonetic exists: what sound cue it suggests (1–2 lines).",
        "- Interpret is_sound_match:",
        "  - True: strong phonetic cue in modern Mandarin.",
        "  - False: candidate phonetic component but modern sound mismatch; give 1–2 plausible reasons only if confident.",
        "",
        f"2) Pronunciation Family (share {pho or 'None'})",
        "For each character in pronunciation_family, output ONE line:",
        "- Character: Classification (Likely true member / Visual only / Simplification artefact / Uncertain) — reason (<= 15 words).",
        "Then add ONE summary sentence: label as \"Sound family\" or safer \"Component family.\"",
        "",
        f"3) Meaning Family (share {sem or 'None'})",
        f"- 1–2 sentence theme of what {sem or 'the semantic component'} often signals in modern characters.",
        "- For each character in semantic_family: one short line on how the theme plausibly applies (no overclaiming).",
        "",
        "4) Learner Takeaway (max 2 bullets)",
        "- One rule-of-thumb about radicals (meaning cues).",
        "- One rule-of-thumb about phonetics (sound cues + why false friends occur).",
        "",
        "5) UI Tooltip Copy",
        "- Tooltip for \"Meaning (Radical)\" (<= 18 words)",
        "- Tooltip for \"Sound Match / Sound Component\" (<= 18 words)"
    ]
    prompt_full = "\n".join(lines)

    # Assemble final HTML
    content = ''.join(html_parts)
    
    full_html = f"""<style>
.insight-box {{background: #fff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.03);}}
.insight-title {{font-weight: 800; color: #37474f; font-size: 1.1em; margin-bottom: 15px;}}
.role-badge {{display: inline-flex; align-items: center; padding: 6px 12px; border-radius: 8px; font-size: 0.9em; font-weight: 600; margin-right: 10px; margin-bottom: 8px;}}
.role-semantic {{background: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9;}}
.role-phonetic {{background: #e3f2fd; color: #1565c0; border: 1px solid #bbdefb;}}
.family-list {{display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px;}}
.family-char {{font-size: 1.4em; color: #333; padding: 2px 8px; background: #f5f5f5; border-radius: 6px; border: 1px solid #eee;}}
</style>
<div class="insight-box">
<div class="insight-title">🧠 Character Logic & Patterns</div>
{content}
</div>"""
    
    base_height = 200
    if p_fam: base_height += 80
    if s_fam: base_height += 80
    
    return full_html, base_height, prompt_full

# Add to radix_ui.py
def render_session_heartbeat():
    """Invisible component that keeps session alive"""
    st_html("""
    <script>
        // Ping the server every 60 seconds
        setInterval(() => {
            fetch(window.location.href, {
                method: 'GET',
                headers: {'Cache-Control': 'no-cache'}
            }).catch(e => console.log('Heartbeat failed:', e));
        }, 60000); // Every 60 seconds
    </script>
    """, height=0)

# Call this in render_sidebar() or main()


# ==================== UI COMPONENTS ====================

def render_definition_search_ui(key_prefix: str):
    """Render definition search interface."""
    st.markdown("**English Definition Search**")
    key = f"{key_prefix}_def_search"
    st.text_input("Search definitions", key=key, placeholder="e.g., water, fire, mountain", label_visibility="collapsed")
    return key  # Return key so caller can check the value
