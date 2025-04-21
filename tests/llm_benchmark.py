import subprocess
import requests
import json
import time
from datetime import datetime
from pathlib import Path

# Liste des tests
tests = [
    {
        "label": "Test simple - météo",
        "question": "Quel temps fait-il à Paris aujourd’hui ?",
        "complexity": "low"
    },
    {
        "label": "Test moyen - résumé",
        "question": "Peux-tu me résumer la théorie de la relativité restreinte ?",
        "complexity": "medium"
    },
    {
        "label": "Test complexe - raisonnement",
        "question": "Si Jean a deux fois l’âge de Marie et que Marie aura 18 ans dans 3 ans, quel est l’âge de Jean ?",
        "complexity": "high"
    }
]

# Endpoints
NOVA_API_URL = "http://localhost:8000/api/chat/send"
OLLAMA_COMMAND = ["ollama", "run", "zephyr"]  # adapte si tu utilises un autre modèle

# Fichier de log
log_file = Path("benchmark_results.jsonl")


def log_result(entry: dict):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_ollama_test(question: str, label: str):
    start = datetime.utcnow().isoformat()
    start_time = time.time()

    try:
        result = subprocess.run(
            OLLAMA_COMMAND + [question],
            capture_output=True,
            text=True,
            timeout=360
        )
        response = result.stdout.strip()
    except Exception as e:
        response = f"Erreur: {str(e)}"

    end_time = time.time()
    end = datetime.utcnow().isoformat()

    log_result({
        "label": label,
        "question": question,
        "type": "ollama",
        "start_time": start,
        "end_time": end,
        "duration_sec": round(end_time - start_time, 2),
        "response": response
    })


def run_nova_test(question: str, label: str):
    start = datetime.utcnow().isoformat()
    start_time = time.time()

    try:
        r = requests.post(NOVA_API_URL, json={
            "content": question,
            "mode": "chat",
            "conversation_id": None,
            "user_id": "benchmark"
        }, timeout=360)


        r.raise_for_status()
        data = r.json()
        response = data.get("response", "(aucune réponse)")
    except Exception as e:
        response = f"Erreur: {str(e)}"

    end_time = time.time()
    end = datetime.utcnow().isoformat()

    log_result({
        "label": label,
        "question": question,
        "type": "nova",
        "start_time": start,
        "end_time": end,
        "duration_sec": round(end_time - start_time, 2),
        "response": response
    })


if __name__ == "__main__":
    print("📊 Lancement des tests de benchmark...")
    for test in tests:
        label = test["label"]
        question = test["question"]

        print(f"\n🧠 {label} : Ollama")
        run_ollama_test(question, label)

        print(f"💬 {label} : Nova")
        run_nova_test(question, label)

    print("\n✅ Tests terminés. Résultats dans 'benchmark_results.jsonl'")
