from flask import Flask, request, jsonify, send_file, render_template, session, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import os
import json
from datetime import datetime, timedelta
import re
from config import Config
from models.user import User
from models.quiz import Quiz
from models.question import Question
from models.session import Session
from models.participant import Participant
from models.response import Response
from services.scoring import ScoringService
from services.qr_generator import QRGenerator
from models.database import db

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object(Config)
Config.init_app(app)

# Initialize extensions
CORS(app, 
     resources={r"/api/*": {"origins": "*"}},
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Active sessions tracking (in-memory for real-time state)
active_sessions = {}  # {session_code: {question_start_time, current_question_id, participants: set()}}
def slugify(s):
    s = (s or '').strip().lower()
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'[^a-z0-9_\-]', '', s)
    return s[:50]
@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))

# Helper to get current user from session or Flask-Login
def get_current_user():
    """Get current authenticated user."""
    if current_user.is_authenticated:
        return current_user
    elif 'user_id' in session:
        return User.get_by_id(session['user_id'])
    return None

# Simple auth decorator for development (bypasses Flask-Login session issues)
def simple_auth_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if user:
            # Store user in Flask's g object for access in route handlers
            from flask import g
            g.current_user = user
            return f(*args, **kwargs)
        else:
            # For MVP development: If no session, use the demo teacher account
            # This bypasses the cross-origin cookie issue
            demo_user = User.get_by_email('teacher@demo.com')
            if demo_user:
                from flask import g
                g.current_user = demo_user
                return f(*args, **kwargs)
            return jsonify({'error': 'Unauthorized'}), 401
    return decorated_function

# ============================================================================
# Authentication Routes
# ============================================================================

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Teacher login."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    user = User.get_by_email(email)
    
    # For MVP, we'll do simple authentication
    # In production, add password hashing
    if user:
        login_user(user, remember=True)
        session['user_id'] = user.id
        session.permanent = True
        response = jsonify({
            'success': True,
            'teacher': user.to_dict()
        })
        return response
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/auth/logout', methods=['POST'])
@simple_auth_required
def logout():
    """Teacher logout."""
    logout_user()
    return jsonify({'success': True})

@app.route('/api/auth/me', methods=['GET'])
@simple_auth_required
def get_current_user_info():
    """Get current logged-in user."""
    from flask import g
    user = g.current_user if hasattr(g, 'current_user') else current_user
    return jsonify({'teacher': user.to_dict()})

# ============================================================================
# Quiz/Course Routes
# ============================================================================

@app.route('/api/quizzes', methods=['POST'])
@simple_auth_required
def create_quiz():
    """Create a new quiz."""
    from flask import g
    data = request.get_json()
    title = data.get('title')
    
    if not title:
        return jsonify({'error': 'Title required'}), 400
    
    user = g.current_user if hasattr(g, 'current_user') else current_user
    quiz_id = Quiz.create(user.id, title)
    return jsonify({'id': quiz_id, 'title': title}), 201

@app.route('/api/quizzes/<int:quiz_id>', methods=['GET'])
@simple_auth_required
def get_quiz(quiz_id):
    """Get quiz with all questions."""
    quiz = Quiz.get_by_id(quiz_id)
    if not quiz:
        return jsonify({'error': 'Quiz not found'}), 404
    
    return jsonify(quiz)

@app.route('/api/quizzes', methods=['GET'])
@simple_auth_required
def list_quizzes():
    """List all quizzes for current user."""
    from flask import g
    user = g.current_user if hasattr(g, 'current_user') else current_user
    quizzes = Quiz.get_by_user(user.id)
    return jsonify([dict(q) for q in quizzes])

@app.route('/api/quizzes/<int:quiz_id>', methods=['DELETE'])
@simple_auth_required
def delete_quiz(quiz_id):
    """Delete a quiz."""
    from flask import g
    user = g.current_user if hasattr(g, 'current_user') else current_user
    success = Quiz.delete(quiz_id, user.id)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Quiz not found or unauthorized'}), 404

# ============================================================================
# Question Routes
# ============================================================================

