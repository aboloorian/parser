#!/usr/bin/env python
# ── generate_chunks_cours.py ───────────────────────────────────────────────────
"""
Transforme les JSON de cours en chunks prêts pour ChromaDB.

Structure de chaque chunk :
    {
        "content": "<texte de la page>",
        "metadata": {
            "titre_document": "Cours",
            "numero_page": <int>,
            "titre_section": "",
            "matiere": "",
            "document_path": ""
        }
    }
Entrée :  output/cours/*.json
Sortie :  output/cours/chunk/*_chunks.json
"""

import json
from pathlib import Path
from typing import Any, Dict, List

INPUT_DIR = Path("output/cours")
OUTPUT_DIR = INPUT_DIR / "chunk"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def make_chunk(page_text: str, page_num: int) -> Dict[str, Any]:
    """Construit un chunk au format cible."""
    return {
        "content": page_text.strip(),
        "metadata": {
            "titre_document": "Cours",
            "numero_page": page_num,
            "titre_section": "",
            "matiere": "",
            "document_path": "",
        },
    }


def process_file(path: Path) -> None:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    chunks: List[Dict[str, Any]] = []

    for page in data.get("pages", []):
        text = page.get("text", "").strip()
        num = page.get("page")
        if text:
            chunks.append(make_chunk(text, num))

    out_path = OUTPUT_DIR / f"{path.stem}_chunks.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"✔  {path.name} → {out_path.relative_to(Path.cwd())}  ({len(chunks)} chunks)")


def main():
    json_files = list(INPUT_DIR.glob("*.json"))
    if not json_files:
        print(f"Aucun fichier JSON trouvé dans {INPUT_DIR}")
        return

    for file_path in json_files:
        try:
            process_file(file_path)
        except Exception as err:
            print(f"⛔  Erreur sur {file_path.name} : {err}")


if __name__ == "__main__":
    main()
