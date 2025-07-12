import json
import os
from typing import List, Dict, Any


def create_chunk(content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crée un chunk au format ChromaDB.

    Args:
        content: Le contenu du chunk (texte)
        metadata: Les métadonnées associées

    Returns:
        Un dictionnaire représentant le chunk
    """
    return {
        "content": content,
        "metadata": metadata
    }


def process_section_to_chunks(section_name: str, section_data: Any, chunks: List[Dict[str, Any]]) -> None:
    """
    Transforme une section du JSON en chunks.

    Args:
        section_name: Le nom de la section
        section_data: Les données de la section
        chunks: La liste des chunks où ajouter les nouveaux chunks
    """

    if section_name == "4 Livrables et étapes de suivi":
        # Section 4 est une liste spéciale
        for item in section_data:
            if isinstance(item, dict) and 'value' in item and 'page' in item:
                if item['value']:  # Ne créer un chunk que si la valeur n'est pas vide
                    metadata = {
                        "titre_document": "Syllabus projet",
                        "numero_page": item['page'],
                        "titre_section": section_name,
                        "matiere": "",
                        "document_path": ""
                    }
                    chunk = create_chunk(item['value'], metadata)
                    chunks.append(chunk)

    elif isinstance(section_data, dict):
        # Pour toutes les autres sections
        for field_name, field_data in section_data.items():
            if isinstance(field_data, dict) and 'value' in field_data and 'page' in field_data:
                if field_data['value']:  # Ne créer un chunk que si la valeur n'est pas vide
                    # Créer le contenu au format "clé: valeur"
                    content = f"{field_name}: {field_data['value']}"

                    metadata = {
                        "titre_document": "Syllabus projet",
                        "numero_page": field_data['page'],
                        "titre_section": section_name,
                        "matiere": "",
                        "document_path": ""
                    }

                    chunk = create_chunk(content, metadata)
                    chunks.append(chunk)


def process_json_to_chunks(json_path: str) -> List[Dict[str, Any]]:
    """
    Convertit un fichier JSON en liste de chunks.

    Args:
        json_path: Le chemin vers le fichier JSON

    Returns:
        Une liste de chunks
    """
    chunks = []

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        # Traiter chaque section
        for section_name, section_data in json_data.items():
            process_section_to_chunks(section_name, section_data, chunks)

    except Exception as e:
        print(f"Erreur lors du traitement de {json_path}: {str(e)}")

    return chunks


def save_chunks(chunks: List[Dict[str, Any]], output_path: str) -> None:
    """
    Sauvegarde les chunks dans un fichier JSON.

    Args:
        chunks: La liste des chunks
        output_path: Le chemin de sortie
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)


def process_all_files():
    """
    Traite tous les fichiers JSON du dossier d'entrée et génère les chunks.
    """
    input_dir = "output_clean_json"
    output_dir = "output/syllabus_projet/chunks"

    # Créer le dossier de sortie s'il n'existe pas
    os.makedirs(output_dir, exist_ok=True)

    # Lister tous les fichiers JSON
    json_files = [f for f in os.listdir(input_dir) if f.endswith('.json')]

    if not json_files:
        print(f"Aucun fichier JSON trouvé dans {input_dir}")
        return

    print(f"Traitement de {len(json_files)} fichiers JSON...")
    print("=" * 70)

    total_chunks = 0

    for json_file in json_files:
        json_path = os.path.join(input_dir, json_file)
        print(f"\nTraitement de: {json_file}")

        # Convertir en chunks
        chunks = process_json_to_chunks(json_path)

        if chunks:
            # Nom du fichier de sortie
            base_name = os.path.splitext(json_file)[0]
            output_filename = f"{base_name}_chunks.json"
            output_path = os.path.join(output_dir, output_filename)

            # Sauvegarder les chunks
            save_chunks(chunks, output_path)

            print(f"  ✓ {len(chunks)} chunks créés")
            print(f"  → Sauvegardé dans: {output_filename}")

            # Afficher un exemple de chunk
            if chunks:
                print("\n  Exemple de chunk:")
                example = chunks[0]
                print(f"    Content: {example['content'][:80]}{'...' if len(example['content']) > 80 else ''}")
                print(f"    Metadata: {json.dumps(example['metadata'], ensure_ascii=False)}")

            total_chunks += len(chunks)
        else:
            print(f"  ⚠ Aucun chunk créé (fichier vide ou erreur)")

    print("\n" + "=" * 70)
    print(f"Traitement terminé!")
    print(f"Total: {total_chunks} chunks créés dans {len(json_files)} fichiers")
    print(f"Chunks sauvegardés dans: {output_dir}/")


def display_sample_chunks():
    """
    Affiche un échantillon des chunks créés pour vérification.
    """
    output_dir = "output/syllabus_projet/chunks"

    # Prendre le premier fichier de chunks disponible
    chunk_files = [f for f in os.listdir(output_dir) if f.endswith('_chunks.json')]

    if chunk_files:
        sample_file = os.path.join(output_dir, chunk_files[0])
        with open(sample_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        print(f"\n{'=' * 70}")
        print(f"Échantillon de chunks depuis: {chunk_files[0]}")
        print(f"{'=' * 70}")

        # Afficher les 5 premiers chunks
        for i, chunk in enumerate(chunks[:5], 1):
            print(f"\nChunk {i}:")
            print(f"Content: {chunk['content']}")
            print(f"Metadata:")
            for key, value in chunk['metadata'].items():
                print(f"  - {key}: {value if value else '[vide]'}")


if __name__ == "__main__":
    # Mode principal
    process_all_files()

    # Optionnel: Afficher un échantillon des résultats
    try:
        display_sample_chunks()
    except:
        pass