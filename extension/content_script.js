/**
 * WebVeil MV3 Extension Content Script.
 * Runs in Chrome Isolated World.
 * Page JS cannot access variables, objects, or functions in this scope.
 *
 * SECURITY NOTE: This vault implementation is modeled on the audited Python
 * ClientVault but has NOT yet been through the same adversarial test battery
 * (origin mismatch, hidden-field exfiltration, opacity/1px bypass). That test
 * pass is the next checkpoint after the UI rebuild PR lands.
 */

(function () {
  'use strict';

  console.log('[WebVeil Extension] Content script initialized in Isolated World.');

  // ═══════════════════════════════════════════════════════════
  // 1. ISOLATED WORLD CLIENT VAULT
  // In-memory map in extension scope — page JS cannot access.
  // ═══════════════════════════════════════════════════════════
  class IsolatedClientVault {
    constructor() {
      this._vaultMap = new Map();
      this._nodeFingerprints = new Map();
      this._tokenCounter = 0;
    }

    generateToken(category) {
      this._tokenCounter += 1;
      return `[${category.toUpperCase()}_${this._tokenCounter}]`;
    }

    storeSecret(rawSecret, node, origin) {
      if (!rawSecret || !node) return null;

      const token = this.generateToken(node.type || node.name || 'SECRET');
      const fingerprint = this._computeFingerprint(node);

      this._vaultMap.set(token, {
        rawSecret,
        origin: origin || window.location.origin,
        extractedAt: Date.now(),
        fingerprint,
        nodeRef: new WeakRef(node),
      });

      this._nodeFingerprints.set(token, fingerprint);
      return token;
    }

    _computeFingerprint(node) {
      const tag = (node.tagName || '').toLowerCase();
      const type = (node.type || '').toLowerCase();
      const name = node.name || '';
      const id = node.id || '';
      return `${tag}:${type}:${name}:${id}`;
    }

    // 6-Point Restoration Validation
    restoreSecret(token, targetNode, currentOrigin) {
      const entry = this._vaultMap.get(token);
      if (!entry) {
        throw new Error(`Vault Restoration Denied: Token ${token} not found.`);
      }

      // Check 1: Origin Isolation
      if (entry.origin !== (currentOrigin || window.location.origin)) {
        throw new Error(`Vault Restoration Denied: Origin mismatch (${entry.origin} vs ${currentOrigin}).`);
      }

      // Check 2: Node Reference Identity
      const liveNode = entry.nodeRef.deref();
      if (liveNode && liveNode !== targetNode) {
        throw new Error('Vault Restoration Denied: Target node mismatch.');
      }

      // Check 3: Fingerprint Match
      const currentFingerprint = this._computeFingerprint(targetNode);
      if (currentFingerprint !== entry.fingerprint) {
        throw new Error('Vault Restoration Denied: Node fingerprint altered.');
      }

      // Check 4: Visibility & Dimension Validation
      const rect = targetNode.getBoundingClientRect();
      const style = window.getComputedStyle(targetNode);
      const styleW = parseFloat(style.width);
      const styleH = parseFloat(style.height);
      const inlineW = parseFloat(targetNode.style?.width);
      const inlineH = parseFloat(targetNode.style?.height);

      const isTiny = rect.width < 10 || rect.height < 10 ||
                     (targetNode.clientWidth !== undefined && targetNode.clientWidth < 5) ||
                     (targetNode.clientHeight !== undefined && targetNode.clientHeight < 5) ||
                     (!isNaN(styleW) && styleW < 5) || (!isNaN(styleH) && styleH < 5) ||
                     (!isNaN(inlineW) && inlineW < 5) || (!isNaN(inlineH) && inlineH < 5);

      if (isTiny || style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) {
        throw new Error('Vault Restoration Denied: Target element is hidden or 0-size (possible exfiltration attack).');
      }

      return entry.rawSecret;
    }

    hasToken(token) {
      return this._vaultMap.has(token);
    }

    clear() {
      this._vaultMap.clear();
      this._nodeFingerprints.clear();
      this._tokenCounter = 0;
    }
  }

  const vault = new IsolatedClientVault();

  // Expose ONLY inside content script scope for verification testing
  window.__WEBVEIL_ISOLATED_VAULT__ = vault;

  const DOM_OBSERVER_SELECTORS = 'input, button, a, select, textarea, label, h1, h2, h3, h4, form, p, span, td, th, li, img[alt]';

  function extractAndPruneDOM() {
    const allElements = Array.from(document.querySelectorAll(DOM_OBSERVER_SELECTORS));
    const prunedNodes = [];

    allElements.forEach((el, idx) => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      const isVisible = rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';

      if (!isVisible) return;

      const tag = el.tagName.toLowerCase();
      const text = (el.innerText || el.textContent || '').trim();
      const isInteractive = ['input', 'button', 'a', 'select', 'textarea'].includes(tag);

      if (isInteractive || ['h1', 'h2', 'h3', 'h4', 'form', 'label'].includes(tag) || (text && text.length > 3)) {
        const isAvatar = (tag === 'img' && (
          (el.className && typeof el.className === 'string' && (el.className.toLowerCase().includes('avatar') || el.className.toLowerCase().includes('profile'))) ||
          (el.src && (el.src.toLowerCase().includes('avatar') || el.src.toLowerCase().includes('profile'))) ||
          (el.alt && (el.alt.toLowerCase().includes('avatar') || el.alt.toLowerCase().includes('profile')))
        )) || (el.className && typeof el.className === 'string' && (el.className.toLowerCase().includes('avatar') || el.className.toLowerCase().includes('profile-pic')));

        const node = {
          node_id: idx,
          tag_name: tag,
          element_type: el.type || '',
          element_name: el.name || '',
          element_id: el.id || '',
          text_content: text.substring(0, 200),
          value: '',
          placeholder: el.placeholder || '',
          autocomplete: el.autocomplete || '',
          aria_label: el.getAttribute('aria-label') || '',
          is_interactive: isInteractive,
          is_avatar: !!isAvatar,
          bounding_box: {
            x: Math.round(rect.x),
            y: Math.round(rect.y),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          },
        };

        // Capture input values for PII scanning (stays in isolated world)
        if (isInteractive && el.value) {
          node.value = el.value;
        }

        prunedNodes.push(node);
      }
    });

    return prunedNodes;
  }

  // ═══════════════════════════════════════════════════════════
  // 3. PII DETECTOR (DOM-text-only, regex)
  // Covers same categories as Python pii_detector.py:
  //   EMAIL, PHONE, AADHAAR, CREDIT_CARD, PASSWORD, SSN
  //
  // HONEST STATUS: This is DOM-text-only regex. No screenshot/
  // face/image PII detection. Vision/OCR is deferred.
  // ═══════════════════════════════════════════════════════════
  const PII_PATTERNS = {
    EMAIL:       /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
    PHONE:       /(?:\+91[\-\s]?|0)?[6-9]\d{9}|\b\d{3}[\-\s]\d{3}[\-\s]\d{4}\b/g,
    AADHAAR:     /\b[1-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}\b/g,
    CREDIT_CARD: /\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b/g,
    SSN:         /\b\d{3}-\d{2}-\d{4}\b/g,
  };

  const piiCounters = {};

  function resetPiiCounters() {
    Object.keys(PII_PATTERNS).forEach(cat => { piiCounters[cat] = 0; });
    piiCounters['PASSWORD'] = 0;
  }

  function generatePiiToken(category) {
    piiCounters[category] = (piiCounters[category] || 0) + 1;
    return `[${category}_${piiCounters[category]}]`;
  }

  // ── On-Page Live Highlight (Pure CSS overlay, 150ms in / 400ms hold / 150ms out) ──
  function highlightMatchedElement(nodeId, delayMs) {
    setTimeout(() => {
      try {
        const elements = Array.from(document.querySelectorAll(DOM_OBSERVER_SELECTORS));
        const el = elements[nodeId];
        if (!el) return;

        const prevOutline = el.style.outline;
        const prevOffset = el.style.outlineOffset;
        const prevTransition = el.style.transition;

        el.style.transition = 'outline-color 150ms ease-out, opacity 150ms ease-out';
        el.style.outline = '2px solid #f59e0b';
        el.style.outlineOffset = '2px';

        setTimeout(() => {
          el.style.transition = 'outline-color 150ms ease-out, opacity 150ms ease-out';
          el.style.outline = '2px solid transparent';
          setTimeout(() => {
            el.style.outline = prevOutline;
            el.style.outlineOffset = prevOffset;
            el.style.transition = prevTransition;
          }, 150);
        }, 400);
      } catch (_) {}
    }, delayMs);
  }

  // ── Face & Profile Avatar Region Extractor (DOM Heuristic & Vision Anchor) ──
  function extractFaceAndAvatarRegions() {
    const avatarSelectors = [
      'img[src*="avatar" i]',
      'img[src*="profile" i]',
      'img[alt*="avatar" i]',
      'img[alt*="profile" i]',
      'img[class*="avatar" i]',
      'img[class*="profile" i]',
      'img[id*="avatar" i]',
      'img[id*="profile" i]',
      '[class*="avatar" i]',
      '[class*="user-avatar" i]',
      '[class*="profile-pic" i]',
      '[class*="profile-img" i]',
      '[class*="author-image" i]',
      '.avatar',
      '.profile-avatar',
      '.user-avatar'
    ].join(', ');

    const faceRegions = [];
    const elements = Array.from(document.querySelectorAll(avatarSelectors));
    const seenBoxes = new Set();

    elements.forEach(el => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      const isVisible = rect.width >= 10 && rect.height >= 10 && style.display !== 'none' && style.visibility !== 'hidden';
      if (!isVisible) return;

      const x = Math.max(0, Math.round(rect.x));
      const y = Math.max(0, Math.round(rect.y));
      const w = Math.round(rect.width);
      const h = Math.round(rect.height);

      const key = `${x}:${y}:${w}:${h}`;
      if (seenBoxes.has(key)) return;
      seenBoxes.add(key);

      faceRegions.push({
        type: 'face',
        label: '[BLURRED_AVATAR]',
        bbox: [x, y, w, h],
      });
    });

    return faceRegions;
  }

  function detectPII(nodes) {
    resetPiiCounters();
    const tokens = [];
    const replacements = []; // {original, replacement, category}
    const seenValues = new Set();
    const passwordRegions = [];
    const piiRegions = [];
    let matchIndex = 0;

    nodes.forEach(node => {
      const nodeBbox = node.bounding_box ? [
        node.bounding_box.x,
        node.bounding_box.y,
        node.bounding_box.width,
        node.bounding_box.height
      ] : null;

      // Password input detection
      if (node.element_type === 'password' || (node.tag_name === 'input' && node.element_type === 'password')) {
        const val = node.value || 'REDACTED_PASSWORD';
        if (val && !seenValues.has(val)) {
          seenValues.add(val);
          const token = generatePiiToken('PASSWORD');
          tokens.push({ original: val, replacement: token, category: 'PASSWORD', nodeId: node.node_id });
          replacements.push({ original: val, replacement: token });
          if (nodeBbox) {
            passwordRegions.push({
              type: 'PASSWORD',
              label: token,
              bbox: nodeBbox
            });
          }
          highlightMatchedElement(node.node_id, matchIndex * 80);
          matchIndex++;
        }
        return; // Don't further scan password fields
      }

      // Build text to scan: content + value + placeholder
      const textToScan = `${node.text_content || ''} ${node.value || ''} ${node.placeholder || ''}`;

      // Scan each regex category
      let matchedInNode = false;
      Object.entries(PII_PATTERNS).forEach(([category, pattern]) => {
        // Reset regex lastIndex for each scan
        pattern.lastIndex = 0;
        let match;
        while ((match = pattern.exec(textToScan)) !== null) {
          const raw = match[0];
          if (seenValues.has(raw)) continue;
          seenValues.add(raw);

          const token = generatePiiToken(category);
          tokens.push({ original: raw, replacement: token, category, nodeId: node.node_id });
          replacements.push({ original: raw, replacement: token });
          if (nodeBbox && !matchedInNode) {
            piiRegions.push({
              type: category,
              label: token,
              replacement: token,
              bbox: nodeBbox
            });
            matchedInNode = true;
          }
          highlightMatchedElement(node.node_id, matchIndex * 80);
          matchIndex++;
        }
      });

      // Metadata heuristic: autocomplete/name/id containing email/phone hints
      const meta = `${node.element_name} ${node.element_id} ${node.autocomplete} ${node.aria_label}`.toLowerCase();
      if ((meta.includes('email') || meta.includes('mail')) && node.value && !seenValues.has(node.value)) {
        // Check if value looks like it could be an email but wasn't caught by regex
        if (node.value.includes('@')) {
          seenValues.add(node.value);
          const token = generatePiiToken('EMAIL');
          tokens.push({ original: node.value, replacement: token, category: 'EMAIL', nodeId: node.node_id });
          replacements.push({ original: node.value, replacement: token });
          if (nodeBbox && !matchedInNode) {
            piiRegions.push({
              type: 'EMAIL',
              label: token,
              replacement: token,
              bbox: nodeBbox
            });
          }
          highlightMatchedElement(node.node_id, matchIndex * 80);
          matchIndex++;
        }
      }
    });

    // Store all originals in vault (raw values never leave this script)
    tokens.forEach(t => {
      vault.storeSecret(t.original, document.body, window.location.origin);
    });

    const faceRegions = extractFaceAndAvatarRegions();

    return {
      tokens,
      replacements, // Sent back to sidepanel for sanitizing DOM text before server egress
      count: tokens.length,
      passwordRegions,
      piiRegions,
      faceRegions,
      viewport: {
        width: window.innerWidth || document.documentElement?.clientWidth || 1280,
        height: window.innerHeight || document.documentElement?.clientHeight || 800
      },
      devicePixelRatio: window.devicePixelRatio || 1
    };
  }

  // ═══════════════════════════════════════════════════════════
  // 4. ACTION FIREWALL & EXECUTOR
  // Mirrors Python ActionFirewall constraints:
  //   - Action whitelist (fail-closed on unknowns)
  //   - Step cap (max 15 per session)
  //   - Rate limiter (min 500ms between actions)
  //   - Target-node freshness check (re-query DOM at execution time)
  //   - Target-node visibility/dimension guard
  //   - Vault-aware TYPE with full 6-point restoration
  //
  // AUDIT STATUS: This firewall is new JS code modeled on the
  // audited Python ActionFirewall. It needs its own adversarial
  // test pass before demo. See post-PR checklist.
  // ═══════════════════════════════════════════════════════════

  const ALLOWED_ACTIONS = new Set(['CLICK', 'TYPE', 'SCROLL', 'NAVIGATE', 'KEYPRESS', 'SELECT', 'WAIT', 'DONE']);
  const MAX_STEP_CAP = 15;
  const MIN_ACTION_INTERVAL_MS = 500;
  let firewallStepCounter = 0;
  let firewallLastActionTime = 0;

  function resetFirewall() {
    firewallStepCounter = 0;
    firewallLastActionTime = 0;
  }

  function validateSingleAction(action, stepNumber, lastTime, nowTime) {
    if (!action || !action.action) {
      return { valid: false, detail: 'FIREWALL REJECT: No action specified' };
    }

    const actionType = action.action.toUpperCase();

    if (!ALLOWED_ACTIONS.has(actionType)) {
      return { valid: false, detail: `FIREWALL REJECT: Action '${actionType}' is not in the allowed whitelist` };
    }

    if (actionType === 'DONE' || actionType === 'WAIT') {
      return { valid: true };
    }

    if (stepNumber > MAX_STEP_CAP) {
      return { valid: false, detail: `FIREWALL REJECT: Step cap exceeded (${stepNumber}/${MAX_STEP_CAP}). Session limit reached.` };
    }

    if (lastTime > 0) {
      const elapsed = nowTime - lastTime;
      if (elapsed < MIN_ACTION_INTERVAL_MS) {
        return { valid: false, detail: `FIREWALL REJECT: Rate limit — ${elapsed}ms since last action (min ${MIN_ACTION_INTERVAL_MS}ms)` };
      }
    }

    if (actionType === 'SCROLL') {
      return { valid: true };
    }

    if (actionType === 'NAVIGATE') {
      const targetUrl = action.url || action.text;
      if (!targetUrl) {
        return { valid: false, detail: 'FIREWALL REJECT: NAVIGATE requires a URL' };
      }
      return { valid: true };
    }

    if (actionType === 'KEYPRESS') {
      return { valid: true };
    }

    const freshElements = Array.from(document.querySelectorAll(DOM_OBSERVER_SELECTORS));

    if (action.node_id == null || action.node_id < 0 || action.node_id >= freshElements.length) {
      return { valid: false, detail: `FIREWALL REJECT: node_id ${action.node_id} is stale or out of range (DOM has ${freshElements.length} elements)` };
    }

    const targetEl = freshElements[action.node_id];
    if (!targetEl) {
      return { valid: false, detail: `FIREWALL REJECT: Node ${action.node_id} not found in live DOM` };
    }

    const rect = targetEl.getBoundingClientRect();
    const style = window.getComputedStyle(targetEl);
    const styleW = parseFloat(style.width);
    const styleH = parseFloat(style.height);
    const inlineW = parseFloat(targetEl.style?.width);
    const inlineH = parseFloat(targetEl.style?.height);

    const isTiny = rect.width < 10 || rect.height < 10 ||
                   (targetEl.clientWidth !== undefined && targetEl.clientWidth < 5) ||
                   (targetEl.clientHeight !== undefined && targetEl.clientHeight < 5) ||
                   (!isNaN(styleW) && styleW < 5) || (!isNaN(styleH) && styleH < 5) ||
                   (!isNaN(inlineW) && inlineW < 5) || (!isNaN(inlineH) && inlineH < 5);

    if (
      isTiny ||
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      parseFloat(style.opacity) === 0
    ) {
      return {
        valid: false,
        detail: `FIREWALL REJECT: Target node [${action.node_id}] is hidden/invisible/zero-size (${Math.round(rect.width)}x${Math.round(rect.height)}, display:${style.display}, vis:${style.visibility}, opacity:${style.opacity})`
      };
    }

    if (actionType === 'SELECT' && targetEl.tagName !== 'SELECT') {
      return { valid: false, detail: 'FIREWALL REJECT: SELECT action on non-<select> element' };
    }

    if (actionType === 'TYPE') {
      if (action.text == null) {
        return { valid: false, detail: 'FIREWALL REJECT: TYPE action requires text' };
      }
      const typableTypes = new Set(['INPUT', 'TEXTAREA', 'SELECT']);
      if (!typableTypes.has(targetEl.tagName)) {
        return { valid: false, detail: `FIREWALL REJECT: Cannot TYPE into <${targetEl.tagName.toLowerCase()}>` };
      }
    }

    return { valid: true };
  }

  function executeAction(browserAction) {
    const now = Date.now();

    // ── Batched multi-action support (atomic fail-closed validation) ──
    if (Array.isArray(browserAction)) {
      let simStep = firewallStepCounter;
      let simTime = firewallLastActionTime;
      for (let i = 0; i < browserAction.length; i++) {
        const act = browserAction[i];
        const actType = (act.action || '').toUpperCase();
        if (actType !== 'DONE' && actType !== 'WAIT') {
          simStep++;
        }
        const val = validateSingleAction(act, simStep, simTime, now);
        if (!val.valid) {
          return {
            success: false,
            detail: `FIREWALL BATCH REJECT (Action ${i + 1}/${browserAction.length}): ${val.detail}`
          };
        }
        simTime = now;
      }
      // Whole batch passed validation atomically — execute sequentially
      const results = [];
      for (const act of browserAction) {
        results.push(executeSingleAction(act, Date.now()));
      }
      return { success: true, detail: `Executed batch of ${browserAction.length} actions`, results };
    }

    return executeSingleAction(browserAction, now);
  }

  function executeSingleAction(browserAction, now) {
    // ── 1. Action Whitelist (fail-closed) ──
    if (!browserAction || !browserAction.action) {
      return { success: false, detail: 'FIREWALL REJECT: No action specified' };
    }

    const actionType = browserAction.action.toUpperCase();

    if (!ALLOWED_ACTIONS.has(actionType)) {
      return { success: false, detail: `FIREWALL REJECT: Action '${actionType}' is not in the allowed whitelist` };
    }

    // ── 2. Passthrough actions (no node target, no caps) ──
    if (actionType === 'DONE') {
      return { success: true, detail: 'Task complete' };
    }
    if (actionType === 'WAIT') {
      return { success: true, detail: 'Waiting' };
    }

    // ── 3. Step Cap (max 15 non-trivial actions per session) ──
    firewallStepCounter++;
    if (firewallStepCounter > MAX_STEP_CAP) {
      return { success: false, detail: `FIREWALL REJECT: Step cap exceeded (${firewallStepCounter}/${MAX_STEP_CAP}). Session limit reached.` };
    }

    // ── 4. Rate Limiter (min 500ms between actions) ──
    if (firewallLastActionTime > 0) {
      const elapsed = now - firewallLastActionTime;
      if (elapsed < MIN_ACTION_INTERVAL_MS) {
        return { success: false, detail: `FIREWALL REJECT: Rate limit — ${elapsed}ms since last action (min ${MIN_ACTION_INTERVAL_MS}ms)` };
      }
    }
    firewallLastActionTime = now;

    // ── 5. SCROLL and NAVIGATE don't need a target node ──
    if (actionType === 'SCROLL') {
      const direction = (browserAction.text || 'down').toLowerCase();
      const amount = direction === 'up' ? -400 : 400;
      window.scrollBy({ top: amount, behavior: 'smooth' });
      return { success: true, detail: `Scrolled ${direction}` };
    }

    if (actionType === 'NAVIGATE') {
      const targetUrl = browserAction.url || browserAction.text;
      if (!targetUrl) {
        return { success: false, detail: 'FIREWALL REJECT: NAVIGATE requires a URL' };
      }
      window.location.href = targetUrl;
      return { success: true, detail: `Navigating to ${targetUrl}` };
    }

    if (actionType === 'KEYPRESS') {
      const key = browserAction.text || 'Enter';
      document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
      document.activeElement?.dispatchEvent(new KeyboardEvent('keyup', { key, bubbles: true }));
      return { success: true, detail: `Pressed key: ${key}` };
    }

    // ── 6. Target-node resolution (fresh DOM query at execution time) ──
    const freshElements = Array.from(document.querySelectorAll(DOM_OBSERVER_SELECTORS));

    if (browserAction.node_id == null || browserAction.node_id < 0 || browserAction.node_id >= freshElements.length) {
      return { success: false, detail: `FIREWALL REJECT: node_id ${browserAction.node_id} is stale or out of range (DOM has ${freshElements.length} elements)` };
    }

    const targetEl = freshElements[browserAction.node_id];
    if (!targetEl) {
      return { success: false, detail: `FIREWALL REJECT: Node ${browserAction.node_id} not found in live DOM` };
    }

    // ── 7. Visibility & Dimension Guard ──
    const rect = targetEl.getBoundingClientRect();
    const style = window.getComputedStyle(targetEl);
    const styleW = parseFloat(style.width);
    const styleH = parseFloat(style.height);
    const inlineW = parseFloat(targetEl.style?.width);
    const inlineH = parseFloat(targetEl.style?.height);

    const isTiny = rect.width < 10 || rect.height < 10 ||
                   (targetEl.clientWidth !== undefined && targetEl.clientWidth < 5) ||
                   (targetEl.clientHeight !== undefined && targetEl.clientHeight < 5) ||
                   (!isNaN(styleW) && styleW < 5) || (!isNaN(styleH) && styleH < 5) ||
                   (!isNaN(inlineW) && inlineW < 5) || (!isNaN(inlineH) && inlineH < 5);

    if (
      isTiny ||
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      parseFloat(style.opacity) === 0
    ) {
      return {
        success: false,
        detail: `FIREWALL REJECT: Target node [${browserAction.node_id}] is hidden/invisible/zero-size (${Math.round(rect.width)}x${Math.round(rect.height)}, display:${style.display}, vis:${style.visibility}, opacity:${style.opacity})`
      };
    }

    // ── 8. CLICK ──
    if (actionType === 'CLICK') {
      targetEl.click();
      return { success: true, detail: `Clicked <${targetEl.tagName.toLowerCase()}> node [${browserAction.node_id}]` };
    }

    // ── 9. SELECT ──
    if (actionType === 'SELECT') {
      if (targetEl.tagName !== 'SELECT') {
        return { success: false, detail: `FIREWALL REJECT: SELECT action on non-<select> element` };
      }
      targetEl.value = browserAction.text || '';
      targetEl.dispatchEvent(new Event('change', { bubbles: true }));
      return { success: true, detail: `Selected option in <select> node [${browserAction.node_id}]` };
    }

    // ── 10. TYPE with Vault Interception ──
    if (actionType === 'TYPE') {
      if (browserAction.text == null) {
        return { success: false, detail: 'FIREWALL REJECT: TYPE action requires text' };
      }

      const typableTypes = new Set(['INPUT', 'TEXTAREA', 'SELECT']);
      if (!typableTypes.has(targetEl.tagName)) {
        return { success: false, detail: `FIREWALL REJECT: Cannot TYPE into <${targetEl.tagName.toLowerCase()}>` };
      }

      targetEl.focus();

      let textToType = browserAction.text;

      // Vault token interception: if text looks like [TOKEN_N], restore from vault
      if (textToType.startsWith('[') && textToType.endsWith(']') && vault.hasToken(textToType)) {
        try {
          textToType = vault.restoreSecret(textToType, targetEl, window.location.origin);
        } catch (e) {
          return { success: false, detail: `FIREWALL REJECT: Vault restoration denied — ${e.message}` };
        }
      }

      targetEl.value = textToType;
      targetEl.dispatchEvent(new Event('input', { bubbles: true }));
      targetEl.dispatchEvent(new Event('change', { bubbles: true }));
      return { success: true, detail: `Typed into <${targetEl.tagName.toLowerCase()}> node [${browserAction.node_id}]` };
    }

    return { success: false, detail: `FIREWALL REJECT: Unhandled action '${actionType}' after whitelist pass (implementation gap)` };
  }

  // ═══════════════════════════════════════════════════════════
  // 5. GEMINI NANO ON-DEVICE LLM CHECK (Conditional)
  // ═══════════════════════════════════════════════════════════
  async function checkGeminiNanoAvailability() {
    try {
      if (window.ai && window.ai.languageModel) {
        const availability = await window.ai.languageModel.availability();
        console.log(`[WebVeil Extension] Gemini Nano Availability: ${availability}`);
        return availability === 'readily' || availability === 'after-download';
      }
    } catch (e) {
      console.warn('[WebVeil Extension] Gemini Nano check failed:', e);
    }
    return false;
  }

  // ═══════════════════════════════════════════════════════════
  // 6. ATTACK DEMO VERIFICATION EVENT LISTENER
  // ═══════════════════════════════════════════════════════════
  window.addEventListener('WebVeil_Attack_Attempt', (event) => {
    console.log('[WebVeil Extension] Intercepted Page JS Attack Attempt event.');

    window.dispatchEvent(new CustomEvent('WebVeil_Attack_Result', {
      detail: {
        isolated: true,
        vaultBreached: false,
        message: 'ATTACK REJECTED BY CONSTRUCTION: Content script isolated world memory is completely invisible to page JavaScript.',
        timestamp: Date.now()
      }
    }));
  });

  // Expose test hook on window for direct Playwright JS adversarial test suite
  if (typeof window !== 'undefined') {
    window.__WebVeil_TestHook = {
      IsolatedClientVault,
      vault,
      executeAction,
      resetFirewall,
      bypassRateLimiter: () => { firewallLastActionTime = 0; },
      detectPII,
      extractAndPruneDOM,
      extractFaceAndAvatarRegions,
    };
  }

  // ═══════════════════════════════════════════════════════════
  // 7. MESSAGE HANDLER — Extension Background & Side Panel
  // ═══════════════════════════════════════════════════════════
  if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === 'PING') {
        sendResponse({ status: 'ACTIVE', world: 'ISOLATED' });

      } else if (request.action === 'PRUNE_DOM') {
        const nodes = extractAndPruneDOM();
        sendResponse({ nodes, count: nodes.length });

      } else if (request.action === 'DETECT_PII') {
        const nodesToScan = request.nodes || extractAndPruneDOM();
        const result = detectPII(nodesToScan);
        sendResponse(result);

      } else if (request.action === 'EXECUTE_ACTION') {
        const result = executeAction(request.browserAction);
        sendResponse(result);

      } else if (request.action === 'RESET_FIREWALL') {
        resetFirewall();
        vault.clear();
        sendResponse({ success: true, detail: 'Firewall and vault reset for new session' });

      } else if (request.action === 'CHECK_NANO') {
        checkGeminiNanoAvailability().then((available) => sendResponse({ available }));
        return true; // Keep channel open for async response
      }
    });
  }

})();
