# spanish_ui.py (v6.4)
# UI helpers + Conjugation Dashboard rendering
# Updated: Preview card shows (Present, Preterite, Future) for 'Yo'
# helpers moved to top for scope visibility

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import pandas as pd
import streamlit as st


# ---------- Display conventions ----------
# Jehle DB person keys:
JEHLE_PERSON_KEYS = [
    "yo",
    "tú",
    "él/ella/usted",
    "nosotros/nosotras",
    "vosotros/vosotras",
    "ellos/ellas/ustedes",
]

# App display order (includes "vos")
DISPLAY_PERSONS: List[Tuple[str, Optional[str]]] = [
    ("yo", "yo"),
    ("tú", "tú"),
    ("vos", None),  # generated / best-effort
    ("él/ella/Ud.", "él/ella/usted"),
    ("nosotros", "nosotros/nosotras"),
    ("vosotros", "vosotros/vosotras"),
    ("ellos/ellas/Uds.", "ellos/ellas/ustedes"),
]

# Auxiliaries for generated periphrastic tables
AUX = {
    "estar": {
        "Present": ["estoy", "estás", "estás", "está", "estamos", "estáis", "están"],
        "Preterite": ["estuve", "estuviste", "estuviste", "estuvo", "estuvimos", "estuvisteis", "estuvieron"],
        "Imperfect": ["estaba", "estabas", "estabas", "estaba", "estábamos", "estabais", "estaban"],
        "Conditional": ["estaría", "estarías", "estarías", "estaría", "estaríamos", "estaríais", "estarían"],
        "Future": ["estaré", "estarás", "estarás", "estará", "estaremos", "estaréis", "estarán"],
    },
    "haber": {
        "Present": ["he", "has", "has", "ha", "hemos", "habéis", "han"],
        "Preterite": ["hube", "hubiste", "hubiste", "hubo", "hubimos", "hubisteis", "hubieron"],
        "Past": ["había", "habías", "habías", "había", "habíamos", "habíais", "habían"],
        "Conditional": ["habría", "habrías", "habrías", "habría", "habríamos", "habríais", "habrían"],
        "Future": ["habré", "habrás", "habrás", "habrá", "habremos", "habréis", "habrán"],
    },
    "haber_subj": {
        "Present": ["haya", "hayas", "hayas", "haya", "hayamos", "hayáis", "hayan"],
        "Past": [
            "hubiera / hubiese",
            "hubieras / hubieses",
            "hubieras / hubieses",
            "hubiera / hubiese",
            "hubiéramos / hubiésemos",
            "hubierais / hubieseis",
            "hubieran / hubiesen",
        ],
        "Future": ["hubiere", "hubieres", "hubieres", "hubiere", "hubiéremos", "hubiereis", "hubieren"],
    },
    "ir": {"Informal Future": ["voy", "vas", "vas", "va", "vamos", "vais", "van"]},
}


# ---------- Helpers (Moved to top) ----------
def _get_conj_map(verb: dict, mood: str) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for c in verb.get("conjugations", []) or []:
        if c.get("mood") == mood:
            out[c.get("tense")] = c.get("forms") or {}
    return out


def _vos_form_for_present(verb: dict) -> str:
    inf = (verb.get("infinitive") or "").lower()
    
    if inf == "ser": return "sos"
    if inf == "ir": return "vas"
    if inf == "haber": return "has"
    
    if len(inf) < 3: return ""
    stem = inf[:-2]
    ending = inf[-2:]
    
    if ending == "ar": return f"{stem}ás"
    if ending == "er": return f"{stem}és"
    if ending == "ir": return f"{stem}ís"
    
    indic = _get_conj_map(verb, "Indicativo")
    return indic.get("Presente", {}).get("tú", "")


def _vos_form_for_subjunctive(verb: dict) -> str:
    inf = (verb.get("infinitive") or "").lower()
    
    if inf == "ir": return "vayas" 
    if inf == "saber": return "sepás"
    if inf == "ser": return "seás"
    if inf == "haber": return "hayas"
    
    if len(inf) < 3: return ""
    stem = inf[:-2]
    ending = inf[-2:]
    
    if ending == "ar": return f"{stem}és"
    if ending in ["er", "ir"]: return f"{stem}ás"
    
    subj = _get_conj_map(verb, "Subjuntivo")
    return subj.get("Presente", {}).get("tú", "")


