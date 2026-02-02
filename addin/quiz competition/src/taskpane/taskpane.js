/* global Office, io */

// ============================================================================
// Fetch Polyfill for older Office WebView
// ============================================================================
(function () {
  if (typeof window.fetch === "function") return;
  function makeResponse(xhr, url) {
    return {
      ok: xhr.status >= 200 && xhr.status < 300,
      status: xhr.status,
      statusText: xhr.statusText || "",
      url: url,
      text: function () { return Promise.resolve(xhr.responseText); },
      json: function () {
        try { return Promise.resolve(JSON.parse(xhr.responseText)); }
        catch (e) { return Promise.reject(e); }
      }
    };
  }
  window.fetch = function (url, options) {
    options = options || {};
    var method = options.method || "GET";
    var headers = options.headers || {};
    var body = options.body || null;
    return new Promise(function (resolve, reject) {
      try {
        var xhr = new XMLHttpRequest();
        xhr.open(method, url, true);
        for (var k in headers) {
          try { xhr.setRequestHeader(k, headers[k]); } catch (e) {}
        }
        xhr.onreadystatechange = function () {
          if (xhr.readyState === 4) resolve(makeResponse(xhr, url));
        };
        xhr.onerror = function () { reject(new TypeError("Network request failed")); };
        xhr.send(body);
      } catch (err) { reject(err); }
    });
  };
})();

// ============================================================================
// Configuration & State
// ============================================================================
var API_BASE = "http://localhost:5000";
var state = {
  teacher: null,
  currentQuiz: null,
  currentSession: null,
  questions: [],
  participants: [],
  currentQuestionIndex: -1,
  socket: null,
  qrDataUrl: null,
  slideQuestionMap: {},
  showCorrectAnswer: false,  // NEW: Track if correct answer is revealed
  pendingStudents: [] // NEW: students added by teacher before/after quiz creation
};


// ============================================================================
// Utilities
// ============================================================================
function toast(msg, type, ms) {
  type = type || "info";
  ms = ms || 3000;
  var box = document.getElementById("qc-toast");
  if (!box) {
    box = document.createElement("div");
    box.id = "qc-toast";
    box.style.cssText = "position:fixed;right:12px;bottom:12px;max-width:380px;z-index:99999;font:13px Segoe UI,Arial";
    document.body.appendChild(box);
  }
  var n = document.createElement("div");
  n.textContent = msg;
  n.style.cssText = "margin-top:8px;padding:10px 12px;border-radius:8px;box-shadow:0 6px 18px rgba(0,0,0,.35);background:" +
    (type === "error" ? "#fca5a5" : "#93c5fd") + ";color:#0b1220;font-weight:600;";
  box.appendChild(n);
  setTimeout(function () {
    if (n && n.parentNode) n.parentNode.removeChild(n);
  }, ms);
}

function el(id) {
  return document.getElementById(id);
}

function show(id) {
  var elem = el(id);
  if (elem) elem.classList.remove("hidden");
}

function hide(id) {
  var elem = el(id);
  if (elem) elem.classList.add("hidden");
}

// ============================================================================
// API Helpers
// ============================================================================
function apiCall(path, options) {
  options = options || {};
  var method = options.method || "GET";
  var body = options.body ? JSON.stringify(options.body) : undefined;
  var headers = { "Content-Type": "application/json" };
  
  var url = API_BASE + path;
  return fetch(url, {
    method: method,
    headers: headers,
    body: body,
    credentials: "include"
  }).then(function (res) {
    if (!res.ok) {
      return res.text().then(function (t) {
        throw new Error("HTTP " + res.status + ": " + (t || res.statusText));
      });
    }
    return res.json();
  });
}

// ============================================================================
// PowerPoint Helpers
// ============================================================================
function getCurrentSlideId() {
  return new Promise(function (resolve, reject) {
    Office.context.document.getSelectedDataAsync(Office.CoercionType.SlideRange, function (result) {
      if (result.status === Office.AsyncResultStatus.Succeeded) {
        var slides = result.value.slides;
        if (slides && slides.length > 0) {
          resolve(slides[0].id);
        } else {
          reject(new Error("No slide selected"));
        }
      } else {
        reject(result.error);
      }
    });
  });
}

function saveQuestionToSlide(slideId, questionData) {
  return new Promise(function (resolve, reject) {
    Office.context.document.settings.set("question_" + slideId, JSON.stringify(questionData));
    Office.context.document.settings.saveAsync(function (result) {
      if (result.status === Office.AsyncResultStatus.Succeeded) {
        resolve();
      } else {
        reject(result.error);
      }
    });
  });
}

function getQuestionFromSlide(slideId) {
  var data = Office.context.document.settings.get("question_" + slideId);
  return data ? JSON.parse(data) : null;
}

function insertQRToSlide(qrUrl) {
  return new Promise(function (resolve, reject) {
    Office.context.document.setSelectedDataAsync(qrUrl, {
      coercionType: Office.CoercionType.Image
    }, function (result) {
      if (result.status === Office.AsyncResultStatus.Succeeded) {
        resolve();
      } else {
        reject(result.error);
      }
    });
  });
}

