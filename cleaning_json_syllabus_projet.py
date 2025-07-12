import json
import os
import re


def extract_value_from_txt(txt_content, field_name, page_num=None):
    """
    Tente d'extraire une valeur du fichier texte pour un champ donné.
    Cherche d'abord dans la page spécifiée, puis dans tout le document.
    """
    # Mapping des noms de champs vers les patterns de recherche
    field_patterns = {
        "Matière liée au projet": [
            r"Matière[s]?\s*(?:liée[s]?\s*au\s*projet)?\s*:\s*([^\n]+)",
            r"Module\s*:\s*([^\n]+)",
            r"Cours\s*:\s*([^\n]+)",
            # Pattern pour extraire depuis l'en-tête (ex: 2025-5A-IABD-DRL)
            r"(\d{4}-\d+[A-Z]-[A-Z]+-[A-Z]+)"
        ],
        "Ouvrages de référence (livres, articles, revues, sites web...)": [
            r"Ouvrages?\s*de\s*référence[^\n]*:\s*\n([^\n]+(?:\n(?!Outils|Imprimé)[^\n]+)*)",
            r"Ouvrages?\s*de\s*référence[^\n]*:\s*([^\n]+)",
            r"Références?\s*:\s*([^\n]+)",
            r"Bibliographie\s*:\s*([^\n]+)"
        ],
        "Outils informatiques à installer": [
            r"Outils?\s*informatiques?\s*à\s*installer\s*:\s*\n([^\n]+(?:\n(?!Imprimé)[^\n]+)*)",
            r"Outils?\s*informatiques?\s*à\s*installer\s*:\s*([^\n]+)",
            r"Outils?\s*:\s*([^\n]+)",
            r"Logiciels?\s*:\s*([^\n]+)",
            r"Installation[s]?\s*:\s*([^\n]+)"
        ],
        "Descriptif détaillé": [
            r"Descriptif\s*détaillé\s*\n([^\n]+(?:\n(?!Imprimé|Ouvrages)[^\n]+)*)",
            r"Descriptif\s*détaillé\s*:\s*([^\n]+(?:\n(?!Imprimé|Ouvrages)[^\n]+)*)",
            r"Description\s*:\s*([^\n]+(?:\n(?!Imprimé)[^\n]+)*)",
            r"Détails?\s*:\s*([^\n]+(?:\n(?!Imprimé)[^\n]+)*)"
        ],
        "Objectif du projet (à la fin du projet les étudiants sauront réaliser un...)": [
            r"Objectif[s]?\s*du\s*projet[^\n]*:\s*([^\n]+(?:\n(?!Descriptif|Ouvrages|Outils|Imprimé)[^\n]+)*)",
            r"Objectif[s]?\s*:\s*([^\n]+)",
            r"But[s]?\s*du\s*projet\s*:\s*([^\n]+)"
        ],
        "Précisions": [
            r"Précisions?\s*:\s*([^\n]+(?:\n(?!Imprimé)[^\n]+)*)",
            r"Remarques?\s*:\s*([^\n]+)",
            r"Notes?\s*:\s*([^\n]+)"
        ]
    }

    def search_in_text(text):
        """Cherche le pattern dans le texte donné."""
        if field_name in field_patterns:
            for pattern in field_patterns[field_name]:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                if match:
                    # Récupérer la valeur trouvée
                    if len(match.groups()) > 0:
                        value = match.group(1).strip()
                    else:
                        value = match.group(0).strip()

                    # Nettoyer la valeur
                    value = re.sub(r'Imprimé le : .*$', '', value, flags=re.MULTILINE)
                    value = re.sub(r'\s+', ' ', value)
                    value = value.strip()

                    # Ne pas retourner de valeurs trop courtes ou non pertinentes
                    if len(value) > 2 and value not in ['-', '_', 'NA', 'N/A']:
                        return value
        return None

    # D'abord, essayer de trouver dans la page spécifique
    if page_num:
        page_pattern = rf"--- TEXTE HORS-TABLE \(PAGE {page_num}\) ---\n(.*?)(?=--- TEXTE HORS-TABLE|$)"
        page_match = re.search(page_pattern, txt_content, re.DOTALL)
        if page_match:
            page_text = page_match.group(1)
            result = search_in_text(page_text)
            if result:
                return result

    # Si pas trouvé dans la page spécifique, chercher dans tout le document
    result = search_in_text(txt_content)
    return result