def _vos_affirmative_imperative(verb: dict) -> str:
    inf = (verb.get("infinitive") or "").lower()
    
    if inf == "ir": return "andá"
    
    if len(inf) < 3: return ""
    stem = inf[:-2]
    ending = inf[-2:]
    
    if ending == "ar": return f"{stem}á"
    if ending == "er": return f"{stem}é"
    if ending == "ir": return f"{stem}í"
    return ""


# ---------- Styling ----------
def apply_styles() -> None:
    st.markdown(
        """
    <style>
    .main .block-container {padding-top: 1.2rem; padding-bottom: 3rem;}
    
    .verb-card {
      background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
      padding: 18px 18px;
      border-radius: 14px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.06);
      border: 1px solid #e9ecef;
      margin-bottom: 14px;
    }
    .verb-title {font-size: 1.6rem; font-weight: 800; margin: 0; line-height: 1.2;}
    .verb-gloss {color: #444; font-size: 1.05rem; font-weight: 600; margin-top: 4px; margin-bottom: 8px;}
    
    /* New style for the Yo summary row */
    .verb-mini-conj {
        font-family: 'Source Code Pro', monospace;
        font-size: 0.9rem;
        color: #2c3e50;
        background-color: #eef2f5;
        padding: 4px 8px;
        border-radius: 6px;
        margin-bottom: 10px;
        display: inline-block;
        font-weight: 600;
    }

    .meta-row {display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top: 6px;}
    .meta-tag {
      background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
      padding: 4px 10px; border-radius: 8px;
      font-size: 0.85rem; color: #495057; font-weight: 700;
      display:inline-block;
    }
    .meta-tag-accent {background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%); color: #856404; border: 1px solid #ffd54f;}
    .hint {font-size: 0.78rem; color: #6c757d; font-weight: 700; margin-top: 6px;}
    </style>
    """,
        unsafe_allow_html=True,
    )


def build_verb_card_html(verb: dict, rating: Optional[int] = None, freq_rank: Optional[int] = None) -> str:
    inf = verb.get("infinitive", "")
    gloss = verb.get("gloss_en") or verb.get("infinitive_english") or ""
    usage = verb.get("usage", {}) or {}
    pro = usage.get("pronominal_infinitive")
    se_type = usage.get("se_type")
    shift = usage.get("meaning_shift")

    # --- Extract Yo forms for: Present, Preterite, Future ---
    indic = _get_conj_map(verb, "Indicativo")
    yo_pres = indic.get("Presente", {}).get("yo", "-")
    yo_pret = indic.get("Pretérito", {}).get("yo", "-")
    yo_fut  = indic.get("Futuro", {}).get("yo", "-")
    
    # Format: "hablo, hablé, hablaré"
    yo_summary_html = f"<div class='verb-mini-conj'>{yo_pres}, {yo_pret}, {yo_fut}</div>"

    tags = []
    if freq_rank is not None:
        tags.append(f"<span class='meta-tag meta-tag-accent'>Rank {freq_rank}</span>")
    if rating is not None:
        tags.append(f"<span class='meta-tag'>Your rating: {rating}/5</span>")
    if usage.get("is_pronominal") and pro:
        tags.append(f"<span class='meta-tag'>Pronominal: {pro}</span>")
        if se_type:
            tags.append(f"<span class='meta-tag'>se-type: {se_type}</span>")

    nf = verb.get("nonfinite") or {}
    if nf.get("gerund"):
        tags.append(f"<span class='meta-tag'>Gerund: {nf.get('gerund')}</span>")
    if nf.get("past_participle"):
        tags.append(f"<span class='meta-tag'>PP: {nf.get('past_participle')}</span>")

    meta_html = f"<div class='meta-row'>{''.join(tags)}</div>" if tags else ""
    shift_html = f"<div class='hint'>Meaning shift: {shift}</div>" if shift else ""

    return f"""
    <div class='verb-card'>
      <div class='verb-title'>{inf}</div>
      <div class='verb-gloss'>{gloss}</div>
      {yo_summary_html}
      {meta_html}
      {shift_html}
    </div>
    """


# ---------- Dashboard rendering ----------
def _wide_table(title: str, col_titles: List[str], rows: List[List[str]]) -> None:
    st.markdown(f"### {title}")
    df = pd.DataFrame(rows, columns=["Pronoun"] + col_titles)
    st.table(df)


