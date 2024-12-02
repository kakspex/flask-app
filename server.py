from flask import Flask, request, jsonify
from transformers import pipeline
import threading
import uuid
import os

app = Flask(__name__)

# Ładowanie modelu na starcie serwera
generator = pipeline("text-generation", model="distilbert/distilgpt2", pad_token_id=50256)

# Przechowywanie zadań w kolejce
tasks = {}

def process_task(task_id, prompt):
    try:
        print(f"Rozpoczynanie przetwarzania zadania {task_id} z promptem: {prompt}")
        
        # Dynamiczne zarządzanie długością
        max_length = 300 if "create" in prompt.lower() else 100
        response = generator(prompt, max_length=max_length, truncation=True)
        
        if response:
            result = response[0]['generated_text']
            
            # Filtracja: Zostaw tylko czysty kod Lua
            if "lua" in result:
                code_start = result.find("lua") + len("lua")
                code_end = result.find("\n", code_start)
                clean_code = result[code_start:code_end].strip() if code_end > -1 else result[code_start:].strip()
            else:
                clean_code = result.strip()
            
            # Usuń dodatkowe znaki końcowe, takie jak "'''"
            clean_code = clean_code.rstrip(" `\"")
            
            tasks[task_id]['result'] = clean_code
            tasks[task_id]['status'] = "completed"
            print(f"Zadanie {task_id} zakończone. Kod Lua: {clean_code}")
        else:
            tasks[task_id]['result'] = None
            tasks[task_id]['status'] = "failed"
            print(f"Zadanie {task_id} zakończone bez wyniku.")
    except Exception as e:
        tasks[task_id]['result'] = None
        tasks[task_id]['status'] = "error"
        print(f"Błąd podczas przetwarzania zadania {task_id}: {e}")


@app.route('/generate-game', methods=['POST'])
def generate_game():
    """
    Tworzy nowe zadanie generowania kodu Lua na podstawie podanego promptu.
    """
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
        
        task_id = str(uuid.uuid4())  # Tworzenie unikalnego ID zadania
        tasks[task_id] = {"status": "processing", "result": None}  # Zapis zadania w tasks
        print(f"Utworzono zadanie {task_id} z promptem: {prompt}")
        
        # Rozpocznij przetwarzanie w tle
        threading.Thread(target=process_task, args=(task_id, prompt)).start()
        
        return jsonify({"task_id": task_id}), 202  # Zwrócenie task_id do klienta
    
    except Exception as e:
        print(f"Błąd podczas tworzenia zadania: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get-result/<task_id>', methods=['GET'])
def get_result(task_id):
    """
    Pobiera wynik dla podanego zadania.
    """
    print(f"Żądanie statusu dla zadania: {task_id}")
    task = tasks.get(task_id)
    if not task:
        print(f"Zadanie o ID {task_id} nie istnieje.")
        return jsonify({"error": "Task not found"}), 404

    print(f"Status zadania {task_id}: {task['status']}")
    if task['result'] is None:
        return jsonify({"status": task['status']}), 202
    else:
        return jsonify({"status": "completed", "game_code": task['result']}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000)) 
    app.run(host='0.0.0.0', port=port) 

