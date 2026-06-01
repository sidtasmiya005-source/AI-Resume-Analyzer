import os, re, uuid
from datetime import datetime
from collections import Counter
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

try:
    import pdfplumber
except Exception:
    pdfplumber = None
try:
    import docx
except Exception:
    docx = None

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

app = Flask(__name__)
# New key every run: project start karte hi login page aayega
app.secret_key = "simple-flow-" + str(uuid.uuid4())
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

FIELD_SKILLS = {
    "Machine Learning / Data Science": ["python", "machine learning", "deep learning", "tensorflow", "pytorch", "scikit", "pandas", "numpy", "statistics", "sql", "nlp", "computer vision", "data analysis", "matplotlib"],
    "Web Development": ["html", "css", "javascript", "react", "node", "express", "flask", "django", "api", "mongodb", "mysql", "bootstrap", "tailwind", "git"],
    "Embedded / IoT / ECE": ["arduino", "esp32", "esp8266", "raspberry pi", "iot", "sensor", "microcontroller", "embedded", "pcb", "circuit", "proteus", "matlab", "vlsi", "verilog"],
    "Cyber Security": ["cyber", "network security", "linux", "kali", "penetration", "vulnerability", "owasp", "firewall", "encryption", "nmap"],
    "Cloud / DevOps": ["aws", "azure", "gcp", "docker", "kubernetes", "linux", "ci/cd", "jenkins", "terraform", "git"],
    "Business / Finance / Marketing": ["excel", "financial", "accounting", "marketing", "sales", "business", "analytics", "power bi", "tableau", "crm"],
    "Core Engineering": ["autocad", "solidworks", "catia", "ansys", "manufacturing", "thermal", "mechanical", "civil", "construction", "quality"],
    "Design / Creative": ["photoshop", "illustrator", "figma", "canva", "ui", "ux", "branding", "video", "editing", "portfolio"]
}
ACTION_VERBS = ["developed", "created", "designed", "implemented", "built", "managed", "improved", "optimized", "analyzed", "led", "deployed", "tested", "automated", "trained"]
STOPWORDS = set("a an the and or of in on for to with from by at is are was were be been being this that as it i we you he she they them our your my me us".split())

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(path):
    ext = path.rsplit(".", 1)[1].lower()
    if ext == "pdf":
        if not pdfplumber:
            return ""
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        return text.strip()
    if ext == "docx":
        if not docx:
            return ""
        document = docx.Document(path)
        return "\n".join([p.text for p in document.paragraphs]).strip()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()

def clean_words(text):
    words = re.findall(r"[a-zA-Z][a-zA-Z+#.\-]{1,}", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]

def contains_any(text, items):
    low = text.lower()
    return [x for x in items if x.lower() in low]

def section_found(text, names):
    low = text.lower()
    return any(re.search(r"(^|\n|\s)(" + re.escape(n) + r")(\s|:|\n)", low) for n in names)

