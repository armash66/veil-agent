/**
 * WebVeil Side Panel — Main Controller
 * View switching, session management with CRUD (rename/delete), automated agent pipeline with
 * real-event step-by-step narration bubbles, programmatic script injection, and feedback row.
 *
 * HONEST STATUS: PII detection is DOM-text-only (regex). No screenshot/face/image
 * PII detection is active. Vision/OCR is explicitly deferred to a follow-up PR.
 */

document.addEventListener('DOMContentLoaded', () => {
  // ═══════════════════════════════════════════════════════════
  // DOM REFERENCES
  // ═══════════════════════════════════════════════════════════
  const viewLanding      = document.getElementById('view-landing');
  const viewConversation = document.getElementById('view-conversation');
  const viewSettings     = document.getElementById('view-settings');

  // Landing
  const newTaskBtn   = document.getElementById('new-task-btn');
  const historyBtn   = document.getElementById('history-btn');
  const sessionList  = document.getElementById('session-list');
  const emptyState   = document.getElementById('empty-state');
  const landingSettingsBtn = document.getElementById('landing-settings-btn');

  // Conversation
  const backBtn       = document.getElementById('back-btn');
  const convTitle     = document.getElementById('conv-title');
  const newSessionBtn = document.getElementById('new-session-btn');
  const convFolderBtn = document.getElementById('conv-folder-btn');
  const convSettingsBtn = document.getElementById('conv-settings-btn');
  const messagesArea  = document.getElementById('messages-area');
  const heroPrompt    = document.getElementById('hero-prompt');
  const taskInput     = document.getElementById('task-input');
  const sendBtn       = document.getElementById('send-btn');
  const statusStrip     = document.getElementById('status-strip');
  const statusStripText = document.getElementById('status-strip-text');
  const statusStripDismiss = document.getElementById('status-strip-dismiss');

  // Settings
  const settingsBackBtn            = document.getElementById('settings-back-btn');
  const settingsServerUrl          = document.getElementById('settings-server-url');
  const runSecurityVerificationBtn = document.getElementById('run-security-verification-btn');

  // Modal
  const payloadModal  = document.getElementById('payload-modal');
  const modalJson     = document.getElementById('modal-json');
  const modalCloseBtn = document.getElementById('modal-close-btn');

  // Server status indicator
  const serverBadge         = document.getElementById('server-badge');
  const serverBadgeText     = document.getElementById('server-badge-text');

  // ═══════════════════════════════════════════════════════════
  // STATE
  // ═══════════════════════════════════════════════════════════
  let sessions = [];          // {id, title, createdAt, messages: [...]}
  let activeSessionId = null;
  let previousView = 'landing';
  let isRunning = false;
  let isServerOnline = false;
  let latestPayload = { status: 'No payload transmitted yet' };

  let serverBaseUrl = 'http://127.0.0.1:8000';

  // Load saved server URL
  try {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get('webveil_server_url', (res) => {
        if (res && res.webveil_server_url) {
          serverBaseUrl = res.webveil_server_url.trim();
          if (settingsServerUrl) settingsServerUrl.value = serverBaseUrl;
          checkServerHealth();
        }
      });
    } else {
      const saved = localStorage.getItem('webveil_server_url');
      if (saved) {
        serverBaseUrl = saved.trim();
        if (settingsServerUrl) settingsServerUrl.value = serverBaseUrl;
      }
    }
  } catch (_) {}

  function getReasoningUrl() {
    const clean = serverBaseUrl.replace(/\/+$/, '');
    return `${clean}/api/reason`;
  }

  function getHealthUrl() {
    const clean = serverBaseUrl.replace(/\/+$/, '');
    return `${clean}/health`;
  }

  // ═══════════════════════════════════════════════════════════
  // REASONING SERVER HEALTH POLLING (5s interval)
  // ═══════════════════════════════════════════════════════════
  async function checkServerHealth() {
    const clean = serverBaseUrl.replace(/\/+$/, '');
    try {
      let res = await fetch(`${clean}/api/health`, {
        signal: AbortSignal.timeout(3000)
      });
      if (!res.ok) {
        res = await fetch(`${clean}/health`, {
          signal: AbortSignal.timeout(3000)
        });
      }
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'ok') {
          setServerStatus(true);
          return;
        }
      }
    } catch (_) {}
    if (!isRunning) {
      setServerStatus(false);
    }
  }

  function setServerStatus(online) {
    isServerOnline = online;

    const badges = document.querySelectorAll('.wv-server-badge');
    badges.forEach(badge => {
      const textEl = badge.querySelector('.wv-badge-text');
      if (online) {
        badge.className = 'wv-server-badge online';
        if (textEl) textEl.textContent = 'Connected';
      } else {
        badge.className = 'wv-server-badge offline';
        if (textEl) textEl.textContent = 'Offline';
      }
    });

    if (!isRunning) {
      taskInput.disabled = false;
      sendBtn.disabled = !taskInput.value.trim();
    }
  }

  // Poll server health immediately & every 5 seconds
  checkServerHealth();
  setInterval(checkServerHealth, 5000);

  // ═══════════════════════════════════════════════════════════
  // VIEW SWITCHING & SKELETON LOADING
  // ═══════════════════════════════════════════════════════
  function showLanding() {
    viewLanding.classList.add('active');
    viewConversation.classList.remove('active');
    if (viewSettings) viewSettings.classList.remove('active');
    activeSessionId = null;
    previousView = 'landing';
    renderSessionList();
  }

  function showConversation(sessionId) {
    viewLanding.classList.remove('active');
    viewConversation.classList.add('active');
    if (viewSettings) viewSettings.classList.remove('active');
    activeSessionId = sessionId;
    previousView = 'conversation';

    const session = sessions.find(s => s.id === sessionId);
    if (session) {
      convTitle.textContent = session.title;
      
      // Skeleton loading transition
      showSkeletonLoading();
      setTimeout(() => {
        renderMessages(session);
      }, 180);
    }
  }

  function showSettings() {
    if (viewLanding.classList.contains('active')) {
      previousView = 'landing';
    } else if (viewConversation.classList.contains('active')) {
      previousView = 'conversation';
    }
    viewLanding.classList.remove('active');
    viewConversation.classList.remove('active');
    if (viewSettings) viewSettings.classList.add('active');
  }

  function showSkeletonLoading() {
    const children = Array.from(messagesArea.children);
    children.forEach(child => {
      if (child.id !== 'hero-prompt') child.remove();
    });
    heroPrompt.style.display = 'none';

    const skel = document.createElement('div');
    skel.id = 'skeleton-loader';
    skel.className = 'wv-skeleton-container';
    skel.innerHTML = `
      <div class="wv-skeleton-box wv-skeleton-title"></div>
      <div class="wv-skeleton-box wv-skeleton-msg right"></div>
      <div class="wv-skeleton-box wv-skeleton-msg"></div>
    `;
    messagesArea.appendChild(skel);
  }

  // ═══════════════════════════════════════════════════════════
  // SESSION MANAGEMENT & CRUD (chrome.storage.local)
  // ═══════════════════════════════════════════════════════════
  function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }

  function createSession() {
    const session = {
      id: generateId(),
      title: 'New Task',
      createdAt: Date.now(),
      messages: [],
    };
    sessions.unshift(session);
    saveSessions();
    return session;
  }

  function saveSessions() {
    try {
      chrome.storage.local.set({ webveil_sessions: sessions });
    } catch (_) {
      localStorage.setItem('webveil_sessions', JSON.stringify(sessions));
    }
  }

  function loadSessions(callback) {
    try {
      chrome.storage.local.get('webveil_sessions', (result) => {
        sessions = result.webveil_sessions || [];
        callback();
      });
    } catch (_) {
      const stored = localStorage.getItem('webveil_sessions');
      sessions = stored ? JSON.parse(stored) : [];
      callback();
    }
  }

  // ═══════════════════════════════════════════════════════════
  // SESSION LIST RENDERING (With Rename & Delete CRUD)
  // ═══════════════════════════════════════════════════════════
  function renderSessionList() {
    sessionList.innerHTML = '';

    if (sessions.length === 0) {
      emptyState.style.display = 'block';
      return;
    }

    emptyState.style.display = 'none';

    sessions.forEach(session => {
      const li = document.createElement('li');
      li.className = 'wv-session-item';

      const leftDiv = document.createElement('div');
      leftDiv.className = 'wv-session-item-left';
      leftDiv.innerHTML = `
        <span class="wv-session-title">${escapeHtml(session.title)}</span>
        <span class="wv-session-time">${formatTime(session.createdAt)}</span>
      `;
      leftDiv.addEventListener('click', () => {
        if (!li.classList.contains('editing')) {
          showConversation(session.id);
        }
      });

      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'wv-session-actions';

      const renameBtn = document.createElement('button');
      renameBtn.className = 'wv-session-action-btn';
      renameBtn.title = 'Rename session';
      renameBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>`;
      renameBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        startRenamingSession(session, leftDiv, li);
      });

      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'wv-session-action-btn delete';
      deleteBtn.title = 'Delete session';
      deleteBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`;
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        confirmDeleteSession(session, actionsDiv);
      });

      actionsDiv.appendChild(renameBtn);
      actionsDiv.appendChild(deleteBtn);

      li.appendChild(leftDiv);
      li.appendChild(actionsDiv);
      sessionList.appendChild(li);
    });
  }

  function startRenamingSession(session, containerEl, liEl) {
    liEl.classList.add('editing');
    const currentTitle = session.title;
    containerEl.innerHTML = '';
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'wv-session-inline-input';
    input.value = currentTitle;

    let saved = false;
    const saveRename = () => {
      if (saved) return;
      saved = true;
      const newTitle = input.value.trim() || currentTitle;
      session.title = newTitle;
      saveSessions();
      renderSessionList();
    };

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') saveRename();
      if (e.key === 'Escape') renderSessionList();
    });
    input.addEventListener('blur', saveRename);

    containerEl.appendChild(input);
    input.focus();
    input.select();
  }

  function confirmDeleteSession(session, actionsContainerEl) {
    actionsContainerEl.innerHTML = `
      <span class="wv-delete-confirm">
        <button class="wv-delete-confirm-btn">Delete</button>
        <button class="wv-delete-cancel-btn">Cancel</button>
      </span>
    `;

    const confirmBtn = actionsContainerEl.querySelector('.wv-delete-confirm-btn');
    const cancelBtn = actionsContainerEl.querySelector('.wv-delete-cancel-btn');

    confirmBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteSession(session.id);
    });

    cancelBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      renderSessionList();
    });
  }

  function deleteSession(sessionId) {
    sessions = sessions.filter(s => s.id !== sessionId);
    saveSessions();
    if (activeSessionId === sessionId) {
      showLanding();
    } else {
      renderSessionList();
    }
  }

  // ═══════════════════════════════════════════════════════════
  // MESSAGE RENDERING
  // ═══════════════════════════════════════════════════════════
  function renderMessages(session) {
    const children = Array.from(messagesArea.children);
    children.forEach(child => {
      if (child.id !== 'hero-prompt') child.remove();
    });

    if (session.messages.length === 0) {
      heroPrompt.style.display = '';
      return;
    }

    heroPrompt.style.display = 'none';

    session.messages.forEach((msg, idx) => {
      appendMessageElement(msg, session.id, idx);
    });

    scrollToBottom();
  }

  function appendMessageElement(msg, sessionId, msgIdx) {
    let el;

    switch (msg.type) {
      case 'user':
        el = document.createElement('div');
        el.className = 'wv-msg wv-msg-user';
        el.textContent = msg.text;
        break;

      case 'agent':
        el = document.createElement('div');
        el.className = 'wv-msg wv-msg-agent';
        el.textContent = msg.text;
        break;

      case 'reasoning':
        el = buildReasoningBlock(msg);
        break;

      case 'result':
        el = buildResultCard(msg.data, sessionId, msgIdx);
        break;

      default:
        return;
    }

    if (el) {
      messagesArea.appendChild(el);
      scrollToBottom();
    }

    return el;
  }

  function addMessage(session, msg) {
    session.messages.push(msg);
    saveSessions();
    const idx = session.messages.length - 1;
    return appendMessageElement(msg, session.id, idx);
  }

  // ═══════════════════════════════════════════════════════════
  // CATEGORY CAPTION MAPPER (Section 2.2)
  // ═══════════════════════════════════════════════════════════
  function getCategoryCaption(category) {
    switch ((category || '').toUpperCase()) {
      case 'EMAIL':
        return 'matched email pattern';
      case 'PASSWORD':
        return 'input type=password';
      case 'AADHAAR':
        return 'matched 12-digit Aadhaar pattern';
      case 'CREDIT_CARD':
        return 'matched credit card pattern';
      case 'PHONE':
        return 'matched phone pattern';
      case 'SSN':
        return 'matched SSN pattern';
      default:
        return `matched ${(category || 'sensitive').toLowerCase()} pattern`;
    }
  }

  function formatTraceTime(ts) {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  // ═══════════════════════════════════════════════════════════
  // UNIFIED REASONING STREAM BLOCK (Section 3)
  // ═══════════════════════════════════════════════════════════
  function buildReasoningBlock(msg) {
    const block = document.createElement('div');
    const isCompleted = msg.status === 'completed' || msg.status === 'error';
    const isError = msg.isError || msg.status === 'error';

    block.className = `wv-reasoning-block ${isCompleted ? 'completed' : ''}`;

    const header = document.createElement('div');
    header.className = 'wv-reasoning-header';

    const summary = document.createElement('div');
    summary.className = 'wv-reasoning-summary';

    const icon = document.createElement('span');
    icon.className = 'wv-reasoning-icon';
    if (isError) {
      icon.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent-red)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
      icon.style.display = 'inline-flex';
    } else {
      icon.style.display = 'none';
    }

    const text = document.createElement('span');
    text.className = `wv-reasoning-text ${!isCompleted ? 'wv-text-pulse' : ''}`;
    text.textContent = msg.summary || msg.stage || 'Reading page';

    summary.appendChild(icon);
    summary.appendChild(text);

    const toggle = document.createElement('button');
    toggle.className = 'wv-reasoning-toggle';
    toggle.title = 'Toggle details';
    toggle.innerHTML = `<svg class="wv-chevron-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`;

    header.appendChild(summary);
    header.appendChild(toggle);

    const trace = document.createElement('div');
    trace.className = 'wv-reasoning-trace';
    trace.style.display = 'none';

    const traceList = document.createElement('div');
    traceList.className = 'wv-trace-list';
    if (msg.trace && msg.trace.length > 0) {
      msg.trace.forEach(item => {
        const line = document.createElement('div');
        line.className = 'wv-trace-item';
        line.innerHTML = `<span class="wv-trace-time">${formatTraceTime(item.time || Date.now())}</span> · <span>${escapeHtml(item.text)}</span>`;
        traceList.appendChild(line);
      });
    }
    trace.appendChild(traceList);

    const toggleExpand = (e) => {
      e.stopPropagation();
      const isExp = block.classList.toggle('expanded');
      trace.style.display = isExp ? 'flex' : 'none';
    };

    header.addEventListener('click', toggleExpand);

    block.appendChild(header);
    block.appendChild(trace);
    return block;
  }

  // ═══════════════════════════════════════════════════════════
  // RESULT CARD BUILDER (Section 2.2, 2.3)
  // ═══════════════════════════════════════════════════════════
  function buildResultCard(data, sessionId, msgIdx) {
    const card = document.createElement('div');
    card.className = 'wv-result-card';

    const countersHtml = `
      <div class="wv-result-label">Task Summary</div>
      <div class="wv-counters">
        <div class="wv-counter">
          <div class="wv-counter-label">Actions</div>
          <div class="wv-counter-value wv-counter-actions">${data.actions || 0}</div>
        </div>
        <div class="wv-counter">
          <div class="wv-counter-label">Protected</div>
          <div class="wv-counter-value green wv-counter-protected">${data.protectedCount || 0}</div>
        </div>
        <div class="wv-counter">
          <div class="wv-counter-label">Transmitted</div>
          <div class="wv-counter-value wv-counter-transmitted">${data.transmittedNodes || 0}</div>
        </div>
      </div>
    `;

    const tokensListHtml = (data.tokens || []).map(t => {
      const tok = typeof t === 'string' ? t : (t.replacement || t.token);
      const cat = typeof t === 'string' ? '' : t.category;
      return `
        <div class="wv-token-row">
          <span class="wv-token-primary">${escapeHtml(tok)}</span>
          <span class="wv-token-secondary">${escapeHtml(getCategoryCaption(cat))}</span>
        </div>
      `;
    }).join('');

    const tokensSectionHtml = `
      <div class="wv-result-label">Protected Tokens</div>
      <div class="wv-tokens-list">
        ${tokensListHtml}
      </div>
    `;

    const inspectHtml = `
      <button class="wv-inspect-link">
        <span>Inspect Outgoing Payload</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
      </button>
    `;

    const feedbackHtml = `
      <div class="wv-feedback-row">
        <button class="wv-feedback-btn thumbs-up" title="Helpful">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h3"/><path d="M7 10V3a1 1 0 0 1 1-1h1.5a2 2 0 0 1 2 2v2"/></svg>
        </button>
        <button class="wv-feedback-btn thumbs-down" title="Not helpful">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-3"/><path d="M17 14v7a1 1 0 0 1-1 1h-1.5a2 2 0 0 1-2-2v-2"/></svg>
        </button>
        <button class="wv-feedback-btn comment-btn" title="Add comment">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        </button>
      </div>
      <div class="wv-feedback-input-container">
        <input type="text" class="wv-feedback-input" placeholder="Add feedback comment..." />
        <button class="wv-feedback-save-btn">Save</button>
      </div>
    `;

    card.innerHTML = countersHtml + tokensSectionHtml + inspectHtml + feedbackHtml;

    const inspectBtn = card.querySelector('.wv-inspect-link');
    if (inspectBtn) {
      inspectBtn.addEventListener('click', () => {
        modalJson.textContent = JSON.stringify(latestPayload, null, 2);
        payloadModal.classList.add('visible');
      });
    }

    const upBtn = card.querySelector('.thumbs-up');
    const downBtn = card.querySelector('.thumbs-down');
    const commentBtn = card.querySelector('.comment-btn');
    const inputContainer = card.querySelector('.wv-feedback-input-container');
    const feedbackInput = card.querySelector('.wv-feedback-input');
    const saveBtn = card.querySelector('.wv-feedback-save-btn');

    if (upBtn && downBtn && commentBtn) {
      upBtn.addEventListener('click', () => {
        upBtn.classList.toggle('active-up');
        downBtn.classList.remove('active-down');
        saveFeedback(sessionId, msgIdx, upBtn.classList.contains('active-up') ? 'up' : null, feedbackInput.value);
      });

      downBtn.addEventListener('click', () => {
        downBtn.classList.toggle('active-down');
        upBtn.classList.remove('active-up');
        saveFeedback(sessionId, msgIdx, downBtn.classList.contains('active-down') ? 'down' : null, feedbackInput.value);
      });

      commentBtn.addEventListener('click', () => {
        inputContainer.classList.toggle('visible');
        if (inputContainer.classList.contains('visible')) {
          feedbackInput.focus();
        }
      });

      saveBtn.addEventListener('click', () => {
        const rating = upBtn.classList.contains('active-up') ? 'up' : (downBtn.classList.contains('active-down') ? 'down' : null);
        saveFeedback(sessionId, msgIdx, rating, feedbackInput.value);
        inputContainer.classList.remove('visible');
      });
    }

    return card;
  }

  function updateResultCardCounters(cardEl, data) {
    if (!cardEl) return;
    const actEl = cardEl.querySelector('.wv-counter-actions');
    const protEl = cardEl.querySelector('.wv-counter-protected');
    const transEl = cardEl.querySelector('.wv-counter-transmitted');
    if (actEl) actEl.textContent = data.actions || 0;
    if (protEl) protEl.textContent = data.protectedCount || 0;
    if (transEl) transEl.textContent = data.transmittedNodes || 0;
  }

  function appendTokenRow(cardEl, token, category) {
    if (!cardEl) return;
    const listEl = cardEl.querySelector('.wv-tokens-list');
    if (!listEl) return;
    const row = document.createElement('div');
    row.className = 'wv-token-row';
    row.innerHTML = `
      <span class="wv-token-primary">${escapeHtml(token)}</span>
      <span class="wv-token-secondary">${escapeHtml(getCategoryCaption(category))}</span>
    `;
    listEl.appendChild(row);
  }

  function saveFeedback(sessionId, msgIdx, rating, comment) {
    try {
      const key = `feedback_${sessionId}_${msgIdx ?? Date.now()}`;
      const payload = { rating, comment, timestamp: Date.now() };
      chrome.storage.local.set({ [key]: payload });
    } catch (_) {}
  }

  // ═══════════════════════════════════════════════════════════
  // AUTOMATED AGENT PIPELINE (Unified Reasoning Stream & Live Tokens)
  // ═══════════════════════════════════════════════════════════
  async function runAgentPipeline(session, task) {
    if (isRunning) return;
    if (!isServerOnline) {
      addMessage(session, { type: 'user', text: task });
      addMessage(session, {
        type: 'reasoning',
        stage: 'Stopped · server offline',
        status: 'error',
        summary: 'Stopped · server offline',
        isError: true,
        trace: [{ text: 'Stopped · server offline', time: Date.now() }]
      });
      return;
    }
    isRunning = true;
    sendBtn.disabled = true;

    session.title = task.length > 40 ? task.substring(0, 40) + '…' : task;
    saveSessions();
    convTitle.textContent = session.title;

    heroPrompt.style.display = 'none';
    addMessage(session, { type: 'user', text: task });

    // Single collapsible reasoning block per task (§3)
    const reasoningMsg = {
      type: 'reasoning',
      stage: 'Reading page',
      status: 'active',
      summary: 'Reading page',
      isError: false,
      trace: [{ text: 'Reading page', time: Date.now() }]
    };
    const reasoningEl = addMessage(session, reasoningMsg);

    // Result data accumulated during pipeline execution
    const resultData = {
      actions: 0,
      protectedCount: 0,
      transmittedNodes: 0,
      tokens: []
    };
    let resultCardEl = null;

    function updateReasoningStage(stageText, traceDetail) {
      reasoningMsg.stage = stageText;
      reasoningMsg.summary = stageText;
      reasoningMsg.trace.push({ text: traceDetail || stageText, time: Date.now() });
      saveSessions();

      if (reasoningEl) {
        const textEl = reasoningEl.querySelector('.wv-reasoning-text');
        if (textEl && reasoningMsg.status === 'active') {
          textEl.textContent = stageText;
        }
        const traceListEl = reasoningEl.querySelector('.wv-trace-list');
        if (traceListEl) {
          const item = document.createElement('div');
          item.className = 'wv-trace-item';
          item.innerHTML = `<span class="wv-trace-time">${formatTraceTime(Date.now())}</span> · <span>${escapeHtml(traceDetail || stageText)}</span>`;
          traceListEl.appendChild(item);
        }
      }
    }

    function completeReasoning(isError, summaryText, traceDetail) {
      reasoningMsg.status = isError ? 'error' : 'completed';
      reasoningMsg.isError = isError;
      reasoningMsg.summary = summaryText;
      if (traceDetail) {
        reasoningMsg.trace.push({ text: traceDetail, time: Date.now() });
      }
      saveSessions();

      if (reasoningEl) {
        reasoningEl.classList.remove('expanded');
        const traceEl = reasoningEl.querySelector('.wv-reasoning-trace');
        if (traceEl) traceEl.style.display = 'none';

        reasoningEl.classList.add('completed');
        const textEl = reasoningEl.querySelector('.wv-reasoning-text');
        if (textEl) {
          textEl.classList.remove('wv-text-pulse');
          textEl.textContent = summaryText;
        }
        const iconEl = reasoningEl.querySelector('.wv-reasoning-icon');
        if (iconEl) {
          if (isError) {
            iconEl.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent-red)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
            iconEl.style.display = 'inline-flex';
          } else {
            iconEl.style.display = 'none';
          }
        }
        const traceListEl = reasoningEl.querySelector('.wv-trace-list');
        if (traceListEl && traceDetail) {
          const item = document.createElement('div');
          item.className = 'wv-trace-item';
          item.innerHTML = `<span class="wv-trace-time">${formatTraceTime(Date.now())}</span> · <span>${escapeHtml(traceDetail)}</span>`;
          traceListEl.appendChild(item);
        }
      }
    }

    let prunedNodes = [];
    let piiResult = { tokens: [], count: 0 };
    let sanitizedDom = [];
    let actionPlan = null;

    try {
      // ── STEP 1: Get active tab ──
      const tab = await getActiveTab();
      if (!tab) {
        completeReasoning(true, "Stopped · couldn't read this page", 'No active tab found');
        addMessage(session, { type: 'agent', text: "Stopped · couldn't read this page. Open a webpage first." });
        return;
      }

      // Ensure content script is injected and reachable
      try {
        await ensureContentScriptInjected(tab);
      } catch (injErr) {
        completeReasoning(true, "Stopped · couldn't read this page", injErr.message);
        return;
      }

      // Reset action firewall & vault on page for new run
      try { await sendTabMessage(tab.id, { action: 'RESET_FIREWALL' }); } catch (_) {}

      // ── STEP 2: DOM Pruning (content script) ──
      updateReasoningStage('Reading page', 'DOM extraction started');

      try {
        const domResult = await sendTabMessage(tab.id, { action: 'PRUNE_DOM' });
        prunedNodes = domResult.nodes || [];
        updateReasoningStage('Reading page', `DOM extraction complete (${prunedNodes.length} nodes)`);
      } catch (e) {
        const lastErr = chrome.runtime?.lastError?.message || e.message || 'Content script disconnected';
        completeReasoning(true, "Stopped · couldn't read this page", lastErr);
        return;
      }

      // ── STEP 3: PII Detection (content script, isolated world) ──
      updateReasoningStage('Scanning for sensitive data', 'PII scan started');

      try {
        piiResult = await sendTabMessage(tab.id, { action: 'DETECT_PII', nodes: prunedNodes });
        updateReasoningStage('Scanning for sensitive data', `PII scan complete (${piiResult.count || 0} fields protected)`);

        // Append tokens live with stagger matching on-page outline sweep
        if (piiResult.tokens && piiResult.tokens.length > 0) {
          for (let i = 0; i < piiResult.tokens.length; i++) {
            const t = piiResult.tokens[i];
            resultData.protectedCount += 1;
            resultData.tokens.push({
              replacement: t.replacement,
              category: t.category
            });
            if (resultCardEl) {
              updateResultCardCounters(resultCardEl, resultData);
              appendTokenRow(resultCardEl, t.replacement, t.category);
            }
            saveSessions();
            if (i < piiResult.tokens.length - 1) {
              await new Promise(r => setTimeout(r, 80));
            }
          }
        }
      } catch (e) {
        updateReasoningStage('Scanning for sensitive data', 'PII scan skipped');
      }

      // Build sanitized DOM (replace raw values with tokens)
      sanitizedDom = prunedNodes.map(node => {
        let text = node.text_content || '';
        if (piiResult.replacements) {
          piiResult.replacements.forEach(r => {
            text = text.split(r.original).join(r.replacement);
          });
        }
        return { ...node, text_content: text };
      });

      // ── STEP 4: Send to reasoning server ──
      updateReasoningStage('Thinking', 'Reasoning request sent');

      const payload = {
        task,
        url: tab.url,
        title: tab.title,
        dom: sanitizedDom,
        sanitized_dom: sanitizedDom,
        redaction_summary: {
          total_redacted: piiResult.count || 0,
          tokens: piiResult.tokens ? piiResult.tokens.map(t => t.replacement) : [],
        }
      };

      latestPayload = payload;

      let reasonData = null;
      try {
        const res = await fetch(getReasoningUrl(), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errBody = await res.text().catch(() => '');
          throw new Error(`HTTP ${res.status}${errBody ? ': ' + errBody : ''}`);
        }

        reasonData = await res.json();
        actionPlan = reasonData.action_plan || reasonData;
        resultData.transmittedNodes = sanitizedDom.length;
        if (resultCardEl) updateResultCardCounters(resultCardEl, resultData);
        updateReasoningStage('Thinking', 'Reasoning response received');
      } catch (e) {
        resultData.transmittedNodes = 0;
        if (resultCardEl) updateResultCardCounters(resultCardEl, resultData);
        const isOffline = e.message.includes('Failed to fetch') || e.message.includes('NetworkError');
        const errLabel = isOffline ? 'Stopped · server offline' : 'Stopped · reasoning failed';
        const errDetail = isOffline ? `Reasoning server unreachable at ${getReasoningUrl()}` : e.message;
        completeReasoning(true, errLabel, errDetail);
        return;
      }

      // Show LLM response text
      if (actionPlan && actionPlan.thought) {
        addMessage(session, { type: 'agent', text: actionPlan.thought });
      }

      // ── STEP 5: Action Execution via Content Script Firewall ──
      let actionsExecuted = 0;
      const actionsList = (actionPlan && actionPlan.actions) ? actionPlan.actions : [];

      if (actionsList.length > 0) {
        updateReasoningStage('Taking action', 'Action execution started');

        for (const action of actionsList) {
          try {
            const execResult = await sendTabMessage(tab.id, {
              action: 'EXECUTE_ACTION',
              browserAction: action,
            });

            if (execResult && execResult.success) {
              actionsExecuted++;
              resultData.actions = actionsExecuted;
              if (resultCardEl) updateResultCardCounters(resultCardEl, resultData);
              saveSessions();
              updateReasoningStage('Taking action', `${action.action} on #${action.node_id ?? 'N/A'}`);
            } else {
              completeReasoning(true, 'Stopped · action blocked', execResult?.detail || 'Firewall rejection');
              resultCardEl = addMessage(session, { type: 'result', data: resultData });
              saveSessions();
              return;
            }
          } catch (e) {
            completeReasoning(true, 'Stopped · action blocked', e.message || 'Action error');
            resultCardEl = addMessage(session, { type: 'result', data: resultData });
            saveSessions();
            return;
          }
        }
      }

      // ── STEP 6: Complete reasoning block & Show Task Summary at end ──
      const stepLabel = actionsExecuted === 1 ? '1 step' : `${actionsExecuted} steps`;
      const fieldLabel = (piiResult?.count || 0) === 1 ? '1 field protected' : `${piiResult?.count || 0} fields protected`;
      completeReasoning(false, `Done · ${stepLabel} · ${fieldLabel}`, 'Pipeline completed');

      // Append Task Summary card at the end of the task
      resultCardEl = addMessage(session, {
        type: 'result',
        data: resultData
      });
      saveSessions();

      showStatusStrip(`Done · ${stepLabel} · ${fieldLabel}`);

    } catch (err) {
      console.error('[WebVeil Sidepanel] Pipeline error:', err);
      completeReasoning(true, 'Stopped · couldn\'t read this page', err.message);
      addMessage(session, { type: 'agent', text: `Stopped · couldn't read this page: ${err.message}` });
    } finally {
      isRunning = false;
      sendBtn.disabled = !taskInput.value.trim();
    }
  }

  // ═══════════════════════════════════════════════════════════
  // CHROME MESSAGING & PROGRAMMATIC INJECTION HELPERS
  // ═══════════════════════════════════════════════════════════
  function getActiveTab() {
    return new Promise((resolve) => {
      try {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          resolve(tabs && tabs.length > 0 ? tabs[0] : null);
        });
      } catch (_) {
        resolve(null);
      }
    });
  }

  async function ensureContentScriptInjected(tab) {
    if (!tab || !tab.id) {
      throw new Error('No active browser tab found.');
    }

    const url = tab.url || '';
    const restrictedPrefixes = ['chrome://', 'chrome-extension://', 'edge://', 'about:', 'chrome-search://', 'devtools://'];
    for (const prefix of restrictedPrefixes) {
      if (url.startsWith(prefix)) {
        const protocol = url.split(':')[0] || 'browser';
        throw new Error(`Cannot inspect restricted browser page (${protocol}:). Please open an HTTP/HTTPS web page.`);
      }
    }

    try {
      const pingResp = await sendTabMessage(tab.id, { action: 'PING' });
      if (pingResp && pingResp.status === 'ACTIVE') {
        return true;
      }
    } catch (_) {}

    if (chrome.scripting && chrome.scripting.executeScript) {
      console.log('[WebVeil] Content script absent on tab', tab.id, '— programmatically injecting content_script.js');
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content_script.js']
        });
        await new Promise(r => setTimeout(r, 120));
        const retryPing = await sendTabMessage(tab.id, { action: 'PING' });
        if (retryPing && retryPing.status === 'ACTIVE') {
          return true;
        }
      } catch (injErr) {
        console.warn('[WebVeil] Auto-injection failed:', injErr);
        const detail = chrome.runtime?.lastError?.message || injErr.message;
        throw new Error(`Content script auto-injection failed (${detail}). Please reload the tab.`);
      }
    }

    throw new Error('Could not establish connection to content script. Please reload the tab.');
  }

  function sendTabMessage(tabId, message) {
    return new Promise((resolve, reject) => {
      try {
        chrome.tabs.sendMessage(tabId, message, (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else if (response) {
            resolve(response);
          } else {
            reject(new Error('No response from content script'));
          }
        });
      } catch (e) {
        reject(e);
      }
    });
  }

  // ═══════════════════════════════════════════════════════════
  // UI HELPERS
  // ═══════════════════════════════════════════════════════════
  function showStatusStrip(text) {
    statusStripText.textContent = text;
    statusStrip.style.display = '';
  }

  function scrollToBottom() {
    requestAnimationFrame(() => {
      messagesArea.scrollTop = messagesArea.scrollHeight;
    });
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function formatTime(ts) {
    const d = new Date(ts);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }

  // ═══════════════════════════════════════════════════════════
  // EVENT HANDLERS
  // ═══════════════════════════════════════════════════════════

  newTaskBtn.addEventListener('click', () => {
    const session = createSession();
    showConversation(session.id);
  });

  backBtn.addEventListener('click', showLanding);

  if (historyBtn) {
    historyBtn.addEventListener('click', showLanding);
  }

  if (convFolderBtn) {
    convFolderBtn.addEventListener('click', showLanding);
  }

  if (landingSettingsBtn) {
    landingSettingsBtn.addEventListener('click', showSettings);
  }

  if (convSettingsBtn) {
    convSettingsBtn.addEventListener('click', showSettings);
  }

  if (settingsBackBtn) {
    settingsBackBtn.addEventListener('click', () => {
      if (previousView === 'conversation' && activeSessionId) {
        showConversation(activeSessionId);
      } else {
        showLanding();
      }
    });
  }

  if (settingsServerUrl) {
    settingsServerUrl.addEventListener('input', () => {
      const val = settingsServerUrl.value.trim();
      if (val) {
        serverBaseUrl = val;
        try {
          if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.set({ webveil_server_url: serverBaseUrl });
          } else {
            localStorage.setItem('webveil_server_url', serverBaseUrl);
          }
        } catch (_) {}
        checkServerHealth();
      }
    });
  }

  if (runSecurityVerificationBtn) {
    runSecurityVerificationBtn.addEventListener('click', () => {
      try {
        if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.create) {
          chrome.tabs.create({ url: chrome.runtime.getURL('attack_demo.html') });
        } else {
          window.open('attack_demo.html', '_blank');
        }
      } catch (_) {
        window.open('attack_demo.html', '_blank');
      }
    });
  }

  newSessionBtn.addEventListener('click', () => {
    const session = createSession();
    showConversation(session.id);
  });

  sendBtn.addEventListener('click', () => {
    const text = taskInput.value.trim();
    if (!text || isRunning) return;

    const session = sessions.find(s => s.id === activeSessionId);
    if (!session) return;

    taskInput.value = '';
    sendBtn.disabled = true;
    runAgentPipeline(session, text);
  });

  taskInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendBtn.click();
    }
  });

  taskInput.addEventListener('input', () => {
    sendBtn.disabled = !taskInput.value.trim() || isRunning;
    taskInput.style.height = '36px';
    taskInput.style.height = Math.min(taskInput.scrollHeight, 100) + 'px';
  });

  document.querySelectorAll('.wv-suggestion-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const task = pill.getAttribute('data-task');
      if (!task || isRunning) return;

      const session = sessions.find(s => s.id === activeSessionId);
      if (!session) return;

      runAgentPipeline(session, task);
    });
  });

  statusStripDismiss.addEventListener('click', () => {
    statusStrip.style.display = 'none';
  });

  modalCloseBtn.addEventListener('click', () => {
    payloadModal.classList.remove('visible');
  });

  payloadModal.addEventListener('click', (e) => {
    if (e.target === payloadModal) {
      payloadModal.classList.remove('visible');
    }
  });

  // ═══════════════════════════════════════════════════════════
  // INIT
  // ═══════════════════════════════════════════════════════════
  loadSessions(() => {
    renderSessionList();
    showLanding();
  });
});
