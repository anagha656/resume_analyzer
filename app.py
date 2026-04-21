import os
import re
import fitz  # PyMuPDF
from groq import Groq
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Set up Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ─────────────────────────────────────────
# FUNCTIONS
# ─────────────────────────────────────────

def extract_text_from_file(filepath):
    """Read text from either a PDF or a TXT file."""
    if filepath.endswith(".pdf"):
        text = ""
        doc = fitz.open(filepath)
        for page in doc:
            text += page.get_text()
        return text
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

def extract_email(text):
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(pattern, text)
    return match.group() if match else "Not found"

def extract_phone(text):
    pattern = r'[\+]?[\d\s\-\(\)]{10,15}'
    match = re.search(pattern, text)
    return match.group().strip() if match else "Not found"

def extract_skills(text, skill_list):
    text_lower = text.lower()
    return [skill for skill in skill_list if skill.lower() in text_lower]

def score_resume(found_skills, required_skills):
    if not required_skills:
        return 0
    return round(len(found_skills) / len(required_skills) * 100)

def get_ai_feedback(resume_text, skills_found, skills_missing):
    """Send resume to Groq and get back feedback."""
    prompt = f"""
You are a professional resume reviewer helping a college student improve their resume.

Here is their resume:
{resume_text}

Skills found: {', '.join(skills_found) if skills_found else 'None'}
Skills missing: {', '.join(skills_missing) if skills_missing else 'None'}

Give short, friendly, and specific feedback in 3 sections:
1. Strengths (what looks good)
2. Missing skills (what to learn or add)
3. One tip to improve the resume

Keep it under 150 words. Be encouraging — this is a student project.
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI feedback unavailable: {str(e)}"


# ─────────────────────────────────────────
# CLASS
# ─────────────────────────────────────────

class ResumeParser:
    REQUIRED_SKILLS = ["python", "flask", "sql", "git", "html", "css", "javascript"]

    def __init__(self, text, filename):
        self.text     = text
        self.filename = filename
        self.email    = None
        self.phone    = None
        self.skills   = []
        self.missing  = []
        self.score    = 0
        self.feedback = ""

    def analyze(self):
        self.email    = extract_email(self.text)
        self.phone    = extract_phone(self.text)
        self.skills   = extract_skills(self.text, self.REQUIRED_SKILLS)
        self.missing  = [s for s in self.REQUIRED_SKILLS if s not in self.skills]
        self.score    = score_resume(self.skills, self.REQUIRED_SKILLS)
        self.feedback = get_ai_feedback(self.text, self.skills, self.missing)
        return self

    def to_dict(self):
        return {
            "filename": self.filename,
            "email":    self.email,
            "phone":    self.phone,
            "skills":   self.skills,
            "missing":  self.missing,
            "score":    self.score,
            "result":   "Strong match" if self.score >= 70 else "Needs improvement",
            "feedback": self.feedback
        }


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    if "resume" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["resume"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    if not (file.filename.endswith(".pdf") or file.filename.endswith(".txt")):
        return jsonify({"error": "Only .pdf and .txt files are supported"}), 400

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    try:
        text = extract_text_from_file(filepath)
    except Exception as e:
        return jsonify({"error": f"Could not read file: {str(e)}"}), 500

    parser = ResumeParser(text, file.filename)
    parser.analyze()

    with open("log.txt", "a") as log:
        log.write(f"{file.filename} | score: {parser.score}% | email: {parser.email}\n")

    return jsonify(parser.to_dict())


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)
