from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from groq import Groq
import os
import hashlib
import json

try:
    from replit import db
except ImportError:
    db = None

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")

client = Groq(api_key=os.environ["GROQ_API_KEY"])

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
    "Your name is Nova."
)

# ---------------- PASSWORD HELPERS ----------------

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def create_user(username, password):
    if db is None:
        return False
    key = f"user:{username}"
    if key in db:
        return False
    db[key] = hash_password(password)
    db[f"convos:{username}"] = "{}"
    return True

def verify_user(username, password):
    if db is None:
        return False
    key = f"user:{username}"
    if key not in db:
        return False
    return db[key] == hash_password(password)

# ---------------- MATH SOLVER ----------------

import ast, operator, re

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
        return redirect("/login")
    return render_template("index.html", username=session["username"])

# ---------------- CHAT API ----------------

@app.route("/load_convos", methods=["GET"])
def load_convos():
    if "username" not in session:
        return jsonify({})
    key = f"convos:{session['username']}"
    raw = db.get(key, "{}")
    return jsonify(json.loads(raw))

@app.route("/save_convos", methods=["POST"])
def save_convos():
    if "username" not in session:
        return jsonify({"ok": False})
    key = f"convos:{session['username']}"
    db[key] = json.dumps(request.json)
    return jsonify({"ok": True})

@app.route("/chat", methods=["POST"])
def chat():
    if "username" not in session:
        return jsonify({"reply": "Not logged in."})

    msg = request.json["message"]
    is_math, result = try_math(msg)
    if is_math:
        return jsonify({"reply": f"The answer is: {result}"})

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": msg}
        ]
    )

    reply = response.choices[0].message.content
    return jsonify({"reply": reply})

@app.after_request
def allow_iframe(response):
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Content-Security-Policy"] = "frame-ancestors *"
    return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)