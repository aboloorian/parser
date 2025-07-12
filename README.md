parser_syllabus_matiere.py -> va chercher les docs pdf dans data/syllabus_projet et met les json et les txt dans output/syllabus_projet 
Même principe pour les 2 autres parser
cleaning_json_syllabus_projet.py -> a pour rôle de compléter le json avec les valeurs du txt et les met dans output_clean_json
chunking_syllabus_projet.py -> va transformer les données clean json en chunk prêt à être ingérer par chromadb et les mets dans output/syllabus_projet/chunks
Même principe pour les autres chunker
