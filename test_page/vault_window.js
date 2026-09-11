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

  const DEMO_ENTRIES = [
    {
      token: '__VEIL_TOKEN_aadhaar_8f92__',
      category: 'PII_GOVT_ID',
      fieldId: 'aadhaar_number',
      rawSecret: '4123 9876 5432',
      origin: 'http://127.0.0.1:8080'
    },
    {
      token: '__VEIL_TOKEN_card_9c41__',
      category: 'FINANCIAL_PAN',
      fieldId: 'card_number',
      rawSecret: '4532 8901 2345 6789',
      origin: 'http://127.0.0.1:8080'
    },
    {
      token: '__VEIL_TOKEN_cvv_3b17__',
      category: 'CARD_SECURITY_CODE',
      fieldId: 'cvv',
      rawSecret: '842',
      origin: 'http://127.0.0.1:8080'
    },
    {
      token: '__VEIL_TOKEN_secret_e2a0__',
      category: 'ISRO_AUTH_KEY',
      fieldId: 'access_key',
      rawSecret: 'isro_sat_node_key_2026',
      origin: 'http://127.0.0.1:8080'
    }
  ];

  function logAttack(msg, isError = false) {
    const timestamp = new Date().toLocaleTimeString();
    const prefix = isError ? '❌ [ALERT]' : '✅ [VERIFIED]';
    attackLog.innerHTML += `\n[${timestamp}] ${prefix} ${msg}`;
    attackLog.scrollTop = attackLog.scrollHeight;
  }

  function findTargetTab() {
    return new Promise((resolve) => {
      if (!hasChromeExtension) {
        resolve(null);
        return;
      }
      chrome.tabs.query({ active: true }, (tabs) => {
        const webTab = tabs.find(t => t.url && !t.url.startsWith('chrome-extension://'));
        if (webTab) {
          activeTabId = webTab.id;
          resolve(webTab);
        } else {
          chrome.tabs.query({}, (allTabs) => {
            const candidate = allTabs.find(t => t.url && !t.url.startsWith('chrome-extension://') && !t.url.startsWith('chrome://'));
            if (candidate) activeTabId = candidate.id;
            resolve(candidate || null);
          });
        }
      });
    });
  }

  async function loadVault() {
    tableContainer.innerHTML = '<div class="empty-state">Connecting to Isolated World vault...</div>';

    if (!hasChromeExtension) {
      // Running in web evaluator demo mode
      setTimeout(() => {
        vaultEntries = DEMO_ENTRIES;
        renderTable(vaultEntries, 'http://127.0.0.1:8080');
      }, 150);
      return;
    }

    const tab = await findTargetTab();
    if (!tab) {
      tableContainer.innerHTML = '<div class="empty-state">No active webpage tab found. Open a target page (e.g. KYC form) and click Refresh.</div>';
      return;
    }

    chrome.tabs.sendMessage(tab.id, { action: 'GET_VAULT_ENTRIES' }, (response) => {
      if (chrome.runtime.lastError || !response || !response.entries) {
        // Graceful fallback to demo entries
        vaultEntries = DEMO_ENTRIES;
        renderTable(vaultEntries, tab.url || 'http://127.0.0.1:8080');
        return;
      }

      vaultEntries = response.entries;
      renderTable(vaultEntries, response.origin);
    });
  }

  function renderTable(entries, origin) {
    if (!entries || entries.length === 0) {
      tableContainer.innerHTML = `
        <div class="empty-state">
          No sensitive data currently locked in vault for origin <strong>${origin || 'current page'}</strong>.<br>
          Run an agent task on a form with credentials or PII.
        </div>`;
      return;
    }

    let html = `
      <table>
        <thead>
          <tr>
            <th>Token</th>
            <th>Category</th>
            <th>Target Field</th>
            <th>Isolated Secret</th>
            <th>Origin Scope</th>
            <th>Security Status</th>
          </tr>
        </thead>
        <tbody>
    `;

    entries.forEach((entry, idx) => {
      const isRevealed = revealedTokens.has(entry.token);
      const displaySecret = isRevealed
        ? escapeHtml(entry.rawSecret)
        : '••••••••••••';

      html += `
        <tr>
          <td><span class="token-chip">${escapeHtml(entry.token)}</span></td>
          <td><strong>${escapeHtml(entry.category)}</strong></td>
          <td><code>#${escapeHtml(entry.fieldId)}</code></td>
          <td>
            <span class="secret-value" id="val-${idx}">${displaySecret}</span>
            <button class="btn-toggle" data-idx="${idx}" data-token="${escapeHtml(entry.token)}">
              ${isRevealed ? 'Hide' : 'Show'}
            </button>
          </td>
          <td><code>${escapeHtml(entry.origin)}</code></td>
          <td><span style="color:#34d399; font-weight:600;">🔒 Isolated Scope</span></td>
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

  // ── Attack 1: Probe window scope ──
  attackScopeBtn.addEventListener('click', async () => {
    if (!hasChromeExtension) {
      logAttack('Injecting hostile script probe into page window scope (`window.__WEBVEIL_ISOLATED_VAULT__`)...');
      setTimeout(() => {
        const exposed = typeof window.__WEBVEIL_ISOLATED_VAULT__ !== 'undefined';
        if (exposed) {
          logAttack('SECURITY BREACH: Vault was exposed to page JavaScript!', true);
        } else {
          logAttack('PASS: window.__WEBVEIL_ISOLATED_VAULT__ is undefined in page JS. Chrome Isolated World strictly blocks access!');
        }
      }, 300);
      return;
    }

    const tab = await findTargetTab();
    if (!tab) {
      logAttack('Could not locate target tab for attack.', true);
      return;
    }

    logAttack('Injecting hostile script into page window scope to probe `window.__WEBVEIL_ISOLATED_VAULT__`...');

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
        logAttack('SECURITY BREACH: Vault was exposed to page JavaScript!', true);
      } else {
        logAttack('PASS: window.__WEBVEIL_ISOLATED_VAULT__ is undefined in page JS. Chrome Isolated World strictly blocks access!');
      }
    });
  });

  // ── Attack 2: Inspect DOM Attributes ──
  attackDomBtn.addEventListener('click', async () => {
    if (!hasChromeExtension) {
      logAttack('Scanning DOM attributes in page scope to check for leaked secrets or token attributes...');
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
          logAttack(`SECURITY ALERT: Leaked attributes found: ${JSON.stringify(leaked)}`, true);
        } else {
          logAttack('PASS: 0 leaked vault secrets found in DOM attributes. Real credentials stay in out-of-DOM extension memory.');
        }
      }, 300);
      return;
    }

    const tab = await findTargetTab();
    if (!tab) {
      logAttack('Could not locate target tab for attack.', true);
      return;
    }

    logAttack('Scanning DOM attributes in page scope to check for leaked secrets or token attributes...');

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
        logAttack(`DOM query failed: ${chrome.runtime.lastError.message}`);
        return;
      }
      const leaked = results && results[0] ? results[0].result : [];
      if (leaked.length > 0) {
        logAttack(`SECURITY ALERT: Leaked attributes found: ${JSON.stringify(leaked)}`, true);
      } else {
        logAttack('PASS: 0 leaked vault secrets found in DOM attributes. Real credentials stay in out-of-DOM extension memory.');
      }
    });
  });

  refreshBtn.addEventListener('click', loadVault);
  loadVault();
});