def analyze_resume(text, job_description=""):
    low = text.lower(); words = clean_words(text); word_count = len(words)
    email_found = bool(re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text))
    phone_found = bool(re.search(r"(\+?\d[\d\s\-()]{8,}\d)", text))
    linkedin_found = "linkedin" in low; github_found = "github" in low or "gitlab" in low
    sections = {
        "Summary": section_found(text, ["summary", "profile", "objective", "career objective"]),
        "Skills": section_found(text, ["skills", "technical skills", "key skills"]),
        "Projects": section_found(text, ["projects", "project work", "academic projects"]),
        "Experience": section_found(text, ["experience", "internship", "work experience", "employment"]),
        "Education": section_found(text, ["education", "qualification", "academic"]),
        "Certifications": section_found(text, ["certification", "certifications", "awards", "achievements"]),
    }
    field_matches = {}
    for field, skills in FIELD_SKILLS.items():
        found = contains_any(low, skills)
        field_matches[field] = {"found": found, "score": round((len(found) / len(skills)) * 100)}
    best_field = max(field_matches, key=lambda k: field_matches[k]["score"])
    best_skills = FIELD_SKILLS[best_field]
    found_best = field_matches[best_field]["found"]
    missing_best = [s for s in best_skills if s not in found_best][:12]
    jd_score = None; jd_missing = []
    if job_description.strip():
        jd_words = set(clean_words(job_description)); resume_words = set(words)
        important = [w for w in jd_words if len(w) > 3]
        matched = [w for w in important if w in resume_words]
        jd_score = round((len(matched) / max(len(important), 1)) * 100)
        jd_missing = [w for w in important if w not in resume_words][:12]
    action_found = contains_any(low, ACTION_VERBS)
    numbers_found = bool(re.search(r"\d+\s*(%|percent|projects?|months?|years?|users?|clients?|students?|hours?)", low))
    ats_score = 0
    ats_score += 10 if email_found else 0; ats_score += 10 if phone_found else 0
    ats_score += 8 if linkedin_found else 0; ats_score += 6 if github_found else 0
    ats_score += sum(8 for v in sections.values() if v)
    ats_score += min(18, len(found_best) * 3)
    ats_score += 8 if len(action_found) >= 3 else len(action_found) * 2
    ats_score += 8 if numbers_found else 0
    ats_score += 8 if 250 <= word_count <= 900 else 3
    ats_score = min(100, ats_score)
    suggestions = []
    if not email_found or not phone_found: 
        suggestions.append("Add a clear email address and phone number at the top of your resume.")
    if not linkedin_found:
        suggestions.append("Add your LinkedIn profile link.")
    if not github_found and best_field in ["Machine Learning / Data Science", "Web Development", "Embedded / IoT / ECE", "Cloud / DevOps"]: 
        suggestions.append("Add your GitHub or portfolio link.")
    for sec, present in sections.items():
        if not present: 
            suggestions.append(f"Add a proper {sec} section.")
    if len(found_best) < 5:
        suggestions.append(f"Add more keywords relevant to {best_field}: " +", ".join(missing_best[:5]) + ".")
    if not numbers_found:
        suggestions.append("Include measurable achievements such as accuracy improvement, completed projects, or time saved.")
    if len(action_found) < 3: 
        suggestions.append("Start bullet points with strong action verbs like Developed, Designed, Implemented, or Built.")
    if word_count < 250:
        suggestions.append("Your resume is too short. Add more details about projects, tools, roles, and impact.")
    if word_count > 900:
        suggestions.append("Your resume is too long. Keep it concise and ATS-friendly within one or two pages.")
    roles = {
        "Machine Learning / Data Science": ["Data Analyst", "ML Engineer Intern", "Python Developer", "AI Project Intern"],
        "Web Development": ["Frontend Developer", "Full Stack Developer", "Flask/Django Developer", "React Developer"],
        "Embedded / IoT / ECE": ["Embedded Engineer", "IoT Developer", "Hardware Testing Engineer", "VLSI Trainee"],
        "Cyber Security": ["SOC Analyst", "Cyber Security Intern", "Network Security Trainee"],
        "Cloud / DevOps": ["Cloud Support Associate", "DevOps Intern", "Linux Administrator"],
        "Business / Finance / Marketing": ["Business Analyst", "Marketing Executive", "Financial Analyst Trainee"],
        "Core Engineering": ["Graduate Engineer Trainee", "Design Engineer", "Quality Engineer"],
        "Design / Creative": ["UI/UX Designer", "Graphic Designer", "Content Designer"]
    }
    return {
        "ats_score": ats_score, "best_field": best_field, "found_skills": found_best,
        "missing_skills": missing_best, "sections": sections, "email_found": email_found,
        "phone_found": phone_found, "linkedin_found": linkedin_found, "github_found": github_found,
        "word_count": word_count, "action_verbs": action_found, "numbers_found": numbers_found,
        "suggestions": suggestions[:12], "roles": roles.get(best_field, []), "jd_score": jd_score,
        "jd_missing": jd_missing, "top_words": Counter(words).most_common(15),
        "date": datetime.now().strftime("%d %b %Y, %I:%M %p")
    }

