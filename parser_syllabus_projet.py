import pdfplumber
import os
import re
import json


# ──────────────────────────────────────────────────────────────
#  Fonctions d'extraction / parsing
# ──────────────────────────────────────────────────────────────

def get_section_raw_text(pdf_path):
    """
    Extrait le texte de chaque section en parcourant toutes les pages pour trouver
    les tables correspondantes. Retourne également le texte non-tabulaire pour le débogage.
    Retourne maintenant aussi les numéros de page pour chaque section.
    """
    sections = {}
    section_pages = {}  # Nouveau dictionnaire pour stocker les numéros de page
    non_table_text_dump = ""
    section4_tables = []  # Liste pour collecter TOUS les tableaux de la section 4
    section4_pages = []  # Pages correspondantes pour la section 4

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # --- Extraction du texte non-tabulaire pour le débogage ---
            for i, page in enumerate(pdf.pages):
                page_tables = page.find_tables()

                def not_in_table(obj):
                    v_center = (obj['top'] + obj['bottom']) / 2
                    return not any(tbl.bbox[1] <= v_center <= tbl.bbox[3] for tbl in page_tables)

                non_table_text = page.filter(not_in_table).extract_text()
                if non_table_text and non_table_text.strip():
                    non_table_text_dump += f"--- TEXTE HORS-TABLE (PAGE {i + 1}) ---\n{non_table_text.strip()}\n\n"

            # Variables pour détecter les sections
            in_section4 = False
            section4_found = False

            # --- Logique d'extraction des sections qui parcourt toutes les pages ---
            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1  # Numéro de page (1-based)
                tables_on_page = page.find_tables()

                for table_idx, table in enumerate(tables_on_page):
                    table_text_sample = page.crop(table.bbox).extract_text(x_tolerance=2, y_tolerance=2, layout=True)

                    # Extraire aussi les données brutes du tableau
                    table_data = table.extract()

                    if not table_text_sample:
                        continue

                    # Identifier et assigner les sections en se basant sur leur titre
                    if re.search(r"1\s+Matières, formations et groupes", table_text_sample):
                        sections["1 Matières, formations et groupes"] = table_text_sample
                        section_pages["1 Matières, formations et groupes"] = page_num
                        in_section4 = False

                    elif re.search(r"2\s+Sujet\(s\) du projet", table_text_sample):
                        sections["2 Sujet(s) du projet"] = table_text_sample
                        section_pages["2 Sujet(s) du projet"] = page_num
                        in_section4 = False

                    elif re.search(r"3\s+Détails du projet", table_text_sample):
                        if "3 Détails du projet" not in sections:
                            sections["3 Détails du projet"] = table_text_sample
                            section_pages["3 Détails du projet"] = page_num
                        else:
                            sections["3 Détails du projet"] += "\n" + table_text_sample
                        in_section4 = False

                    elif re.search(r"5\s+Soutenance", table_text_sample):
                        sections["5 Soutenance"] = table_text_sample
                        section_pages["5 Soutenance"] = page_num
                        in_section4 = False

                    elif re.search(r"4\s+Livrables et étapes de suivi", table_text_sample):
                        # On entre dans la section 4
                        in_section4 = True
                        section4_found = True
                        if "4 Livrables et étapes de suivi" not in section_pages:
                            section_pages["4 Livrables et étapes de suivi"] = page_num

                    # Si on est dans la section 4 ou si on trouve un tableau qui ressemble aux livrables
                    if (in_section4 or section4_found) and table_data and len(table_data) > 0:
                        # Vérifier si c'est un tableau de livrables (4 colonnes et contient des mots-clés)
                        first_row = table_data[0] if table_data else []
                        if len(first_row) == 4:
                            # Vérifier qu'on n'est pas dans la section 5
                            table_str = str(table_data)
                            if not re.search(r"Audience|Durée de présentation", table_str):
                                # C'est un tableau de la section 4
                                for row in table_data:
                                    # Ignorer les en-têtes
                                    if any(re.search(r"4\s+Livrables et étapes de suivi", str(cell)) for cell in row if
                                           cell):
                                        continue
                                    # Ajouter seulement les lignes avec du contenu
                                    if any(cell for cell in row if cell):
                                        section4_tables.append(row)
                                        section4_pages.append(page_num)
                            else:
                                in_section4 = False

            # Traiter tous les tableaux collectés pour la section 4
            if section4_tables:
                section4_content = ""
                ligne_counter = 1
                seen_rows = set()  # Pour éviter les doublons

                for row in section4_tables:
                    # Créer une clé unique pour identifier les lignes dupliquées
                    row_key = tuple(str(cell).strip() if cell else "" for cell in row)
                    if row_key in seen_rows:
                        continue  # Ignorer les doublons
                    seen_rows.add(row_key)

                    # Nettoyer les cellules
                    cleaned_cells = []
                    for cell in row:
                        if cell is None:
                            cleaned_cells.append("")
                        else:
                            cleaned_cell = re.sub(r'\s+', ' ', str(cell)).strip()
                            cleaned_cells.append(cleaned_cell)

                    # Vérifier si la ligne contient des données significatives
                    if any(cell for cell in cleaned_cells):
                        section4_content += f"--- LIGNE {ligne_counter} ---\n"
                        section4_content += "\n".join(cleaned_cells) + "\n"
                        ligne_counter += 1

                sections["4 Livrables et étapes de suivi"] = section4_content

    except Exception as e:
        return {"Erreur": f"Une erreur est survenue : {e}"}, "", {}
    return sections, non_table_text_dump, section_pages