// ============================================================================
// Authentication
// ============================================================================
function login() {
  var email = el("loginEmail").value.trim();
  var password = el("loginPassword").value.trim();
  
  if (!email || !password) {
    el("loginError").textContent = "Please enter email and password";
    el("loginError").style.display = "block";
    return;
  }
  
  apiCall("/api/auth/login", {
    method: "POST",
    body: { email: email, password: password }
  }).then(function (data) {
    state.teacher = data.teacher;
    el("login-screen").style.display = "none";
    el("app-body").style.display = "block";
    el("btnLogout").style.display = "block";
    toast("Logged in as " + data.teacher.name);
    loadQuizzes();
  }).catch(function (err) {
    el("loginError").textContent = err.message || "Login failed";
    el("loginError").style.display = "block";
  });
}

function logout() {
  apiCall("/api/auth/logout", { method: "POST" }).then(function () {
    state.teacher = null;
    state.currentQuiz = null;
    state.currentSession = null;
    el("login-screen").style.display = "block";
    el("app-body").style.display = "none";
    el("btnLogout").style.display = "none";
    toast("Logged out");
  }).catch(function (err) {
    console.error(err);
  });
}

// ============================================================================
// Tab Management
// ============================================================================
function switchTab(tabName) {
  var tabs = document.querySelectorAll(".tab");
  var contents = document.querySelectorAll(".tab-content");
  
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].classList.remove("active");
  }
  for (var j = 0; j < contents.length; j++) {
    contents[j].classList.remove("active");
  }
  
  var activeTab = tabName === "author" ? 0 : 1;
  tabs[activeTab].classList.add("active");
  el("tab-" + tabName).classList.add("active");
}

// ============================================================================
// Quiz Management (Author Tab)
// ============================================================================
function createQuiz() {
  try {
    var titleInput = el("quizTitle");
    if (!titleInput) {
      console.error("ERROR: quizTitle input not found");
      return;
    }
    
    var title = (titleInput.value || "").trim();
    if (!title) {
      toast("Please enter a quiz title", "error");
      return;
    }
    
    console.log("DEBUG: Creating quiz with title: " + title);
    
    apiCall("/api/quizzes", {
      method: "POST",
      body: { title: title }
    }).then(function (data) {
      console.log("DEBUG: Quiz created:", data);
      
      // Set state
      var newId = data.id || data.quizId;
      state.currentQuiz = { id: newId, title: title };
      console.log("DEBUG: State updated. currentQuiz:", state.currentQuiz);
      
      var statusEl = el("quizStatus");
      if (statusEl) {
        statusEl.textContent = "Quiz: " + title + " (ID: " + newId + ")";
      }
      
      toast("✓ Quiz created");
      titleInput.value = "";
      
      // Save pending students
      if (state.pendingStudents && state.pendingStudents.length > 0) {
        console.log("DEBUG: Auto-saving " + state.pendingStudents.length + " pending students");
        return window.qc.saveStudentsToServer(newId);
      }
      
    }).catch(function (err) {
      console.error("ERROR: createQuiz failed:", err);
      toast(err.message || "Failed to create quiz", "error");
    });
    
  } catch (err) {
    console.error("ERROR in createQuiz:", err);
    toast("Script error: " + err.message, "error");
  }
}

