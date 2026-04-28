import os
import json
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file (override ensures hot-reloads catch .env changes)
load_dotenv(override=True)

app = Flask(__name__)
# Secret key required for session management
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-adaptive-key-12345")

def init_session():
    if 'score' not in session:
        session['score'] = 0
    if 'solved_count' not in session:
        session['solved_count'] = 0
    if 'current_difficulty' not in session:
        session['current_difficulty'] = 'Easy'


@app.route('/')
def index():
    """Render the main UI."""
    return render_template('index.html')

@app.route('/dashboard_stats', methods=['GET'])
def get_dashboard_stats():
    """Returns current user adaptive tracking stats for the UI dashboard."""
    init_session()
    return jsonify({
        "score": session['score'],
        "solved_count": session['solved_count'],
        "current_difficulty": session['current_difficulty'],

    })

@app.route('/generate_puzzle', methods=['POST'])
def generate_puzzle():
    """Generate a new puzzle using Gemini based on ADAPTIVE difficulty and CATEGORY."""
    init_session()
    
    data = request.json or {}
    category = data.get('category', 'Random')
    manual_difficulty = data.get('difficulty', 'Adaptive')

    
    # Logic for difficulty: if manual is specified (and not Adaptive), use it. Otherwise use session difficulty.
    if manual_difficulty and manual_difficulty != 'Adaptive':
        difficulty = manual_difficulty
    else:
        difficulty = session['current_difficulty']
    
    # If daily challenge, maybe force difficulty to be higher or randomly selected
    # But let's stick to their current difficulty for daily as well to keep it adaptive
    
    category_instruction = f"The puzzle must be of category: {category}." if category != 'Random' else "The puzzle can be any logic-based category."


    prompt = f"""
    System role: You are a Universal Puzzle Master. You specialize in creating a wide variety of intellectual challenges, including logic, math, linguistics, and situational reasoning.
    
    Task: Generate a high-quality puzzle of {difficulty} difficulty.
    {category_instruction}
    
    Include clear formatting. For math or logic grids, ensure the constraints are consistent. For word games, ensure the answers are unambiguous.
    
    The response must be in strict JSON format with the following keys:
    - title: A catchy title for the puzzle
    - content: The text of the puzzle (use HTML like <br>, <b>, or <ul><li> for beautiful formatting)
    - type: The specific sub-category (e.g. Algebraic, Anagram, Lateral Logic)
    - solution: The exact answer or explanation of the solution
    
    Return only the raw JSON object.
    """
    
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"success": False, "error": "API Key is missing or .env file is not loaded properly."})
            
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                "temperature": 0.7,
                "top_p": 0.9
            }
        )
        
        # Clean output to ensure pure JSON
        out = response.text.strip()
        if out.startswith("```json"):
            out = out[7:]
        if out.startswith("```"):
            out = out[3:]
        if out.endswith("```"):
            out = out[:-3]
        out = out.strip()
            
        puzzle_data = json.loads(out)
        
        # Store tracking data in session
        session['current_puzzle'] = puzzle_data
        session['hint_count'] = 0
        session['start_time'] = time.time()
        session.modified = True
        
        # Omit solution from client data!
        puzzle_client = {
            "title": puzzle_data.get("title"),
            "content": puzzle_data.get("content"),
            "type": puzzle_data.get("type")
        }
        
        return jsonify({"success": True, "puzzle": puzzle_client, "difficulty": difficulty})
        
    except Exception as e:
        print("Error generating puzzle:", e)
        return jsonify({"success": False, "error": str(e)})

@app.route('/get_hint', methods=['POST'])
def get_hint():
    """Provide a personalized multi-level hint analyzing user mistakes."""
    init_session()
    data = request.json
    message = data.get('message', '')
    
    puzzle_context = session.get('current_puzzle', {})
    hint_count = session.get('hint_count', 0)
    
    # Multi-level hint increment
    hint_count += 1
    session['hint_count'] = hint_count
    session.modified = True
    
    if hint_count == 1:
        hint_level = "Level 1: Provide general guidance only. Point them in the right direction but remain vague."
    elif hint_count == 2:
        hint_level = "Level 2: Provide specific logical guidance. Break down a specific clue for them."
    else:
        hint_level = "Level 3: Provide a near-solution hint. Almost give it away, but let them make the last logical leap."

    prompt = f"""
    System role: You are a dedicated Universal Puzzle Assistant. Your sole purpose is to help the user solve the specific challenge below, whether it is logic, math, linguistics, or situational.
    
    The user is currently trying to solve the following puzzle:
    Title: {puzzle_context.get('title')}
    Content: {puzzle_context.get('content')}
    Actual Solution: {puzzle_context.get('solution')}
    
    The user says/asks: "{message}"
    
    IMPORTANT RULES:
    1. NEVER reveal the final answer.
    2. Analyze the user's input/mistakes if they provided any guesses.
    3. {hint_level}
    4. Keep your response brief, friendly, and step-by-step logical.
    5. ONLY discuss the puzzle. If the user asks anything unrelated (e.g., general knowledge, trivia, or other topics), politely decline and redirect them to the puzzle logic.
    """
    
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                "temperature": 0.7,
                "top_p": 0.9
            }
        )
        return jsonify({"success": True, "hint": response.text.strip(), "hint_number": hint_count})
    except Exception as e:
        print("Error getting hint:", e)
        return jsonify({"success": False, "error": str(e)})

