#!/usr/bin/env python3
"""
pdf2json_batch.py
-----------------
• Entrée : tous les PDF dans          data/cours/
• Sortie : un JSON par PDF dans       output/cours/<nom>.json

Dépendances :
    pip install PyMuPDF ftfy
"""

from pathlib import Path
import json, re, sys
import fitz          # PyMuPDF
import ftfy          # répare les caractères Unicode “cassés”

# ── Répertoires d’entrées / sorties ───────────────────────────────────────────
INPUT_DIR  = Path("data/cours")
OUTPUT_DIR = Path("output/cours")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Tables de remplacement & regex ────────────────────────────────────────────
TRANSLATE = str.maketrans({
    "Ø": "é", "Ł": "è",
    "Œ": "œ", "œ": "œ",
    "ﬂ": "fl", "ﬁ": "fi", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl",
})
MULTI_WS = re.compile(r"\s+")


def clean(txt: str) -> str:
    """Normalise ligatures + Unicode + espaces."""
    txt = ftfy.fix_text(txt).translate(TRANSLATE)
    return MULTI_WS.sub(" ", txt).strip()


def pdf_to_json(pdf_path: Path) -> Path:
    """Convertit un PDF en JSON et renvoie le chemin du fichier écrit."""
    out_file = OUTPUT_DIR / f"{pdf_path.stem}.json"

    result = {"meta": {"source": pdf_path.name, "page_count": 0}, "pages": []}
    with fitz.open(pdf_path) as doc:
        result["meta"]["page_count"] = len(doc)
        for i, page in enumerate(doc, start=1):
            text = clean(page.get_text("text") or "")
            result["pages"].append({"page": i, "text": text})

    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_file


def main() -> None:
    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        sys.exit(f"❌ Aucun PDF trouvé dans {INPUT_DIR.resolve()}")

    for pdf in pdf_files:
        try:
            out_path = pdf_to_json(pdf)
            print(f"✅ {pdf.name}  →  {out_path.relative_to(Path.cwd())}")
        except Exception as err:
            print(f"⛔ Erreur avec {pdf.name} : {err}")


if __name__ == "__main__":
    main()