def create_pdf_report(result):
    filename = f"resume_report_{uuid.uuid4().hex[:8]}.pdf"
    path = os.path.join(REPORT_DIR, filename)
    c = canvas.Canvas(path, pagesize=A4); w, h = A4; y = h - 50
    c.setFont("Helvetica-Bold", 18); c.drawString(40, y, "AI Resume Analyzer Report"); y -= 30
    c.setFont("Helvetica", 10); c.drawString(40, y, f"Generated: {result['date']}"); y -= 30
    c.setFont("Helvetica-Bold", 13); c.drawString(40, y, f"ATS Score: {result['ats_score']} / 100"); y -= 22
    c.drawString(40, y, f"Detected Field: {result['best_field']}"); y -= 30
    c.setFont("Helvetica-Bold", 12); c.drawString(40, y, "Found Skills:"); y -= 18
    c.setFont("Helvetica", 10); c.drawString(55, y, ", ".join(result['found_skills'][:15]) or "Not enough skills found"); y -= 30
    c.setFont("Helvetica-Bold", 12); c.drawString(40, y, "Missing / Recommended Skills:"); y -= 18
    c.setFont("Helvetica", 10); c.drawString(55, y, ", ".join(result['missing_skills'][:15]) or "Good coverage"); y -= 30
    c.setFont("Helvetica-Bold", 12); c.drawString(40, y, "Improvement Suggestions:"); y -= 18
    c.setFont("Helvetica", 10)
    for i, s in enumerate(result['suggestions'], 1):
        for j, line in enumerate([s[k:k+90] for k in range(0, len(s), 90)]):
            c.drawString(55, y, f"{i}. {line}" if j == 0 else f"   {line}"); y -= 15
            if y < 60: c.showPage(); y = h - 50; c.setFont("Helvetica", 10)
    c.save(); return filename

@app.before_request
def require_login():
    public = {"login", "google_login", "static"}
    if request.endpoint not in public and "user" not in session:
        return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            flash("Email enter karo.", "danger"); return redirect(url_for("login"))
        session["user"] = email; session["name"] = email.split("@")[0].title()
        return redirect(url_for("home"))
    return render_template("login.html")

@app.route("/google-login")
def google_login():
    session["user"] = "google_user@example.com"; session["name"] = "Google User"
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/analyze", methods=["GET", "POST"])
def analyze():
    if request.method == "POST":
        file = request.files.get("resume"); jd = request.form.get("job_description", "")
        if not file or file.filename == "":
            flash("Resume file upload karo.", "danger"); return redirect(url_for("analyze"))
        if not allowed_file(file.filename):
            flash("Only PDF, DOCX aur TXT supported hai.", "danger"); return redirect(url_for("analyze"))
        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:8]}_{filename}"); file.save(path)
        text = extract_text(path)
        if len(text.strip()) < 40:
            flash("Resume text read nahi ho paya. Text-based PDF/DOCX use karo, scanned image PDF nahi.", "danger")
            return redirect(url_for("analyze"))
        result = analyze_resume(text, jd); report_name = create_pdf_report(result)
        result["report_name"] = report_name; session["last_result"] = result
        return redirect(url_for("processing"))
    return render_template("analyze.html")

@app.route("/processing")
def processing():
    if not session.get("last_result"): return redirect(url_for("analyze"))
    return render_template("processing.html")

@app.route("/result")
def result():
    if not session.get("last_result"): return redirect(url_for("analyze"))
    return render_template("result.html", result=session["last_result"])

@app.route("/roadmap")
def roadmap():
    if not session.get("last_result"): return redirect(url_for("analyze"))
    return render_template("roadmap.html", result=session["last_result"])

@app.route("/uploads-history")
def uploads_history():
    if not session.get("user"):
        return redirect(url_for("login"))

    upload_files = []
    for name in sorted(os.listdir(UPLOAD_DIR)):
        path = os.path.join(UPLOAD_DIR, name)
        if os.path.isfile(path):
            upload_files.append({
                "name": name,
                "size": round(os.path.getsize(path) / 1024, 2),
                "time": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%d %b %Y, %I:%M %p")
            })

    report_files = []
    for name in sorted(os.listdir(REPORT_DIR)):
        path = os.path.join(REPORT_DIR, name)
        if os.path.isfile(path):
            report_files.append({
                "name": name,
                "size": round(os.path.getsize(path) / 1024, 2),
                "time": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%d %b %Y, %I:%M %p")
            })

    return render_template("uploads_history.html", upload_files=upload_files, report_files=report_files)

@app.route("/download-report/<filename>")
def download_report(filename):
    path = os.path.join(REPORT_DIR, secure_filename(filename))
    if not os.path.exists(path):
        flash("Report file not found. Resume dobara analyze karo.", "danger"); return redirect(url_for("result"))
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
