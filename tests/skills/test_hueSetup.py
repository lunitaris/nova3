#!/usr/bin/env python
"""
Script pour configurer la connexion à un Philips Hue Bridge.
"""
import sys
import os
import json

# Ajouter la racine du projet au PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Si le module phue n'est pas installé, proposer de l'installer
try:
    from phue import Bridge
except ImportError:
    print("Le module 'phue' n'est pas installé.")
    install = input("Voulez-vous l'installer maintenant? (o/n): ")
    if install.lower() == 'o':
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "phue"])
        from phue import Bridge
    else:
        print("Installation annulée. Le script ne peut pas continuer sans le module 'phue'.")
        sys.exit(1)

def setup_hue_bridge(bridge_ip=None):
    """
    Configure un nouvel utilisateur sur le Bridge Philips Hue.
    Enregistre les informations de connexion dans un fichier pour une utilisation ultérieure.
    
    Args:
        bridge_ip: Adresse IP du Bridge (optionnelle)
    """
    # Si l'IP n'est pas fournie, demander à l'utilisateur
    if not bridge_ip:
        bridge_ip = input("Entrez l'adresse IP de votre Philips Hue Bridge: ")
    
    print(f"\n1. Appuyez sur le bouton de liaison sur votre Hue Bridge.")
    print(f"2. Puis appuyez sur Entrée dans les 30 secondes suivantes pour continuer...")
    input()
    
    try:
        # Créer une connexion au bridge et un nouvel utilisateur
        bridge = Bridge(bridge_ip)
        
        # Cette ligne va déclencher la création d'un utilisateur si nécessaire
        # Il faut avoir appuyé sur le bouton du bridge avant
        bridge.connect()
        
        # Récupérer et afficher les informations
        bridge_config = {
            "bridge_ip": bridge_ip,
            "username": bridge.username
        }
        
        # Sauvegarder dans un fichier de configuration
        config_dir = os.path.join(project_root, "data", "config")
        os.makedirs(config_dir, exist_ok=True)
        
        config_file = os.path.join(config_dir, "hue_config.json")
        with open(config_file, 'w') as f:
            json.dump(bridge_config, f, indent=2)
        
        print(f"\nConfiguration sauvegardée dans {config_file}")
        
        # Afficher les lumières disponibles
        lights = bridge.get_light_objects()
        
        print(f"\nLumières détectées ({len(lights)}):")
        for light in lights:
            print(f"- {light.name} (ID: {light.light_id})")
        
        return bridge, bridge_config
    
    except Exception as e:
        print(f"Erreur lors de la configuration du Bridge: {str(e)}")
        print("Assurez-vous d'avoir appuyé sur le bouton du Bridge et que l'adresse IP est correcte.")
        return None, None

if __name__ == "__main__":
    bridge, config = setup_hue_bridge()
    
    if bridge:
        print("\nTests de base des lumières:")
        
        # Demander à l'utilisateur s'il veut tester une lumière
        test_lights = input("\nVoulez-vous tester une lumière? (o/n): ").lower() == 'o'
        
        if test_lights:
            lights = bridge.get_light_objects()
            if not lights:
                print("Aucune lumière trouvée.")
            else:
                # Afficher la liste pour sélection
                print("\nChoisissez une lumière à tester:")
                for i, light in enumerate(lights):
                    print(f"{i+1}. {light.name}")
                
                choice = input("Numéro de la lumière: ")
                try:
                    light_index = int(choice) - 1
                    if 0 <= light_index < len(lights):
                        test_light = lights[light_index]
                        
                        # Sauvegarder l'état actuel
                        initial_state = test_light.on
                        
                        # Test d'allumage
                        print(f"\nAllumage de {test_light.name}...")
                        test_light.on = True
                        
                        # Pause
                        input("Appuyez sur Entrée pour éteindre...")
                        
                        # Test d'extinction
                        print(f"Extinction de {test_light.name}...")
                        test_light.on = False
                        
                        # Pause
                        input("Appuyez sur Entrée pour restaurer l'état initial...")
                        
                        # Restaurer l'état initial
                        test_light.on = initial_state
                        print(f"État initial restauré pour {test_light.name}")
                    else:
                        print("Choix invalide.")
                except ValueError:
                    print("Entrée invalide.")
        
        print("\nConfiguration et test terminés avec succès.")