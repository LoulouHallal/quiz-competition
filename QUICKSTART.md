# Quick Start - 5 Minutes to Your First Quiz

## Prerequisites Check
- [ ] PostgreSQL installed and running
- [ ] Python 3.8+ installed
- [ ] Node.js 14+ installed
- [ ] PowerPoint (Office 365 or 2019+)

## Step 1: Database (2 minutes)

```bash
# Create database
createdb quiz_competition

# Initialize schema and demo data
cd backend
python init_db.py --seed
```

You should see:
```
✓ Database initialization completed successfully!

Demo Teacher Account:
  Email: teacher@demo.com
  Password: demo123
```

## Step 2: Backend (1 minute)

```bash
# Still in backend directory
pip install -r requirements.txt
python run.py
```

You should see:
```
Server starting on https://localhost:5000
```

Keep this terminal open.

## Step 3: Add-in (1 minute)

Open a NEW terminal:

```bash
cd "addin/quiz competition"
npm install
npm start
```

PowerPoint will open automatically with the add-in loaded.

## Step 4: Test (1 minute)

### In PowerPoint:
1. Click "Show Task Pane" in ribbon
2. Login with: `teacher@demo.com` / `demo123`
3. You'll see a demo quiz already loaded!

### Test the Demo Quiz:
1. Click **Live** tab
2. Click **Start Quiz**
3. Note the 6-digit code

### Join as Student:
1. Open browser: `https://localhost:5000/join`
2. Enter the code and your name
3. Click "Join Quiz"

### Run the Quiz:
1. In PowerPoint, click **Next Question**
2. In browser, answer the question
3. Watch the leaderboard update in PowerPoint!

## Troubleshooting

### "Database connection failed"
```bash
# Check PostgreSQL is running
# Windows:
net start postgresql-x64-14

# Verify connection:
psql -d quiz_competition -c "SELECT 1"
```

### "Port 5000 already in use"
```bash
# Find and kill the process
# Windows:
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

### "Add-in not loading"
1. Clear Office cache:
   - Close PowerPoint
   - Delete: `%LOCALAPPDATA%\Microsoft\Office\16.0\Wef\`
   - Restart PowerPoint
   - Run `npm start` again

### "Certificate error in browser"
- Click "Advanced" > "Proceed to localhost (unsafe)"
- This is normal for development with self-signed certificates

## Next Steps

1. **Create Your Own Quiz**:
   - Author tab > Enter title > Create New Quiz
   - Add questions to slides
   - Start a new session

2. **Read Full Documentation**:
   - `README.md` - Complete setup and API docs
   - `ADMIN_GUIDE.md` - Teacher guide with best practices

3. **Production Deployment**:
   - Update `.env` with production database
   - Configure HTTPS with real certificates
   - Update `manifest.xml` with production URLs
   - Deploy backend with gunicorn + nginx

## Demo Quiz Questions

The seed data includes 5 questions:

1. What is the capital of France? (Answer: Paris)
2. Which planet is known as the Red Planet? (Answer: Mars)
3. What is 15 × 8? (Answer: 120)
4. Who wrote "Romeo and Juliet"? (Answer: William Shakespeare)
5. What is the largest ocean on Earth? (Answer: Pacific Ocean)

## Common Commands

```bash
# Start backend
cd backend
python run.py

# Start add-in dev server
cd "addin/quiz competition"
npm run dev-server

# Sideload add-in automatically
npm start

# Build for production
npm run build

# Reset database
dropdb quiz_competition
createdb quiz_competition
python init_db.py --seed
```

## Support

- Issues: Create GitHub issue
- Questions: Check README.md and ADMIN_GUIDE.md
- Email: support@example.com

---

**You're ready to go! 🎉**

Create your first quiz and run a live session with your students!
