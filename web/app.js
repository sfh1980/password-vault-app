/**
 * Phase 4: minimal vault UI. Session in sessionStorage; inactivity timeout locks;
 * copy password then clear clipboard after 30s. No secrets in console.log.
 */

(function () {
  'use strict';

  const SESSION_TIMEOUT_MINUTES = 15;
  const CLIPBOARD_CLEAR_MS = 30000;

  let inactivityTimerId = null;
  let clipboardClearTimerId = null;

  const loginScreen = document.getElementById('login-screen');
  const vaultScreen = document.getElementById('vault-screen');
  const loginForm = document.getElementById('login-form');
  const loginError = document.getElementById('login-error');
  const loginMessage = document.getElementById('login-message');
  const vaultError = document.getElementById('vault-error');
  const sessionMessage = document.getElementById('session-message');
  const lockBtn = document.getElementById('lock-btn');
  const folderList = document.getElementById('folder-list');
  const entryList = document.getElementById('entry-list');
  const entriesHeading = document.getElementById('entries-heading');
  const entryDetail = document.getElementById('entry-detail');
  const addEntryForm = document.getElementById('add-entry-form');
  const newEntryForm = document.getElementById('new-entry-form');
  const addEntryBtn = document.getElementById('add-entry-btn');
  const vaultActivity = document.getElementById('vault-activity');

  function getSessionId() {
    return sessionStorage.getItem('vault_session_id');
  }

  function setSessionId(id) {
    if (id) sessionStorage.setItem('vault_session_id', id);
    else sessionStorage.removeItem('vault_session_id');
  }

  /**
   * @param {string} url
   * @param {RequestInit} [options]
   * @returns {Promise<Response>}
   */
  function api(url, options = {}) {
    const sid = getSessionId();
    const headers = new Headers(options.headers || {});
    if (sid) headers.set('X-Vault-Session', sid);
    if (!headers.has('Content-Type') && options.body && typeof options.body === 'string')
      headers.set('Content-Type', 'application/json');
    return fetch(url, { ...options, headers }).then(function (res) {
      if (res.status === 401) {
        setSessionId(null);
        showLogin('Session expired or invalid.');
        throw new Error('Unauthorized');
      }
      return res;
    });
  }

  function showLogin(message) {
    vaultScreen.classList.add('hidden');
    loginScreen.classList.remove('hidden');
    loginError.classList.add('hidden');
    loginMessage.classList.remove('hidden');
    loginMessage.textContent = message || '';
    if (!message) loginMessage.classList.add('hidden');
    stopInactivityTimer();
  }

  function showVault() {
    loginScreen.classList.add('hidden');
    vaultScreen.classList.remove('hidden');
    loginError.classList.add('hidden');
    vaultError.classList.add('hidden');
    sessionMessage.classList.add('hidden');
    startInactivityTimer();
  }

  function showVaultError(msg) {
    vaultError.textContent = msg;
    vaultError.classList.remove('hidden');
  }

  function startInactivityTimer() {
    stopInactivityTimer();
    inactivityTimerId = setTimeout(function () {
      lock();
    }, SESSION_TIMEOUT_MINUTES * 60 * 1000);
  }

  function stopInactivityTimer() {
    if (inactivityTimerId) {
      clearTimeout(inactivityTimerId);
      inactivityTimerId = null;
    }
  }

  function resetInactivityTimer() {
    if (getSessionId()) startInactivityTimer();
  }

  function lock() {
    const sid = getSessionId();
    if (sid) {
      api('/lock', { method: 'POST' }).catch(function () {});
    }
    setSessionId(null);
    showLogin('Locked.');
  }

  /**
   * Copy password to clipboard; clear clipboard after CLIPBOARD_CLEAR_MS.
   * We do not keep the password in a variable after this call.
   */
  function copyPassword(plaintext) {
    if (clipboardClearTimerId) clearTimeout(clipboardClearTimerId);
    navigator.clipboard.writeText(plaintext).then(function () {
      clipboardClearTimerId = setTimeout(function () {
        navigator.clipboard.writeText('');
        clipboardClearTimerId = null;
      }, CLIPBOARD_CLEAR_MS);
    });
  }

  function loadFolders() {
    return api('/folders').then(function (r) { return r.json(); }).then(function (folders) {
      folderList.innerHTML = '';
      folders.forEach(function (f) {
        const li = document.createElement('li');
        const btn = document.createElement('button');
        btn.textContent = f.name;
        btn.type = 'button';
        btn.dataset.folderId = String(f.id);
        btn.addEventListener('click', function () {
          loadEntries(f.id);
          addEntryBtn.dataset.folderId = String(f.id);
          entryDetail.classList.add('hidden');
          addEntryForm.classList.add('hidden');
        });
        li.appendChild(btn);
        folderList.appendChild(li);
      });
    });
  }

  function loadEntries(folderId) {
    addEntryBtn.dataset.folderId = String(folderId);
    return api('/entries?folder_id=' + encodeURIComponent(folderId)).then(function (r) { return r.json(); }).then(function (entries) {
      entryList.innerHTML = '';
      entriesHeading.textContent = 'Entries';
      entries.forEach(function (e) {
        const li = document.createElement('li');
        const span = document.createElement('span');
        span.textContent = e.title;
        const copyBtn = document.createElement('button');
        copyBtn.textContent = 'Copy password';
        copyBtn.type = 'button';
        copyBtn.addEventListener('click', function () {
          copyPassword(e.password);
          resetInactivityTimer();
        });
        li.appendChild(span);
        li.appendChild(copyBtn);
        li.addEventListener('click', function (ev) {
          if (ev.target === copyBtn) return;
          showEntryDetail(e);
          resetInactivityTimer();
        });
        entryList.appendChild(li);
      });
    });
  }

  function showEntryDetail(entry) {
    entryDetail.innerHTML =
      '<p><strong>' + escapeHtml(entry.title) + '</strong></p>' +
      (entry.username ? '<p>Username: ' + escapeHtml(entry.username) + '</p>' : '') +
      (entry.url ? '<p>URL: <a href="' + escapeHtml(entry.url) + '" target="_blank" rel="noopener">' + escapeHtml(entry.url) + '</a></p>' : '') +
      (entry.notes ? '<p>Notes: ' + escapeHtml(entry.notes) + '</p>' : '') +
      '<button type="button" id="copy-detail-password">Copy password</button>';
    entryDetail.classList.remove('hidden');
    document.getElementById('copy-detail-password').addEventListener('click', function () {
      copyPassword(entry.password);
      resetInactivityTimer();
    });
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  loginForm.addEventListener('submit', function (e) {
    e.preventDefault();
    loginError.classList.add('hidden');
    const password = document.getElementById('password').value;
    api('/unlock', {
      method: 'POST',
      body: JSON.stringify({ password: password }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        setSessionId(data.session_id);
        document.getElementById('password').value = '';
        showVault();
        loadFolders();
      })
      .catch(function (err) {
        if (err.message !== 'Unauthorized') {
          loginError.textContent = err.message || 'Unlock failed.';
          loginError.classList.remove('hidden');
        }
      });
  });

  lockBtn.addEventListener('click', function () {
    lock();
  });

  vaultActivity.addEventListener('click', resetInactivityTimer);
  vaultActivity.addEventListener('keydown', resetInactivityTimer);

  addEntryBtn.addEventListener('click', function () {
    const folderId = addEntryBtn.dataset.folderId;
    if (!folderId) {
      showVaultError('Select a folder first.');
      return;
    }
    addEntryForm.classList.remove('hidden');
    document.getElementById('new-entry-folder-id').value = folderId;
    resetInactivityTimer();
  });

  newEntryForm.addEventListener('submit', function (e) {
    e.preventDefault();
    const folderId = parseInt(document.getElementById('new-entry-folder-id').value, 10);
    const payload = {
      folder_id: folderId,
      title: document.getElementById('new-title').value,
      username: document.getElementById('new-username').value,
      password: document.getElementById('new-password').value,
      url: document.getElementById('new-url').value,
      notes: document.getElementById('new-notes').value,
    };
    api('/entries', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function () {
        newEntryForm.reset();
        addEntryForm.classList.add('hidden');
        loadEntries(folderId);
        resetInactivityTimer();
      })
      .catch(function (err) {
        if (err.message !== 'Unauthorized') showVaultError(err.message || 'Failed to create entry.');
      });
  });

  document.getElementById('generate-password-btn').addEventListener('click', function () {
    api('/generate-password?length=20')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        document.getElementById('new-password').value = data.password;
        resetInactivityTimer();
      })
      .catch(function (err) {
        if (err.message !== 'Unauthorized') showVaultError(err.message || 'Failed to generate password.');
      });
  });

  // On load: if we have a session, try to use it
  if (getSessionId()) {
    api('/folders')
      .then(function (r) {
        if (!r.ok) throw new Error('Unauthorized');
        showVault();
        return loadFolders();
      })
      .catch(function () {
        showLogin('');
      });
  }
})();