def _build_rows_for_tenses(
    tenses: List[str],
    tense_to_forms: Dict[str, Dict[str, str]],
    vos_present_override: Optional[str] = None,
    show_vos: bool = True,
    show_vosotros: bool = True,
) -> List[List[str]]:
    rows: List[List[str]] = []
    
    for display_label, jehle_key in DISPLAY_PERSONS:
        # Filter based on flags
        if display_label == "vos" and not show_vos:
            continue
        if display_label == "vosotros" and not show_vosotros:
            continue

        row = [display_label]
        for tense in tenses:
            forms = tense_to_forms.get(tense, {})
            if display_label == "vos":
                if (tense == "Presente" or tense == "Present") and vos_present_override is not None:
                    row.append(vos_present_override)
                else:
                    row.append(forms.get("tú", ""))
            else:
                row.append(forms.get(jehle_key or "", ""))
        rows.append(row)
    return rows


def render_conjugation_dashboard(verb: dict, show_vos: bool = True, show_vosotros: bool = True) -> None:
    infinitive = verb.get("infinitive", "")
    st.markdown(f"## 🔹 Verb: **{infinitive.upper()}**")
    st.markdown("### Practice Conjugation Dashboard")

    # Participles
    nf = verb.get("nonfinite", {}) or {}
    st.markdown("### 🧩 Participles")
    st.table(
        pd.DataFrame(
            [
                ["Present participle", nf.get("gerund", "")],
                ["Past participle", nf.get("past_participle", "")],
            ],
            columns=["Type", "Form"],
        )
    )

    # --- INDICATIVE (simple) ---
    indic = _get_conj_map(verb, "Indicativo")
    indic_tenses = ["Presente", "Pretérito", "Imperfecto", "Condicional", "Futuro"]
    vos_indic_pres = _vos_form_for_present(verb)
    rows = _build_rows_for_tenses(
        indic_tenses, indic, 
        vos_present_override=vos_indic_pres, 
        show_vos=show_vos, 
        show_vosotros=show_vosotros
    )
    _wide_table(
        f'Indicative of "{infinitive}"',
        ["Present", "Preterite", "Imperfect", "Conditional", "Future"],
        rows,
    )

    # --- SUBJUNCTIVE (simple) ---
    subj = _get_conj_map(verb, "Subjuntivo")
    subj_tenses = ["Presente", "Imperfecto", "Futuro"]
    vos_subj_pres = _vos_form_for_subjunctive(verb)
    rows = _build_rows_for_tenses(
        subj_tenses, subj, 
        vos_present_override=vos_subj_pres,
        show_vos=show_vos, 
        show_vosotros=show_vosotros
    )
    _wide_table(
        f'Subjunctive of "{infinitive}"',
        ["Present", "Imperfect", "Future"],
        rows,
    )

    # --- IMPERATIVE (affirm/neg) ---
    imp_aff = _get_conj_map(verb, "Imperativo Afirmativo")
    imp_neg = _get_conj_map(verb, "Imperativo Negativo")

    aff_forms = next(iter(imp_aff.values()), {}) if imp_aff else {}
    neg_forms = next(iter(imp_neg.values()), {}) if imp_neg else {}

    def neg_wrap(form: str) -> str:
        form = (form or "").strip()
        return f"no {form}" if form and not form.startswith("no ") else form

    rows = []
    rows.append(["yo", "-", "-"])
    rows.append(["tú", aff_forms.get("tú", ""), neg_wrap(neg_forms.get("tú", ""))])

    if show_vos:
        vos_aff = _vos_affirmative_imperative(verb)
        vos_neg_cmd = neg_wrap(vos_subj_pres) 
        rows.append(["vos", vos_aff, vos_neg_cmd])

    rows.append(["Ud.", aff_forms.get("él/ella/usted", ""), neg_wrap(neg_forms.get("él/ella/usted", ""))])
    rows.append(["nosotros", aff_forms.get("nosotros/nosotras", ""), neg_wrap(neg_forms.get("nosotros/nosotras", ""))])
    
    if show_vosotros:
        rows.append(["vosotros", aff_forms.get("vosotros/vosotras", ""), neg_wrap(neg_forms.get("vosotros/vosotras", ""))])
    
    rows.append(["Uds.", aff_forms.get("ellos/ellas/ustedes", ""), neg_wrap(neg_forms.get("ellos/ellas/ustedes", ""))])

    _wide_table(f'Imperative of "{infinitive}"', ["Affirmative", "Negative"], rows)

    # --- PROGRESSIVE ---
    render_progressive_table(verb, show_vos, show_vosotros)

    # --- PERFECT + PERFECT SUBJUNCTIVE ---
    render_perfect_tables(verb, show_vos, show_vosotros)

    # --- INFORMAL FUTURE ---
    render_informal_future_table(verb, show_vos, show_vosotros)


