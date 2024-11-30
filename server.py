from flask import Flask, request, jsonify
from transformers import pipeline
import threading
import uuid
import os

app = Flask(__name__)

# Ładowanie modelu na starcie serwera
generator = pipeline("text-generation", model="EleutherAI/gpt-neo-125m", pad_token_id=50256)

# Przechowywanie zadań w kolejce
tasks = {}

def process_task(task_id, prompt):
    """
    Przetwarza zadanie w tle, generując kod Lua na podstawie podanego promptu.
    """
    try:
        print(f"Rozpoczynanie przetwarzania zadania {task_id} z promptem: {prompt}")
        
        response = generator(prompt, max_length=300, truncation=True)
        print(f"Generated response: {response}")

        if response and 'generated_text' in response[0]:
            result = response[0]['generated_text']
            
            # Usuwanie nadmiarowych znaków i formatowanie wyniku
            code_start = result.find("local")
            clean_code = result[code_start:].strip() if code_start != -1 else result.strip()

            # Zapisanie wyniku
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

@app.route('/')
def home():
    return "Flask app is running!"

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
    port = int(os.environ.get('PORT', 10000))  # Pobiera port z Render
    app.run(host='0.0.0.0', port=port)

