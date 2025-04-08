Ce projet utilise 'pip-tools' pour gérer les librairies et les interdépendances entre elles.
pip-tool, en gros, on lui passe un fichier 'requirements.in' en entrée, avec juste le nom des libs, et il va tester toutes les combinaisons des versions des libs
pour trouver lesquelles sont compatibles entre elles et générer le fichier 'requirements.txt' avec les bonnes versions des libs.


1) Install pip-tools
pip install pip-tools


2) Crée un fichier requirements.in

3) compiler : pip-compile requirements.in
