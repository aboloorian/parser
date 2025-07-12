#!/usr/bin/env python
# ── generate_chunks.py ─────────────────────────────────────────────────────────
"""
Transforme chaque syllabus JSON en une liste de chunks prête pour ChromaDB
selon le schéma :

    {
        "content": "<Champ>: <Valeur>",
        "metadata": {
            "titre_document": "Syllabus matière",
            "numero_page": <int>,
            "titre_section": "<Titre de la section>",
            "matiere": "",
            "document_path": ""
        }
    }

- Source :  output/syllabus_matiere/*.json
- Sortie :  output/syllabus_matiere/chunks/<fichier>_chunks.json
"""

import json
from pathlib import Path
from typing import Any, Dict, List

# Répertoires
INPUT_DIR = Path("output/syllabus_matiere")
OUTPUT_DIR = INPUT_DIR / "chunks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ──────────────────────────────────────────────────────────────────────────────
def _to_str(value: Any) -> str:
    """Normalise la valeur en chaîne (dict/list ➜ JSON compact)."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _add_chunk(
    chunks: List[Dict[str, Any]],
    section: str,
    field: str,
    value: Any,
    page: int,
) -> None:
    """Ajoute un chunk au tableau."""
    chunks.append(
        {
            "content": f"{field}: {_to_str(value)}",
            "metadata": {
                "titre_document": "Syllabus matière",
                "numero_page": page,
                "titre_section": section,
                "matiere": "",
                "document_path": "",
            },
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# Extraction récursive
# ──────────────────────────────────────────────────────────────────────────────
def _visit(section_name: str, node: Any, chunks: List[Dict[str, Any]]) -> None:
    """
    Explore récursivement un nœud (dict ou list) afin de générer les chunks.
    - Si node possède 'value' et 'page' ➜ feuille.
    - Sinon, descente récursive.
    """
    if isinstance(node, dict):
        # Feuille {'value': ..., 'page': ...}
        if {"value", "page"} <= node.keys():
            _add_chunk(chunks, section_name, section_name, node["value"], node["page"])
        else:
            # Dictionnaire de sous-champs
            for sub_key, sub_val in node.items():
                if isinstance(sub_val, dict) and {"value", "page"} <= sub_val.keys():
                    _add_chunk(
                        chunks, section_name, sub_key, sub_val["value"], sub_val["page"]
                    )
                else:
                    _visit(sub_key, sub_val, chunks)
    elif isinstance(node, list):
        for item in node:
            _visit(section_name, item, chunks)


# ──────────────────────────────────────────────────────────────────────────────
# Traitement d'un fichier
# ──────────────────────────────────────────────────────────────────────────────
def _process_file(path: Path) -> None:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    chunks: List[Dict[str, Any]] = []
    for section, body in data.items():
        if section == "_meta":
            continue
        _visit(section, body, chunks)

    out_path = OUTPUT_DIR / f"{path.stem}_chunks.json"
    out_path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✔ {path.name} → {out_path.relative_to(Path.cwd())} ({len(chunks)} chunks)")


# ──────────────────────────────────────────────────────────────────────────────
# Point d’entrée
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    json_files = sorted(INPUT_DIR.glob("*.json"))
    if not json_files:
        print(f"Aucun fichier JSON trouvé dans {INPUT_DIR.resolve()}")
        return

    for file_path in json_files:
        try:
            _process_file(file_path)
        except Exception as err:
            print(f"⛔  Erreur sur {file_path.name}: {err}")


if __name__ == "__main__":
    main()
