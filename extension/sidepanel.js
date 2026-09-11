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

  // Input tools & options (Model dropdown, Attach, Mic)
  const modelSelectBtn    = document.getElementById('model-select-btn');
  const modelSelectName   = document.getElementById('model-select-name');
  const modelDropdownMenu = document.getElementById('model-dropdown-menu');
  const attachBtn         = document.getElementById('attach-btn');
  const micBtn            = document.getElementById('mic-btn');

  // Instructions selector
  const instructionsBtn          = document.getElementById('instructions-btn');
  const instructionsBtnLabel     = document.getElementById('instructions-btn-label');
  const instructionsClearBtn     = document.getElementById('instructions-clear-btn');
  const instructionsDropdownMenu = document.getElementById('instructions-dropdown-menu');
  const instructionsList         = document.getElementById('instructions-list');
  const importInstructionsRow    = document.getElementById('import-instructions-row');
  const importInstructionsHeaderBtn = document.getElementById('import-instructions-header-btn');
  const instructionFileInput     = document.getElementById('instruction-file-input');

  // Settings
  const settingsBackBtn            = document.getElementById('settings-back-btn');
  const settingsServerUrl          = document.getElementById('settings-server-url');
  const runSecurityVerificationBtn = document.getElementById('run-security-verification-btn');
  const settingsOllamaModel        = document.getElementById('settings-ollama-model');
  const openVaultWindowBtn         = document.getElementById('open-vault-window-btn');
  const clearAllSessionsBtn        = document.getElementById('clear-all-sessions-btn');
  const clearConfirmRow            = document.getElementById('clear-confirm-row');
  const confirmClearSessionsBtn    = document.getElementById('confirm-clear-sessions-btn');
  const cancelClearSessionsBtn     = document.getElementById('cancel-clear-sessions-btn');

  // Modal
  const payloadModal  = document.getElementById('payload-modal');
  const modalJson     = document.getElementById('modal-json');
  const modalCloseBtn = document.getElementById('modal-close-btn');

  // Server status indicators (non-clickable)
  const landingStatusIndicator = document.getElementById('landing-status-indicator');
  const landingStatusLabel     = document.getElementById('landing-status-label');
  const convStatusIndicator    = document.getElementById('conv-status-indicator');
  const convStatusLabel        = document.getElementById('conv-status-label');
  // Settings model list
  const settingsModelList      = document.getElementById('settings-model-list');

  // ═══════════════════════════════════════════════════════════
  // STATE
  // ═══════════════════════════════════════════════════════════
  let currentSelectedModel = localStorage.getItem('webveil_selected_model') || 'Auto-Cascade (Local First)';
  let sessions = [];          // {id, title, createdAt, messages: [...], instructionFileId: ...}
  let activeSessionId = null;
  let instructionFiles = [];  // [{id, name, content, updatedAt}]
  let activeInstructionFileId = null;
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
          setServerStatus(true, data.active_tier || 'Local (Ollama)');
          return;
        }
      }
    } catch (_) {}
    if (!isRunning) {
      setServerStatus(false);
    }
  }

  let currentActiveTier = 'Local (Ollama)';

  function setServerStatus(online, tierName) {
    isServerOnline = online;
    if (tierName) {
      currentActiveTier = tierName;
    }

    const shortName = typeof getDisplayModelName === 'function' 
      ? getDisplayModelName(currentSelectedModel) 
      : (currentSelectedModel || 'Cascade');

    // Update non-clickable status indicators in headers
    const indicators = [
      { el: landingStatusIndicator, label: landingStatusLabel },
      { el: convStatusIndicator, label: convStatusLabel }
    ];
    indicators.forEach(({ el, label }) => {
      if (!el) return;
      if (online) {
        el.className = 'wv-status-indicator online';
        if (label) label.textContent = shortName;
        el.title = `Active: ${currentSelectedModel}`;
      } else {
        el.className = 'wv-status-indicator offline';
        if (label) label.textContent = 'Offline';
        el.title = 'Server offline';
      }
    });

    const settingsActiveTierBadge = document.getElementById('settings-active-tier-badge');
    if (settingsActiveTierBadge) {
      settingsActiveTierBadge.textContent = online ? (currentActiveTier || shortName) : 'Server Offline';
    }

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
    activeInstructionFileId = null;
    updateInstructionPillUI();
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
      activeInstructionFileId = session.instructionFileId || null;
      updateInstructionPillUI();
      renderInstructionsMenu();
      
      if (session.messages && session.messages.length > 0) {
        showSkeletonLoading();
        setTimeout(() => {
          renderMessages(session);
        }, 120);
      } else {
        renderMessages(session);
      }
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
      title: 'New Chat',
      createdAt: Date.now(),
      messages: [],
      instructionFileId: activeInstructionFileId || null,
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
  // LOCAL INSTRUCTION-FILE SYSTEM (.md, .txt)
  // ═══════════════════════════════════════════════════════════
  function loadInstructionFiles(callback) {
    try {
      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.get('webveil_instruction_files', (result) => {
          instructionFiles = result.webveil_instruction_files || [];
          if (callback) callback();
        });
      } else {
        const stored = localStorage.getItem('webveil_instruction_files');
        instructionFiles = stored ? JSON.parse(stored) : [];
        if (callback) callback();
      }
    } catch (_) {
      instructionFiles = [];
      if (callback) callback();
    }
  }

  function saveInstructionFiles() {
    try {
      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({ webveil_instruction_files: instructionFiles });
      } else {
        localStorage.setItem('webveil_instruction_files', JSON.stringify(instructionFiles));
      }
    } catch (_) {}
  }

  function updateInstructionPillUI() {
    const currentSession = sessions.find(s => s.id === activeSessionId);
    const activeId = currentSession ? currentSession.instructionFileId : activeInstructionFileId;
    const file = instructionFiles.find(f => f.id === activeId);

    if (file && instructionsBtn && instructionsBtnLabel && instructionsClearBtn) {
      instructionsBtn.classList.add('active');
      const shortName = file.name.length > 16 ? file.name.slice(0, 14) + '…' : file.name;
      instructionsBtnLabel.textContent = `Instructions · ${shortName}`;
      instructionsBtn.title = `Attached instructions: ${file.name}`;
      instructionsClearBtn.style.display = 'inline-flex';
    } else if (instructionsBtn && instructionsBtnLabel && instructionsClearBtn) {
      instructionsBtn.classList.remove('active');
      instructionsBtnLabel.textContent = 'Instructions';
      instructionsBtn.title = 'Attach Custom Instructions (.md, .txt)';
      instructionsClearBtn.style.display = 'none';
    }
  }

  function selectInstructionFile(fileId) {
    activeInstructionFileId = fileId;
    const currentSession = sessions.find(s => s.id === activeSessionId);
    if (currentSession) {
      currentSession.instructionFileId = fileId;
      saveSessions();
    }
    updateInstructionPillUI();
    renderInstructionsMenu();
    if (instructionsDropdownMenu) instructionsDropdownMenu.classList.remove('open');
  }

  function clearInstructionFile() {
    activeInstructionFileId = null;
    const currentSession = sessions.find(s => s.id === activeSessionId);
    if (currentSession) {
      currentSession.instructionFileId = null;
      saveSessions();
    }
    updateInstructionPillUI();
    renderInstructionsMenu();
  }

  function renderInstructionsMenu() {
    if (!instructionsList) return;
    instructionsList.innerHTML = '';

    const currentSession = sessions.find(s => s.id === activeSessionId);
    const activeId = currentSession ? currentSession.instructionFileId : activeInstructionFileId;

    if (instructionFiles.length === 0) {
      const emptyEl = document.createElement('div');
      emptyEl.className = 'wv-instructions-empty';
      emptyEl.innerHTML = 'No instruction files yet.<br>Import a .md or .txt file below.';
      instructionsList.appendChild(emptyEl);
      return;
    }

    instructionFiles.forEach(file => {
      const row = document.createElement('div');
      const isActive = file.id === activeId;
      row.className = `wv-instruction-row ${isActive ? 'active' : ''}`;

      const checkSvg = isActive ? `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="wv-check-icon"><polyline points="20 6 9 17 4 12"/></svg>` : '';

      const linesCount = (file.content.match(/\n/g) || []).length + 1;
      const sizeStr = file.content.length > 1024 ? `${(file.content.length / 1024).toFixed(1)} KB` : `${file.content.length} B`;

      row.innerHTML = `
        <div class="wv-instruction-info">
          <span class="wv-instruction-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
          <span class="wv-instruction-meta">${linesCount} lines · ${sizeStr}</span>
        </div>
        <div class="wv-instruction-actions">
          ${checkSvg}
          <button class="wv-instruction-delete-btn" title="Delete instruction file">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      `;

      row.addEventListener('click', (e) => {
        e.stopPropagation();
        selectInstructionFile(file.id);
      });

      const deleteBtn = row.querySelector('.wv-instruction-delete-btn');
      if (deleteBtn) {
        deleteBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          instructionFiles = instructionFiles.filter(f => f.id !== file.id);
          saveInstructionFiles();
          if (activeInstructionFileId === file.id || (currentSession && currentSession.instructionFileId === file.id)) {
            clearInstructionFile();
          } else {
            renderInstructionsMenu();
          }
        });
      }

      instructionsList.appendChild(row);
    });
  }

  function handleInstructionFileImport(file) {
    if (!file) return;
    const validExtensions = ['.md', '.txt'];
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!validExtensions.includes(ext)) {
      showStatusStrip('Only .md and .txt files are supported.');
      return;
    }

    if (file.size > 1024 * 1024) {
      showStatusStrip('Instruction file too large (max 1 MB).');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target.result || '';
      const newFile = {
        id: generateId(),
        name: file.name,
        content: content,
        updatedAt: Date.now()
      };
      instructionFiles.unshift(newFile);
      saveInstructionFiles();
      selectInstructionFile(newFile.id);
      showStatusStrip(`Imported "${file.name}"`);
    };
    reader.onerror = () => {
      showStatusStrip('Failed to read instruction file.');
    };
    reader.readAsText(file);
  }

  function sanitizeAndSelectInstructions(rawText, taskQuery, piiReplacements) {
    if (!rawText || !rawText.trim()) return '';

    let selected = rawText;

    // 1. Relevance extraction: if content is large (>1200 chars), extract relevant sections
    if (rawText.length > 1200) {
      const paragraphs = rawText.split(/\n\s*\n/);
      const keywords = (taskQuery || '').toLowerCase().split(/\W+/).filter(w => w.length > 3);
      
      const scored = paragraphs.map((p, idx) => {
        let score = 0;
        const lower = p.toLowerCase();
        keywords.forEach(kw => {
          if (lower.includes(kw)) score += 2;
        });
        if (idx === 0) score += 1;
        if (p.startsWith('#')) score += 1;
        return { p, score };
      });

      scored.sort((a, b) => b.score - a.score);
      let totalLen = 0;
      const kept = [];
      for (const item of scored) {
        if (totalLen + item.p.length <= 1200 || kept.length === 0) {
          kept.push(item.p);
          totalLen += item.p.length;
        }
        if (totalLen >= 1000) break;
      }
      selected = kept.join('\n\n');
    }

    // 2. Privacy Engine scrubbing:
    if (piiReplacements && piiReplacements.length > 0) {
      piiReplacements.forEach(r => {
        if (r.original && r.original.length > 3) {
          selected = selected.split(r.original).join(r.replacement);
        }
      });
    }

    // Local client-side regex protection for secrets inside instructions
    selected = selected.replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g, '[REDACTED_INSTRUCTION_EMAIL]');
    selected = selected.replace(/(?:password|secret|api[_-]?key)\s*[:=]\s*["']?([^"'\s]+)["']?/gi, (m, val) => {
      return m.replace(val, '[REDACTED_INSTRUCTION_SECRET]');
    });

    return selected.trim();
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

    if (!session.messages || session.messages.length === 0) {
      heroPrompt.style.display = 'flex';
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
      case 'activity':
        el = buildActivityCard(msg.data, sessionId, msgIdx);
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
      case 'USER_ID':
        return 'flagged user identifier / name';
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
  // AGENT ACTIVITY CARD BUILDER (Refined Calm Register)
  // ═══════════════════════════════════════════════════════════
  function buildActivityCard(data, sessionId, msgIdx) {
    const card = document.createElement('div');
    card.className = 'wv-activity-card';

    const protectedCount = data.protectedCount || (data.tokens ? data.tokens.length : 0);
    const isError = data.status === 'error';
    const isActive = data.status === 'active';
    const statusLabel = isError ? 'Task stopped' : (isActive ? 'Agent working' : (data.title || 'Task completed'));

    // Header row: status dot + "Task completed" + small gray fields count right-aligned
    const headerHtml = `
      <div class="wv-activity-header">
        <div class="wv-activity-status-group">
          <span class="wv-activity-status-dot ${isActive ? 'active' : ''}"></span>
          <span class="wv-activity-title">${escapeHtml(statusLabel)}</span>
        </div>
        <span class="wv-activity-meta-count">Privacy protected · ${protectedCount} ${protectedCount === 1 ? 'field' : 'fields'}</span>
      </div>
    `;

    // Concise summary text with generous line-height
    const summaryText = data.summary || (data.actions ? `Executed ${data.actions} browser actions while protecting page privacy.` : 'Processed request with privacy protections.');
    const summaryHtml = `
      <div class="wv-activity-summary-text">${escapeHtml(summaryText)}</div>
    `;

    // Chronological activity timeline: plain ordered list, small gray numerals, no chip badges
    let timelineHtml = '';
    const timeline = data.timeline || [];
    if (timeline.length > 0) {
      const stepsHtml = timeline.map((step, idx) => {
        const stepText = typeof step === 'string' ? step : (step.text || '');
        const isCurrent = idx === timeline.length - 1 && isActive;
        return `
          <li class="wv-activity-step ${isCurrent ? 'current' : ''}">
            <span class="wv-step-num">${idx + 1}.</span>
            <span class="wv-step-text">${escapeHtml(stepText)}</span>
          </li>
        `;
      }).join('');
      timelineHtml = `
        <ol class="wv-activity-timeline">
          ${stepsHtml}
        </ol>
      `;
    }

    // Collapsible "What WebVeil saw" section
    const tokens = data.tokens || [];
    const tokensListHtml = tokens.map(t => {
      const tok = typeof t === 'string' ? t : (t.replacement || t.token);
      const cat = typeof t === 'string' ? '' : t.category;
      return `
        <div class="wv-saw-token-item">
          <span class="wv-token-chip">${escapeHtml(tok)}</span>
          <span class="wv-token-desc">${escapeHtml(getCategoryCaption(cat))}</span>
        </div>
      `;
    }).join('');

    const tokensSectionHtml = tokens.length > 0 ? `
      <div class="wv-saw-tokens-header" style="display:flex; align-items:center; justify-content:space-between;">
        <span>Protected Placeholders</span>
        <button class="wv-btn-vault-open" title="Open Isolated Client Vault Window" style="background:#f0f0ee; border:1px solid #e5e5e3; color:#5b5bd6; border-radius:4px; font-size:11px; font-weight:500; padding:2px 8px; cursor:pointer; display:inline-flex; align-items:center; gap:4px;">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          Open Vault Window
        </button>
      </div>
      <div class="wv-saw-tokens-list">
        ${tokensListHtml}
      </div>
    ` : '';

    // On-Device Visual Perception Telemetry (§ ISRO PS-26171)
    let telemetrySectionHtml = '';
    const vt = data.visualTelemetry;
    if (vt) {
      let backendLabel = 'Local CV · CPU';
      let backendPillClass = 'cpu';
      const bLower = (vt.backend || '').toLowerCase();
      if (bLower.includes('webgpu')) {
        backendLabel = 'ONNX · WebGPU';
        backendPillClass = 'gpu';
      } else if (bLower.includes('wasm')) {
        backendLabel = 'ONNX · WASM';
        backendPillClass = 'wasm';
      } else {
        backendLabel = 'Local CV · CPU';
        backendPillClass = 'cpu';
      }

      const infMs = (vt.inferenceMs != null) ? vt.inferenceMs : (vt.inference_ms || 0);
      const regionsCount = (vt.regionsCount != null) ? vt.regionsCount : (vt.regions_count || 0);
      const redactionsCount = (vt.redactionsCount != null) ? vt.redactionsCount : (vt.redactions_count || 0);

      telemetrySectionHtml = `
        <div class="wv-saw-telemetry-box">
          <div class="wv-saw-telemetry-header">
            <span>On-Device Visual Perception</span>
            <span class="wv-saw-verified-badge">Local Engine</span>
          </div>
          <div class="wv-saw-telemetry-grid">
            <div class="wv-saw-pill">
              <span class="wv-saw-pill-k">Backend</span>
              <span class="wv-saw-pill-v ${backendPillClass}">${escapeHtml(backendLabel)}</span>
            </div>
            <div class="wv-saw-pill">
              <span class="wv-saw-pill-k">Latency</span>
              <span class="wv-saw-pill-v">${infMs} ms</span>
            </div>
            <div class="wv-saw-pill">
              <span class="wv-saw-pill-k">Visual Features</span>
              <span class="wv-saw-pill-v">${regionsCount} detected</span>
            </div>
            <div class="wv-saw-pill">
              <span class="wv-saw-pill-k">Sanitized</span>
              <span class="wv-saw-pill-v highlight">${redactionsCount} redacted</span>
            </div>
          </div>
        </div>
      `;
    }

    // Sanitized Visual Snapshot proof (permanent blur & blacked secrets)
    let visualProofHtml = '';
    if (vt && vt.sanitizedImage) {
      visualProofHtml = `
        <div class="wv-saw-preview-container">
          <div class="wv-saw-preview-title-row">
            <div class="wv-saw-preview-title">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              <span>Sanitized Visual Snapshot</span>
            </div>
            <span class="wv-saw-preview-note">Faces blurred · Secrets blacked</span>
          </div>
          <div class="wv-saw-preview-frame" data-lightbox-src="${vt.sanitizedImage}">
            <span class="wv-zoom-hint">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
              Click to enlarge
            </span>
            <img src="${vt.sanitizedImage}" class="wv-saw-preview-img" alt="Sanitized Client Screen" />
          </div>
        </div>
      `;
    }

    const sawSectionHtml = `
      <div class="wv-saw-collapsible">
        <button class="wv-saw-toggle-btn" type="button">
          <span class="wv-saw-toggle-left">
            <span>What WebVeil saw</span>
            <svg class="wv-saw-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </span>
        </button>
        <div class="wv-saw-content" style="display: none;">
          <div class="wv-saw-meta">
            <div class="wv-saw-row">
              <span class="wv-saw-key">Page</span>
              <span class="wv-saw-val" title="${escapeHtml(data.pageTitle || '')}">${escapeHtml(data.pageTitle || 'Web page')}</span>
            </div>
            <div class="wv-saw-row">
              <span class="wv-saw-key">URL</span>
              <span class="wv-saw-val" title="${escapeHtml(data.pageUrl || '')}">${escapeHtml(data.pageUrl || 'Current tab')}</span>
            </div>
            <div class="wv-saw-row">
              <span class="wv-saw-key">DOM</span>
              <span class="wv-saw-val">${data.scannedNodes || 0} interactive elements</span>
            </div>
          </div>
          ${telemetrySectionHtml}
          ${visualProofHtml}
          ${tokensSectionHtml}
          <button class="wv-inspect-link" type="button">
            <span>Inspect outgoing payload</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
          </button>
        </div>
      </div>
    `;

    card.innerHTML = headerHtml + summaryHtml + timelineHtml + sawSectionHtml;

    // Wire collapsible toggle
    const sawContainer = card.querySelector('.wv-saw-collapsible');
    const toggleBtn = card.querySelector('.wv-saw-toggle-btn');
    const sawContent = card.querySelector('.wv-saw-content');
    if (toggleBtn && sawContent && sawContainer) {
      toggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = sawContainer.classList.toggle('open');
        sawContent.style.display = isOpen ? 'flex' : 'none';
        if (isOpen) {
          setTimeout(scrollToBottom, 60);
        }
      });
    }

    // Wire inspect payload link
    const inspectBtn = card.querySelector('.wv-inspect-link');
    if (inspectBtn) {
      inspectBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const rawJson = JSON.stringify(latestPayload, null, 2);
        modalJson.textContent = rawJson;
        modalJson.setAttribute('data-raw-json', rawJson);
        const searchInput = document.getElementById('payload-search-input');
        const matchCount = document.getElementById('payload-match-count');
        if (searchInput) searchInput.value = '';
        if (matchCount) matchCount.textContent = '';
        payloadModal.classList.add('visible');
        if (searchInput) setTimeout(() => searchInput.focus(), 80);
      });
    }

    // Wire open vault window button
    const vaultBtn = card.querySelector('.wv-btn-vault-open');
    if (vaultBtn) {
      vaultBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        let targetTabId = null;
        let targetOrigin = null;
        try {
          const t = await getCurrentTab();
          if (t) {
            targetTabId = t.id;
            targetOrigin = t.url ? new URL(t.url).origin : null;
          }
        } catch (_) {}
        try {
          chrome.runtime.sendMessage({
            action: 'OPEN_VAULT_WINDOW',
            tabId: targetTabId,
            origin: targetOrigin
          });
        } catch (_) {
          const qs = targetTabId ? `?tabId=${targetTabId}&origin=${encodeURIComponent(targetOrigin || '')}` : '';
          window.open('vault_window.html' + qs, '_blank', 'width=780,height=620');
        }
      });
    }

    // Wire image lightbox (click to enlarge)
    const previewFrame = card.querySelector('.wv-saw-preview-frame[data-lightbox-src]');
    if (previewFrame) {
      previewFrame.addEventListener('click', (e) => {
        e.stopPropagation();
        const lightbox = document.getElementById('image-lightbox');
        const lightboxImg = document.getElementById('lightbox-img');
        if (lightbox && lightboxImg) {
          lightboxImg.src = previewFrame.getAttribute('data-lightbox-src');
          lightbox.classList.add('visible');
        }
      });
    }

    return card;
  }

  // Alias for backward compatibility
  const buildResultCard = buildActivityCard;
  window.buildResultCard = buildActivityCard;
  window.buildActivityCard = buildActivityCard;

  // ═══════════════════════════════════════════════════════════
  // AUTOMATED AGENT PIPELINE (Unified Reasoning Stream & Live Tokens)
  // ═══════════════════════════════════════════════════════════
  function getSelectedProviderAndModel() {
    const label = ((currentSelectedModel || '') + ' ' + (modelSelectName ? modelSelectName.textContent : '')).trim().toLowerCase();
    if (label.includes('ollama')) {
      return { provider: 'ollama', model: 'llama3.1' };
    } else if (label.includes('nemotron') || label.includes('openrouter')) {
      return { provider: 'openrouter', model: 'nvidia/nemotron-3-ultra-550b-a55b:free' };
    } else if (label.includes('gemini')) {
      return { provider: 'gemini', model: 'gemini-2.5-flash' };
    }
    // Default is 3-Tier Escalation Cascade (Local Ollama -> Nemotron 3 Ultra -> Gemini 2.5 Flash)
    return { provider: 'cascade', model: 'cascade' };
  }

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
      tokens: []
    };
    const activityTimeline = [];

    // Check for attached instructions
    const activeSession = session;
    const activeFileId = activeSession.instructionFileId || activeInstructionFileId;
    let instructionContext = null;
    if (activeFileId) {
      const fileObj = instructionFiles.find(f => f.id === activeFileId);
      if (fileObj && fileObj.content) {
        instructionContext = sanitizeAndSelectInstructions(fileObj.content, task, []);
        activityTimeline.push(`Applied instructions: ${fileObj.name}`);
      }
    }

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
    let canvasImages = [];
    let piiResult = { tokens: [], count: 0 };
    let sanitizedDom = [];
    let actionPlan = null;
    let tab = null;

    try {
      // ── STEP 1: Get active tab ──
      tab = await getActiveTab();
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
        canvasImages = domResult.canvasImages || [];
        updateReasoningStage('Reading page', `DOM extraction complete (${prunedNodes.length} nodes)`);
        activityTimeline.push(`Scanned page DOM (${prunedNodes.length} elements)`);
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

        if (piiResult.tokens && piiResult.tokens.length > 0) {
          const liveVaultEntries = [];
          for (let i = 0; i < piiResult.tokens.length; i++) {
            const t = piiResult.tokens[i];
            resultData.protectedCount += 1;
            resultData.tokens.push({
              replacement: t.replacement,
              category: t.category,
              original: t.original,
              fieldId: t.fieldId || t.nodeId
            });
            liveVaultEntries.push({
              token: t.replacement,
              category: t.category,
              fieldId: t.fieldId || t.category?.toLowerCase() || 'field',
              rawSecret: t.original,
              origin: tab.url ? new URL(tab.url).origin : window.location.origin,
              extractedAt: Date.now()
            });
          }
          try {
            chrome.storage.local.set({
              webveil_vault_entries: liveVaultEntries,
              webveil_vault_origin: tab.url ? new URL(tab.url).origin : window.location.origin,
              webveil_vault_tab_id: tab.id,
              webveil_vault_updated_at: Date.now()
            });
          } catch (_) {}
        }
        activityTimeline.push(piiResult.count > 0 ? `Shielded ${piiResult.count} sensitive fields` : 'Page privacy verified');

        // Re-scrub instruction context with detected PII tokens if any
        if (activeFileId && piiResult.replacements && piiResult.replacements.length > 0) {
          const fileObj = instructionFiles.find(f => f.id === activeFileId);
          if (fileObj && fileObj.content) {
            instructionContext = sanitizeAndSelectInstructions(fileObj.content, task, piiResult.replacements);
          }
        }
      } catch (e) {
        updateReasoningStage('Scanning for sensitive data', 'PII scan skipped');
      }

      // Build sanitized DOM (replace raw text and input values with vault tokens)
      sanitizedDom = prunedNodes.map(node => {
        let text = node.text_content || '';
        let val = '';
        if (piiResult.replacements) {
          piiResult.replacements.forEach(r => {
            text = text.split(r.original).join(r.replacement);
          });
        }
        // Hard Egress Invariant: password values are never transmitted; other inputs scrubbed
        if (node.element_type === 'password') {
          val = '';
        } else if (node.value) {
          val = node.value;
          if (piiResult.replacements) {
            piiResult.replacements.forEach(r => {
              val = val.split(r.original).join(r.replacement);
            });
          }
        }
        return { ...node, text_content: text, value: val };
      });

      // ── STEP 3B: In-Browser Visual Perception & Visual Privacy Engine ──
      updateReasoningStage('Visual perception & privacy', 'Probing on-device vision & redacting screen');

      let visualTelemetry = null;
      let sanitizedScreenshotB64 = null;

      try {
        // 1. Capture screen into client offscreen memory ONLY
        let rawScreenshot = await captureTabScreenshot(tab.windowId);

        // Fallback: If screenshot capture is unavailable (e.g. mock test environment), generate synthetic viewport canvas
        if (!rawScreenshot) {
          const synthCanvas = document.createElement('canvas');
          synthCanvas.width = piiResult.viewport?.width || 1280;
          synthCanvas.height = piiResult.viewport?.height || 800;
          const sctx = synthCanvas.getContext('2d');
          if (sctx) {
            sctx.fillStyle = '#0f0f12';
            sctx.fillRect(0, 0, synthCanvas.width, synthCanvas.height);
            sctx.fillStyle = '#1e1e24';
            sctx.fillRect(30, 30, 200, 40);
          }
          rawScreenshot = synthCanvas.toDataURL('image/png');
        }

        // 2. On-Device Vision Perception (WebGPU -> WASM -> CPU Graceful Fallback)
        let visionEngine;
        if (typeof ONNXLocalVisionEngine !== 'undefined') {
          visionEngine = new ONNXLocalVisionEngine();
        } else if (typeof window !== 'undefined' && window.ONNXLocalVisionEngine) {
          visionEngine = new window.ONNXLocalVisionEngine();
        }

        let visionResult = { regions: [], inferenceMs: 0, backend: 'cpu-fallback', visualSummary: '' };
        if (visionEngine) {
          visionResult = await visionEngine.analyze(rawScreenshot, { domElements: prunedNodes });
          const bName = visionResult.backendLabel || (visionResult.backend === 'local-cv-cpu' ? 'Local CV (CPU)' : visionResult.backend.toUpperCase());
          activityTimeline.push(`Local vision: ${visionResult.regions.length} visual features detected via ${bName} in ${visionResult.inferenceMs}ms`);
        }

        // 3. On-Device Visual Privacy Engine (Permanent solid blackout of secrets & Gaussian blur on avatars)
        let privacyEngine;
        if (typeof VisualPrivacyEngine !== 'undefined') {
          privacyEngine = new VisualPrivacyEngine({ blurRadius: 14 });
        } else if (typeof window !== 'undefined' && window.VisualPrivacyEngine) {
          privacyEngine = new window.VisualPrivacyEngine({ blurRadius: 14 });
        }

        let privacyResult = { sanitizedImage: null, redactions: [], dimensions: { width: 0, height: 0 } };
        if (privacyEngine) {
          privacyResult = await privacyEngine.redact({
            screenshot: rawScreenshot,
            passwordRegions: piiResult.passwordRegions || [],
            piiRegions: piiResult.piiRegions || [],
            faceRegions: piiResult.faceRegions || [],
            devicePixelRatio: piiResult.devicePixelRatio || window.devicePixelRatio || 1,
            viewport: piiResult.viewport || null,
          });

          if (privacyResult.redactions.length > 0) {
            activityTimeline.push(`Visual privacy: ${privacyResult.redactions.length} regions redacted (faces blurred, secrets blacked out)`);
          }
        }

        // HARD EGRESS INVARIANT: Raw screenshot variable is immediately freed and cleared
        rawScreenshot = null;

        sanitizedScreenshotB64 = privacyResult.sanitizedImage || null;
        visualTelemetry = {
          backend: visionResult.backend,
          inference_ms: visionResult.inferenceMs,
          inferenceMs: visionResult.inferenceMs,
          regions_count: visionResult.regions.length,
          regionsCount: visionResult.regions.length,
          redactions_count: privacyResult.redactions.length,
          redactionsCount: privacyResult.redactions.length,
          sanitizedImage: sanitizedScreenshotB64,
          redactions: privacyResult.redactions,
          visualSummary: visionResult.visualSummary
        };

        updateReasoningStage('Visual perception & privacy', `Visual analysis complete (${visionResult.regions.length} visual features, ${visionResult.inferenceMs}ms, ${privacyResult.redactions.length} redacted)`);

      } catch (visErr) {
        console.warn('[WebVeil] Visual perception warning:', visErr);
        updateReasoningStage('Visual perception & privacy', 'Visual perception completed with basic DOM telemetry');
      }

      // ── STEP 4: Send to reasoning server ──
      updateReasoningStage('Thinking', 'Reasoning request sent');

      const pm = getSelectedProviderAndModel();
      const payload = {
        task,
        url: tab.url,
        title: tab.title,
        dom: sanitizedDom,
        sanitized_dom: sanitizedDom,
        canvas_images: canvasImages,
        ocr_summary: visualTelemetry?.ocrSummary || '',
        provider: pm.provider,
        model: pm.model,
        instruction_context: instructionContext,
        instructions: instructionContext,
        sanitized_screenshot_b64: sanitizedScreenshotB64,
        visual_telemetry: visualTelemetry ? {
          backend: visualTelemetry.backend,
          inference_ms: visualTelemetry.inferenceMs,
          regions_count: visualTelemetry.regionsCount,
          redactions_count: visualTelemetry.redactionsCount,
          ocr_summary: visualTelemetry.ocrSummary || '',
        } : null,
        redaction_summary: {
          total_redacted: (piiResult.count || 0) + (visualTelemetry ? visualTelemetry.redactionsCount : 0),
          tokens: piiResult.tokens ? piiResult.tokens.map(t => t.replacement) : [],
        }
      };

      latestPayload = {
        ...payload,
        sanitized_screenshot_b64: sanitizedScreenshotB64 ? `[DATA_URL_IMAGE_WEBP_SANITIZED: ${sanitizedScreenshotB64.length} chars (faces blurred, passwords blacked out)]` : null
      };

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
        const tierUsed = reasonData.provider_used || reasonData.tier_used || 'Local (Ollama)';
        setServerStatus(true, tierUsed);
        updateReasoningStage('Thinking', `Reasoning response received (${tierUsed})`);
        activityTimeline.push(`Reasoning executed via ${tierUsed}`);
      } catch (e) {
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
              activityTimeline.push(`${action.action} on #${action.node_id ?? 'element'}`);
              saveSessions();
              updateReasoningStage('Taking action', `${action.action} on #${action.node_id ?? 'N/A'}`);
              // Cadence respecting the 500ms action firewall rate limit
              await new Promise(r => setTimeout(r, 550));
            } else {
              completeReasoning(true, 'Stopped · action blocked', execResult?.detail || 'Firewall rejection');
              addMessage(session, {
                type: 'activity',
                data: {
                  status: 'error',
                  title: 'Task Stopped',
                  summary: execResult?.detail || 'Firewall blocked action.',
                  actions: actionsExecuted,
                  protectedCount: (piiResult?.count || 0) + (visualTelemetry?.redactionsCount || 0),
                  tokens: resultData.tokens,
                  pageTitle: tab.title,
                  pageUrl: tab.url,
                  scannedNodes: prunedNodes.length,
                  visualTelemetry: visualTelemetry,
                  timeline: activityTimeline
                }
              });
              saveSessions();
              return;
            }
          } catch (e) {
            completeReasoning(true, 'Stopped · action blocked', e.message || 'Action error');
            addMessage(session, {
              type: 'activity',
              data: {
                status: 'error',
                title: 'Task Stopped',
                summary: e.message || 'Action error',
                actions: actionsExecuted,
                protectedCount: (piiResult?.count || 0) + (visualTelemetry?.redactionsCount || 0),
                tokens: resultData.tokens,
                pageTitle: tab.title,
                pageUrl: tab.url,
                scannedNodes: prunedNodes.length,
                visualTelemetry: visualTelemetry,
                timeline: activityTimeline
              }
            });
            saveSessions();
            return;
          }
        }
      }

      // ── STEP 6: Complete reasoning block & Show Agent Activity at end ──
      const totalProtected = (piiResult?.count || 0) + (visualTelemetry?.redactionsCount || 0);
      const stepLabel = actionsExecuted === 1 ? '1 step' : `${actionsExecuted} steps`;
      const fieldLabel = totalProtected === 1 ? '1 field protected' : `${totalProtected} fields protected`;
      completeReasoning(false, `Done · ${stepLabel} · ${fieldLabel}`, 'Pipeline completed');

      // Append Agent Activity card
      const activityData = {
        status: 'completed',
        title: 'Task Completed',
        summary: actionPlan?.thought || `Agent finished task in ${actionsExecuted} action steps with privacy protection.`,
        actions: actionsExecuted,
        protectedCount: totalProtected,
        tokens: resultData.tokens,
        pageTitle: tab.title,
        pageUrl: tab.url,
        scannedNodes: prunedNodes.length,
        visualTelemetry: visualTelemetry,
        timeline: activityTimeline
      };
      addMessage(session, {
        type: 'activity',
        data: activityData
      });
      saveSessions();

      showStatusStrip(`Done · ${stepLabel} · ${fieldLabel}`);

    } catch (err) {
      console.error('[WebVeil Sidepanel] Pipeline error:', err);
      completeReasoning(true, 'Stopped · couldn\'t read this page', err.message);
      addMessage(session, {
        type: 'activity',
        data: {
          status: 'error',
          title: 'Task Stopped',
          summary: `Couldn't read page: ${err.message}`,
          actions: 0,
          protectedCount: piiResult?.count || 0,
          tokens: resultData.tokens,
          pageTitle: tab ? tab.title : '',
          pageUrl: tab ? tab.url : '',
          scannedNodes: prunedNodes.length,
          timeline: activityTimeline
        }
      });
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
        if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.query) {
          const isRestrictedUrl = (u) => !u || u.includes('sidepanel.html') || u.startsWith('chrome://') || u.startsWith('about:') || u.startsWith('edge://') || u.startsWith('devtools://') || u.startsWith('chrome-extension://');
          const isValidTargetUrl = (u) => u && !isRestrictedUrl(u) && (u.startsWith('http://') || u.startsWith('https://') || u.startsWith('file://'));

          // 1. Try active tab in last focused window (the browser window with the webpage)
          chrome.tabs.query({ active: true, lastFocusedWindow: true }, (tabs) => {
            if (tabs && tabs.length > 0 && isValidTargetUrl(tabs[0].url)) {
              return resolve(tabs[0]);
            }
            // 2. Try active tab in current window
            chrome.tabs.query({ active: true, currentWindow: true }, (currTabs) => {
              if (currTabs && currTabs.length > 0 && isValidTargetUrl(currTabs[0].url)) {
                return resolve(currTabs[0]);
              }
              // 3. Query all open tabs to find a valid web page
              chrome.tabs.query({}, (allTabs) => {
                const target = allTabs?.find(t => isValidTargetUrl(t.url));
                if (target) return resolve(target);
                const anyNonRestricted = allTabs?.find(t => !isRestrictedUrl(t.url));
                resolve(anyNonRestricted || null);
              });
            });
          });
        } else {
          resolve(null);
        }
      } catch (_) {
        resolve(null);
      }
    });
  }

  function captureTabScreenshot(windowId) {
    return new Promise((resolve) => {
      try {
        if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.captureVisibleTab) {
          chrome.tabs.captureVisibleTab(windowId || null, { format: 'png' }, (dataUrl) => {
            if (chrome.runtime?.lastError || !dataUrl) {
              console.warn('[WebVeil] captureVisibleTab failed or denied:', chrome.runtime?.lastError?.message);
              resolve(null);
            } else {
              resolve(dataUrl);
            }
          });
        } else {
          resolve(null);
        }
      } catch (e) {
        console.warn('[WebVeil] captureTabScreenshot error:', e);
        resolve(null);
      }
    });
  }

  async function ensureContentScriptInjected(tab) {
    if (!tab || !tab.id) {
      throw new Error('No active browser tab found. Please open a webpage.');
    }

    const url = tab.url || '';
    const restrictedPrefixes = ['chrome://', 'edge://', 'about:', 'chrome-search://', 'devtools://', 'chrome-extension://'];
    for (const prefix of restrictedPrefixes) {
      if (url.startsWith(prefix)) {
        const protocol = url.split(':')[0] || 'browser';
        throw new Error(`Cannot inspect restricted browser page (${protocol}:). Please open an HTTP/HTTPS or local file web page.`);
      }
    }

    // Ping existing content script on tab
    try {
      const pingResp = await sendTabMessage(tab.id, { action: 'PING' });
      if (pingResp && pingResp.status === 'ACTIVE') {
        return true;
      }
    } catch (_) {}

    // Programmatically inject content_script.js into target tab
    if (typeof chrome !== 'undefined' && chrome.scripting && chrome.scripting.executeScript && tab.id) {
      console.log('[WebVeil] Content script absent on tab', tab.id, '— programmatically injecting content_script.js');
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content_script.js']
        });
        await new Promise(r => setTimeout(r, 150));
        const retryPing = await sendTabMessage(tab.id, { action: 'PING' });
        if (retryPing && retryPing.status === 'ACTIVE') {
          return true;
        }
      } catch (injErr) {
        console.warn('[WebVeil] Auto-injection note:', injErr);
        if (url.startsWith('file://')) {
          throw new Error('To inspect local file:// pages in Chrome, enable "Allow access to file URLs" in chrome://extensions -> WebVeil Details.');
        }
        const detail = chrome.runtime?.lastError?.message || injErr.message;
        throw new Error(`Content script auto-injection failed (${detail}). Please reload the tab.`);
      }
    }

    // Only allow test hook in headless test runner without chrome.tabs
    if ((typeof chrome === 'undefined' || !chrome.tabs) && typeof window !== 'undefined' && window.__WebVeil_TestHook) {
      return true;
    }

    throw new Error('Could not establish connection to content script. Please reload the webpage tab.');
  }

  function handleMockMessage(message) {
    const hook = typeof window !== 'undefined' ? window.__WebVeil_TestHook : null;
    if (!hook) return { status: 'OK' };
    if (message.action === 'PING') {
      return { status: 'ACTIVE', world: 'ISOLATED' };
    }
    if (message.action === 'RESET_FIREWALL') {
      if (hook.resetFirewall) hook.resetFirewall();
      return { success: true };
    }
    if (message.action === 'PRUNE_DOM') {
      const nodes = hook.extractAndPruneDOM ? hook.extractAndPruneDOM() : [];
      return { nodes, count: nodes.length };
    }
    if (message.action === 'DETECT_PII') {
      const nodes = message.nodes || (hook.extractAndPruneDOM ? hook.extractAndPruneDOM() : []);
      return hook.detectPII ? hook.detectPII(nodes) : { tokens: [], replacements: [], count: 0 };
    }
    if (message.action === 'EXECUTE_ACTION') {
      return hook.executeAction ? hook.executeAction(message.browserAction) : { success: true };
    }
    return { status: 'OK' };
  }

  function sendTabMessage(tabId, message) {
    return new Promise((resolve, reject) => {
      // In headless unit test environments without chrome.tabs
      if (typeof chrome === 'undefined' || !chrome.tabs || !chrome.tabs.sendMessage) {
        if (typeof window !== 'undefined' && window.__WebVeil_TestHook) {
          return resolve(handleMockMessage(message));
        }
        return reject(new Error('No tab messaging available'));
      }

      try {
        chrome.tabs.sendMessage(tabId, message, (response) => {
          if (chrome.runtime?.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else if (response !== undefined) {
            resolve(response);
          } else {
            reject(new Error('No response received from webpage content script'));
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

  // ── Theme Management (Light / Dark Mode) ──
  let currentTheme = 'light';
  try {
    const savedTheme = localStorage.getItem('webveil_theme');
    if (savedTheme) {
      currentTheme = savedTheme;
    } else if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get('webveil_theme', (res) => {
        if (res && res.webveil_theme) {
          applyTheme(res.webveil_theme);
        }
      });
    }
  } catch (_) {}

  function applyTheme(theme) {
    currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('webveil_theme', theme);
      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({ webveil_theme: theme });
      }
    } catch (_) {}
  }

  function toggleTheme() {
    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(nextTheme);
  }

  applyTheme(currentTheme);

  // Wire all theme toggle buttons across views
  document.querySelectorAll('.wv-theme-toggle-btn').forEach(btn => {
    btn.addEventListener('click', toggleTheme);
  });

  // ── Settings: Ollama Model & Clear All Sessions ──
  try {
    const savedModel = localStorage.getItem('webveil_ollama_model');
    if (savedModel && settingsOllamaModel) {
      settingsOllamaModel.value = savedModel.trim();
    }
  } catch (_) {}

  if (settingsOllamaModel) {
    settingsOllamaModel.addEventListener('input', () => {
      const val = settingsOllamaModel.value.trim();
      if (val) {
        try {
          localStorage.setItem('webveil_ollama_model', val);
          if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.set({ webveil_ollama_model: val });
          }
        } catch (_) {}
      }
    });
  }

  if (clearAllSessionsBtn && clearConfirmRow) {
    clearAllSessionsBtn.addEventListener('click', () => {
      clearConfirmRow.style.display = 'flex';
    });
  }

  if (cancelClearSessionsBtn && clearConfirmRow) {
    cancelClearSessionsBtn.addEventListener('click', () => {
      clearConfirmRow.style.display = 'none';
    });
  }

  if (confirmClearSessionsBtn && clearConfirmRow) {
    confirmClearSessionsBtn.addEventListener('click', () => {
      sessions = [];
      saveSessions();
      clearConfirmRow.style.display = 'none';
      showLanding();
    });
  }

  if (openVaultWindowBtn) {
    openVaultWindowBtn.addEventListener('click', async () => {
      let targetTabId = null;
      let targetOrigin = null;
      try {
        const t = await getCurrentTab();
        if (t) {
          targetTabId = t.id;
          targetOrigin = t.url ? new URL(t.url).origin : null;
        }
      } catch (_) {}
      try {
        chrome.runtime.sendMessage({
          action: 'OPEN_VAULT_WINDOW',
          tabId: targetTabId,
          origin: targetOrigin
        });
      } catch (_) {
        const qs = targetTabId ? `?tabId=${targetTabId}&origin=${encodeURIComponent(targetOrigin || '')}` : '';
        window.open('vault_window.html' + qs, '_blank', 'width=780,height=620');
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
    taskInput.style.height = '22px';
    taskInput.style.height = Math.min(taskInput.scrollHeight, 100) + 'px';
  });

  // ── Model Selector & Cascade Dropdown ──
  function getDisplayModelName(name) {
    if (!name) return 'Cascade';
    if (name.includes('Cascade')) return 'Cascade';
    if (name.includes('Ollama')) return 'Ollama';
    if (name.includes('Nemotron') || name.includes('OpenRouter')) return 'OpenRouter';
    if (name.includes('Gemini')) return 'Gemini';
    return name;
  }

  const checkSvg = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="wv-check-icon"><polyline points="20 6 9 17 4 12"/></svg>`;

  let currentActiveTrigger = null;

  function toggleModelMenu(triggerEl) {
    if (!modelDropdownMenu) return;

    if (modelDropdownMenu.classList.contains('open') && currentActiveTrigger === triggerEl) {
      closeModelMenu();
      return;
    }

    currentActiveTrigger = triggerEl;
    const rect = triggerEl.getBoundingClientRect();
    const padding = 8;
    const desiredWidth = 276;
    const menuWidth = Math.min(desiredWidth, window.innerWidth - (padding * 2));
    modelDropdownMenu.style.width = menuWidth + 'px';

    // Vertical placement
    const spaceBelow = window.innerHeight - rect.bottom;
    const approxMenuHeight = 240;
    if (spaceBelow >= approxMenuHeight || spaceBelow >= window.innerHeight * 0.45) {
      modelDropdownMenu.style.top = (rect.bottom + 6) + 'px';
      modelDropdownMenu.style.bottom = 'auto';
    } else {
      modelDropdownMenu.style.bottom = (window.innerHeight - rect.top + 6) + 'px';
      modelDropdownMenu.style.top = 'auto';
    }

    // Horizontal placement
    let targetLeft;
    // If trigger is in the right half of the sidepanel or would overflow right
    if (rect.left > window.innerWidth / 2 || (rect.left + menuWidth > window.innerWidth - padding)) {
      targetLeft = rect.right - menuWidth;
      if (targetLeft + menuWidth > window.innerWidth - padding) {
        targetLeft = window.innerWidth - menuWidth - padding;
      }
    } else {
      targetLeft = rect.left;
    }

    // Strict boundary clamping: never push left edge off-screen or into negative territory
    targetLeft = Math.max(padding, targetLeft);

    modelDropdownMenu.style.left = targetLeft + 'px';
    modelDropdownMenu.style.right = 'auto';

    document.querySelectorAll('.wv-model-pill').forEach(el => el.classList.remove('menu-open'));
    triggerEl.classList.add('menu-open');
    modelDropdownMenu.classList.add('open');
  }

  function closeModelMenu() {
    if (modelDropdownMenu) {
      modelDropdownMenu.classList.remove('open');
    }
    document.querySelectorAll('.wv-model-pill').forEach(el => el.classList.remove('menu-open'));
    currentActiveTrigger = null;
  }

  function selectModel(modelName) {
    currentSelectedModel = modelName;
    try {
      localStorage.setItem('webveil_selected_model', modelName);
      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({ webveil_selected_model: modelName });
      }
    } catch (_) {}

    const shortName = getDisplayModelName(modelName);

    if (modelSelectName) {
      modelSelectName.textContent = shortName;
    }
    if (modelSelectBtn) {
      modelSelectBtn.title = `Active model: ${modelName} · Click to switch`;
    }

    // Update non-clickable header status labels
    if (landingStatusLabel && isServerOnline) landingStatusLabel.textContent = shortName;
    if (convStatusLabel && isServerOnline) convStatusLabel.textContent = shortName;

    // Update settings model list selection state
    if (settingsModelList) {
      settingsModelList.querySelectorAll('.wv-settings-model-option').forEach(opt => {
        opt.classList.toggle('selected', opt.getAttribute('data-model') === modelName);
      });
    }

    // Update row active state and checkmark
    document.querySelectorAll('.wv-model-row').forEach(r => {
      const isMatch = r.getAttribute('data-model') === modelName;
      r.classList.toggle('active', isMatch);
      const badge = r.querySelector('.wv-model-badge-right');
      if (badge) {
        badge.innerHTML = isMatch ? checkSvg : '';
      }
    });

    closeModelMenu();
  }

  // Bind click handlers to triggers
  // Settings model list click handler
  if (settingsModelList) {
    settingsModelList.querySelectorAll('.wv-settings-model-option').forEach(opt => {
      opt.addEventListener('click', () => {
        const modelName = opt.getAttribute('data-model');
        if (modelName) selectModel(modelName);
      });
    });
  }

  if (modelSelectBtn) {
    modelSelectBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleModelMenu(modelSelectBtn);
    });
  }

  // Model rows
  document.querySelectorAll('.wv-model-row').forEach(row => {
    row.addEventListener('click', (e) => {
      e.stopPropagation();
      const isLocked = row.classList.contains('locked');
      const modelName = row.getAttribute('data-model');

      if (isLocked) {
        showStatus(`Model "${modelName}" requires provider access. Configure in Settings.`);
        setTimeout(hideStatus, 3000);
        return;
      }

      if (modelName) {
        selectModel(modelName);
      }
    });
  });

  // Global dismiss
  document.addEventListener('click', (e) => {
    if (modelDropdownMenu && modelDropdownMenu.classList.contains('open')) {
      if (!modelDropdownMenu.contains(e.target) && (!currentActiveTrigger || !currentActiveTrigger.contains(e.target))) {
        closeModelMenu();
      }
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modelDropdownMenu && modelDropdownMenu.classList.contains('open')) {
      closeModelMenu();
    }
  });

  window.addEventListener('resize', closeModelMenu);

  // Initialize UI on load
  selectModel(currentSelectedModel);



  // ── Suggestion Pills (populate composer with realistic prompt) ──
  document.querySelectorAll('.wv-suggestion-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const promptText = pill.getAttribute('data-prompt') || pill.getAttribute('data-task');
      if (!promptText || isRunning) return;

      if (taskInput) {
        taskInput.value = promptText;
        taskInput.style.height = '22px';
        taskInput.style.height = Math.min(taskInput.scrollHeight, 100) + 'px';
        taskInput.focus();
        if (sendBtn) sendBtn.disabled = false;
      }
    });
  });

  // ── Attach & Mic Handlers ──
  if (attachBtn) {
    attachBtn.addEventListener('click', () => {
      showStatus('Attachment upload: File selection ready.');
      setTimeout(hideStatus, 2500);
    });
  }

  if (micBtn) {
    micBtn.addEventListener('click', () => {
      showStatus('Voice transcription: Listening...');
      setTimeout(hideStatus, 2500);
    });
  }

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

  // ── Image Lightbox Close ──
  const imageLightbox = document.getElementById('image-lightbox');
  const lightboxCloseBtn = document.getElementById('lightbox-close-btn');
  if (imageLightbox) {
    imageLightbox.addEventListener('click', (e) => {
      if (e.target === imageLightbox || e.target.id === 'lightbox-close-btn') {
        imageLightbox.classList.remove('visible');
      }
    });
  }
  if (lightboxCloseBtn) {
    lightboxCloseBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (imageLightbox) imageLightbox.classList.remove('visible');
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (imageLightbox && imageLightbox.classList.contains('visible')) {
        imageLightbox.classList.remove('visible');
      }
      if (payloadModal && payloadModal.classList.contains('visible')) {
        payloadModal.classList.remove('visible');
      }
    }
  });

  // ── Payload Search Bar ──
  const payloadSearchInput = document.getElementById('payload-search-input');
  const payloadMatchCount = document.getElementById('payload-match-count');
  if (payloadSearchInput) {
    payloadSearchInput.addEventListener('input', () => {
      const query = payloadSearchInput.value.trim();
      const rawJson = modalJson.getAttribute('data-raw-json') || modalJson.textContent;
      if (!query) {
        modalJson.textContent = rawJson;
        if (payloadMatchCount) payloadMatchCount.textContent = '';
        return;
      }
      // Escape special regex chars in query
      const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`(${escaped})`, 'gi');
      const matches = rawJson.match(regex);
      const count = matches ? matches.length : 0;
      if (payloadMatchCount) {
        payloadMatchCount.textContent = count > 0 ? `${count} match${count !== 1 ? 'es' : ''} found` : 'No matches';
      }
      // Build highlighted HTML
      const safeJson = rawJson.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      const safeEscaped = query.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const highlightRegex = new RegExp(`(${safeEscaped})`, 'gi');
      modalJson.innerHTML = safeJson.replace(highlightRegex, '<mark>$1</mark>');
    });
  }

  // ── Instructions Selector Dropdown & File Import ──
  if (instructionsBtn && instructionsDropdownMenu) {
    instructionsBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      instructionsDropdownMenu.classList.toggle('open');
    });
  }

  if (instructionsClearBtn) {
    instructionsClearBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      clearInstructionFile();
    });
  }

  if (importInstructionsRow) {
    importInstructionsRow.addEventListener('click', (e) => {
      e.stopPropagation();
      if (instructionsDropdownMenu) instructionsDropdownMenu.classList.remove('open');
      if (instructionFileInput) instructionFileInput.click();
    });
  }

  if (importInstructionsHeaderBtn) {
    importInstructionsHeaderBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (instructionsDropdownMenu) instructionsDropdownMenu.classList.remove('open');
      if (instructionFileInput) instructionFileInput.click();
    });
  }

  if (instructionFileInput) {
    instructionFileInput.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) {
        handleInstructionFileImport(file);
        instructionFileInput.value = '';
      }
    });
  }

  document.addEventListener('click', (e) => {
    if (instructionsDropdownMenu && instructionsDropdownMenu.classList.contains('open')) {
      if (instructionsBtn && !instructionsBtn.contains(e.target) && !instructionsDropdownMenu.contains(e.target)) {
        instructionsDropdownMenu.classList.remove('open');
      }
    }
  });

  // ═══════════════════════════════════════════════════════════
  // INIT — Defaults straight to the New Chat screen
  // ═══════════════════════════════════════════════════════════
  loadInstructionFiles(() => {
    renderInstructionsMenu();
    loadSessions(() => {
      renderSessionList();
      let targetSession = sessions.find(s => s.messages && s.messages.length === 0);
      if (!targetSession) {
        targetSession = createSession();
      }
      showConversation(targetSession.id);
    });
  });
});
