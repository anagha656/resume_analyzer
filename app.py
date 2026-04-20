import os
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # allows your HTML frontend to talk to this backend

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ─────────────────────────────────────────
# FUNCTIONS
# ─────────────────────────────────────────

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

    def analyze(self):
        self.email   = extract_email(self.text)
        self.phone   = extract_phone(self.text)
        self.skills  = extract_skills(self.text, self.REQUIRED_SKILLS)
        self.missing = [s for s in self.REQUIRED_SKILLS if s not in self.skills]
        self.score   = score_resume(self.skills, self.REQUIRED_SKILLS)
        return self

    def to_dict(self):
        """Convert results to a dict — Flask turns this into JSON."""
        return {
            "filename": self.filename,
            "email":    self.email,
            "phone":    self.phone,
            "skills":   self.skills,
            "missing":  self.missing,
            "score":    self.score,
            "result":   "Strong match" if self.score >= 70 else "Needs improvement"
        }


# ─────────────────────────────────────────
# ROUTES  (Flask listens at these URLs)
# ─────────────────────────────────────────

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Accepts a POST request with a text file upload.
    Returns the resume analysis as JSON.
    """
    # 1. Check a file was actually sent
    if "resume" not in request.files:
        return jsonify({"error": "No file uploaded. Send a file with key 'resume'"}), 400

    file = request.files["resume"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    # 2. Save the uploaded file
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    # 3. Read the text (for now we support .txt — PDF comes in the next step)
    try:
        with open(filepath, "r") as f:
            text = f.read()
    except Exception as e:
        return jsonify({"error": f"Could not read file: {str(e)}"}), 500

    # 4. Run your ResumeParser class
    parser = ResumeParser(text, file.filename)
    parser.analyze()

    # 5. Log the activity
    with open("log.txt", "a") as log:
        log.write(f"{file.filename} | score: {parser.score}% | email: {parser.email}\n")

    # 6. Return JSON — Flask's jsonify() converts the dict automatically
    return jsonify(parser.to_dict())


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)  # debug=True auto-reloads when you save changes
