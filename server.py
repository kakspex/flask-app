from flask import Flask, request, jsonify
from transformers import pipeline
import threading
import uuid
import os

app = Flask(__name__)

# Ładowanie modelu na starcie serwera
generator = pipeline("text-generation", model="codeparrot/codeparrot-small", pad_token_id=50256)

# Przechowywanie zadań w kolejce
tasks = {}

def calculate_max_length(prompt_length):
    """
    Oblicza maksymalną długość generowanego tekstu na podstawie długości promptu.
    """
    base_length = 50  # Minimalna liczba tokenów
    factor = 2        # Mnożnik
    return min(base_length + prompt_length * factor, 1000)  # Ograniczenie maksymalne do 1000

def process_task(task_id, prompt):
    try:
        print(f"Rozpoczynanie przetwarzania zadania {task_id} z promptem: {prompt}")
        
        # Obliczanie dynamicznej wartości max_length
        max_length = calculate_max_length(len(prompt))
        
        response = generator(prompt, max_length=max_length, truncation=True)
        print(f"Generated response: {response}")

        if response:
            result = response[0]['generated_text']
            print(f"Generated Lua Code: {result}")
            
            # Zapewniamy, że kod zaczyna się od "local"
            code_start = result.find("local")
            clean_code = result[code_start:].strip() if code_start != -1 else result.strip()
            
            # Usuwanie końcowego znaku ''' (jeśli istnieje)
            clean_code = clean_code.rstrip("`")  # Usunięcie nadmiarowych apostrofów na końcu

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
