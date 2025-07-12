#!/usr/bin/env python3
"""
parse_syllabus_esgi_v8_with_pages.py – version avec numéros de page

• Nettoyage complet des lignes "DD/MM/YY Page x/x …".
• « Charge de travail de l'étudiant » = uniquement le nombre d'heures.
• Lecture du tableau "Contrôle de connaissances" via pdfplumber.extract_tables :
  repère la colonne qui contient "X".
• Tableau "Contenu détaillé des séances" extrait (5 colonnes) ; valeurs vides si cellule vide.
• Pré‑requis (ligne inline) fusionné dans Evaluation finale.
• Compétences RNCP gardées identiques (Titre / Compétence).
• NOUVEAU: Ajout des numéros de page pour chaque sous-champ
"""

import json, re, itertools
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import pdfplumber

# ── Chemins ────────────────────────────────────────────────────────────────
INPUT_DIR = Path("data/syllabus_matiere")
OUTPUT_DIR = Path("output/syllabus_matiere")

# ── Définition des sections ────────────────────────────────────────────────
SECTIONS = [
    ("Détails du syllabus", r"Détails\s+du\s+syllabus"),
    ("Evaluation finale", r"Evaluation\s+finale"),
    ("Pré-requis", r"Pré[-\s]?requis"),
    ("Objectifs pédagogiques", r"Objectifs\s+pédagogiques"),
    ("Méthodologie utilisée", r"Méthodologie\s+utilisée"),
    ("Références Crossknowledge", r"Références\s+Crossknowledge"),
    ("Ouvrages de référence", r"Ouvrages\s+de\s+référence"),
    ("Références Cyberlibris", r"Références\s+Cyberlibris"),
    ("Autres références", r"Autres\s+références"),
    ("Outils informatiques", r"Outils\s+informatiques"),
    ("Programme détaillé", r"Programme\s+détaillé"),
    ("Contenu détaillé des séances", r"Contenu\s+détaillé\s+des\s+séances"),
    ("Compétences professionnelles à développer ou à acquérir",
     r"Compétences\s+professionnelles.+développer.+acquérir")
]

DETAIL_KEYS = [
    "Matière", "Code", "Cursus", "Semestre",
    "Responsable du cours", "Mail du responsable du cours",
    "Responsable pédagogique", "Professeur associé",
    "Charge de travail de l'étudiant", "Ects", "Coef", "Volume"
]
EVAL_KEYS = [
    "Type d'examen", "Durée",
    "Documents autorisés", "Critères d'évaluation", "Pré-requis"
]

KEY_REGEX_DETAIL = re.compile(rf"({'|'.join(map(re.escape, DETAIL_KEYS))})\s*:\s*", re.I)
KEY_REGEX_EVAL = re.compile(rf"({'|'.join(map(re.escape, EVAL_KEYS))})\s*:\s*", re.I)

PAGE_RE = re.compile(r"\d{2}/\d{2}/\d{2}\s+Page\s+\d+/\d+\s+Syllabus[^\n]*", re.I)

CONTROL_COLS = [
    "Cas Pratique", "Contrôle Continu", "Dossier",
    "Dossier Individuel", "Examen", "Projet", "QCM"
]

SESSION_HEADERS = ["Séances", "Thèmes", "Travail à domicile", "Références", "Evaluation"]


