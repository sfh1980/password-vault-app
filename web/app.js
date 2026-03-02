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
  const addFolderBtn = document.getElementById('add-folder-btn');
  const addFolderForm = document.getElementById('add-folder-form');
  const newFolderNameInput = document.getElementById('new-folder-name');
  const saveFolderBtn = document.getElementById('save-folder-btn');
  const cancelFolderBtn = document.getElementById('cancel-folder-btn');
  const newFolderForm = document.getElementById('new-folder-form');
  const vaultActivity = document.getElementById('vault-activity');
  const searchInput = document.getElementById('search-input');
  const searchBtn = document.getElementById('search-btn');
  const searchResults = document.getElementById('search-results');
  const searchResultsList = document.getElementById('search-results-list');
  const searchResultsHeading = document.getElementById('search-results-heading');
  const unlockPasswordArea = document.getElementById('unlock-password-area');
  const unlockRecoveryArea = document.getElementById('unlock-recovery-area');
  const recoveryKeyInput = document.getElementById('recovery-key-input');
  const setupRecoveryBtn = document.getElementById('setup-recovery-btn');
  const recoveryConfiguredMsg = document.getElementById('recovery-configured-msg');
  const recoverySetupResult = document.getElementById('recovery-setup-result');
  const recoveryKeyDisplay = document.getElementById('recovery-key-display');

  /** Folder id for the currently listed entries (so we can refresh after edit/delete). */
  let currentFolderId = null;

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

  function hideCreateFolderForm() {
    addFolderForm.classList.add('hidden');
    newFolderNameInput.value = '';
  }

  function loadRecoveryStatus() {
    api('/recovery/status')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.configured) {
          setupRecoveryBtn.classList.add('hidden');
          recoveryConfiguredMsg.classList.remove('hidden');
        } else {
          setupRecoveryBtn.classList.remove('hidden');
          recoveryConfiguredMsg.classList.add('hidden');
        }
        recoverySetupResult.classList.add('hidden');
      })
      .catch(function () {
        setupRecoveryBtn.classList.add('hidden');
        recoveryConfiguredMsg.classList.add('hidden');
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

  function hideSearchResults() {
    searchResults.classList.add('hidden');
    searchResultsList.innerHTML = '';
  }

  function showSearchResults(entries) {
    searchResultsList.innerHTML = '';
    searchResultsHeading.textContent = 'Search results (' + entries.length + ')';
    entries.forEach(function (entry) {
      const li = document.createElement('li');
      const span = document.createElement('span');
      span.textContent = entry.title + (entry.folder_name ? ' — ' + entry.folder_name : '');
      li.appendChild(span);
      li.addEventListener('click', function () {
        currentFolderId = entry.folder_id;
        showEntryDetail(entry);
        resetInactivityTimer();
      });
      searchResultsList.appendChild(li);
    });
    searchResults.classList.remove('hidden');
  }

  function runSearch() {
    const q = searchInput.value.trim();
    if (!q) {
      hideSearchResults();
      return;
    }
    api('/search?q=' + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(function (entries) {
        showSearchResults(entries);
        resetInactivityTimer();
      })
      .catch(function (err) {
        if (err.message !== 'Unauthorized') showVaultError(err.message || 'Search failed.');
      });
  }

  function loadEntries(folderId) {
    currentFolderId = folderId;
    addEntryBtn.dataset.folderId = String(folderId);
    hideSearchResults();
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
      '<button type="button" id="copy-detail-password">Copy password</button> ' +
      '<button type="button" id="edit-entry-btn">Edit</button> ' +
      '<button type="button" id="delete-entry-btn">Delete</button>' +
      '<div id="edit-entry-form" class="hidden" style="margin-top:1rem;"></div>';
    entryDetail.classList.remove('hidden');
    entryDetail.dataset.entryId = String(entry.id);
    document.getElementById('copy-detail-password').addEventListener('click', function () {
      copyPassword(entry.password);
      resetInactivityTimer();
    });
    document.getElementById('edit-entry-btn').addEventListener('click', function () {
      showEditEntryForm(entry);
      resetInactivityTimer();
    });
    document.getElementById('delete-entry-btn').addEventListener('click', function () {
      if (confirm('Delete this entry? This cannot be undone.')) {
        deleteEntry(entry.id);
      }
      resetInactivityTimer();
    });
  }

  function showEditEntryForm(entry) {
    const formEl = document.getElementById('edit-entry-form');
    if (!formEl) return;
    formEl.innerHTML =
      '<form id="entry-edit-form">' +
      '<label for="edit-title">Title</label><input type="text" id="edit-title" value="' + escapeHtml(entry.title) + '" required> ' +
      '<label for="edit-username">Username</label><input type="text" id="edit-username" value="' + escapeHtml(entry.username) + '"> ' +
      '<label for="edit-password">Password</label><input type="password" id="edit-password" value="' + escapeHtml(entry.password) + '"> <button type="button" id="edit-generate-password">Generate</button> ' +
      '<label for="edit-url">URL</label><input type="url" id="edit-url" value="' + escapeHtml(entry.url || '') + '"> ' +
      '<label for="edit-notes">Notes</label><textarea id="edit-notes" rows="2">' + escapeHtml(entry.notes || '') + '</textarea> ' +
      '<button type="submit">Save</button> <button type="button" id="edit-cancel-btn">Cancel</button>' +
      '</form>';
    formEl.classList.remove('hidden');
    document.getElementById('entry-edit-form').addEventListener('submit', function (e) {
      e.preventDefault();
      saveEntryEdit(entry.id);
    });
    document.getElementById('edit-cancel-btn').addEventListener('click', function () {
      formEl.classList.add('hidden');
      formEl.innerHTML = '';
    });
    document.getElementById('edit-generate-password').addEventListener('click', function () {
      api('/generate-password?length=20').then(function (r) { return r.json(); }).then(function (data) {
        document.getElementById('edit-password').value = data.password;
      }).catch(function () {});
    });
  }

  function saveEntryEdit(entryId) {
    const payload = {
      title: document.getElementById('edit-title').value.trim(),
      username: document.getElementById('edit-username').value,
      password: document.getElementById('edit-password').value,
      url: document.getElementById('edit-url').value,
      notes: document.getElementById('edit-notes').value,
    };
    if (!payload.title) {
      showVaultError('Title is required.');
      return;
    }
    api('/entries/' + entryId, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        if (r.status !== 204) return r.json().then(function () { throw new Error('Update failed'); });
      })
      .then(function () {
        document.getElementById('edit-entry-form').classList.add('hidden');
        document.getElementById('edit-entry-form').innerHTML = '';
        entryDetail.classList.add('hidden');
        entryDetail.innerHTML = '';
        if (currentFolderId != null) loadEntries(currentFolderId);
        resetInactivityTimer();
      })
      .catch(function (err) {
        if (err.message !== 'Unauthorized') showVaultError(err.message || 'Failed to update entry.');
      });
  }

  function deleteEntry(entryId) {
    api('/entries/' + entryId, { method: 'DELETE' })
      .then(function (r) {
        if (r.status !== 204) throw new Error('Delete failed');
      })
      .then(function () {
        entryDetail.classList.add('hidden');
        entryDetail.innerHTML = '';
        if (currentFolderId != null) loadEntries(currentFolderId);
        resetInactivityTimer();
      })
      .catch(function (err) {
        if (err.message !== 'Unauthorized') showVaultError(err.message || 'Failed to delete entry.');
      });
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function unlockWithPayload(payload) {
    loginError.classList.add('hidden');
    return api('/unlock', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        setSessionId(data.session_id);
        document.getElementById('password').value = '';
        if (recoveryKeyInput) recoveryKeyInput.value = '';
        showVault();
        loadFolders().then(function () { loadRecoveryStatus(); });
      })
      .catch(function (err) {
        if (err.message !== 'Unauthorized') {
          loginError.textContent = err.message || 'Unlock failed.';
          loginError.classList.remove('hidden');
        }
      });
  }

  loginForm.addEventListener('submit', function (e) {
    e.preventDefault();
    const password = document.getElementById('password').value;
    if (!password.trim()) {
      loginError.textContent = 'Enter your master password.';
      loginError.classList.remove('hidden');
      return;
    }
    unlockWithPayload({ password: password });
  });

  document.getElementById('show-recovery-unlock').addEventListener('click', function () {
    unlockPasswordArea.classList.add('hidden');
    unlockRecoveryArea.classList.remove('hidden');
    loginError.classList.add('hidden');
    recoveryKeyInput.value = '';
    recoveryKeyInput.focus();
  });

  document.getElementById('back-to-password-btn').addEventListener('click', function () {
    unlockRecoveryArea.classList.add('hidden');
    unlockPasswordArea.classList.remove('hidden');
    recoveryKeyInput.value = '';
    loginError.classList.add('hidden');
  });

  document.getElementById('unlock-with-recovery-btn').addEventListener('click', function () {
    const key = recoveryKeyInput.value.trim();
    if (!key) {
      loginError.textContent = 'Paste your recovery key.';
      loginError.classList.remove('hidden');
      return;
    }
    unlockWithPayload({ recovery_key: key });
  });

  lockBtn.addEventListener('click', function () {
    lock();
  });

  addFolderBtn.addEventListener('click', function () {
    addFolderForm.classList.remove('hidden');
    newFolderNameInput.focus();
    resetInactivityTimer();
  });

  cancelFolderBtn.addEventListener('click', function () {
    hideCreateFolderForm();
    resetInactivityTimer();
  });

  function submitCreateFolder() {
    const name = newFolderNameInput.value.trim();
    if (!name) {
      showVaultError('Enter a folder name.');
      return;
    }
    api('/folders', {
      method: 'POST',
      body: JSON.stringify({ name: name }),
    })
      .then(function (r) { return r.json(); })
      .then(function () {
        hideCreateFolderForm();
        loadFolders();
        resetInactivityTimer();
      })
      .catch(function (err) {
        if (err.message !== 'Unauthorized') showVaultError(err.message || 'Failed to create folder.');
      });
  }

  newFolderForm.addEventListener('submit', function (e) {
    e.preventDefault();
    submitCreateFolder();
  });

  vaultActivity.addEventListener('click', resetInactivityTimer);
  vaultActivity.addEventListener('keydown', resetInactivityTimer);

  searchBtn.addEventListener('click', function () {
    runSearch();
    resetInactivityTimer();
  });
  searchInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      runSearch();
      resetInactivityTimer();
    }
  });

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

  setupRecoveryBtn.addEventListener('click', function () {
    api('/recovery/setup', { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        recoveryKeyDisplay.textContent = data.recovery_key;
        recoverySetupResult.classList.remove('hidden');
        setupRecoveryBtn.classList.add('hidden');
        resetInactivityTimer();
      })
      .catch(function (err) {
        if (err.message !== 'Unauthorized') showVaultError(err.message || 'Failed to set up recovery key.');
      });
  });

  document.getElementById('copy-recovery-key-btn').addEventListener('click', function () {
    const key = recoveryKeyDisplay.textContent;
    if (key) copyPassword(key);
    resetInactivityTimer();
  });

  document.getElementById('recovery-saved-btn').addEventListener('click', function () {
    recoverySetupResult.classList.add('hidden');
    recoveryKeyDisplay.textContent = '';
    loadRecoveryStatus();
    resetInactivityTimer();
  });

  // On load: if we have a session, try to use it
  if (getSessionId()) {
    api('/folders')
      .then(function (r) {
        if (!r.ok) throw new Error('Unauthorized');
        showVault();
        return loadFolders();
      })
      .then(function () { loadRecoveryStatus(); })
      .catch(function () {
        showLogin('');
      });
  }
})();