def render_progressive_table(verb: dict, show_vos: bool = True, show_vosotros: bool = True) -> None:
    infinitive = verb.get("infinitive", "")
    ger = (verb.get("nonfinite", {}) or {}).get("gerund", "")
    tenses = ["Present", "Preterite", "Imperfect", "Conditional", "Future"]

    rows = []
    for i, (label, _) in enumerate(DISPLAY_PERSONS):
        if label == "vos" and not show_vos: continue
        if label == "vosotros" and not show_vosotros: continue
        
        aux = [AUX["estar"][t][i] for t in tenses]
        rows.append([label] + [f"{aux[j]} {ger}".strip() for j in range(len(tenses))])

    _wide_table(f'Progressive of "{infinitive}"', tenses, rows)


def render_perfect_tables(verb: dict, show_vos: bool = True, show_vosotros: bool = True) -> None:
    infinitive = verb.get("infinitive", "")
    pp = (verb.get("nonfinite", {}) or {}).get("past_participle", "")

    # Prefer Jehle compound tenses if present
    indic = _get_conj_map(verb, "Indicativo")
    indic_map = {
        "Present": "Pretérito perfecto",
        "Preterite": "Pretérito anterior",
        "Past": "Pluscuamperfecto",
        "Conditional": "Condicional perfecto",
        "Future": "Futuro perfecto",
    }

    if all(k in indic for k in indic_map.values()):
        col_titles = list(indic_map.keys())
        rows = []
        for display_label, jehle_key in DISPLAY_PERSONS:
            if display_label == "vos" and not show_vos: continue
            if display_label == "vosotros" and not show_vosotros: continue

            row = [display_label]
            for col, jehle_tense in indic_map.items():
                forms = indic.get(jehle_tense, {})
                if display_label == "vos":
                    row.append(forms.get("tú", ""))
                else:
                    row.append(forms.get(jehle_key or "", ""))
            rows.append(row)
        _wide_table(f'Perfect of "{infinitive}"', col_titles, rows)
    else:
        tenses = ["Present", "Preterite", "Past", "Conditional", "Future"]
        rows = []
        for i, (label, _) in enumerate(DISPLAY_PERSONS):
            if label == "vos" and not show_vos: continue
            if label == "vosotros" and not show_vosotros: continue

            aux = [AUX["haber"][t][i] for t in tenses]
            rows.append([label] + [f"{aux[j]} {pp}".strip() for j in range(len(tenses))])
        _wide_table(f'Perfect of "{infinitive}"', tenses, rows)

    # Perfect Subjunctive
    subj = _get_conj_map(verb, "Subjuntivo")
    subj_map = {"Present": "Pretérito perfecto", "Past": "Pluscuamperfecto", "Future": "Futuro perfecto"}

    if all(k in subj for k in subj_map.values()):
        col_titles = list(subj_map.keys())
        rows = []
        for display_label, jehle_key in DISPLAY_PERSONS:
            if display_label == "vos" and not show_vos: continue
            if display_label == "vosotros" and not show_vosotros: continue

            row = [display_label]
            for col, jehle_tense in subj_map.items():
                forms = subj.get(jehle_tense, {})
                if display_label == "vos":
                    row.append(forms.get("tú", ""))
                else:
                    row.append(forms.get(jehle_key or "", ""))
            rows.append(row)
        _wide_table(f'Perfect Subjunctive of "{infinitive}"', col_titles, rows)
    else:
        tenses = ["Present", "Past", "Future"]
        rows = []
        for i, (label, _) in enumerate(DISPLAY_PERSONS):
            if label == "vos" and not show_vos: continue
            if label == "vosotros" and not show_vosotros: continue

            aux = [AUX["haber_subj"][t][i] for t in tenses]
            rows.append([label] + [f"{aux[j]} {pp}".strip() for j in range(len(tenses))])
        _wide_table(f'Perfect Subjunctive of "{infinitive}"', tenses, rows)


def render_informal_future_table(verb: dict, show_vos: bool = True, show_vosotros: bool = True) -> None:
    infinitive = verb.get("infinitive", "")
    rows = []
    for i, (label, _) in enumerate(DISPLAY_PERSONS):
        if label == "vos" and not show_vos: continue
        if label == "vosotros" and not show_vosotros: continue

        aux = AUX["ir"]["Informal Future"][i]
        rows.append([label, f"{aux} a {infinitive}"])
    _wide_table(f'Informal Future of "{infinitive}"', ["Informal Future"], rows)