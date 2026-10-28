# Learnly – Online Learning Management System

A simple LMS built with Flask and SQLite.

## Features
- Student and teacher registration and login (hashed passwords)
- Teachers create courses and add lessons
- Students enroll, read lessons, mark them complete and track progress
- Teachers see enrollment counts

## Project structure
```
app.py             Flask app (routes, database, templates)
requirements.txt   Python dependencies
frontend-demo/     Standalone browser demo (open index.html)
```

## Run locally
```bash
git clone <your-repo-url>
cd <repo-folder>
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

For development mode set `FLASK_DEBUG=1`. In production set a real `SECRET_KEY`.

## Future work
Quizzes, file uploads, admin panel, certificates.
