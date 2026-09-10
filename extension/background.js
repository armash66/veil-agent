/**
 * WebVeil MV3 Service Worker (Background Script)
 * - Opens side panel on extension icon click (no popup)
 * - Tab screenshot capture
 * - Tab info queries
 */

console.log('[WebVeil ServiceWorker] Background worker started.');

// Open side panel when extension icon is clicked (no popup)
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ windowId: tab.windowId });
});

chrome.runtime.onInstalled.addListener(() => {
  console.log('[WebVeil ServiceWorker] Installed successfully.');
  // Enable side panel for all tabs
  chrome.sidePanel.setOptions({
    enabled: true,
  });
});

// Message handlers
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'GET_TAB_INFO') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs.length > 0) {
        sendResponse({ url: tabs[0].url, title: tabs[0].title, id: tabs[0].id });
      } else {
        sendResponse({ error: 'No active tab found' });
      }
    });
    return true;

  } else if (request.action === 'CAPTURE_TAB') {
    chrome.tabs.captureVisibleTab(null, { format: 'png' }, (dataUrl) => {
      if (chrome.runtime.lastError) {
        sendResponse({ error: chrome.runtime.lastError.message });
      } else {
        sendResponse({ screenshot: dataUrl });
      }
    });
    return true; // Async channel

  } else if (request.action === 'OPEN_VAULT_WINDOW') {
    chrome.windows.create({
      url: chrome.runtime.getURL('vault_window.html'),
      type: 'popup',
      width: 740,
      height: 580,
    }, (win) => {
      sendResponse({ success: true, windowId: win?.id });
    });
    return true;
  }
});
