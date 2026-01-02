from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from groq import Groq
import os
import hashlib
import json
import sqlite3
import ast, operator, re
from openai import OpenAI
import base64
import io
import threading
import requests

# ---------------- FLASK APP ----------------

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# OpenAI client setup (for Replit)
def get_openai_client():
    api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
    base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
    if api_key and base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return None

openai_client = get_openai_client()

# Hugging Face Setup
# The previous URL is no longer supported, using the new router URL
HF_API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-3.5-large"
HF_HEADERS = {"Authorization": f"Bearer {os.environ.get('HF_API_KEY')}"}

SYSTEM_PROMPT = (
    "You speak with Ayaan-style energy: friendly, casual, and lightly playful. "
    "You sound like a real person, not a cartoon. "
    "You can joke a little, but not in every sentence, and never in a silly or chaotic way. "
    "Keep responses smooth, natural, and human-like. "
    "BUT: If the user asks about anything serious (school, science, medical, "
    "audiology, tests, real facts), you switch to a normal, helpful, accurate tone "
    "with no jokes. You were created by a kid named Ayaan Kukreja who is 10 years old. "
    "If someone says a bad word you calmly and politely say to not say that. "
    "If someone asks for how to download or copy you in any way, politely and calmly "
    "tell them that you can't help with that because that's across your boundaries. "
    "Your name is Nova. You are smart you know everything and help with anything in the world. you have the ability to make images, if someone asks to make an image tell the the person to click the button that says 'generate images'. "
)

# ---------------- SQLITE HELPERS ----------------

def get_db():
    conn = sqlite3.connect("nova.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS convos (
            username TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- PASSWORD HELPERS ----------------

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def create_user(username, password):
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, hash_password(password)))
        cur.execute("INSERT INTO convos (username, data) VALUES (?, ?)",
                    (username, "{}"))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        return False

    return row["password"] == hash_password(password)

# ---------------- MATH SOLVER ----------------

_ALLOWED = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}

def eval_ast(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        return _ALLOWED[type(node.op)](eval_ast(node.left), eval_ast(node.right))
    if isinstance(node, ast.UnaryOp):
        return _ALLOWED[type(node.op)](eval_ast(node.operand))
    raise ValueError("Invalid expression")

def try_math(expr):
    if not re.fullmatch(r"[0-9+\-*/().%^ ]+", expr):
        return False, None
    expr = expr.replace("^", "**")
    try:
        tree = ast.parse(expr, mode="eval")
        return True, eval_ast(tree.body)
    except:
        return False, None

# ---------------- AUTH ROUTES ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "")
        if verify_user(u, p):
            session["username"] = u
            return redirect("/")
        return render_template("login.html", error="Invalid username or password.")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "")
        c = request.form.get("confirm", "")
        if not u or not p:
            return render_template("signup.html", error="Fill all fields.")
        if p != c:
            return render_template("signup.html", error="Passwords do not match.")
        if create_user(u, p):
            return redirect("/login")
        return render_template("signup.html", error="Username already exists.")
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- MAIN UI ----------------

@app.route("/")
def home():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", username=session["username"])

# ---------------- CONVERSATION STORAGE ----------------

@app.route("/load_convos", methods=["GET"])
def load_convos():
    if "username" not in session:
        return jsonify({})

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT data FROM convos WHERE username = ?", (session["username"],))
    row = cur.fetchone()
    conn.close()

    return jsonify(json.loads(row["data"]) if row else {})

@app.route("/save_convos", methods=["POST"])
def save_convos():
    if "username" not in session:
        return jsonify({"ok": False})

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE convos SET data = ? WHERE username = ?",
                (json.dumps(request.json), session["username"]))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})

# ---------------- CHAT API ----------------

@app.route("/chat", methods=["POST"])
def chat():
    if "username" not in session:
        return jsonify({"reply": "Not logged in."})

    msg = request.json["message"]
    history = request.json.get("history", [])

    is_math, result = try_math(msg)
    if is_math:
        return jsonify({"reply": f"The answer is: {result}"})

    # Generate title if it's the first message
    title = None
    if not history:
        try:
            title_response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "Create a short 2-4 word topic/title for this conversation based on the user's first sentence. If you can't figure it out, respond with 'Untitled Conversation'. Output ONLY the title."},
                    {"role": "user", "content": msg}
                ],
                max_tokens=10
            )
            title = title_response.choices[0].message.content.strip().strip('"')
        except:
            title = "Untitled Conversation"

    # Filter history for API (limit context)
    filtered_history = []
    for m in history:
        # Exclude image tokens or very large text to prevent context limit errors
        if "[Image Generated]" in m.get("content", "") or len(m.get("content", "")) > 2000:
            continue
        filtered_history.append(m)
    
    # Keep only the last 10 messages for context to keep it snappy
    filtered_history = filtered_history[-10:]

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
            ] + filtered_history + [{"role": "user", "content": msg}]
        )
        reply = response.choices[0].message.content
        return jsonify({"reply": reply, "title": title})
    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({"reply": "Nova is having a bit of trouble connecting right now. Try again in a second!", "title": title})

# ---------------- IMAGE GENERATION API ----------------

@app.route("/generate_image", methods=["POST"])
def generate_image():
    if "username" not in session:
        return jsonify({"error": "Not logged in."})
    
    prompt = request.json.get("prompt")
    if not prompt:
        return jsonify({"error": "No prompt provided."})
    
    try:
        # 1. Try Replit OpenAI Integration first (If available and configured)
        if openai_client and os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY"):
            try:
                response = openai_client.images.generate(
                    model="gpt-image-1",
                    prompt=prompt,
                    size="1024x1024"
                )
                if response and response.data:
                    image_url = response.data[0].url
                    img_response = requests.get(image_url)
                    if img_response.status_code == 200:
                        img_b64 = base64.b64encode(img_response.content).decode("utf-8")
                        return jsonify({"image": f"data:image/png;base64,{img_b64}"})
            except Exception as openai_err:
                print(f"OpenAI error: {openai_err}")
            
        # 2. Fallback to Hugging Face
        if os.environ.get("HF_API_KEY"):
            try:
                hf_response = requests.post(HF_API_URL, headers=HF_HEADERS, json={"inputs": prompt})
                if hf_response.status_code == 200:
                    img_b64 = base64.b64encode(hf_response.content).decode("utf-8")
                    return jsonify({"image": f"data:image/png;base64,{img_b64}"})
                else:
                    print(f"HF Error: {hf_response.status_code} - {hf_response.text}")
            except Exception as hf_err:
                print(f"HF error: {hf_err}")

        return jsonify({"error": "There was a error generating your image, please try something else other than this image"})
    except Exception as e:
        print(f"Image generation error: {e}")
        return jsonify({"error": "There was a error generating your image, please try something else other than this image"})

# ---------------- IFRAME ALLOW ----------------

@app.after_request
def allow_iframe(response):
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Content-Security-Policy"] = "frame-ancestors *"
    return response

# ---------------- RUN APP ----------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