def update_json_with_txt(json_data, txt_content):
    """
    Met à jour les champs vides du JSON avec les données du fichier TXT.
    """
    updated_data = json_data.copy()
    fields_updated = 0

    def update_section(section_data, section_name):
        """Helper pour mettre à jour une section."""
        nonlocal fields_updated

        if isinstance(section_data, dict):
            for key, value in section_data.items():
                if isinstance(value, dict) and 'value' in value and 'page' in value:
                    # Si la valeur est vide, essayer de la trouver dans le TXT
                    if not value['value'] or value['value'] == "":
                        extracted_value = extract_value_from_txt(txt_content, key, value['page'])
                        if extracted_value:
                            value['value'] = extracted_value
                            fields_updated += 1
                            print(
                                f"  ✓ Mis à jour '{key}': {extracted_value[:60]}{'...' if len(extracted_value) > 60 else ''}")
                        else:
                            print(f"  ⚠ Pas trouvé: '{key}'")

    # Parcourir toutes les sections
    for section_name, section_data in updated_data.items():
        if section_name == "4 Livrables et étapes de suivi":
            # Section 4 est une liste, pas besoin de la traiter
            continue
        else:
            print(f"\n  Section: {section_name}")
            update_section(section_data, section_name)

    print(f"\n  Total: {fields_updated} champs mis à jour")
    return updated_data


def process_files():
    """
    Traite tous les fichiers JSON et leurs dumps TXT correspondants.
    """
    input_dir = "output/syllabus_projet"
    output_dir = "output_clean_json"

    # Créer le dossier de sortie s'il n'existe pas
    os.makedirs(output_dir, exist_ok=True)

    # Lister tous les fichiers JSON
    json_files = [f for f in os.listdir(input_dir) if f.endswith('.json')]

    if not json_files:
        print("Aucun fichier JSON trouvé dans", input_dir)
        return

    for json_file in json_files:
        base_name = os.path.splitext(json_file)[0]
        txt_file = f"{base_name}_non_table.txt"

        json_path = os.path.join(input_dir, json_file)
        txt_path = os.path.join(input_dir, txt_file)

        print(f"\n{'=' * 70}")
        print(f"Traitement de: {json_file}")

        try:
            # Charger le JSON
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            # Vérifier si le fichier TXT existe
            if not os.path.exists(txt_path):
                print(f"  ⚠ Fichier TXT non trouvé: {txt_file}")
                print("  → Copie du JSON sans modification")
            else:
                # Charger le TXT
                with open(txt_path, 'r', encoding='utf-8') as f:
                    txt_content = f.read()

                # Afficher un aperçu du contenu TXT
                print(f"  → Fichier TXT trouvé ({len(txt_content)} caractères)")

                # Mettre à jour le JSON avec les données du TXT
                json_data = update_json_with_txt(json_data, txt_content)

            # Sauvegarder le JSON nettoyé
            output_path = os.path.join(output_dir, json_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            print(f"\n  ✓ JSON sauvegardé dans: {output_path}")

        except Exception as e:
            print(f"  ❌ Erreur lors du traitement: {str(e)}")
            continue

    print(f"\n{'=' * 70}")
    print(f"Traitement terminé! {len(json_files)} fichiers traités.")
    print(f"Les fichiers nettoyés sont dans: {output_dir}/")


if __name__ == "__main__":
    # Test avec l'exemple fourni
    test_mode = False  # Mettre à True pour tester avec l'exemple

    if test_mode:
        # Test avec l'exemple fourni
        txt_content = """--- TEXTE HORS-TABLE (PAGE 1) ---
Syllabus projet
Année :2024-2025
Enseignant(s) Email(s)
VIDAL Nicolas nvidal@myges.fr
2025-5A-IABD-DRL
Imprimé le : 06/07/25 23:05

--- TEXTE HORS-TABLE (PAGE 2) ---
Descriptif détaillé
Environnements de départ :
- pour tests : Line World
- pour tests : Grid World
- pour tests : TicTacToe versus Random
+ 1 au choix parmi :
- Farkle (solo ou vs Random ou Heuristique)
> https://boardgamearena.com/gamepanel?game=farkle
- LuckyNumbers (vs Random ou Heuristique)
> https://boardgamearena.com/gamepanel?game=luckynumbers
- Pond (versus Random ou Heuristique)
> https://boardgamearena.com/gamepanel?game=pond
Imprimé le : 06/07/25 23:05

--- TEXTE HORS-TABLE (PAGE 3) ---
Ouvrages de référence (livres, articles, revues, sites web...)
Reinforcement Learning: An Introduction de Richard S. Sutton and Andrew G. Barto
Outils informatiques à installer
tensorflow / keras / pytorch / jax / keras_core / burn
Imprimé le : 06/07/25 23:05"""

        # Tester l'extraction
        print("Test d'extraction:")
        print("Matière:", extract_value_from_txt(txt_content, "Matière liée au projet", 1))
        print("Descriptif:", extract_value_from_txt(txt_content, "Descriptif détaillé", 1))
        print("Ouvrages:",
              extract_value_from_txt(txt_content, "Ouvrages de référence (livres, articles, revues, sites web...)", 1))
        print("Outils:", extract_value_from_txt(txt_content, "Outils informatiques à installer", 1))
    else:
        # Mode normal
        process_files()