@app.route('/explain_mistake', methods=['POST'])
def explain_mistake():
    """Explains why the user's answer was wrong without revealing the full solution."""
    init_session()
    data = request.json
    wrong_answer = data.get('answer', '')
    
    puzzle_context = session.get('current_puzzle')
    if not puzzle_context:
        return jsonify({"success": False, "error": "No active puzzle context."})
        
    prompt = f"""
    System role: You are an educational AI tutor for logic puzzles.
    
    Puzzle Context:
    Content: {puzzle_context.get('content')}
    Actual Solution: {puzzle_context.get('solution')}
    
    The user submitted the wrong answer: "{wrong_answer}"
    
    Task:
    Explain to the user WHY their answer is wrong. Point out the flaw in their reasoning or a constraint they missed from the puzzle. 
    Give them advice on how to approach the puzzle correctly.
    CRITICAL: DO NOT reveal the actual final solution. The goal is to educate and guide them back on track. Keep it concise, friendly, and under 3 sentences if possible.
    """
    
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                "temperature": 0.7,
                "top_p": 0.9
            }
        )
        return jsonify({"success": True, "explanation": response.text.strip()})
    except Exception as e:
        print("Error in explain_mistake:", e)
        return jsonify({"success": False, "error": str(e)})

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    """Grades the user's explicit answer via Gemini and updates adaptive stats, streaks, and badges."""
    init_session()
    data = request.json
    user_answer = data.get('answer', '')
    
    puzzle_context = session.get('current_puzzle')
    if not puzzle_context:
        return jsonify({"success": False, "error": "No active puzzle generated."})
        
    start_time = session.get('start_time', time.time())
    time_taken = time.time() - start_time
    hints_used = session.get('hint_count', 0)
    current_difficulty = session.get('current_difficulty', 'Easy')
    
    # Grade using Gemini Semantic check
    grading_prompt = f"""
    You are an AI grading a puzzle.
    Puzzle: {puzzle_context.get('content')}
    True Solution: {puzzle_context.get('solution')}
    
    User's Answer: "{user_answer}"
    
    Does the user's answer correctly solve the puzzle? It doesn't need to be exact words, but it must be logically correct and answer the final question accurately.
    Respond with strictly valid JSON format:
    {{"is_correct": true/false, "explanation": "A very short, friendly 1-sentence feedback on their specific answer."}}
    
    Return raw JSON.
    """
    
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=grading_prompt,
            config={
                "temperature": 0.7,
                "top_p": 0.9
            }
        )
        
        out = response.text.strip()
        if out.startswith("```json"): out = out[7:]
        if out.startswith("```"): out = out[3:]
        if out.endswith("```"): out = out[:-3]
        out = out.strip()
        
        grade_data = json.loads(out)
        is_correct = grade_data.get("is_correct", False)
        explanation = grade_data.get("explanation", "")
        
        if is_correct:
            # Score logic
            base_points = {"Easy": 10, "Medium": 20, "Hard": 30}.get(current_difficulty, 10)
            time_bonus = 5 if time_taken < 120 else 0
            hint_penalty = hints_used * 2
            points_earned = max(1, base_points + time_bonus - hint_penalty)
            
            session['score'] += points_earned
            session['solved_count'] += 1
            
            # Adaptive Difficulty Upgrade
            if hints_used <= 1 and time_taken < 180:
                if current_difficulty == 'Easy': session['current_difficulty'] = 'Medium'
                elif current_difficulty == 'Medium': session['current_difficulty'] = 'Hard'
            
            session['current_puzzle'] = None # Clear puzzle
            session.modified = True
            
            return jsonify({
                "success": True, 
                "is_correct": True, 
                "points_earned": points_earned,
                "feedback": explanation,
                "current_difficulty": session['current_difficulty']
            })
        else:
            # Downgrade logic
            if hints_used >= 3:
                if current_difficulty == 'Hard': session['current_difficulty'] = 'Medium'
                elif current_difficulty == 'Medium': session['current_difficulty'] = 'Easy'
                session.modified = True
                
            return jsonify({
                "success": True,
                "is_correct": False,
                "feedback": explanation,
                "current_difficulty": session['current_difficulty']
            })
            
    except Exception as e:
        print("Error grading answer:", e)
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
