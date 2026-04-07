# 🔐 Secure Keylogger-Based Log Monitoring and Analysis System

## 📌 Overview

This project is an advanced cybersecurity-focused system that captures keystroke data, securely stores logs, and analyzes them through a web-based dashboard.

The system is designed for **ethical monitoring, threat detection, and behavioral analysis**.

---

## 🚀 Features

* ⌨️ Real-time keystroke capture
* 🔐 Encrypted log storage
* 🌐 Remote log transmission to server
* 📊 Web dashboard for log analysis
* 📁 Organized logs (date & time-based storage)
* ⚡ Automatic log upload every 15 minutes
* 🛑 Sends logs on process termination

---

## 🏗️ Architecture

Client (Keylogger) → Encryption → Server → Database → Web Dashboard

---

## 🛠️ Tech Stack

* Python
* Flask (Web Dashboard)
* REST API
* SQLite Database

---

## 📂 Project Structure

```
keylogger.py          # Captures keystrokes
server.py             # Handles incoming logs
analysis_engine.py    # Processes logs
database.db           # Stores logs (ignored in Git)
```

---

## ⚙️ Setup Instructions

1. Clone repository:

```
git clone https://github.com/your-username/keylogger-project.git
```

2. Install dependencies:

```
pip install -r requirements.txt
```

3. Run server:

```
python server.py
```

4. Run keylogger:

```
python keylogger.py
```

---

## ⚠️ Ethical Disclaimer

This project is developed strictly for:

* Educational purposes
* Cybersecurity research
* Authorized monitoring environments only

Do NOT use this for unauthorized surveillance.

---

## 👨‍💻 Author

Dheeraj Poreddy
