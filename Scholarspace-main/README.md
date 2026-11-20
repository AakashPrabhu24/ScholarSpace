# ScholarSpace

ScholarSpace is a full-stack student productivity dashboard and study management web application built with Python and Django. It brings together homework tracking, study planning, automatic timetable generation, practice quizzes, and academic tools into a single platform.

---

## What It Does

Most students end up using 4 or 5 different apps to manage college work—one for notes, another for calendar events, a separate app for flashcards/quizzes, and random web tools for math or dictionary lookups. ScholarSpace combines these essentials into a clean, unified workspace:

- **Dashboard & Notes**: Quick note taking, homework deadline tracking, and a personal todo list.
- **Smart Workload Manager (`manage_work`)**: Add deadlines, automatically detect scheduling conflicts between assignments, generate balanced daily study routines, and receive email/SMS reminders.
- **Automated Timetable Generator**: Answer a brief study-habit questionnaire to generate a weekly study timetable tailored to your schedule.
- **Interactive Quiz Engine**: Create custom subject quizzes, add questions, practice with timed assessments, and review scores.
- **Course Portal**: Organized repository of study domains, subjects, and curated video lectures.
- **Academic Utilities**:
  - Math solver and equation graphing tool (with image/handwriting recognition support).
  - Book search querying Google Books and OpenLibrary with typo tolerance.
  - Educational YouTube search and video viewer.
  - Dictionary definitions and unit conversion calculator.
- **User Accounts & Google Sync**: Support for standard registration/login plus Google OAuth 2.0 and Google Calendar sync.
- **Interface**: Responsive layout with Dark / Light theme toggle and multi-language internationalization (i18n).

---

## Tech Stack

- **Backend**: Python 3.10+, Django 5.x
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 4 (`crispy-forms`), Tailwind CSS
- **Database**: SQLite3 (default for local development, easily swapped for PostgreSQL or MySQL)
- **External APIs & Services**:
  - Google Books API
  - Google Calendar API & Google OAuth 2.0
  - YouTube Search Python
  - Wikipedia API
  - Twilio SMS (optional, for study reminders)

---

## Project Structure

```text
ScholarSpace/
├── dashboard/           # Notes, homework, todo, dictionary, books, youtube search
├── manage_work/         # Deadline tracker, conflict detector, study plans, reminders
├── timetable_app/       # Survey-based weekly timetable generator
├── timetable_maker/     # Timetable configuration engine
├── quiz_app/            # Custom quiz builder, question banks, score tracking
├── portal/              # Course portal, academic domains, subjects & video lessons
├── calculator/          # Math solver, grapher, and equation recognition
├── ScholarSpace/        # Core Django project settings, root URLs, and WSGI/ASGI
├── locale/              # Multi-language translation files (i18n)
├── manage.py            # Django management CLI
├── requirements.txt     # Python dependencies
└── .env.example         # Template for environment variables
```

---

## Getting Started

### Prerequisites

- Python 3.10, 3.11, or 3.12 installed on your machine
- Git
- `pip` (Python package manager)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/ScholarSpace.git
   cd ScholarSpace
   ```

2. **Create and activate a virtual environment:**
   - On Windows (PowerShell / Command Prompt):
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   - On macOS / Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Copy the example environment file and create your local `.env`:
   - On Windows:
     ```powershell
     copy .env.example .env
     ```
   - On macOS / Linux:
     ```bash
     cp .env.example .env
     ```

   Open `.env` in an editor and configure your keys. (Basic features like notes, todos, quizzes, and timetable work even without third-party API keys).

5. **Run database migrations:**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser (optional, for Django admin access):**
   ```bash
   python manage.py createsuperuser
   ```

7. **Start the development server:**
   ```bash
   python manage.py runserver
   ```

8. Open your browser and navigate to:
   ```text
   http://127.0.0.1:8000/
   ```

---

## Environment Variables (.env)

| Variable | Description | Required? |
| :--- | :--- | :--- |
| `DJANGO_SECRET_KEY` | Secret key for Django cryptographic signing | Recommended in production |
| `DEBUG` | Set to `True` for local development, `False` for production | Yes |
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth 2.0 Client ID from Google Cloud Console | Optional (for Google login) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth 2.0 Client Secret from Google Cloud Console | Optional (for Google login) |
| `GOOGLE_CALENDAR_API_KEY` | API key with Google Calendar enabled | Optional (for Calendar sync) |
| `GOOGLE_BOOKS_API_KEY` | API key with Google Books enabled | Optional (falls back to OpenLibrary) |
| `GEMINI_API_KEY` | Google Gemini API key for smart features | Optional |
| `EMAIL_HOST_USER` | SMTP email address for sending reminders | Optional |
| `EMAIL_HOST_PASSWORD` | SMTP app password for sending reminders | Optional |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID for SMS reminders | Optional |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token for SMS reminders | Optional |
| `TWILIO_PHONE_NUMBER` | Twilio Phone Number | Optional |

---

## Contributing

Pull requests are welcome! If you want to contribute:

1. Fork this repository.
2. Create a new feature branch (`git checkout -b feature/new-tool`).
3. Commit your changes (`git commit -m "Add new student utility"`).
4. Push to the branch (`git push origin feature/new-tool`).
5. Open a Pull Request.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