# ── Helpers ────────────────────────────────────────────────────────────────
def clean(text: str) -> str:
    text = PAGE_RE.sub("", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def find_section_pages(pages_text: List[Tuple[str, int]]) -> Dict[str, int]:
    """Trouve le numéro de page pour chaque section."""
    section_pages = {}
    full_text = "\n".join([text for text, _ in pages_text])

    for name, pat in SECTIONS:
        m = re.search(pat, full_text, re.I)
        if m:
            pos = m.start()
            current_pos = 0
            for text, page_num in pages_text:
                if current_pos <= pos < current_pos + len(text):
                    section_pages[name] = page_num
                    break
                current_pos += len(text) + 1  # +1 pour le \n

    return section_pages


def slice_sections_with_pages(pages_text: List[Tuple[str, int]]) -> Tuple[Dict[str, str], Dict[str, int]]:
    """Découpe le texte en sections et retourne aussi les numéros de page."""
    full_text = "\n".join([text for text, _ in pages_text])
    section_pages = find_section_pages(pages_text)

    idx = {}
    for name, pat in SECTIONS:
        m = re.search(pat, full_text, re.I)
        if m:
            idx[name] = m.start()

    ordered = sorted(idx.items(), key=lambda kv: kv[1])
    blocks = {}

    for i, (name, start) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else len(full_text)
        block = full_text[start:end]
        block = "\n".join(block.splitlines()[1:]).strip()
        blocks[name] = clean(block)

    return blocks, section_pages


def kv_extract_with_page(block: str, regex: re.Pattern, keys: List[str], page_num: int) -> Dict[str, Dict[str, Any]]:
    """Extrait les paires clé-valeur avec numéro de page."""
    out = {k: {"value": "", "page": page_num} for k in keys}
    matches = list(regex.finditer(block))

    for i, m in enumerate(matches):
        key = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        val = clean(block[start:end])
        val = regex.sub("", val).strip()
        out[key]["value"] = val

    return out


def parse_charge(val: str) -> str:
    m = re.search(r"\d[\d,]*\s*h", val)
    return m.group(0) if m else ""


def parse_control_table_with_page(pages) -> Tuple[Dict[str, bool], int]:
    """Parse le tableau de contrôle et retourne aussi le numéro de page."""
    res = {h: False for h in CONTROL_COLS}
    found_page = 1

    for page_idx, page in enumerate(pages):
        for table in page.extract_tables():
            if not table or not table[0]:
                continue
            header_row = [clean(cell or "") for cell in table[0]]
            if all(col in header_row for col in CONTROL_COLS):
                found_page = page_idx + 1
                for row in table[1:]:
                    if row and clean(row[0]).lower().startswith("contrôle de connaissances"):
                        for col_name, cell in zip(header_row[1:], row[1:]):
                            if clean(cell or "").upper() == "X":
                                res[col_name] = True
                        return res, found_page

    return res, found_page


def concat_inline(block: str) -> str:
    lines = [clean(re.sub(r"^[\s\-•]+", "", ln)) for ln in block.splitlines() if ln.strip()]
    return " ".join(dict.fromkeys(lines))


def parse_sessions_table_with_page(pages) -> Tuple[List[Dict[str, Any]], int]:
    """Parse le tableau des séances et retourne le numéro de page."""
    for page_idx, page in enumerate(pages):
        for table in page.extract_tables():
            if not table or len(table[0]) < 5:
                continue
            header = [clean(c or "") for c in table[0]]
            if all(h in header for h in ("Séances", "Thèmes")):
                rows = []
                page_num = page_idx + 1
                for raw in table[1:]:
                    if not any(raw):
                        continue
                    padded = list(raw) + [""] * (5 - len(raw))
                    line = {}
                    for h, v in zip(SESSION_HEADERS, map(lambda x: clean(x or ""), padded[:5])):
                        line[h] = {"value": v, "page": page_num}
                    rows.append(line)
                return rows, page_num

    # Fallback avec page par défaut
    return [], 2


def parse_competences_block_with_page(block: str, page_num: int) -> List[Dict[str, Any]]:
    """Parse le bloc des compétences avec numéro de page."""
    rows = []
    for ln in block.splitlines():
        ln = clean(ln)
        if not ln or ln.lower().startswith("titre"):
            continue
        rncp = re.findall(r"RNCP\w+", ln)
        if len(rncp) >= 2:
            second = ln.find(rncp[1])
            rows.append({
                "Titre": {"value": ln[:second].strip(), "page": page_num},
                "Compétence": {"value": ln[second:].strip(), "page": page_num}
            })
    return rows


# ── Core parser ────────────────────────────────────────────────────────────
def parse_pdf(pdf_path: Path) -> Dict[str, Any]:
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages
        pages_text = [(clean(p.extract_text() or ""), i + 1) for i, p in enumerate(pages)]

    full_text = "\n".join([text for text, _ in pages_text])

    # Intitulé
    title = ""
    title_page = 1
    for i, ln in enumerate(full_text.splitlines()):
        if re.search(r"Syllabus\s*/\s*Plan\s+de\s+cours", ln, re.I):
            title = next((l.strip() for l in full_text.splitlines()[i + 1:] if l.strip()), "")
            # Trouver la page du titre
            pos = full_text.find(ln)
            current_pos = 0
            for text, page_num in pages_text:
                if current_pos <= pos < current_pos + len(text):
                    title_page = page_num
                    break
                current_pos += len(text) + 1
            break

    sections, section_pages = slice_sections_with_pages(pages_text)

    # Détails du syllabus
    details_block = sections.get("Détails du syllabus", "")
    details_page = section_pages.get("Détails du syllabus", 1)
    details = kv_extract_with_page(details_block, KEY_REGEX_DETAIL, DETAIL_KEYS, details_page)

    if details["Charge de travail de l'étudiant"]["value"]:
        details["Charge de travail de l'étudiant"]["value"] = parse_charge(
            details["Charge de travail de l'étudiant"]["value"])

    control_dict, control_page = parse_control_table_with_page(pages)
    details["Contrôle de connaissances"] = {"value": control_dict, "page": control_page}

    if title:
        details["Intitulé"] = {"value": title, "page": title_page}

    # Evaluation finale
    evaluation_block = sections.get("Evaluation finale", "")
    eval_page = section_pages.get("Evaluation finale", 1)
    evaluation = kv_extract_with_page(evaluation_block, KEY_REGEX_EVAL, EVAL_KEYS, eval_page)

    prerequis_page = section_pages.get("Pré-requis", eval_page)
    evaluation["Pré-requis"] = {
        "value": concat_inline(sections.get("Pré-requis", "")),
        "page": prerequis_page
    }

    # Objectifs pédagogiques
    objectifs_page = section_pages.get("Objectifs pédagogiques", 1)
    objectifs = {
        "value": concat_inline(sections.get("Objectifs pédagogiques", "")),
        "page": objectifs_page
    }

    # Sessions
    sessions, sessions_page = parse_sessions_table_with_page(pages)
    if not sessions:
        sessions_page = section_pages.get("Contenu détaillé des séances", 2)
        sessions = [{
            "Séances": {"value": "", "page": sessions_page},
            "Thèmes": {"value": concat_inline(sections.get("Contenu détaillé des séances", "")), "page": sessions_page},
            "Travail à domicile": {"value": "", "page": sessions_page},
            "Références": {"value": "", "page": sessions_page},
            "Evaluation": {"value": "", "page": sessions_page}
        }]

    # Compétences
    compet_page = section_pages.get("Compétences professionnelles à développer ou à acquérir", 3)
    compet = parse_competences_block_with_page(
        sections.get("Compétences professionnelles à développer ou à acquérir", ""),
        compet_page
    )

    # Construction du résultat final
    data = {
        "_meta": {"source_pdf": pdf_path.name, "parsed_at": datetime.utcnow().isoformat() + "Z"},
        "Détails du syllabus": details,
        "Evaluation finale": evaluation,
        "Objectifs pédagogiques": objectifs,
        "Contenu détaillé des séances": sessions,
        "Compétences professionnelles à développer ou à acquérir": compet
    }

    # Ajouter les autres sections
    for name, _ in SECTIONS:
        if name in data or name == "Pré-requis":
            continue
        page = section_pages.get(name, 1)
        data[name] = {
            "value": sections.get(name, ""),
            "page": page
        }

    return data


# ── Batch ──────────────────────────────────────────────────────────────────
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for pdf in INPUT_DIR.glob("*.pdf"):
        print(f"Traitement de {pdf.name}...")
        parsed = parse_pdf(pdf)
        outfile = OUTPUT_DIR / f"{pdf.stem}.json"
        outfile.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✔ {pdf.name} → {outfile}")


if __name__ == "__main__":
    main()