@app.route('/api/quizzes/<int:quiz_id>/questions', methods=['POST'])
@simple_auth_required
def create_question(quiz_id):
    """Create a question for a quiz."""
    data = request.get_json()
    
    question_content = data.get('title') or data.get('question_content')
    options = data.get('options', [])
    correct_index = data.get('correctIndex')
    timer_seconds = data.get('timerSeconds', 30)
    
    if not question_content or not options or correct_index is None:
        return jsonify({'error': 'Missing required fields'}), 400
    
    # For MVP, single correct answer (mcq_single = questiontype_id 1)
    question_id = Question.create(
        course_id=quiz_id,
        question_content=question_content,
        questiontype_id=1,  # mcq_single
        points=100,
        time_limit_seconds=timer_seconds,
        options=options,
        correct_indices=[correct_index]
    )
    
    return jsonify({'id': question_id}), 201

@app.route('/api/questions/<int:question_id>', methods=['GET'])
@simple_auth_required
def get_question(question_id):
    """Get a question."""
    question = Question.get_by_id(question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404
    
    return jsonify(question)

@app.route('/api/questions/<int:question_id>', methods=['PUT'])
@simple_auth_required
def update_question(question_id):
    """Update a question."""
    data = request.get_json()
    
    Question.update(
        question_id=question_id,
        question_content=data.get('title'),
        points=data.get('points'),
        time_limit_seconds=data.get('timerSeconds'),
        options=data.get('options'),
        correct_indices=[data.get('correctIndex')] if data.get('correctIndex') is not None else None
    )
    
    return jsonify({'success': True})

@app.route('/api/questions/<int:question_id>', methods=['DELETE'])
@simple_auth_required
def delete_question(question_id):
    """Delete a question."""
    success = Question.delete(question_id)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Question not found'}), 404

# ============================================================================
# Session Routes
# ============================================================================

@app.route('/api/sessions', methods=['POST'])
@simple_auth_required
def create_session():
    """Create a new live session."""
    from flask import g
    data = request.get_json()
    quiz_id = data.get('quizId')
    
    if not quiz_id:
        return jsonify({'error': 'Quiz ID required'}), 400
    
    # Verify quiz exists and belongs to user
    quiz = Quiz.get_by_id(quiz_id)
    user = g.current_user if hasattr(g, 'current_user') else current_user
    if not quiz or quiz['user_id'] != user.id:
        return jsonify({'error': 'Quiz not found or unauthorized'}), 404
    
    # Create session
    session_data = Session.create(quiz_id, quiz['course_name'])
    session_id = session_data['class_id']
    session_code = session_data['class_code']
    
    # Get all questions and add to session
    questions = Question.get_by_course(quiz_id)
    for idx, question in enumerate(questions):
        Session.add_question_to_session(session_id, question['question_id'], idx)
    
    # Generate QR code
    qr_url = QRGenerator.generate_session_qr(session_code)
    
    # Initialize active session tracking
    active_sessions[session_code] = {
        'session_id': session_id,
        'current_question_id': None,
        'question_start_time': None,
        'participants': set()
    }
    
    return jsonify({
        'sessionId': session_id,
        'code': session_code,
        'qrUrl': qr_url,
        'joinUrl': f"{Config.PUBLIC_BASE_URL}/join?code={session_code}"
    }), 201

@app.route('/api/sessions/<int:session_id>', methods=['GET'])
@simple_auth_required
def get_session(session_id):
    """Get session details."""
    session = Session.get_by_id(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    questions = Session.get_session_questions(session_id)
    participants = Participant.get_by_session(session_id)
    
    return jsonify({
        'session': dict(session),
        'questions': [dict(q) for q in questions],
        'participants': [dict(p) for p in participants]
    })

@app.route('/api/sessions/<int:session_id>/next', methods=['POST'])
@simple_auth_required
def next_question(session_id):
    """Advance to next question."""
    data = request.get_json()
    question_id = data.get('questionId')
    
    session = Session.get_by_id(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    # Set question as active
    Session.set_active_question(session_id, question_id)
    
    # Update session status to active if in lobby
    if session['status'] == 'lobby':
        Session.update_status(session_id, 'active')
    
    # Get question details
    question = Question.get_by_id(question_id)
    
    # Update active session tracking
    session_code = session['class_code']
    if session_code in active_sessions:
        active_sessions[session_code]['current_question_id'] = question_id
        active_sessions[session_code]['question_start_time'] = datetime.now()
    
    # Broadcast to all participants via WebSocket
    socketio.emit('question_open', {
        'questionId': question_id,
        'content': question['question_content'],
        'options': [{'index': idx, 'content': ans['answer_content']} 
                   for idx, ans in enumerate(question['answers'])],
        'timeLimit': question['time_limit_seconds'],
        'startTime': datetime.now().isoformat()
    }, room=f"session:{session_code}")
    
    return jsonify({'success': True})

@app.route('/api/sessions/<int:session_id>/end', methods=['POST'])
@simple_auth_required
def end_session(session_id):
    """End a session."""
    session = Session.get_by_id(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    Session.update_status(session_id, 'ended')
    
    # Broadcast end event
    session_code = session['class_code']
    socketio.emit('quiz_end', {'sessionId': session_id}, room=f"session:{session_code}")
    
    # Clean up active session
    if session_code in active_sessions:
        del active_sessions[session_code]
    
    return jsonify({'success': True})

@app.route('/api/sessions/<int:session_id>/summary', methods=['GET'])
@simple_auth_required
def get_session_summary(session_id):
    """Get session summary and results."""
    summary = ScoringService.get_session_summary(session_id)
    if not summary:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify(summary)

@app.route('/api/sessions/<int:session_id>/export', methods=['GET'])
@simple_auth_required
def export_session_csv(session_id):
    """Export session results as CSV."""
    csv_data = ScoringService.export_to_csv(session_id)
    if not csv_data:
        return jsonify({'error': 'Session not found'}), 404
    
    # Create temporary file
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.csv')
    with os.fdopen(fd, 'w') as f:
        f.write(csv_data)
    
    return send_file(path, mimetype='text/csv', as_attachment=True, 
                     download_name=f'session_{session_id}_results.csv')

# ============================================================================
# Student Join Routes (Public)
# ============================================================================
@app.route('/api/join', methods=['POST'])
def join_session():
    """Student joins a session."""
    data = request.get_json()
    code = (data.get('code') or '').strip().upper()
    name = data.get('name')
    
    if not code or not name:
        return jsonify({'error': 'Code and name required'}), 400
    
    # Find session
    session = Session.get_by_code(code)
    if not session:
        return jsonify({'error': 'Invalid session code'}), 404
    
    if session['status'] == 'ended':
        return jsonify({'error': 'Session has ended'}), 400
    
    # Create temporary user for student
    user_id = None
    try:
        user = User.get_by_email(f"student_{code}_{name}@temp.local")
        if user:
            user_id = user.id
        else:
            user_id = User.create_user(name, '', f"student_{code}_{name}@temp.local", role_id=1)
    except Exception as e:
        print(f"Error creating/finding user: {e}")
    
    # Add participant
    try:
        participant_id = Participant.create(session['class_id'], user_id, name)
        
        # Include timestamp in the participant data
        current_time = datetime.now().strftime("%H:%M:%S")
        
        participant_data = {
            'participantId': participant_id,
            'name': name,
            'joinedAt': current_time,
            'userId': user_id
        }
        
        print(f"DEBUG: Student {name} joined session {code}, participant_id: {participant_id}, user_id: {user_id}")
        
        # CRITICAL: Ensure active_sessions has the session and pending_joins
        if code not in active_sessions:
            print(f"DEBUG: Creating active_sessions entry for {code}")
            active_sessions[code] = {
                'session_id': session['class_id'],
                'current_question_id': None,
                'question_start_time': None,
                'participants': set(),
                'pending_joins': []
            }
        
        # Initialize pending_joins if it doesn't exist
        if 'pending_joins' not in active_sessions[code]:
            print(f"DEBUG: Initializing pending_joins for {code}")
            active_sessions[code]['pending_joins'] = []
        
        # Add to pending joins
        active_sessions[code]['pending_joins'].append(participant_data)
        print(f"DEBUG: Added to pending_joins for session {code}. Now has {len(active_sessions[code]['pending_joins'])} pending joins")
        
        # Debug: show current pending joins
        for i, pending in enumerate(active_sessions[code]['pending_joins']):
            print(f"DEBUG: Pending {i}: name={pending['name']}, userId={pending['userId']}")
        
        # Emit immediately to the room
        room = f"session:{code}"
        print(f"DEBUG: Attempting immediate emit to room {room}")
        
        # Get current clients in room for debugging
        try:
            manager = socketio.server.manager
            clients_in_room = manager.rooms.get('/', {}).get(room, set())
            print(f"DEBUG: Currently {len(clients_in_room)} clients in room {room}")
            if clients_in_room:
                print(f"DEBUG: Clients in room: {list(clients_in_room)}")
        except Exception as e:
            print(f"DEBUG: Could not get room clients: {e}")
        
        socketio.emit('lobby_update', participant_data, room=room, namespace='/')
        print(f"DEBUG: Immediate emit completed for {name}")
        
        return jsonify({
            'sessionId': session['class_id'],
            'participantId': participant_id,
            'userId': user_id,
            'code': code,
            'status': session['status']
        })
        
    except Exception as e:
        print(f"Error in join_session: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<int:session_id>/answer', methods=['POST'])
def submit_answer(session_id):
    """Student submits an answer."""
    data = request.get_json()
    user_id = data.get('userId')
    question_id = data.get('questionId')
    answer_index = data.get('optionIndex')
    latency_ms = data.get('latencyMs', 0)
    
    if not all([user_id, question_id, answer_index is not None]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if question is still active
    session = Session.get_by_id(session_id)
    questions = Session.get_session_questions(session_id)
    
    current_question = next((q for q in questions if q['question_id'] == question_id), None)
    if not current_question or not current_question['is_active']:
        return jsonify({'error': 'Question is not active'}), 400
    
    # Check if already answered
    if Response.has_answered(session_id, user_id, question_id):
        return jsonify({'error': 'Already answered'}), 400
    
    # Get the answer
    question = Question.get_by_id(question_id)
    if answer_index >= len(question['answers']):
        return jsonify({'error': 'Invalid answer index'}), 400
    
    answer = question['answers'][answer_index]
    is_correct = answer['is_correct']
    
    # Calculate points
    points = ScoringService.calculate_points(is_correct, question['points'], latency_ms, 
                                            question['time_limit_seconds'])
    
    # Save response
    Response.create(user_id, session_id, question_id, answer['answer_id'], latency_ms, points)
    answer_stats, correct_index = Response.get_answer_distribution(session_id, question_id)
    # Broadcast stats update to teacher
    stats = Response.get_question_stats(session_id, question_id)
    leaderboard = ScoringService.get_leaderboard(session_id)
    
    socketio.emit('stats_update', {
        'questionId': question_id,
        'totalResponses': stats['total_responses'],
        'correctCount': stats['correct_count'],
        'answerStats': answer_stats,        # NEW: Answer distribution [count_A, count_B, count_C, ...]
        'correctIndex': correct_index,      # NEW: Correct answer index (0-5)
        'leaderboard': leaderboard[:10]     # Top 10
    }, room=f"session:{session['class_code']}")
    
    return jsonify({
        'accepted': True,
        'isCorrect': is_correct,
        'points': points
    })

# Replace these two endpoints in app.py

@app.route('/api/quizzes/<int:quiz_id>/students', methods=['POST'])
def add_students_for_quiz(quiz_id):
    """
    Create/update students for a quiz.
    Stores students with synthetic email: student_{quiz_id}_{slug(name)}@students.local
    """
    data = request.get_json() or {}
    students = data.get('students') or []
    
    if not isinstance(students, list):
        return jsonify({"error": "students must be an array"}), 400

    results = []
    created = 0
    
    for s in students:
        name = (s.get('name') or '').strip()
        password = (s.get('password') or '').strip()
        
        if not name or not password:
            results.append({
                "name": name, 
                "email": None, 
                "action": "skipped", 
                "reason": "missing name or password"
            })
            continue

        slug = slugify(name)
        email = f"student_{quiz_id}_{slug}@students.local"
        
        print(f"DEBUG: Processing student: {name} -> {email}")
        
        try:
            # Check if user already exists
            existing_user = User.get_by_email(email)
            
            if existing_user:
                # Update existing user's password
                print(f"DEBUG: Updating password for existing user {email}")
                if existing_user.set_password(password):
                    results.append({
                        "name": name,
                        "email": email,
                        "action": "updated"
                    })
                    created += 1
                else:
                    results.append({
                        "name": name,
                        "email": email,
                        "action": "error",
                        "error": "Failed to update password"
                    })
            else:
                # Create new user
                # Split name into first and last (simple approach)
                parts = name.split(' ', 1)
                fname = parts[0]
                lname = parts[1] if len(parts) > 1 else ""
                
                print(f"DEBUG: Creating new user {fname} {lname} ({email})")
                user_id = User.create_user(fname, lname, email, password=password, role_id=1)
                
                if user_id:
                    print(f"DEBUG: User created successfully, id={user_id}")
                    results.append({
                        "name": name,
                        "email": email,
                        "user_id": user_id,
                        "action": "created"
                    })
                    created += 1
                else:
                    print(f"ERROR: Failed to create user {email}")
                    results.append({
                        "name": name,
                        "email": email,
                        "action": "error",
                        "error": "Failed to create user"
                    })
                    
        except Exception as e:
            print(f"ERROR: Exception processing student {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "name": name,
                "email": email,
                "action": "error",
                "error": str(e)
            })

    print(f"DEBUG: add_students_for_quiz completed: {created} students processed")
    return jsonify({
        "ok": True,
        "count": created,
        "results": results
    }), 201


# @app.route('/api/sessions/join', methods=['POST'])
# def validate_join():
#     """
#     Validate student joining by session code + name + password.
#     """
#     body = request.get_json() or {}
#     code = (body.get('code') or '').strip().upper()
#     name = (body.get('name') or '').strip()
#     password = (body.get('password') or '').strip()
    
#     if not code or not name or not password:
#         return jsonify({"error": "code, name and password required"}), 400

#     print(f"DEBUG: Student join attempt - code={code}, name={name}")

#     # Step 1: Find session by code
#     try:
#         session_record = Session.get_by_code(code)
#     except Exception as e:
#         print(f"ERROR: Session.get_by_code({code}): {e}")
#         return jsonify({"error": "Invalid session code"}), 404

#     if not session_record:
#         print(f"WARNING: No session found for code {code}")
#         return jsonify({"error": "Invalid session code"}), 404

#     # Step 2: Extract session info
#     def safe_get(obj, *keys):
#         if isinstance(obj, dict):
#             for k in keys:
#                 if k in obj:
#                     return obj[k]
#         else:
#             for k in keys:
#                 if hasattr(obj, k):
#                     return getattr(obj, k, None)
#         return None

#     session_id = safe_get(session_record, 'class_id', 'id')
#     quiz_id = safe_get(session_record, 'course_id', 'quiz_id')

#     if not session_id or not quiz_id:
#         print(f"ERROR: Missing session_id={session_id} or quiz_id={quiz_id}")
#         return jsonify({"error": "Session configuration error"}), 500

#     # Step 3: Find user by synthetic email
#     email = f"student_{quiz_id}_{slugify(name)}@students.local"
#     print(f"DEBUG: Looking for user with email={email}")

#     user = User.get_by_email(email)

#     if not user:
#         print(f"ERROR: User not found for {email}")
#         return jsonify({"error": "Invalid name or password"}), 401

#     print(f"DEBUG: User found: {user.user_fname} {user.user_lname}")

#     # Step 4: Verify password
#     if not user.verify_password(password):
#         print(f"WARNING: Password verification failed for {email}")
#         return jsonify({"error": "Invalid name or password"}), 401

#     print(f"DEBUG: Password verified successfully")

#     # Step 5: Create participant entry
#     participant_id = None
#     try:
#         participant_id = Participant.create(session_id, user.id, name)
#         print(f"DEBUG: Participant created, id={participant_id}")
#     except Exception as e:
#         print(f"DEBUG: Participant.create error (may already exist): {e}")
#         # Try to find existing
#         try:
#             existing = Participant.get_by_session_and_user(session_id, user.id)
#             if existing:
#                 participant_id = safe_get(existing, 'id', 'participant_id')
#                 print(f"DEBUG: Found existing participant, id={participant_id}")
#         except Exception as e2:
#             print(f"WARNING: Could not find existing participant: {e2}")

#     print(f"SUCCESS: Student {name} authenticated and joined session {code}")

#     return jsonify({
#         "ok": True,
#         "sessionId": session_id,
#         "session_id": session_id,
#         "userId": user.id,
#         "user_id": user.id,
#         "participantId": participant_id,
#         "name": f"{user.user_fname} {user.user_lname}"
#     }), 200

@app.route('/api/quizzes/<int:quiz_id>/students/debug', methods=['GET'])
def debug_students_for_quiz(quiz_id):
    """
    Debug endpoint: list users created with the synthetic student email prefix.
    """
    prefix = f"student_{quiz_id}_%"
    try:
        rows = db.session.execute(
            "SELECT id, name, email FROM users WHERE email LIKE :p ORDER BY id",
            {"p": prefix}
        ).fetchall()
        out = []
        for r in rows:
            # SQLAlchemy RowProxy/Row has ._mapping on newer versions
            if hasattr(r, '_mapping'):
                m = r._mapping
                out.append({"id": m.get('id'), "name": m.get('name'), "email": m.get('email')})
            else:
                out.append({"id": r[0], "name": r[1], "email": r[2]})
        return jsonify(out), 200
    except Exception as e:
        print("DEBUG: debug_students_for_quiz error:", e)
        return jsonify({"error": "debug failed", "detail": str(e)}), 500
# ...existing code...
@app.route('/api/quizzes/<int:quiz_id>/students', methods=['GET'])
def get_students_for_quiz(quiz_id):
    """
    Return student list for a quiz (without password hashes).
    """
    try:
        # Use direct database connection instead of SQLAlchemy session
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT u.user_id, u.user_fname, u.user_lname, u.user_email 
                FROM app_user u 
                WHERE u.user_email LIKE %s
                ORDER BY u.user_fname, u.user_lname
            """, [f"student_{quiz_id}_%@students.local"])
            
            students = cursor.fetchall()
            
            out = []
            for student in students:
                # Access results by index since we're using raw cursor
                out.append({
                    "id": student[0],  # user_id
                    "name": f"{student[1] or ''} {student[2] or ''}".strip(),  # fname + lname
                    "email": student[3]  # user_email
                })

            return jsonify({
                "ok": True,
                "students": out,
                "count": len(out)
            }), 200

    except Exception as e:
        print(f"ERROR in get_students_for_quiz: {str(e)}")
        return jsonify({
            "error": "Failed to fetch students",
            "detail": str(e)
        }), 500
    
@app.route('/api/sessions/join', methods=['POST'])
def validate_join():
    """
    Validate student joining by session code + name + password.
    Includes extensive debugging output.
    """
    body = request.get_json() or {}
    code = (body.get('code') or '').strip().upper()
    name = (body.get('name') or '').strip()
    password = (body.get('password') or '').strip()
    
    if not code or not name or not password:
        return jsonify({"error": "code, name and password required"}), 400

    # Find session
    session_record = None
    try:
        session_record = Session.get_by_code(code)
    except Exception as e:
        print(f"ERROR: Session.get_by_code({code}) raised: {e}")
        return jsonify({"error": "Invalid session code"}), 404

    if not session_record:
        print(f"WARNING: No session found for code {code}")
        return jsonify({"error": "Invalid session code"}), 404

    # Extract IDs from session record
    def extract_value(obj, *keys):
        if isinstance(obj, dict):
            for k in keys:
                if k in obj:
                    return obj[k]
        else:
            for k in keys:
                if hasattr(obj, k):
                    return getattr(obj, k, None)
        return None

    session_id = extract_value(session_record, 'class_id', 'id')
    quiz_id = extract_value(session_record, 'course_id', 'quiz_id')

    if not session_id or not quiz_id:
        print(f"ERROR: session_id={session_id}, quiz_id={quiz_id} - session record: {session_record}")
        return jsonify({"error": "Session configuration error"}), 500

    # Build synthetic email
    email = f"student_{quiz_id}_{slugify(name)}@students.local"
    print(f"DEBUG: Looking for user email={email}")

    # Find user
    user = None
    try:
        user = User.get_by_email(email)
    except Exception as e:
        print(f"ERROR: User.get_by_email({email}): {e}")

    if not user:
        print(f"DEBUG: User not found. Listing all students for quiz {quiz_id}:")
        try:
            rows = db.session.execute(
                "SELECT user_id, user_fname, user_lname, user_email, user_password FROM app_user WHERE user_email LIKE :p LIMIT 20",
                {"p": f"student_{quiz_id}_%"}
            ).fetchall()
            for row in rows:
                print(f"  Found: {row}")
        except Exception as e:
            print(f"ERROR listing users: {e}")
        return jsonify({"error": "Invalid credentials"}), 401

    # DEBUG: inspect returned user object/row
    try:
        print("DEBUG: user repr:", repr(user))
        # robust user id extraction (support dict, SQLAlchemy Row, or User object)
        if isinstance(user, dict):
            user_id_val = user.get('user_id') or user.get('id') or user.get('userId')
        else:
            user_id_val = getattr(user, 'id', None) or getattr(user, 'user_id', None)
        print(f"DEBUG: resolved user_id = {user_id_val}, email={getattr(user,'user_email',None) or (user.get('user_email') if isinstance(user, dict) else None)}")
    except Exception as e:
        print("DEBUG: error inspecting user:", e)
        user_id_val = getattr(user, 'id', None) or getattr(user, 'user_id', None)

    # Check password (existing logic)
    stored_hash = getattr(user, 'user_password', None) or getattr(user, 'password', None)
    if not stored_hash:
        print(f"ERROR: User {user} has no password_hash field")
        return jsonify({"error": "Invalid credentials"}), 401

    # Check password
    stored_hash = getattr(user, 'user_password', None) or getattr(user, 'password', None)
    if not stored_hash:
        print(f"ERROR: User {user} has no password_hash field")
        return jsonify({"error": "Invalid credentials"}), 401

    try:
        if not check_password_hash(stored_hash, password):
            print(f"WARNING: Password mismatch for {email}")
            return jsonify({"error": "Invalid name or password"}), 401
    except Exception as e:
        print(f"ERROR: check_password_hash failed: {e}")
        return jsonify({"error": "System error"}), 500

    # Create participant
    user_id = getattr(user, 'id', user.get('id') if isinstance(user, dict) else None)
    participant_id = None

    try:
        participant_id = Participant.create(session_id, user_id, name)
    except Exception as e:
        print(f"ERROR: Participant.create({session_id}, {user_id}, {name}): {e}")

    print(f"SUCCESS: Student {name} joined session {code} (participant_id={participant_id})")

    return jsonify({
        "ok": True,
        "sessionId": session_id,
        "userId": user_id,
        "participantId": participant_id,
        "name": name
    }), 200
# ============================================================================
# WebSocket Events
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_session')
def handle_join_session(data):
    """Join a session room."""
    code = data.get('code')
    role = data.get('role', 'student')  # teacher or student
    name = data.get('name')  # Student name
    user_id = data.get('userId')  # Student user ID
    participant_id = data.get('participantId')  # Student participant ID
    
    if not code:
        emit('error', {'message': 'Session code required'})
        return
    
    room = f"session:{code}"
    join_room(room)
    
    print(f"DEBUG: Client {request.sid} joined room {room} as {role}")
    
    # If this is a student joining, get their participant data from database
    if role == 'student':
        print(f"DEBUG: Student joined - name: {name}, user_id: {user_id}, participant_id: {participant_id}")
        
        # Try to find the participant in database
        participant_data = None
        
        # Method 1: Use participant_id if provided
        if participant_id:
            try:
                participant = Participant.get_by_id(participant_id)
                if participant:
                    participant_data = {
                        'participantId': participant['id'],
                        'name': participant['name'],
                        'joinedAt': participant['joined_at'].strftime("%H:%M:%S") if hasattr(participant['joined_at'], 'strftime') else str(participant['joined_at']),
                        'userId': participant['user_id']
                    }
                    print(f"DEBUG: Found participant by ID: {participant_data}")
            except Exception as e:
                print(f"DEBUG: Error getting participant by ID: {e}")
        
        # Method 2: Use session and user_id
        if not participant_data and user_id and code:
            try:
                session = Session.get_by_code(code)
                if session:
                    participants = Participant.get_by_session_and_user(session['class_id'], user_id)
                    if participants:
                        participant = participants[0]  # Take the first one
                        participant_data = {
                            'participantId': participant['id'],
                            'name': participant['name'],
                            'joinedAt': participant['joined_at'].strftime("%H:%M:%S") if hasattr(participant['joined_at'], 'strftime') else str(participant['joined_at']),
                            'userId': participant['user_id']
                        }
                        print(f"DEBUG: Found participant by session/user: {participant_data}")
            except Exception as e:
                print(f"DEBUG: Error getting participant by session/user: {e}")
        
        # Method 3: Use name and session (fallback)
        if not participant_data and name and code:
            try:
                session = Session.get_by_code(code)
                if session:
                    participants = Participant.get_by_session(session['class_id'])
                    for participant in participants:
                        if participant['name'] == name:
                            participant_data = {
                                'participantId': participant['id'],
                                'name': participant['name'],
                                'joinedAt': participant['joined_at'].strftime("%H:%M:%S") if hasattr(participant['joined_at'], 'strftime') else str(participant['joined_at']),
                                'userId': participant['user_id']
                            }
                            print(f"DEBUG: Found participant by name: {participant_data}")
                            break
            except Exception as e:
                print(f"DEBUG: Error getting participant by name: {e}")
        
        # Emit the participant data if found
        if participant_data:
            print(f"DEBUG: Emitting lobby_update for {participant_data['name']}")
            socketio.emit('lobby_update', participant_data, room=room, namespace='/')
        else:
            print(f"DEBUG: Could not find participant data in database")
            # Try pending joins as fallback
            if code in active_sessions:
                pending_joins = active_sessions[code].get('pending_joins', [])
                print(f"DEBUG: Checking {len(pending_joins)} pending joins as fallback")
                if pending_joins:
                    print(f"DEBUG: Emitting first pending join: {pending_joins[0]['name']}")
                    socketio.emit('lobby_update', pending_joins[0], room=room, namespace='/')
                    pending_joins.pop(0)
    
    if code in active_sessions:
        active_sessions[code]['participants'].add(request.sid)
    
    emit('joined', {'code': code, 'role': role})
    print(f"DEBUG: Sent 'joined' event to client {request.sid}")

@app.route('/api/debug/rooms/<session_code>')
def debug_rooms(session_code):
    """Debug which clients are in a room."""
    room = f"session:{session_code}"
    manager = socketio.server.manager
    
    try:
        # Get clients in the room for the default namespace
        clients = manager.rooms.get('/', {}).get(room, set())
        return jsonify({
            'room': room,
            'client_count': len(clients),
            'clients': list(clients)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('leave_session')
def handle_leave_session(data):
    """Leave a session room."""
    code = data.get('code')
    
    if not code:
        return
    
    room = f"session:{code}"
    leave_room(room)
    
    if code in active_sessions:
        active_sessions[code]['participants'].discard(request.sid)
    
    print(f"Client {request.sid} left session {code}")

@socketio.on('lock_question')
def handle_lock_question(data):
    """Teacher locks a question."""
    session_id = data.get('sessionId')
    question_id = data.get('questionId')
    
    Session.lock_question(session_id, question_id)
    
    session = Session.get_by_id(session_id)
    emit('question_close', {'questionId': question_id}, room=f"session:{session['class_code']}")

# ============================================================================
# Static Routes
# ============================================================================

@app.route('/join')
def join_page():
    """Student join page."""
    return render_template('join.html')

@app.route('/static/qr/<filename>')
def serve_qr(filename):
    """Serve QR code images."""
    return send_file(os.path.join(Config.QR_CODE_DIR, filename))

@app.route('/')
def index():
    """Health check."""
    return jsonify({'status': 'ok', 'service': 'Quiz Competition API'})

# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, 
                 ssl_context='adhoc' if os.environ.get('FLASK_ENV') != 'production' else None)