def safe_search(pattern, text):
    """
    Effectue une recherche d'expression régulière et renvoie le groupe 1 si trouvé,
    sinon renvoie None. Utilise les flags DOTALL et IGNORECASE.
    """
    if not text:
        return None
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def parse_final_data(raw_sections, section_pages):
    """
    Transforme le texte brut extrait en un dictionnaire clé-valeur structuré final.
    Ajoute maintenant le numéro de page pour chaque sous-champ.
    """
    structured_data = {}

    # --- SECTION 1 ---
    text1 = raw_sections.get("1 Matières, formations et groupes", "")
    page1 = section_pages.get("1 Matières, formations et groupes", None)
    regles_raw = safe_search(r"Règles de constitution des groupes\s*:\s*(.*?)(?=Charge de travail)", text1)
    regles_clean = re.sub(r'\s*par groupe\s*:?$', '', regles_raw).strip() if regles_raw else None

    s1_data = {
        "Matière liée au projet": {
            "value": safe_search(r"Matière liée au projet\s*:\s*(.*?)(?=Formations\s*:)", text1) or "",
            "page": page1
        },
        "Formations": {
            "value": safe_search(r"Formations\s*:\s*(.*?)(?=Nombre d'étudiant)", text1) or "",
            "page": page1
        },
        "Nombre d'étudiant par groupe": {
            "value": safe_search(r"Nombre d'étudiant[\s\S]*?([\d\sà-]+)[\s\S]*?par groupe", text1) or "",
            "page": page1
        },
        "Règles de constitution des groupes": {
            "value": regles_clean or "",
            "page": page1
        },
        "Charge de travail estimée par étudiant": {
            "value": safe_search(r"Charge de travail[\s\S]*?([\d,]+\s*h)[\s\S]*?estimée par étudiant", text1) or "",
            "page": page1
        }
    }
    structured_data["1 Matières, formations et groupes"] = s1_data

    # --- SECTION 2 ---
    text2 = raw_sections.get("2 Sujet(s) du projet", "")
    page2 = section_pages.get("2 Sujet(s) du projet", None)
    s2_data = {
        "Type de sujet": {
            "value": safe_search(r"Type de sujet\s*:\s*(.*)", text2) or "",
            "page": page2
        }
    }
    structured_data["2 Sujet(s) du projet"] = s2_data

    # --- SECTION 3 ---
    text3 = raw_sections.get("3 Détails du projet", "")
    page3 = section_pages.get("3 Détails du projet", None)
    keys3 = [
        "Objectif du projet (à la fin du projet les étudiants sauront réaliser un...)",
        "Descriptif détaillé",
        "Ouvrages de référence (livres, articles, revues, sites web...)",
        "Outils informatiques à installer"
    ]
    s3_data = {}
    for i, key in enumerate(keys3):
        next_key_pattern = re.escape(keys3[i + 1]) if i + 1 < len(keys3) else '$'
        pattern = re.escape(key) + r'\s*:?\s*(.*?)(?=' + next_key_pattern + ')'
        value = safe_search(pattern, text3)
        s3_data[key] = {
            "value": re.sub(r'\s+', ' ', value) if value else "",
            "page": page3
        }
    structured_data["3 Détails du projet"] = s3_data

    # --- SECTION 4 (avec pages pour chaque étape) ---
    text4 = raw_sections.get("4 Livrables et étapes de suivi", "")
    page4 = section_pages.get("4 Livrables et étapes de suivi", None)
    s4_data = []
    lignes = text4.split('--- LIGNE ')[1:]

    for ligne in lignes:
        parts = [p.strip() for p in ligne.split('\n') if p.strip()]

        if len(parts) >= 4:
            # Identifier les éléments en fonction de leur contenu
            description = ""
            numero = ""
            details = ""
            date = ""

            for i, part in enumerate(parts):
                # Ignorer le numéro de ligne (premier élément qui se termine par ---)
                if i == 0 and part.endswith('---'):
                    continue

                # Chercher le numéro d'étape (généralement un chiffre seul)
                if re.match(r'^\d+$', part) and not numero:
                    numero = part
                # Chercher la date (contient / et h ou un jour de la semaine)
                elif re.search(r'\d{1,2}/\d{1,2}/\d{4}|\d+h\d+|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche',
                               part, re.IGNORECASE):
                    date = part
                # Le premier texte non-numérique est généralement la description
                elif not description and len(part) > 2 and not re.match(r'^\d+$', part):
                    description = part
                # Le reste est les détails
                elif description and not details:
                    details = part

            # Si on n'a pas trouvé de numéro mais qu'on a une description et des détails,
            # le numéro pourrait être dans les détails
            if not numero and details:
                num_match = re.match(r'^(\d+)\s*(.*)$', details)
                if num_match:
                    numero = num_match.group(1)
                    details = num_match.group(2)

            # Construire la sortie
            if description:
                output = f"Étape {numero or '?'}: {description}"
                if details and details != description:
                    output += f" - {details}"
                if date:
                    output += f" - Date de rendu: {date}"
                s4_data.append({
                    "value": output,
                    "page": page4
                })

    structured_data["4 Livrables et étapes de suivi"] = s4_data

    # --- SECTION 5 ---
    text5 = raw_sections.get("5 Soutenance", "")
    page5 = section_pages.get("5 Soutenance", None)
    audience_raw = safe_search(r"Audience\s*:\s*(.*?)(?=Type de présentation)", text5)
    audience_clean = re.sub(r'\s*par groupe\s*:?$', '', audience_raw).strip() if audience_raw else None

    s5_data = {
        "Durée de présentation par groupe": {
            "value": safe_search(r"Durée de présentation[\s\S]*?(\d+\s*min)[\s\S]*?par groupe", text5) or "",
            "page": page5
        },
        "Audience": {
            "value": audience_clean or "",
            "page": page5
        },
        "Type de présentation": {
            "value": safe_search(r"Type de présentation\s*:\s*(.*?)(?=Précisions)", text5) or "",
            "page": page5
        },
        "Précisions": {
            "value": safe_search(r"Précisions\s*:\s*(.*)", text5) or "",
            "page": page5
        }
    }
    structured_data["5 Soutenance"] = s5_data

    return structured_data


