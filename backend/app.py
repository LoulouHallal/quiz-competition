from flask import Flask, request, jsonify, send_file, render_template, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import os
import json
from datetime import datetime, timedelta

from config import Config
from models.user import User
from models.quiz import Quiz
from models.question import Question
from models.session import Session
from models.participant import Participant
from models.response import Response
from services.scoring import ScoringService
from services.qr_generator import QRGenerator

# Initialize Flask app
app = Flask(__name__)
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
    code = data.get('code')
    name = data.get('name')
    
    if not code or not name:
        return jsonify({'error': 'Code and name required'}), 400
    
    # Find session
    session = Session.get_by_code(code)
    if not session:
        return jsonify({'error': 'Invalid session code'}), 404
    
    if session['status'] == 'ended':
        return jsonify({'error': 'Session has ended'}), 400
    
    # Create temporary user for student (or find existing)
    # For MVP, create ephemeral users
    user = User.get_by_email(f"student_{code}_{name}@temp.local")
    if not user:
        user_id = User.create_user(name, '', f"student_{code}_{name}@temp.local", role_id=1)
    else:
        user_id = user.id
    
    # Add participant
    participant_id = Participant.create(session['class_id'], user_id, name)
    
    # Broadcast new participant to teacher
    socketio.emit('lobby_update', {
        'participantId': participant_id,
        'name': name,
        'joinedAt': datetime.now().isoformat()
    }, room=f"session:{code}")
    
    return jsonify({
        'sessionId': session['class_id'],
        'participantId': participant_id,
        'userId': user_id,
        'code': code,
        'status': session['status']
    })

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
    
    # Broadcast stats update to teacher
    stats = Response.get_question_stats(session_id, question_id)
    leaderboard = ScoringService.get_leaderboard(session_id)
    
    socketio.emit('stats_update', {
        'questionId': question_id,
        'totalResponses': stats['total_responses'],
        'correctCount': stats['correct_count'],
        'leaderboard': leaderboard[:10]  # Top 10
    }, room=f"session:{session['class_code']}")
    
    return jsonify({
        'accepted': True,
        'isCorrect': is_correct,
        'points': points
    })

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
    
    if not code:
        emit('error', {'message': 'Session code required'})
        return
    
    room = f"session:{code}"
    join_room(room)
    
    if code in active_sessions:
        active_sessions[code]['participants'].add(request.sid)
    
    emit('joined', {'code': code, 'role': role})
    print(f"Client {request.sid} joined session {code} as {role}")

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