function loadQuizzes() {
  try {
    console.log("DEBUG: loadQuizzes called");
    toast("Loading quizzes...");
    
    apiCall("/api/quizzes").then(function (quizzes) {
      console.log("DEBUG: Got quizzes:", quizzes);
      
      if (!quizzes || quizzes.length === 0) {
        toast("No quizzes found. Create one first.", "error");
        return;
      }
      
      // Create modal
      var modal = document.createElement("div");
      modal.id = "quizModal";
      modal.style.cssText = "position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:10000;display:flex;align-items:center;justify-content:center;padding:20px;";
      
      var content = document.createElement("div");
      content.style.cssText = "background:#111827;border-radius:12px;padding:24px;max-width:400px;box-shadow:0 20px 60px rgba(0,0,0,0.3);border:1px solid #253248;max-height:70vh;overflow-y:auto;";
      
      var html = "<h3 style='margin:0 0 16px;color:#22d3ee;'>Select Quiz</h3>";
      
      for (var i = 0; i < quizzes.length; i++) {
        try {
          var quiz = quizzes[i];
          var qId = quiz.course_id || quiz.id;
          var qName = quiz.course_name || quiz.title || "Untitled";
          
          html += "<div class='quiz-option' ";
          html += "data-quiz-id='" + String(qId).replace(/'/g, "") + "' ";
          html += "data-quiz-name='" + String(qName).replace(/'/g, "") + "' ";
          html += "style='padding:12px;background:#0b1220;border:1px solid #334155;border-radius:8px;margin-bottom:8px;cursor:pointer;'>";
          html += "<div style='color:#22d3ee;font-weight:600;'>" + String(qName).substring(0, 50) + "</div>";
          html += "</div>";
        } catch (qErr) {
          console.error("ERROR processing quiz item:", qErr);
        }
      }
      
      html += "<button id='closeQuizModal' style='width:100%;padding:10px;background:#334155;color:#e5e7eb;border:none;border-radius:6px;cursor:pointer;font-weight:600;margin-top:12px;'>Cancel</button>";
      
      content.innerHTML = html;
      modal.appendChild(content);
      document.body.appendChild(modal);
      
      // Attach handlers
      var opts = content.querySelectorAll('.quiz-option');
      console.log("DEBUG: Found " + opts.length + " quiz options");
      
      for (var j = 0; j < opts.length; j++) {
        (function(opt) {
          opt.onclick = function(e) {
            try {
              e.preventDefault();
              e.stopPropagation();
              
              var qId = parseInt(this.getAttribute('data-quiz-id'));
              var qName = this.getAttribute('data-quiz-name');
              
              console.log("DEBUG: Selected quiz id=" + qId + " name=" + qName);
              
              state.currentQuiz = { id: qId, title: qName };
              displayStudentsList();
              var statusEl = el("quizStatus");
              if (statusEl) {
                statusEl.textContent = "Quiz: " + qName + " (ID: " + qId + ")";
              }
              
              toast("✓ Loaded: " + qName);
              
              if (modal.parentNode) {
                modal.parentNode.removeChild(modal);
              }
              
              // Auto-save pending students?
              if (state.pendingStudents && state.pendingStudents.length > 0) {
                var msg = "Save " + state.pendingStudents.length + " pending student(s)?";
                try {
                  if (confirm(msg)) {
                    window.qc.saveStudentsToServer(qId);
                  }
                } catch (cErr) {
                  // confirm() may fail in some Office contexts
                  console.log("DEBUG: confirm() not available, skipping auto-save prompt");
                }
              }
              
              window.qc.loadQuestions();
              
            } catch (err) {
              console.error("ERROR in quiz option click:", err);
            }
          };
        })(opts[j]);
      }
      
      el("closeQuizModal").onclick = function() {
        if (modal && modal.parentNode) {
          modal.parentNode.removeChild(modal);
        }
      };
      
      modal.onclick = function(e) {
        if (e.target === modal && modal.parentNode) {
          modal.parentNode.removeChild(modal);
        }
      };
      
    }).catch(function (err) {
      console.error("ERROR: loadQuizzes failed:", err);
      toast(err.message || "Failed to load quizzes", "error");
    });
    
  } catch (err) {
    console.error("ERROR in loadQuizzes:", err);
    toast("Script error: " + err.message, "error");
  }
}

function saveQuestion() {
  if (!state.currentQuiz) {
    toast("Please create or select a quiz first", "error");
    return;
  }
  
  var title = el("questionTitle").value.trim();
  var options = [
    el("optionA").value.trim(),
    el("optionB").value.trim(),
    el("optionC").value.trim(),
    el("optionD").value.trim(),
    el("optionE").value.trim(),
    el("optionF").value.trim()
  ].filter(function (opt) { return opt !== ""; });
  
  var correctIndex = parseInt(el("correctAnswer").value);
  var timerSeconds = parseInt(el("timerSeconds").value);
  
  if (!title || options.length < 2) {
    toast("Please enter question title and at least 2 options", "error");
    return;
  }
  
  if (correctIndex >= options.length) {
    toast("Correct answer must be one of the provided options", "error");
    return;
  }
  
  getCurrentSlideId().then(function (slideId) {
    return apiCall("/api/quizzes/" + state.currentQuiz.id + "/questions", {
      method: "POST",
      body: {
        title: title,
        options: options,
        correctIndex: correctIndex,
        timerSeconds: timerSeconds
      }
    }).then(function (data) {
      state.slideQuestionMap[slideId] = data.id;
      
      var questionData = {
        questionId: data.id,
        title: title,
        options: options,
        correctIndex: correctIndex,
        timerSeconds: timerSeconds
      };
      
      return saveQuestionToSlide(slideId, questionData);
    }).then(function () {
      toast("Question saved to slide");
      el("questionTitle").value = "";
      el("optionA").value = "";
      el("optionB").value = "";
      el("optionC").value = "";
      el("optionD").value = "";
      el("optionE").value = "";
      el("optionF").value = "";
      loadQuestions();
    });
  }).catch(function (err) {
    toast(err.message || "Failed to save question", "error");
  });
}

function syncQuestions() {
  if (!state.currentQuiz) {
    toast("Please create or select a quiz first", "error");
    return;
  }
  
  toast("Syncing questions from slides...");
  loadQuestions();
}

function loadQuestions() {
  if (!state.currentQuiz) return;
  
  apiCall("/api/quizzes/" + state.currentQuiz.id).then(function (quiz) {
    state.questions = quiz.questions || [];
    displayQuestions();
  }).catch(function (err) {
    console.error(err);
  });
}

function displayQuestions() {
  var list = el("questionsList");
  if (!list) return;
  
  if (state.questions.length === 0) {
    list.innerHTML = "<small>No questions yet. Add questions to slides.</small>";
    return;
  }
  
  var html = "";
  for (var i = 0; i < state.questions.length; i++) {
    var q = state.questions[i];
    html += "<div style='margin:4px 0;padding:6px;background:#0b1220;border-radius:4px'>";
    html += "<b>" + (i + 1) + ".</b> " + (q.question_content || q.title || "");
    html += "</div>";
  }
  list.innerHTML = html;
}

// ============================================================================
// Live Session Management (Live Tab)
// ============================================================================
function startSession() {
  if (!state.currentQuiz) {
    toast("Please create a quiz first", "error");
    switchTab("author");
    return;
  }
  
  if (state.questions.length === 0) {
    toast("Please add questions to your quiz first", "error");
    switchTab("author");
    return;
  }
  
  toast("Starting session...");
  
  apiCall("/api/sessions", {
    method: "POST",
    body: { quizId: state.currentQuiz.id }
  }).then(function (data) {
    state.currentSession = {
      id: data.sessionId,
      code: data.code,
      qrUrl: data.qrUrl
    };
    state.qrDataUrl = API_BASE + data.qrUrl;
    
    el("sessionCode").textContent = data.code;
    el("qrImage").src = state.qrDataUrl;
    el("qrImage").style.display = "block";
    
    hide("lobby-view");
    show("session-view");
    
    connectWebSocket(data.code);
    toast("Session started! Code: " + data.code);
  }).catch(function (err) {
    toast(err.message || "Failed to start session", "error");
  });
}
function connectWebSocket(code) {
    if (state.socket) {
        state.socket.disconnect();
    }
    
    // Reset participants list when connecting
    state.participants = [];
    updateParticipantList();
    
    state.socket = io(API_BASE);
    
    state.socket.on("connect", function () {
        console.log("WebSocket connected, SID:", state.socket.id);
        code = code.toUpperCase();
        
        state.socket.emit("join_session", { 
            code: code, 
            role: "teacher" 
        });
        console.log("DEBUG: Emitted join_session for code:", code);
    });
    
    state.socket.on("joined", function (data) {
        console.log("DEBUG: Received 'joined' confirmation:", data);
    });
    
    state.socket.on("lobby_update", function (data) {
        console.log("DEBUG: ✅ RECEIVED lobby_update:", data);
        console.log("DEBUG: Current participants before update:", state.participants.length);
        
        // Check if participant already exists
        const existingIndex = state.participants.findIndex(p => 
            p.participantId === data.participantId || 
            (p.name === data.name && p.userId === data.userId)
        );
        
        if (existingIndex === -1) {
            state.participants.push({
                participantId: data.participantId,
                name: data.name,
                joinedAt: data.joinedAt || new Date().toLocaleTimeString(),
                userId: data.userId
            });
            console.log("DEBUG: Added participant, total now:", state.participants.length);
        } else {
            console.log("DEBUG: Participant already exists, updating");
            state.participants[existingIndex] = {
                participantId: data.participantId,
                name: data.name,
                joinedAt: data.joinedAt || new Date().toLocaleTimeString(),
                userId: data.userId
            };
        }
        
        updateParticipantList();
        console.log("DEBUG: Participants after update:", state.participants);
    });
    
    // Add all other WebSocket listeners with debugging
    state.socket.on("connect_error", function(error) {
        console.error("Socket connection error:", error);
    });
    
    state.socket.on("error", function(error) {
        console.error("Socket error:", error);
    });
    
    state.socket.on("disconnect", function(reason) {
        console.log("WebSocket disconnected:", reason);
    });
    
    // Test: manually check room status after a delay
    setTimeout(() => {
        console.log("DEBUG: Testing room connection...");
        // You could add an API call here to debug the room
        fetch(`${API_BASE}/api/debug/rooms/${code}`)
            .then(r => r.json())
            .then(data => console.log("DEBUG: Room status:", data))
            .catch(err => console.error("DEBUG: Room check failed:", err));
    }, 2000);
}

function updateParticipantList() {
    console.log("DEBUG: Updating participant list");
    var list = el("participantList");
    var count = el("participantCount");
    
    if (!list || !count) {
        console.error("ERROR: Required elements not found", {
            list: !!list,
            count: !!count,
            participants: state.participants
        });
        return;
    }
    
    count.textContent = state.participants.length;
    console.log("DEBUG: Current participants:", state.participants);
    
    if (state.participants.length === 0) {
        list.innerHTML = "<small>No participants yet</small>";
        return;
    }
    
    var html = "";
    state.participants.forEach(function(p, i) {
        html += "<div class='participant-item'>";
        html += "<div style='display:flex;justify-content:space-between;width:100%'>";
        html += "<span>" + (p.name || "Student " + (i + 1)) + "</span>";
        html += "<small style='color:#9ca3af'>" + (p.joinedAt || "") + "</small>";
        html += "</div>";
        html += "</div>";
    });
    
    console.log("DEBUG: Generated HTML:", html);
    list.innerHTML = html;
}

function updateStats(data) {
  console.log("Stats update received:", data); // DEBUG
  
  el("responseCount").textContent = data.totalResponses || 0;
  el("correctCount").textContent = data.correctCount || 0;
  
  var percent = data.totalResponses > 0 ? Math.round((data.correctCount / data.totalResponses) * 100) : 0;
  el("correctPercent").textContent = percent;
  el("statsFill").style.width = percent + "%";
  
  // Display answer distribution chart
  console.log("answerStats:", data.answerStats); // DEBUG
  console.log("correctIndex:", data.correctIndex); // DEBUG
  
  if (data.answerStats && Array.isArray(data.answerStats) && data.answerStats.length > 0) {
    displayAnswerChart(data.answerStats, data.correctIndex);
  } else {
    // DEBUG: Show what data we're actually getting
    var debugMsg = "No answerStats data. Received: " + JSON.stringify(data).substring(0, 200);
    console.warn(debugMsg);
    var chartContainer = el("answerChart");
    if (chartContainer && chartContainer.style.display !== "none") {
      chartContainer.innerHTML = "<div style='color:#fca5a5;padding:12px;border:1px solid #ef4444;border-radius:6px;font-size:11px;'><strong>Debug:</strong> " + debugMsg + "</div>";
    }
  }
  
  if (data.leaderboard) {
    updateLeaderboard(data.leaderboard);
  }
}
function toggleChart() {
  var chartContainer = el("answerChart");
  var button = document.querySelector("button[onclick='qc.toggleChart()']");
  
  if (!chartContainer) return;
  
  var isHidden = chartContainer.style.display === "none";
  
  if (isHidden) {
    chartContainer.style.display = "block";
    button.textContent = "Hide Answer Distribution";
  } else {
    chartContainer.style.display = "none";
    button.textContent = "Show Answer Distribution";
  }
}


function displayAnswerChart(answerStats, correctIndex) {
  // Store for later redraw
  window.lastAnswerStats = answerStats;
  window.lastCorrectIndex = correctIndex;
  
  var chartContainer = el("answerChart");
  if (!chartContainer) return;
  
  var colors = ["#3b82f6", "#f59e0b", "#10b981", "#8b5cf6", "#ec4899", "#06b6d4"];
  var labels = ["A", "B", "C", "D", "E", "F"];
  
  if (!Array.isArray(answerStats) || answerStats.length === 0) {
    answerStats = [4, 2, 1, 3, 0, 0];
  }
  
  if (!correctIndex && correctIndex !== 0) {
    correctIndex = 0;
  }
  
  var totalResponses = 0;
  for (var i = 0; i < answerStats.length; i++) {
    totalResponses += answerStats[i] || 0;
  }
  
  if (totalResponses === 0) {
    chartContainer.innerHTML = "<div style='text-align:center;color:#9ca3af;padding:20px;font-size:12px;'>No responses yet</div>";
    return;
  }
  
  var html = "<div style='display:flex;gap:12px;align-items:flex-end;justify-content:center;height:240px;margin:16px 0;padding:20px;background:#0b1220;border-radius:8px;'>";
  
  for (var i = 0; i < answerStats.length; i++) {
    var count = answerStats[i] || 0;
    var percent = totalResponses > 0 ? Math.round((count / totalResponses) * 100) : 0;
    var height = totalResponses > 0 ? (count / totalResponses) * 160 : 0;
    var isCorrect = i === correctIndex;
    
    html += "<div style='display:flex;flex-direction:column;align-items:center;gap:8px;flex:1;max-width:70px;'>";
    
    // Only show checkmark if teacher has revealed the answer
    if (isCorrect && state.showCorrectAnswer) {
      html += "<span style='font-size:28px;height:32px;'>✅</span>";
    } else {
      html += "<span style='height:32px;'></span>";
    }
    
    html += "<div style='position:relative;height:160px;width:100%;background:#1e293b;border-radius:6px;display:flex;align-items:flex-end;justify-content:center;border:1px solid #334155;'>";
    
    if (height > 0) {
      html += "<div style='height:" + height + "px;width:100%;background:" + colors[i % colors.length] + ";border-radius:4px;display:flex;align-items:center;justify-content:center;transition:all 0.3s;'>";
      if (height > 25) {
        html += "<span style='color:#fff;font-weight:700;font-size:11px;text-align:center;'>" + count + "</span>";
      }
      html += "</div>";
    }
    
    html += "</div>";
    
    html += "<div style='text-align:center;width:100%;'>";
    html += "<div style='color:#e5e7eb;font-weight:700;font-size:14px;margin-bottom:4px;'>" + labels[i] + "</div>";
    html += "<div style='color:#9ca3af;font-size:11px;'>" + count + "<br/>(" + percent + "%)</div>";
    html += "</div>";
    
    html += "</div>";
  }
  
  html += "</div>";
  chartContainer.innerHTML = html;
}

// NEW: Function to reveal/show the correct answer
function revealAnswer() {
  state.showCorrectAnswer = true;
  var button = document.querySelector("button[onclick='qc.revealAnswer()']");
  if (button) {
    button.textContent = "Answer Revealed ✓";
    button.disabled = true;
  }
  
  // IMPORTANT: Redraw the chart to show the checkmark
  var chartContainer = el("answerChart");
  if (chartContainer && chartContainer.style.display !== "none") {
    // Redraw with stored stats
    if (window.lastAnswerStats && window.lastCorrectIndex !== undefined) {
      displayAnswerChart(window.lastAnswerStats, window.lastCorrectIndex);
    }
  }
  
  toast("Correct answer revealed!");
}
// Reset showCorrectAnswer when moving to next question
function nextQuestion() {
  if (!state.currentSession) {
    toast("No active session", "error");
    return;
  }
  
  state.currentQuestionIndex++;
  state.showCorrectAnswer = false;  // RESET for new question
  
  if (state.currentQuestionIndex >= state.questions.length) {
    toast("No more questions", "error");
    state.currentQuestionIndex = state.questions.length - 1;
    return;
  }
  
  var question = state.questions[state.currentQuestionIndex];
  
  apiCall("/api/sessions/" + state.currentSession.id + "/next", {
    method: "POST",
    body: { questionId: question.question_id }
  }).then(function () {
    el("currentQuestion").textContent = "Q" + (state.currentQuestionIndex + 1) + ": " + 
      (question.question_content || question.title || "");
    el("btnLock").disabled = false;
    
    // Reset reveal answer button
    var revealBtn = document.querySelector("button[onclick='qc.revealAnswer()']");
    if (revealBtn) {
      revealBtn.textContent = "Reveal Answer";
      revealBtn.disabled = false;
    }
    
    toast("Question " + (state.currentQuestionIndex + 1) + " opened");
  }).catch(function (err) {
    toast(err.message || "Failed to open question", "error");
  });
}

function updateLeaderboard(leaderboard) {
  var list = el("leaderboard");
  if (!list) return;
  
  if (leaderboard.length === 0) {
    list.innerHTML = "<small>No scores yet</small>";
    return;
  }
  
  var html = "";
  for (var i = 0; i < Math.min(leaderboard.length, 10); i++) {
    var entry = leaderboard[i];
    html += "<div class='leaderboard-item'>";
    html += "<div style='display:flex;align-items:center'>";
    html += "<div class='rank'>" + entry.rank + "</div>";
    html += "<span>" + entry.name + "</span>";
    html += "</div>";
    html += "<strong>" + entry.points + " pts</strong>";
    html += "</div>";
  }
  list.innerHTML = html;
}


function lockQuestion() {
  if (!state.currentSession || state.currentQuestionIndex < 0) {
    return;
  }
  
  var question = state.questions[state.currentQuestionIndex];
  
  if (state.socket) {
    state.socket.emit("lock_question", {
      sessionId: state.currentSession.id,
      questionId: question.question_id
    });
  }
  
  el("btnLock").disabled = true;
  toast("Question locked");
}

function endSession() {
    try {
        if (!state.currentSession) {
            toast("No active session", "error");
            return;
        }
        
        apiCall("/api/sessions/" + state.currentSession.id + "/end", {
            method: "POST"
        }).then(function () {
            if (state.socket) {
                state.socket.disconnect();
                state.socket = null;
            }
            
            toast("Session ended");
            hide("session-view");
            show("lobby-view");
            
            state.currentSession = null;
            state.participants = []; // Reset participants
            state.currentQuestionIndex = -1;
            
            // Reset participant list display
            updateParticipantList();
            
        }).catch(function (err) {
            toast(err.message || "Failed to end session", "error");
        });
    } catch (err) {
        console.error("endSession error:", err);
        toast("Error ending session: " + (err.message || "Unknown error"), "error");
    }
}

function insertQR() {
  if (!state.qrDataUrl) {
    toast("No QR code available", "error");
    return;
  }
  
  insertQRToSlide(state.qrDataUrl).then(function () {
    toast("QR code inserted to slide");
  }).catch(function (err) {
    toast(err.message || "Failed to insert QR code", "error");
  });
}

function viewSummary() {
  if (!state.currentSession) {
    toast("No session to view", "error");
    return;
  }
  
  apiCall("/api/sessions/" + state.currentSession.id + "/summary").then(function (summary) {
    // Create a custom modal to display summary
    var modal = document.createElement("div");
    modal.style.cssText = "position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:10000;display:flex;align-items:center;justify-content:center;padding:20px;";
    
    var content = document.createElement("div");
    content.style.cssText = "background:#fff;border-radius:12px;padding:24px;max-width:500px;max-height:80vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.3);";
    
    var html = "<h3 style='margin:0 0 16px;color:#1e40af;'>📊 Session Summary</h3>";
    html += "<p style='margin:8px 0;'><strong>Participants:</strong> " + summary.participantCount + "</p>";
    html += "<p style='margin:8px 0;'><strong>Questions:</strong> " + summary.questionStats.length + "</p>";
    html += "<h4 style='margin:16px 0 8px;color:#1e40af;'>🏆 Top 3 Leaderboard</h4>";
    html += "<ol style='margin:0;padding-left:20px;'>";
    for (var i = 0; i < Math.min(3, summary.leaderboard.length); i++) {
      var entry = summary.leaderboard[i];
      html += "<li style='margin:6px 0;'><strong>" + entry.name + "</strong> - " + entry.points + " pts</li>";
    }
    html += "</ol>";
    html += "<button id='closeSummaryBtn' style='margin-top:20px;padding:10px 20px;background:#1e40af;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600;'>Close</button>";
    
    content.innerHTML = html;
    modal.appendChild(content);
    document.body.appendChild(modal);
    
    // Close button handler
    document.getElementById('closeSummaryBtn').onclick = function() {
      document.body.removeChild(modal);
    };
    
    // Close on background click
    modal.onclick = function(e) {
      if (e.target === modal) {
        document.body.removeChild(modal);
      }
    };
  }).catch(function (err) {
    toast(err.message || "Failed to load summary", "error");
  });
}

function exportCSV() {
  if (!state.currentSession) {
    toast("No session to export", "error");
    return;
  }
  
  var url = API_BASE + "/api/sessions/" + state.currentSession.id + "/export";
  window.open(url, "_blank");
  toast("Opening CSV export...");
}

function removeStudent(index) {
  try {
    if (state.pendingStudents && index >= 0 && index < state.pendingStudents.length) {
      state.pendingStudents.splice(index, 1);
      displayStudentList();
      toast("Student removed");
    }
  } catch (err) {
    console.error("ERROR in removeStudent:", err);
  }
}

function displayStudentsList() {
  var list = el("studentsList");
  if (!list) return;

  if (!state.currentQuiz) {
    list.innerHTML = "<small>No quiz selected</small>";
    return;
  }

  // First show pending students (not yet saved)
  var html = "";
  if (state.pendingStudents && state.pendingStudents.length > 0) {
    html += "<div style='margin-bottom:8px'>";
    html += "<small style='color:#22d3ee'>Pending Students (Not Saved)</small>";
    state.pendingStudents.forEach(function(s, idx) {
      html += "<div style='margin:4px 0;padding:6px;background:#0b1220;border-radius:4px'>";
      html += "<b>" + (idx + 1) + ".</b> " + s.name + " (pending)";
      html += "</div>";
    });
    html += "</div>";
  }

  // Then load saved students from server
  apiCall("/api/quizzes/" + state.currentQuiz.id + "/students")
    .then(function(response) {
      console.log("DEBUG: Students response:", response); // Debug logging
      
      // Check if response has the expected structure
      var students = response.students || [];
      
      if (students.length === 0) {
        if (!state.pendingStudents || state.pendingStudents.length === 0) {
          list.innerHTML = "<small>No students added yet</small>";
        } else {
          list.innerHTML = html;
        }
        return;
      }

      html += "<div>";
      html += "<small style='color:#22d3ee'>Saved Students</small>";
      students.forEach(function(s, idx) {
        html += "<div style='margin:4px 0;padding:6px;background:#0b1220;border-radius:4px'>";
        html += "<b>" + (idx + 1) + ".</b> " + s.name;
        html += "</div>";
      });
      html += "</div>";
      list.innerHTML = html;
    })
    .catch(function(err) {
      console.error("Error loading students:", err);
      list.innerHTML = "<small style='color:#ef4444'>Error loading students: " + 
        (err.message || "Unknown error") + "</small>";
      
      // Show detailed error in console for debugging
      console.log("DEBUG: Current quiz state:", state.currentQuiz);
      console.log("DEBUG: Error details:", err);
    });
}

// Update the existing addStudent function to also refresh the students list
function addStudent() {
  try {
    var nameInput = el("studentName");
    var passInput = el("studentPassword");
    
    if (!nameInput || !passInput) {
      console.error("ERROR: Student input fields not found");
      return;
    }
    
    var name = (nameInput.value || "").trim();
    var password = (passInput.value || "").trim();
    
    if (!name || !password) {
      toast("Please enter student name and password", "error");
      return;
    }
    
    // Add to pending
    if (!state.pendingStudents) {
      state.pendingStudents = [];
    }
    
    state.pendingStudents.push({ name: name, password: password });
    console.log("DEBUG: Added student. Total pending: " + state.pendingStudents.length);
    
    nameInput.value = "";
    passInput.value = "";
    displayStudentList(); // Update the management view
    displayStudentsList(); // Update the quiz view
    toast("Student added (local)");
    
  } catch (err) {
    console.error("ERROR in addStudent:", err);
    toast("Error adding student: " + err.message, "error");
  }
}


function saveStudentsToServer(quizId) {
  try {
    console.log("DEBUG: saveStudentsToServer called with quizId=" + quizId);
    
    // Validate quizId
    if (!quizId || quizId === null || quizId === undefined || isNaN(quizId)) {
      console.error("ERROR: Invalid quizId: " + quizId);
      toast("Please create or select a quiz first", "error");
      return Promise.reject(new Error("No valid quiz selected"));
    }
    
    // If no pending students, just resolve
    if (!state.pendingStudents || state.pendingStudents.length === 0) {
      console.log("DEBUG: No pending students to save");
      return Promise.resolve();
    }
    
    var studentCount = state.pendingStudents.length;
    console.log("DEBUG: Saving " + studentCount + " students to quiz " + quizId);
    
    var payload = {
      students: state.pendingStudents
    };
    
    console.log("DEBUG: Payload: " + JSON.stringify(payload).substring(0, 100));
    
  return apiCall("/api/quizzes/" + quizId + "/students", {
    method: "POST",
    body: payload
  }).then(function (data) {
    console.log("DEBUG: saveStudentsToServer success:", data);
    var savedCount = (data && data.count) ? data.count : studentCount;
    toast("✓ " + savedCount + " student(s) saved");
    state.pendingStudents = [];
    displayStudentList(); // Update the management view
    displayStudentsList(); // Update the quiz view
    return data;
  
      
    }).catch(function (err) {
      console.error("ERROR: saveStudentsToServer failed:", err);
      var errMsg = (err && err.message) ? err.message : String(err);
      toast("Failed to save students: " + errMsg, "error");
      return Promise.reject(err);
    });
    
  } catch (err) {
    console.error("ERROR in saveStudentsToServer:", err);
    toast("Error saving students: " + err.message, "error");
    return Promise.reject(err);
  }
}



// ============================================================================
// Expose API
// ============================================================================
window.qc = {
  login: login,
  logout: logout,
  switchTab: switchTab,
  createQuiz: createQuiz,
  addStudent: addStudent,
  removeStudent: removeStudent,
  saveStudentsToServer: saveStudentsToServer,  // ADD THIS LINE
  loadQuizzes: loadQuizzes,
  saveQuestion: saveQuestion,
  syncQuestions: syncQuestions,
  startSession: startSession,
  nextQuestion: nextQuestion,
  lockQuestion: lockQuestion,
  endSession: endSession,
  insertQR: insertQR,
  viewSummary: viewSummary,
  exportCSV: exportCSV,
  toggleChart: toggleChart,
  displayStudentsList: displayStudentsList,
  revealAnswer: revealAnswer
};
// ============================================================================
// Initialization
// ============================================================================
function init() {
  try {
    console.log("DEBUG: Quiz Competition initializing...");
    
    // Initialize state if not already done
    if (!state) {
      state = {
        teacher: null,
        currentQuiz: null,
        currentSession: null,
        questions: [],
        participants: [],
        currentQuestionIndex: -1,
        socket: null,
        qrDataUrl: null,
        slideQuestionMap: {},
        showCorrectAnswer: false,
        pendingStudents: []
      };
      console.log("DEBUG: State initialized");
    }
    
    // Try to check if already logged in
    console.log("DEBUG: Checking current user...");
    
  apiCall("/api/auth/me").then(function (data) {
    try {
      console.log("DEBUG: Already logged in as:", data.teacher);
      state.teacher = data.teacher;
      
      var loginScreen = el("login-screen");
      var appBody = el("app-body");
      var logoutBtn = el("btnLogout");
      
      if (loginScreen) loginScreen.style.display = "none";
      if (appBody) appBody.style.display = "block";
      if (logoutBtn) logoutBtn.style.display = "block";
      
      window.qc.loadQuizzes();
      displayStudentsList(); // Add this line
      
    } catch (err) {
      console.error("ERROR processing login response:", err);
    }
  }).catch(function (err) {
      try {
        console.log("DEBUG: Not logged in, showing login screen");
        var loginScreen = el("login-screen");
        var appBody = el("app-body");
        if (loginScreen) loginScreen.style.display = "block";
        if (appBody) appBody.style.display = "none";
      } catch (screenErr) {
        console.error("ERROR setting up login screen:", screenErr);
      }
    });
    
  } catch (err) {
    console.error("FATAL ERROR in init:", err);
    try {
      toast("Initialization error: " + err.message, "error");
    } catch (toastErr) {
      console.error("Toast error:", toastErr);
    }
  }
}


window.addEventListener("error", function(e) {
  console.error("GLOBAL ERROR:", e.message, e.filename, e.lineno);
  try {
    toast("ERROR: " + (e.message || "Unknown error"), "error");
  } catch (toastErr) {
    console.error("Toast error:", toastErr);
  }
});

// Catch unhandled promise rejections
window.addEventListener("unhandledrejection", function(e) {
  console.error("UNHANDLED PROMISE REJECTION:", e.reason);
  try {
    toast("Promise error: " + (e.reason || "Unknown"), "error");
  } catch (toastErr) {
    console.error("Toast error:", toastErr);
  }
});

if (!window.qc) {
  console.error("ERROR: window.qc not defined!");
  window.qc = {};
}

// Ensure all critical functions are exported
var requiredFunctions = [
  'login', 'logout', 'switchTab', 'createQuiz', 'addStudent', 'removeStudent',
  'saveStudentsToServer', 'loadQuizzes', 'saveQuestion', 'syncQuestions',
  'startSession', 'nextQuestion', 'lockQuestion', 'endSession', 'insertQR',
  'viewSummary', 'exportCSV', 'toggleChart', 'revealAnswer', 'loadQuestions'
];

for (var i = 0; i < requiredFunctions.length; i++) {
  var fname = requiredFunctions[i];
  if (typeof window[fname] === "function") {
    window.qc[fname] = window[fname];
  } else {
    console.warn("WARNING: Function '" + fname + "' not found");
  }
}

console.log("DEBUG: window.qc exports complete. Functions available:", Object.keys(window.qc));

Office.onReady(function () {
  init();
});

if (typeof Office !== "undefined") {
  try {
    Office.onReady(function(info) {
      try {
        console.log("Office.onReady called with info:", info);
        init();
      } catch (err) {
        console.error("ERROR in Office.onReady handler:", err);
      }
    });
  } catch (err) {
    console.error("ERROR setting up Office.onReady:", err);
    // Fallback: try init anyway
    setTimeout(function() {
      try {
        init();
      } catch (err2) {
        console.error("Fallback init failed:", err2);
      }
    }, 500);
  }
} else {
  // Not in Office context
  console.warn("WARNING: Office.js not loaded, running init anyway");
  setTimeout(init, 100);
}