# ──────────────────────────────────────────────────────────────
#  Point d'entrée principal
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    INPUT_DIR = "data/syllabus_projet"
    OUTPUT_DIR = "output/syllabus_projet"

    # 1) Vérifier le dossier d'entrée
    if not os.path.isdir(INPUT_DIR):
        raise FileNotFoundError(
            f"Le dossier '{INPUT_DIR}' est introuvable. "
            "Assure-toi qu'il existe et contient tes PDF."
        )

    # 2) Créer le dossier de sortie si besoin
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 3) Boucler sur chaque PDF
    for filename in os.listdir(INPUT_DIR):
        if not filename.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(INPUT_DIR, filename)
        print(f"--- Traitement du fichier : {filename} ---")

        # Extraction + parsing
        raw_sections, non_table_dump, section_pages = get_section_raw_text(pdf_path)
        final_data = parse_final_data(raw_sections, section_pages)

        # 4) Sauvegarder le JSON
        json_filename = os.path.splitext(filename)[0] + ".json"
        json_out_path = os.path.join(OUTPUT_DIR, json_filename)
        with open(json_out_path, "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        print(f"→ Résultat écrit dans : {json_out_path}")

        # (optionnel) dump de débogage
        if non_table_dump:
            debug_path = os.path.join(
                OUTPUT_DIR,
                os.path.splitext(filename)[0] + "_non_table.txt"
            )
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(non_table_dump)
            print(f"→ Dump non-tabulaire enregistré dans : {debug_path}")

        print("=" * 60 + "\n")






# import pdfplumber
# import os
# import re
# import json
#
#
# # --------------------------------------------------------------------------- #
# # 1. Extraction des sections + carte complète « page → texte »                #
# # --------------------------------------------------------------------------- #
# def get_section_raw_text(pdf_path):
#     """
#     Renvoie :
#         sections         : dict {nom_section: texte brut concaténé}
#         non_table_dump   : dump (debug) du texte hors-table
#         pages_info       : dict {nom_section: dernière page rencontrée}
#         page_text_map    : dict {numéro_page: texte intégral de la page}
#     """
#     sections = {}
#     non_table_dump = ""
#     pages_info = {}
#     page_text_map = {}  # <── Nouveau : carte globale page → texte
#
#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             for i, page in enumerate(pdf.pages):
#                 page_num = i + 1
#                 page_text_map[page_num] = page.extract_text() or ""
#
#                 page_tables = page.find_tables()
#
#                 # ---- Dump de débogage hors-table ----
#                 def not_in_table(obj):
#                     v_center = (obj["top"] + obj["bottom"]) / 2
#                     return not any(tbl.bbox[1] <= v_center <= tbl.bbox[3] for tbl in page_tables)
#
#                 non_table = page.filter(not_in_table).extract_text()
#                 if non_table and non_table.strip():
#                     non_table_dump += f"--- TEXTE HORS-TABLE (PAGE {page_num}) ---\n{non_table.strip()}\n\n"
#
#                 # ---- Parcours des tables pour repérer les sections ----
#                 for tbl in page_tables:
#                     snippet = page.crop(tbl.bbox).extract_text(x_tolerance=2, y_tolerance=2, layout=True)
#                     if not snippet:
#                         continue
#
#                     def add(sec):
#                         sections[sec] = sections.get(sec, "") + "\n" + snippet
#                         pages_info[sec] = page_num
#
#                     if re.search(r"1\s+Matières, formations et groupes", snippet):
#                         add("1 Matières, formations et groupes")
#                     elif re.search(r"2\s+Sujet\(s\) du projet", snippet):
#                         add("2 Sujet(s) du projet")
#                     elif re.search(r"3\s+Détails du projet", snippet):
#                         add("3 Détails du projet")
#                     elif re.search(r"4\s+Livrables et étapes de suivi", snippet):
#                         add("4 Livrables et étapes de suivi")
#                     elif re.search(r"5\s+Soutenance", snippet):
#                         add("5 Soutenance")
#
#     except Exception as e:
#         return {"Erreur": f"Une erreur est survenue : {e}"}, "", {}, {}
#
#     return sections, non_table_dump, pages_info, page_text_map
#
#
# # --------------------------------------------------------------------------- #
# # 2. Outils de recherche                                                       #
# # --------------------------------------------------------------------------- #
# def safe_search(pattern, text):
#     if not text:
#         return None
#     m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
#     return m.group(1).strip() if m else None
#
#
# def parse_livrables_section(text, pages_info, page_text_map):
#     """
#     Parse spécifiquement la section "Livrables et étapes de suivi"
#     pour gérer correctement le format tableau.
#     """
#     result = {}
#
#     # Nettoyer le texte
#     lines = text.strip().split('\n')
#     clean_lines = [line.strip() for line in lines if line.strip()]
#
#     # Trouver où commence vraiment le contenu du tableau
#     start_idx = 0
#     for i, line in enumerate(clean_lines):
#         if re.search(r'4\s+Livrables et étapes de suivi', line):
#             start_idx = i + 1
#             break
#
#     # Extraire les données du tableau
#     i = start_idx
#     while i < len(clean_lines):
#         # Chercher un numéro d'étape (0, 1, 2, etc.)
#         if re.match(r'^\d+$', clean_lines[i]):
#             numero_etape = clean_lines[i]
#
#             # Collecter les informations de cette étape
#             type_livrable = ""
#             description = ""
#             date_info = ""
#
#             j = i + 1
#             # Construire le type de livrable (peut être sur plusieurs lignes)
#             while j < len(clean_lines) and not re.match(r'^\d+$', clean_lines[j]):
#                 # Vérifier si on a atteint une date
#                 if re.search(r'(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)', clean_lines[j], re.IGNORECASE):
#                     # On a trouvé la ligne de date
#                     date_line_start = j
#
#                     # Récupérer toutes les infos de date (jour, date, heure)
#                     date_parts = []
#                     while j < len(clean_lines) and not re.match(r'^\d+$', clean_lines[j]):
#                         date_parts.append(clean_lines[j])
#                         j += 1
#
#                     # Assembler les infos de date
#                     date_info = " ".join(date_parts)
#
#                     # La description est tout ce qui est entre le type et la date
#                     if date_line_start > i + 2:
#                         description = " ".join(clean_lines[i + 2:date_line_start])
#
#                     break
#                 else:
#                     # C'est soit le type de livrable, soit la description
#                     if not type_livrable and j == i + 1:
#                         type_livrable = clean_lines[j]
#                     elif type_livrable and not description:
#                         description = clean_lines[j]
#                     j += 1
#
#             # Créer l'entrée pour ce livrable
#             if type_livrable:
#                 # Nettoyer le type de livrable (peut contenir des sauts de ligne)
#                 type_livrable = re.sub(r'\s+', ' ', type_livrable)
#
#                 # Construire la clé et la valeur
#                 key = f"Étape {numero_etape} - {type_livrable}"
#
#                 # Construire la valeur complète
#                 valeur_parts = []
#                 if description:
#                     valeur_parts.append(description)
#                 if date_info:
#                     valeur_parts.append(date_info)
#
#                 valeur = " - ".join(valeur_parts) if valeur_parts else type_livrable
#
#                 # Trouver la page
#                 page = pages_info.get("4 Livrables et étapes de suivi", 2)
#                 for pg, txt in page_text_map.items():
#                     if type_livrable in txt or (description and description in txt):
#                         page = pg
#                         break
#
#                 result[key] = {
#                     "valeur": valeur,
#                     "page": page
#                 }
#
#             i = j
#         else:
#             i += 1
#
#     return result
#
#
# def parse_final_data(raw_sections, pages_info, page_text_map):
#     """
#     Construit le JSON final : chaque champ contient sa valeur ET la page où il apparaît.
#     """
#
#     # -- utilitaire pour localiser la page d'un libellé ou de sa valeur --
#     def find_field_page(label_regex, value=None):
#         for pg, txt in page_text_map.items():
#             if re.search(label_regex, txt, re.IGNORECASE):
#                 return pg
#             if value and value not in ("", None) and value in txt:
#                 return pg
#         return None
#
#     final = {}
#
#     # --------------------------- SECTION 1 -------------------------------- #
#     t1 = raw_sections.get("1 Matières, formations et groupes", "")
#     sec1 = {
#         "Matière liée au projet": {
#             "valeur": (val := safe_search(r"Matière liée au projet\s*:\s*(.*?)(?=Formations\s*:)", t1)) or "",
#             "page": find_field_page(r"Matière liée au projet", val)
#         },
#         "Formations": {
#             "valeur": (val := safe_search(r"Formations\s*:\s*(.*?)(?=Nombre d'étudiant)", t1)) or "",
#             "page": find_field_page(r"Formations", val)
#         },
#         "Nombre d'étudiant par groupe": {
#             "valeur": (val := safe_search(r"Nombre d'étudiant[\s\S]*?([\d\sà-]+)[\s\S]*?par groupe", t1)) or "",
#             "page": find_field_page(r"Nombre d'étudiant", val)
#         },
#         "Règles de constitution des groupes": {
#             "valeur": (val := re.sub(r'\s*par groupe\s*:?$', '',
#                                      safe_search(r"Règles de constitution des groupes\s*:\s*(.*?)(?=Charge de travail)",
#                                                  t1) or "").strip()) or "",
#             "page": find_field_page(r"Règles de constitution des groupes", val)
#         },
#         "Charge de travail estimée par étudiant": {
#             "valeur": (val := safe_search(r"Charge de travail[\s\S]*?([\d,]+\s*h)[\s\S]*?estimée par étudiant",
#                                           t1)) or "",
#             "page": find_field_page(r"Charge de travail", val)
#         }
#     }
#     final["1 Matières, formations et groupes"] = sec1
#
#     # --------------------------- SECTION 2 -------------------------------- #
#     t2 = raw_sections.get("2 Sujet(s) du projet", "")
#     sec2 = {
#         "Type de sujet": {
#             "valeur": (val := safe_search(r"Type de sujet\s*:\s*(.*)", t2)) or "",
#             "page": find_field_page(r"Type de sujet", val)
#         }
#     }
#     final["2 Sujet(s) du projet"] = sec2
#
#     # --------------------------- SECTION 3 -------------------------------- #
#     t3 = raw_sections.get("3 Détails du projet", "")
#     keys3 = [
#         "Objectif du projet (à la fin du projet les étudiants sauront réaliser un...)",
#         "Descriptif détaillé",
#         "Ouvrages de référence (livres, articles, revues, sites web...)",
#         "Outils informatiques à installer"
#     ]
#     sec3 = {}
#     for i, key in enumerate(keys3):
#         nxt = re.escape(keys3[i + 1]) if i + 1 < len(keys3) else '$'
#         pattern = re.escape(key) + r"\s*:?\s*(.*?)(?=" + nxt + ")"
#         raw_val = safe_search(pattern, t3)
#         val = re.sub(r'\s+', ' ', raw_val) if raw_val else ""
#         sec3[key] = {
#             "valeur": val,
#             "page": find_field_page(re.escape(key), val)
#         }
#     final["3 Détails du projet"] = sec3
#
#     # --------------------------- SECTION 4 -------------------------------- #
#     t4 = raw_sections.get("4 Livrables et étapes de suivi", "")
#     if t4:
#         # Utiliser la nouvelle fonction de parsing pour les livrables
#         sec4 = parse_livrables_section(t4, pages_info, page_text_map)
#         final["4 Livrables et étapes de suivi"] = sec4
#     else:
#         final["4 Livrables et étapes de suivi"] = {}
#
#     # --------------------------- SECTION 5 -------------------------------- #
#     t5 = raw_sections.get("5 Soutenance", "")
#     sec5 = {
#         "Durée de présentation par groupe": {
#             "valeur": (val := safe_search(r"Durée de présentation[\s\S]*?(\d+\s*min)[\s\S]*?par groupe", t5)) or "",
#             "page": find_field_page(r"Durée de présentation", val)
#         },
#         "Audience": {
#             "valeur": (val := re.sub(r'\s*par groupe\s*:?$', '',
#                                      safe_search(r"Audience\s*:\s*(.*?)(?=Type de présentation)",
#                                                  t5) or "").strip()) or "",
#             "page": find_field_page(r"Audience", val)
#         },
#         "Type de présentation": {
#             "valeur": (val := safe_search(r"Type de présentation\s*:\s*(.*?)(?=Précisions)", t5)) or "",
#             "page": find_field_page(r"Type de présentation", val)
#         },
#         "Précisions": {
#             "valeur": (val := safe_search(r"Précisions\s*:\s*(.*)", t5) or "") or "",
#             "page": find_field_page(r"Précisions", val)
#         }
#     }
#     final["5 Soutenance"] = sec5
#
#     return final
#
#
# # --------------------------------------------------------------------------- #
# # 3. Point d'entrée principal                                                 #
# # --------------------------------------------------------------------------- #
# if __name__ == "__main__":
#     input_folder = "data/syllabus_projet"
#     output_folder = "output/syllabus_projet"
#
#     if not os.path.exists(input_folder):
#         print(f"ERREUR : Le dossier « {input_folder} » est introuvable.")
#         exit()
#
#     os.makedirs(output_folder, exist_ok=True)
#
#     for filename in os.listdir(input_folder):
#         if filename.lower().endswith(".pdf"):
#             pdf_path = os.path.join(input_folder, filename)
#             print(f"--- Traitement du fichier : {filename} ---")
#
#             sections, dump, pages_info, page_text_map = get_section_raw_text(pdf_path)
#             json_data = parse_final_data(sections, pages_info, page_text_map)
#
#             out_path = os.path.join(
#                 output_folder, os.path.splitext(filename)[0] + ".json"
#             )
#             with open(out_path, "w", encoding="utf-8") as f:
#                 json.dump(json_data, f, indent=2, ensure_ascii=False)
#
#             print(f"✔ JSON généré : {out_path}\n")
# import pdfplumber
# import os
# import re
# import json
#
#
# # --------------------------------------------------------------------------- #
# # 1. Extraction des sections + carte complète « page → texte »                #
# # --------------------------------------------------------------------------- #
# def get_section_raw_text(pdf_path):
#     """
#     Renvoie :
#         sections         : dict {nom_section: texte brut concaténé}
#         non_table_dump   : dump (debug) du texte hors-table
#         pages_info       : dict {nom_section: dernière page rencontrée}
#         page_text_map    : dict {numéro_page: texte intégral de la page}
#     """
#     sections = {}
#     non_table_dump = ""
#     pages_info = {}
#     page_text_map = {}        # <── Nouveau : carte globale page → texte
#
#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             for i, page in enumerate(pdf.pages):
#                 page_num = i + 1
#                 page_text_map[page_num] = page.extract_text() or ""
#
#                 page_tables = page.find_tables()
#
#                 # ---- Dump de débogage hors-table ----
#                 def not_in_table(obj):
#                     v_center = (obj["top"] + obj["bottom"]) / 2
#                     return not any(tbl.bbox[1] <= v_center <= tbl.bbox[3] for tbl in page_tables)
#
#                 non_table = page.filter(not_in_table).extract_text()
#                 if non_table and non_table.strip():
#                     non_table_dump += f"--- TEXTE HORS-TABLE (PAGE {page_num}) ---\n{non_table.strip()}\n\n"
#
#                 # ---- Parcours des tables pour repérer les sections ----
#                 for tbl in page_tables:
#                     snippet = page.crop(tbl.bbox).extract_text(x_tolerance=2, y_tolerance=2, layout=True)
#                     if not snippet:
#                         continue
#
#                     def add(sec):
#                         sections[sec] = sections.get(sec, "") + "\n" + snippet
#                         pages_info[sec] = page_num
#
#                     if re.search(r"1\s+Matières, formations et groupes", snippet):
#                         add("1 Matières, formations et groupes")
#                     elif re.search(r"2\s+Sujet\(s\) du projet", snippet):
#                         add("2 Sujet(s) du projet")
#                     elif re.search(r"3\s+Détails du projet", snippet):
#                         add("3 Détails du projet")
#                     elif re.search(r"4\s+Livrables et étapes de suivi", snippet):
#                         add("4 Livrables et étapes de suivi")
#                     elif re.search(r"5\s+Soutenance", snippet):
#                         add("5 Soutenance")
#
#     except Exception as e:
#         return {"Erreur": f"Une erreur est survenue : {e}"}, "", {}, {}
#
#     return sections, non_table_dump, pages_info, page_text_map
#
#
# # --------------------------------------------------------------------------- #
# # 2. Outils de recherche                                                       #
# # --------------------------------------------------------------------------- #
# def safe_search(pattern, text):
#     if not text:
#         return None
#     m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
#     return m.group(1).strip() if m else None
#
#
# def parse_final_data(raw_sections, pages_info, page_text_map):
#     """
#     Construit le JSON final : chaque champ contient sa valeur ET la page où il apparaît.
#     """
#     # -- utilitaire pour localiser la page d’un libellé ou de sa valeur --
#     def find_field_page(label_regex, value=None):
#         for pg, txt in page_text_map.items():
#             if re.search(label_regex, txt, re.IGNORECASE):
#                 return pg
#             if value and value not in ("", None) and value in txt:
#                 return pg
#         return None
#
#     final = {}
#
#     # --------------------------- SECTION 1 -------------------------------- #
#     t1 = raw_sections.get("1 Matières, formations et groupes", "")
#     sec1 = {
#         "Matière liée au projet": {
#             "valeur": (val := safe_search(r"Matière liée au projet\s*:\s*(.*?)(?=Formations\s*:)", t1)),
#             "page":  find_field_page(r"Matière liée au projet", val)
#         },
#         "Formations": {
#             "valeur": (val := safe_search(r"Formations\s*:\s*(.*?)(?=Nombre d'étudiant)", t1)),
#             "page":  find_field_page(r"Formations", val)
#         },
#         "Nombre d'étudiant par groupe": {
#             "valeur": (val := safe_search(r"Nombre d'étudiant[\s\S]*?([\d\sà-]+)[\s\S]*?par groupe", t1)),
#             "page":  find_field_page(r"Nombre d'étudiant", val)
#         },
#         "Règles de constitution des groupes": {
#             "valeur": (val := re.sub(r'\s*par groupe\s*:?$', '',
#                                      safe_search(r"Règles de constitution des groupes\s*:\s*(.*?)(?=Charge de travail)", t1) or "").strip()),
#             "page":  find_field_page(r"Règles de constitution des groupes", val)
#         },
#         "Charge de travail estimée par étudiant": {
#             "valeur": (val := safe_search(r"Charge de travail[\s\S]*?([\d,]+\s*h)[\s\S]*?estimée par étudiant", t1)),
#             "page":  find_field_page(r"Charge de travail", val)
#         }
#     }
#     final["1 Matières, formations et groupes"] = sec1
#
#     # --------------------------- SECTION 2 -------------------------------- #
#     t2 = raw_sections.get("2 Sujet(s) du projet", "")
#     sec2 = {
#         "Type de sujet": {
#             "valeur": (val := safe_search(r"Type de sujet\s*:\s*(.*)", t2)),
#             "page":  find_field_page(r"Type de sujet", val)
#         }
#     }
#     final["2 Sujet(s) du projet"] = sec2
#
#     # --------------------------- SECTION 3 -------------------------------- #
#     t3 = raw_sections.get("3 Détails du projet", "")
#     keys3 = [
#         "Objectif du projet (à la fin du projet les étudiants sauront réaliser un...)",
#         "Descriptif détaillé",
#         "Ouvrages de référence (livres, articles, revues, sites web...)",
#         "Outils informatiques à installer"
#     ]
#     sec3 = {}
#     for i, key in enumerate(keys3):
#         nxt = re.escape(keys3[i + 1]) if i + 1 < len(keys3) else '$'
#         pattern = re.escape(key) + r"\s*:?\s*(.*?)(?=" + nxt + ")"
#         raw_val = safe_search(pattern, t3)
#         val = re.sub(r'\s+', ' ', raw_val) if raw_val else ""
#         sec3[key] = {
#             "valeur": val,
#             "page":  find_field_page(re.escape(key), val)
#         }
#     final["3 Détails du projet"] = sec3
#
#     # --------------------------- SECTION 4 -------------------------------- #
#     t4 = raw_sections.get("4 Livrables et étapes de suivi", "")
#     sec4 = []
#     for row in t4.split('--- LIGNE ')[1:]:
#         cells = [c.strip() for c in row.split('\n') if c.strip()]
#         if len(cells) >= 4:
#             idx, *desc, date = cells
#             texte = f"Étape {idx} : {' '.join(desc)} date de rendu - {date}"
#             page = find_field_page(re.escape(' '.join(desc)), ' '.join(desc)) or pages_info.get("4 Livrables et étapes de suivi")
#             sec4.append({"valeur": texte, "page": page})
#     final["4 Livrables et étapes de suivi"] = sec4
#
#     # --------------------------- SECTION 5 -------------------------------- #
#     t5 = raw_sections.get("5 Soutenance", "")
#     sec5 = {
#         "Durée de présentation par groupe": {
#             "valeur": (val := safe_search(r"Durée de présentation[\s\S]*?(\d+\s*min)[\s\S]*?par groupe", t5)),
#             "page" : find_field_page(r"Durée de présentation", val)
#         },
#         "Audience": {
#             "valeur": (val := re.sub(r'\s*par groupe\s*:?$', '',
#                                      safe_search(r"Audience\s*:\s*(.*?)(?=Type de présentation)", t5) or "").strip()),
#             "page" : find_field_page(r"Audience", val)
#         },
#         "Type de présentation": {
#             "valeur": (val := safe_search(r"Type de présentation\s*:\s*(.*?)(?=Précisions)", t5)),
#             "page" : find_field_page(r"Type de présentation", val)
#         },
#         "Précisions": {
#             "valeur": (val := safe_search(r"Précisions\s*:\s*(.*)", t5) or ""),
#             "page" : find_field_page(r"Précisions", val)
#         }
#     }
#     final["5 Soutenance"] = sec5
#
#     return final
#
#
# # --------------------------------------------------------------------------- #
# # 3. Point d’entrée principal                                                 #
# # --------------------------------------------------------------------------- #
# if __name__ == "__main__":
#     input_folder = "data/syllabus_projet"
#     output_folder = "output/syllabus_projet"
#
#     if not os.path.exists(input_folder):
#         print(f"ERREUR : Le dossier « {input_folder} » est introuvable.")
#         exit()
#
#     os.makedirs(output_folder, exist_ok=True)
#
#     for filename in os.listdir(input_folder):
#         if filename.lower().endswith(".pdf"):
#             pdf_path = os.path.join(input_folder, filename)
#             print(f"--- Traitement du fichier : {filename} ---")
#
#             sections, dump, pages_info, page_text_map = get_section_raw_text(pdf_path)
#             json_data = parse_final_data(sections, pages_info, page_text_map)
#
#             out_path = os.path.join(
#                 output_folder, os.path.splitext(filename)[0] + ".json"
#             )
#             with open(out_path, "w", encoding="utf-8") as f:
#                 json.dump(json_data, f, indent=2, ensure_ascii=False)
#
#             print(f"✔ JSON généré : {out_path}\n")
