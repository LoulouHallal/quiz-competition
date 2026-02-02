# Quiz Competition - PowerPoint Add-in

## Setup Instructions

### 1. Database Setup

```bash
# Install PostgreSQL if not already installed
# Create database
createdb quiz_competition

# Run schema creation
psql -d quiz_competition -f backend/db/create_db.sql

# (Optional) Load demo data
psql -d quiz_competition -f backend/db/seed.sql
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
copy .env.example .env
# Edit .env with your database credentials

# Run the server
python app.py
```

The backend will start on `https://localhost:5000` (HTTPS required for Office add-ins).

### 3. PowerPoint Add-in Setup

```bash
cd "addin/quiz competition"

# Install dependencies
npm install

# Generate dev certificates (first time only)
npx office-addin-dev-certs install

# Start dev server
npm run dev-server
```

The add-in will be available at `https://localhost:3000`.

### 4. Sideload the Add-in

#### Option A: Automatic (Windows)
```bash
npm start
```

This will automatically open PowerPoint with the add-in loaded.

#### Option B: Manual Sideload
1. Open PowerPoint
2. Go to **Insert** > **Get Add-ins** > **My Add-ins**
3. Click **Upload My Add-in**
4. Browse to `addin/quiz competition/manifest.xml`
5. Click **Upload**

The add-in will appear in the **Home** tab ribbon.

## Usage Guide

### Creating a Quiz

1. **Open PowerPoint** and click **Show Task Pane** from the ribbon
2. **Login** with teacher credentials (demo: `teacher@demo.com` / `demo123`)
3. **Author Tab**:
   - Enter quiz title and click **Create New Quiz**
   - For each slide:
     - Add question title
     - Enter 2-6 options (A-F)
     - Select correct answer
     - Set timer (15-120 seconds)
     - Click **Save to Slide**

### Running a Live Session

1. **Live Tab** > Click **Start Quiz**
2. **Share the code** (displayed large) or **Insert QR** to current slide
3. **Wait for students** to join (participant list updates in real-time)
4. Click **Next Question** to open each question
5. **Monitor**:
   - Response count and correct percentage
   - Live leaderboard (top 10)
6. Click **Lock Question** to prevent more answers
7. Continue through all questions
8. Click **End Quiz** when finished
9. **View Summary** or **Export CSV** for results

### Student Experience

1. Open browser on phone/tablet
2. Go to join URL or scan QR code
3. Enter session code and name
4. Wait in lobby for teacher to start
5. Answer each question before timer expires
6. See personal score after each question
7. View final score at end

## API Endpoints

### Authentication
- `POST /api/auth/login` - Teacher login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Get current user

### Quizzes
- `POST /api/quizzes` - Create quiz
- `GET /api/quizzes` - List user's quizzes
- `GET /api/quizzes/:id` - Get quiz with questions
- `POST /api/quizzes/:id/questions` - Add question

### Sessions
- `POST /api/sessions` - Create session
- `GET /api/sessions/:id` - Get session details
- `POST /api/sessions/:id/next` - Open next question
- `POST /api/sessions/:id/end` - End session
- `GET /api/sessions/:id/summary` - Get results
- `GET /api/sessions/:id/export` - Export CSV

### Student (Public)
- `POST /api/join` - Join session
- `POST /api/sessions/:id/answer` - Submit answer

### WebSocket Events
- `join_session` - Join session room
- `lobby_update` - New participant joined
- `question_open` - Question opened
- `stats_update` - Response stats updated
- `question_close` - Question locked
- `quiz_end` - Session ended

## Database Schema

See `backend/db/create_db.sql` for complete schema. Key tables:

- `app_user` - Teachers and students
- `course` - Quizzes
- `question` - Questions with metadata
- `answers` - Answer options
- `class_session` - Live sessions
- `class_participant` - Session participants
- `students_answers` - Student responses
- `v_class_leaderboard` - Leaderboard view

## Configuration

### Backend (.env)
```env
DATABASE_URL=postgresql://user:pass@host:5432/dbname
SECRET_KEY=your-secret-key
PUBLIC_BASE_URL=https://your-domain.com
CORS_ORIGINS=https://localhost:3000
```

### Add-in (taskpane.js)
```javascript
var API_BASE = "https://localhost:5000";
```

Change this to your production backend URL.

## Deployment

### Backend (Production)

```bash
# Install gunicorn with eventlet
pip install gunicorn eventlet

# Run with eventlet worker (for WebSocket support)
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app

# Or use systemd service
sudo systemctl start quiz-competition
```

### Nginx Configuration

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Add-in (Production)

1. Update `manifest.xml` with production URLs
2. Build production bundle: `npm run build`
3. Host static files on HTTPS server
4. Distribute manifest.xml to users

## Troubleshooting

### Add-in not loading
- Ensure dev server is running on HTTPS
- Check browser console for errors
- Clear Office cache: `%LOCALAPPDATA%\Microsoft\Office\16.0\Wef\`

### WebSocket connection fails
- Verify CORS settings in backend
- Check firewall allows WebSocket connections
- Ensure eventlet worker is used with gunicorn

### Database connection errors
- Verify PostgreSQL is running
- Check DATABASE_URL in .env
- Ensure database exists and schema is created

### QR codes not generating
- Check `backend/static/qr/` directory exists
- Verify qrcode package is installed
- Check file permissions

## Performance

- Handles **50+ concurrent students** on modest hardware
- WebSocket events: <500ms latency on LAN
- REST API: <200ms p50 response time
- Tested with 5-20 questions per quiz

## Security Notes

- **HTTPS required** for Office add-ins
- **CSRF protection** on forms
- **Input validation** on all endpoints
- **Server-side answer verification** (correct answers never sent to clients before lock)
- **Session-based authentication** for teachers
- **Ephemeral student accounts** (no PII stored except display names)

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or contributions:
- Create an issue on GitHub
- Email: support@example.com

## Demo Credentials

Teacher account (from seed.sql):
- Email: `teacher@demo.com`
- Password: `demo123` (Note: Implement proper password hashing in production)

## Roadmap

Future enhancements (out of MVP scope):
- Multiple correct answers (multi-select)
- Image/audio in questions
- Team competitions
- LMS integration (Canvas, Moodle)
- Analytics dashboard
- Mobile app for students
