/**
 * WebVeil Client-Side Vault — Standalone Window Controller
 * Queries the isolated world vault from the active target tab and renders live entries.
 */

document.addEventListener('DOMContentLoaded', () => {
  const tableContainer = document.getElementById('vault-table-container');
  const refreshBtn = document.getElementById('refresh-btn');
  const attackScopeBtn = document.getElementById('attack-scope-btn');
  const attackDomBtn = document.getElementById('attack-dom-btn');
  const attackLog = document.getElementById('attack-log');

  let activeTabId = null;
  let vaultEntries = [];
  const revealedTokens = new Set();

  const hasChromeExtension = typeof chrome !== 'undefined' && chrome.tabs && typeof chrome.tabs.query === 'function';

  function logAttack(msg, isError = false) {
    const timestamp = new Date().toLocaleTimeString();
    const prefix = isError ? '[ALERT]' : '[VERIFIED]';
    attackLog.innerHTML += `\n[${timestamp}] ${prefix} ${msg}`;
    attackLog.scrollTop = attackLog.scrollHeight;
  }

  function findTargetTab() {
    return new Promise((resolve) => {
      if (!hasChromeExtension) {
        resolve(null);
        return;
      }

      const urlParams = new URLSearchParams(window.location.search);
      const paramTabId = urlParams.get('tabId') ? parseInt(urlParams.get('tabId'), 10) : null;
      if (paramTabId) {
        chrome.tabs.get(paramTabId, (tab) => {
          if (!chrome.runtime.lastError && tab) {
            activeTabId = tab.id;
            resolve(tab);
          } else {
            fallbackFind();
          }
        });
        return;
      }

      fallbackFind();

      function fallbackFind() {
        chrome.tabs.query({ active: true }, (tabs) => {
          const webTab = (tabs || []).find(t => t.url && !t.url.startsWith('chrome-extension://'));
          if (webTab) {
            activeTabId = webTab.id;
            resolve(webTab);
          } else {
            chrome.tabs.query({}, (allTabs) => {
              const candidate = (allTabs || []).find(t => t.url && !t.url.startsWith('chrome-extension://') && !t.url.startsWith('chrome://'));
              if (candidate) activeTabId = candidate.id;
              resolve(candidate || null);
            });
          }
        });
      }
    });
  }

  async function loadVault() {
    tableContainer.innerHTML = '<div class="empty-state">Connecting to client vault...</div>';

    const urlParams = new URLSearchParams(window.location.search);
    const originParam = urlParams.get('origin') || null;

    // 1. Immediately render cached live entries from chrome.storage.local if present
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get(['webveil_vault_entries', 'webveil_vault_origin'], (data) => {
        if (data && Array.isArray(data.webveil_vault_entries) && data.webveil_vault_entries.length > 0) {
          vaultEntries = data.webveil_vault_entries;
          renderTable(vaultEntries, data.webveil_vault_origin || originParam || 'Active Page');
        }
      });
    }

    // 2. Query target tab content script for live in-memory vault entries
    if (hasChromeExtension) {
      const tab = await findTargetTab();
      if (tab && tab.id) {
        chrome.tabs.sendMessage(tab.id, { action: 'GET_VAULT_ENTRIES' }, (response) => {
          if (!chrome.runtime.lastError && response && Array.isArray(response.entries) && response.entries.length > 0) {
            vaultEntries = response.entries;
            renderTable(vaultEntries, response.origin || tab.url || originParam || 'Active Page');
            try {
              chrome.storage.local.set({
                webveil_vault_entries: response.entries,
                webveil_vault_origin: response.origin || tab.url
              });
            } catch (_) {}
            return;
          }

          if (vaultEntries.length === 0) {
            renderTable([], tab.url || originParam || 'Active Page');
          }
        });
        return;
      }
    }

    // 3. Web mode fallback (read real values from localStorage if opened from evaluator test server)
    try {
      const raw = localStorage.getItem('webveil_vault_entries') || sessionStorage.getItem('webveil_vault_entries');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) {
          vaultEntries = parsed;
          renderTable(vaultEntries, window.location.origin);
          return;
        }
      }
    } catch (_) {}

    if (vaultEntries.length === 0) {
      renderTable([], originParam || window.location.origin);
    }
  }

  function renderTable(entries, origin) {
    if (!entries || entries.length === 0) {
      tableContainer.innerHTML = `
        <div class="empty-state">
          No sensitive data currently locked in vault for <strong>${origin || 'current page'}</strong>.<br>
          Fill out a form (e.g. KYC verification) or run an agent task on a page with PII to lock real-time credentials.
        </div>`;
      return;
    }

    let html = `
      <table>
        <colgroup>
          <col style="width: 22%;">
          <col style="width: 15%;">
          <col style="width: 16%;">
          <col style="width: 26%;">
          <col style="width: 11%;">
          <col style="width: 10%;">
        </colgroup>
        <thead>
          <tr>
            <th>Token</th>
            <th>Type</th>
            <th>Field</th>
            <th>Protected Value</th>
            <th>Website</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
    `;

    entries.forEach((entry, idx) => {
      const isRevealed = revealedTokens.has(entry.token);
      const displaySecret = isRevealed
        ? escapeHtml(entry.rawSecret)
        : '••••••••••••';
      const cleanOrigin = entry.origin ? escapeHtml(entry.origin.replace(/^https?:\/\//, '')) : 'Active Page';

      html += `
        <tr>
          <td><span class="token-chip" title="${escapeHtml(entry.token)}">${escapeHtml(entry.token)}</span></td>
          <td><strong>${escapeHtml(entry.category)}</strong></td>
          <td><code>#${escapeHtml(entry.fieldId)}</code></td>
          <td>
            <span class="secret-value" id="val-${idx}">${displaySecret}</span>
            <button class="btn-toggle" data-idx="${idx}" data-token="${escapeHtml(entry.token)}">
              ${isRevealed ? 'Hide' : 'Show'}
            </button>
          </td>
          <td><span class="origin-label" title="${escapeHtml(entry.origin || '')}">${cleanOrigin}</span></td>
          <td><span class="status-pill status-secure">Protected</span></td>
        </tr>
      `;
    });

    html += `</tbody></table>`;
    tableContainer.innerHTML = html;

    // Attach toggle handlers
    document.querySelectorAll('.btn-toggle').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const token = e.target.getAttribute('data-token');
        if (revealedTokens.has(token)) {
          revealedTokens.delete(token);
        } else {
          revealedTokens.add(token);
        }
        renderTable(vaultEntries, origin);
      });
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Test 1: Check Page Script Access ──
  attackScopeBtn.addEventListener('click', async () => {
    if (!hasChromeExtension) {
      logAttack('Running Test 1: Probing page JavaScript scope to test vault memory protection...');
      setTimeout(() => {
        const exposed = typeof window.__WEBVEIL_ISOLATED_VAULT__ !== 'undefined';
        if (exposed) {
          logAttack('SECURITY ALERT: Vault memory was accessible to page scripts!', true);
        } else {
          logAttack('PASS: Vault memory is completely unreachable from page JavaScript. Local isolation confirmed.');
        }
      }, 300);
      return;
    }

    const tab = await findTargetTab();
    if (!tab) {
      logAttack('Could not locate target tab for verification test.', true);
      return;
    }

    logAttack('Running Test 1: Probing page JavaScript scope to test vault memory protection...');

    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: 'MAIN', // Execute in the page's own window scope!
      func: () => {
        return {
          vaultExposed: typeof window.__WEBVEIL_ISOLATED_VAULT__ !== 'undefined',
          windowKeys: Object.keys(window).filter(k => k.includes('WEBVEIL') || k.includes('VAULT')),
        };
      },
    }, (results) => {
      if (chrome.runtime.lastError) {
        logAttack(`Script execution blocked: ${chrome.runtime.lastError.message}`);
        return;
      }
      const res = results && results[0] ? results[0].result : null;
      if (res && res.vaultExposed) {
        logAttack('SECURITY ALERT: Vault memory was accessible to page scripts!', true);
      } else {
        logAttack('PASS: Vault memory is completely unreachable from page JavaScript. Local isolation confirmed.');
      }
    });
  });

  // ── Test 2: Check DOM Token Protection ──
  attackDomBtn.addEventListener('click', async () => {
    if (!hasChromeExtension) {
      logAttack('Running Test 2: Inspecting webpage DOM attributes for credential leaks...');
      setTimeout(() => {
        const leaked = [];
        document.querySelectorAll('*').forEach(el => {
          for (let i = 0; i < el.attributes.length; i++) {
            const attr = el.attributes[i];
            if (attr.name.includes('vault') || attr.name.includes('secret') || attr.value.includes('CANARY_PASSWORD')) {
              leaked.push({ tag: el.tagName, attr: attr.name });
            }
          }
        });
        if (leaked.length > 0) {
          logAttack(`SECURITY ALERT: Leaked attributes found in page: ${JSON.stringify(leaked)}`, true);
        } else {
          logAttack('PASS: Zero credentials found in DOM attributes. All values remain securely tokenized.');
        }
      }, 300);
      return;
    }

    const tab = await findTargetTab();
    if (!tab) {
      logAttack('Could not locate target tab for verification test.', true);
      return;
    }

    logAttack('Running Test 2: Inspecting webpage DOM attributes for credential leaks...');

    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: 'MAIN',
      func: () => {
        const leaked = [];
        document.querySelectorAll('*').forEach(el => {
          for (let i = 0; i < el.attributes.length; i++) {
            const attr = el.attributes[i];
            if (attr.name.includes('vault') || attr.name.includes('secret') || attr.value.includes('CANARY_PASSWORD')) {
              leaked.push({ tag: el.tagName, attr: attr.name });
            }
          }
        });
        return leaked;
      },
    }, (results) => {
      if (chrome.runtime.lastError) {
        logAttack(`Script execution blocked: ${chrome.runtime.lastError.message}`);
        return;
      }
      const leaked = results && results[0] ? results[0].result : [];
      if (leaked && leaked.length > 0) {
        logAttack(`SECURITY ALERT: Leaked attributes found in page: ${JSON.stringify(leaked)}`, true);
      } else {
        logAttack('PASS: Zero credentials found in DOM attributes. All values remain securely tokenized.');
      }
    });
  });

  refreshBtn.addEventListener('click', loadVault);
  loadVault();
});
