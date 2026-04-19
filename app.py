import os
import json
import time
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
        "current_difficulty": session['current_difficulty']
    })

@app.route('/generate_puzzle', methods=['POST'])
def generate_puzzle():
    """Generate a new puzzle using Gemini based on ADAPTIVE difficulty."""
    init_session()
    difficulty = session['current_difficulty']
    
    prompt = f"""
    System role: You are a logic puzzle expert. You generate puzzles and help users by giving hints only. Never reveal the final answer unless explicitly asked.
    
    Task: Generate a logic-based puzzle (not general text) of {difficulty} difficulty.
    Include clear question format.
    The response must be in strict JSON format with the following keys:
    - title: A catchy title for the puzzle
    - content: The text of the puzzle (can use simple HTML like <br> or <ul><li> for formatting)
    - type: The type of puzzle (e.g. Logic Grid, Sequence, Riddle)
    - solution: The actual solution
    
    Make it engaging and appropriate for the difficulty level. Do not wrap the JSON in markdown blocks like ```json ... ```, just return the raw JSON object.
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
    System role: You are a logic puzzle expert providing personalized hints.
    
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

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    """Grades the user's explicit answer via Gemini and updates adaptive stats."""
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
    You are an AI grading a logic puzzle.
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
            
            # Adaptive Difficulty Upgrade!
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
            # Adaptive Difficulty Downgrade! If they guess wrong extremely repeatedly or time is super long, we could lower it.
            # But let's just downgrade if they used 3 hints and still failed.
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
