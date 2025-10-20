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
  slideQuestionMap: {} // slideId -> questionId
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
  var title = el("quizTitle").value.trim();
  if (!title) {
    toast("Please enter a quiz title", "error");
    return;
  }
  
  apiCall("/api/quizzes", {
    method: "POST",
    body: { title: title }
  }).then(function (data) {
    state.currentQuiz = { id: data.id, title: title };
    el("quizStatus").textContent = "Quiz: " + title + " (ID: " + data.id + ")";
    toast("Quiz created successfully");
    el("quizTitle").value = "";
  }).catch(function (err) {
    toast(err.message || "Failed to create quiz", "error");
  });
}

function loadQuizzes() {
  apiCall("/api/quizzes").then(function (quizzes) {
    if (quizzes.length > 0) {
      state.currentQuiz = {
        id: quizzes[0].course_id,
        title: quizzes[0].course_name
      };
      el("quizStatus").textContent = "Quiz: " + quizzes[0].course_name + " (ID: " + quizzes[0].course_id + ")";
      loadQuestions();
    }
  }).catch(function (err) {
    console.error(err);
  });
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
  
  state.socket = io(API_BASE);
  
  state.socket.on("connect", function () {
    console.log("WebSocket connected");
    state.socket.emit("join_session", { code: code, role: "teacher" });
  });
  
  state.socket.on("joined", function (data) {
    console.log("Joined session:", data);
  });
  
  state.socket.on("lobby_update", function (data) {
    console.log("Participant joined:", data);
    state.participants.push(data);
    updateParticipantList();
  });
  
  state.socket.on("stats_update", function (data) {
    console.log("Stats update:", data);
    updateStats(data);
  });
  
  state.socket.on("disconnect", function () {
    console.log("WebSocket disconnected");
  });
}

function updateParticipantList() {
  var list = el("participantList");
  var count = el("participantCount");
  
  if (!list || !count) return;
  
  count.textContent = state.participants.length;
  
  if (state.participants.length === 0) {
    list.innerHTML = "<small>No participants yet</small>";
    return;
  }
  
  var html = "";
  for (var i = 0; i < state.participants.length; i++) {
    var p = state.participants[i];
    html += "<div class='participant-item'>";
    html += "<span>" + (p.name || "Student " + (i + 1)) + "</span>";
    html += "<small>" + (p.joinedAt || "") + "</small>";
    html += "</div>";
  }
  list.innerHTML = html;
  
  // Enable next button if we have participants
  if (state.participants.length > 0) {
    el("btnNext").disabled = false;
  }
}

function updateStats(data) {
  el("responseCount").textContent = data.totalResponses || 0;
  el("correctCount").textContent = data.correctCount || 0;
  
  var percent = data.totalResponses > 0 ? Math.round((data.correctCount / data.totalResponses) * 100) : 0;
  el("correctPercent").textContent = percent;
  el("statsFill").style.width = percent + "%";
  
  if (data.leaderboard) {
    updateLeaderboard(data.leaderboard);
  }
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

function nextQuestion() {
  if (!state.currentSession) {
    toast("No active session", "error");
    return;
  }
  
  state.currentQuestionIndex++;
  
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
    toast("Question " + (state.currentQuestionIndex + 1) + " opened");
  }).catch(function (err) {
    toast(err.message || "Failed to open question", "error");
  });
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
    
    // Use a simple confirmation without confirm() which may not work in Office context
    var shouldEnd = true;
    try {
      shouldEnd = confirm("Are you sure you want to end this quiz session?");
    } catch (e) {
      // If confirm fails, just proceed
      shouldEnd = true;
    }
    
    if (!shouldEnd) {
      return;
    }
    
    apiCall("/api/sessions/" + state.currentSession.id + "/end", {
      method: "POST"
    }).then(function () {
      try {
        if (state.socket) {
          state.socket.disconnect();
          state.socket = null;
        }
      } catch (e) {
        console.error("Socket disconnect error:", e);
      }
      
      toast("Session ended");
      hide("session-view");
      show("lobby-view");
      
      state.currentSession = null;
      state.participants = [];
      state.currentQuestionIndex = -1;
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

// ============================================================================
// Expose API
// ============================================================================
window.qc = {
  login: login,
  logout: logout,
  switchTab: switchTab,
  createQuiz: createQuiz,
  loadQuizzes: loadQuizzes,
  saveQuestion: saveQuestion,
  syncQuestions: syncQuestions,
  startSession: startSession,
  nextQuestion: nextQuestion,
  lockQuestion: lockQuestion,
  endSession: endSession,
  insertQR: insertQR,
  viewSummary: viewSummary,
  exportCSV: exportCSV
};

// ============================================================================
// Initialization
// ============================================================================
function init() {
  console.log("Quiz Competition Add-in initialized");
  
  // Check if already logged in
  apiCall("/api/auth/me").then(function (data) {
    state.teacher = data.teacher;
    el("login-screen").style.display = "none";
    el("app-body").style.display = "block";
    el("btnLogout").style.display = "block";
    loadQuizzes();
  }).catch(function () {
    // Not logged in, show login screen
    el("login-screen").style.display = "block";
    el("app-body").style.display = "none";
  });
}

Office.onReady(function () {
  init();
});
