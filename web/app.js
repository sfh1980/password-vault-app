/**
 * Phase 4: minimal vault UI. Session in sessionStorage; inactivity timeout locks;
 * copy password then clear clipboard after 30s. No secrets in console.log.
 */

(function () {
  'use strict';

  /** Must match backend VAULT_SESSION_TIMEOUT_MINUTES (default 15). */
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
  const firstTimeSetupArea = document.getElementById('first-time-setup-area');
  const setupForm = document.getElementById('setup-form');
  const unlockIntro = document.getElementById('unlock-intro');
  const folderListEmpty = document.getElementById('folder-list-empty');
  const entryListEmpty = document.getElementById('entry-list-empty');
  const recoveryRequiredOverlay = document.getElementById('recovery-required-overlay');
  const recoveryRequiredChoices = document.getElementById('recovery-required-choices');
  const recoveryRequiredKeyFlow = document.getElementById('recovery-required-key-flow');
  const recoveryRequiredKeyDisplay = document.getElementById('recovery-required-key-display');
  const recoveryRequiredQuestionsFlow = document.getElementById('recovery-required-questions-flow');
  const unlockQuestionsArea = document.getElementById('unlock-questions-area');
  const unlockQuestionsFormContainer = document.getElementById('unlock-questions-form-container');
  const quoteText = document.getElementById('quote-text');
  const quoteAuthor = document.getElementById('quote-author');
  const quoteError = document.getElementById('quote-error');

  /** Folder id for the currently listed entries (so we can refresh after edit/delete). */
  let currentFolderId = null;

  /**
   * Fetch vault status and show either first-time setup or unlock form.
   * Does not require session. Use after load (no session) or after reset.
   */
  function applyVaultStatus(initialized) {
    loginError.classList.add('hidden');
    loginMessage.classList.add('hidden');
    if (unlockQuestionsArea) unlockQuestionsArea.classList.add('hidden');
    var signupArea = document.getElementById('signup-area');
    if (signupArea) signupArea.classList.add('hidden');
    if (initialized) {
      firstTimeSetupArea.classList.add('hidden');
      unlockIntro.classList.remove('hidden');
      unlockPasswordArea.classList.remove('hidden');
      unlockRecoveryArea.classList.add('hidden');
    } else {
      firstTimeSetupArea.classList.remove('hidden');
      unlockIntro.classList.add('hidden');
      unlockPasswordArea.classList.add('hidden');
      unlockRecoveryArea.classList.add('hidden');
    }
  }

  function loadLoginScreen() {
    fetch('/vault/status')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        applyVaultStatus(data.initialized);
      })
      .catch(function () {
        applyVaultStatus(true);
      });
  }

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
        loadLoginScreen();
        throw new Error('Unauthorized');
      }
      return res;
    });
  }

  function setQuote(content, author) {
    if (!quoteText) return;
    quoteText.textContent = content ? '“' + content + '”' : '';
    if (quoteAuthor) {
      quoteAuthor.textContent = author ? '— ' + author : '';
    }
    if (quoteError) {
      quoteError.classList.add('hidden');
      quoteError.textContent = '';
    }
  }

  /** Set a static quote. No external API to avoid third-party dependency and failure surface. */
  function loadQuoteOfDay() {
    if (!quoteText) return;
    setQuote('Security is a process, not a product.', 'Bruce Schneier');
  }

  function showLogin(message) {
    vaultScreen.classList.add('hidden');
    vaultScreen.classList.remove('fade-in');
    loginScreen.classList.remove('hidden');
    loginScreen.classList.add('fade-in');
    loginError.classList.add('hidden');
    loginMessage.classList.remove('hidden');
    loginMessage.textContent = message || '';
    if (!message) loginMessage.classList.add('hidden');
    stopInactivityTimer();
    loadLoginScreen();
  }

  function showVault() {
    loginScreen.classList.add('hidden');
    loginScreen.classList.remove('fade-in');
    vaultScreen.classList.remove('hidden');
    vaultScreen.classList.add('fade-in');
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
   * Guards against missing clipboard API (e.g. non-HTTPS, old browsers).
   */
  function copyPassword(plaintext) {
    if (!navigator.clipboard || typeof navigator.clipboard.writeText !== 'function') {
      showVaultError('Clipboard not available. Copy the password manually.');
      return;
    }
    if (clipboardClearTimerId) clearTimeout(clipboardClearTimerId);
    navigator.clipboard.writeText(plaintext).then(function () {
      clipboardClearTimerId = setTimeout(function () {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText('');
        }
        clipboardClearTimerId = null;
      }, CLIPBOARD_CLEAR_MS);
    }).catch(function () {
      showVaultError('Could not copy to clipboard.');
    });
  }

  function hideCreateFolderForm() {
    addFolderForm.classList.remove('visible');
    newFolderNameInput.value = '';
  }

  function showRecoveryRequiredOverlay() {
    if (!recoveryRequiredOverlay) return;
    recoveryRequiredOverlay.classList.remove('hidden');
    recoveryRequiredChoices.classList.remove('hidden');
    recoveryRequiredKeyFlow.classList.add('hidden');
    recoveryRequiredQuestionsFlow.classList.add('hidden');
  }

  function hideRecoveryRequiredOverlay() {
    if (!recoveryRequiredOverlay) return;
    recoveryRequiredOverlay.classList.add('hidden');
  }

  function loadRecoveryStatus() {
    api('/recovery/status')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.configured) {
          setupRecoveryBtn.classList.add('hidden');
          recoveryConfiguredMsg.classList.remove('hidden');
          recoveryConfiguredMsg.textContent = 'Recovery is set (key or questions).';
          hideRecoveryRequiredOverlay();
        } else {
          setupRecoveryBtn.classList.remove('hidden');
          recoveryConfiguredMsg.classList.add('hidden');
          showRecoveryRequiredOverlay();
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
          addEntryForm.classList.remove('visible');
        });
        li.appendChild(btn);
        folderList.appendChild(li);
      });
      if (folderListEmpty) {
        if (folders.length === 0) folderListEmpty.classList.remove('hidden');
        else folderListEmpty.classList.add('hidden');
      }
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
      if (entryListEmpty) {
        if (entries.length === 0) entryListEmpty.classList.remove('hidden');
        else entryListEmpty.classList.add('hidden');
      }
    });
  }

  function showEntryDetail(entry) {
    entryDetail.innerHTML =
      '<p><strong>' + escapeHtml(entry.title) + '</strong></p>' +
      (entry.username ? '<p>Username: ' + escapeHtml(entry.username) + '</p>' : '') +
      (entry.url ? '<p>URL: <a href="' + escapeHtml(safeUrlForHref(entry.url)) + '" target="_blank" rel="noopener">' + escapeHtml(entry.url) + '</a></p>' : '') +
      (entry.notes ? '<p>Notes: ' + escapeHtml(entry.notes) + '</p>' : '') +
      '<button type="button" id="copy-detail-password">Copy password</button> ' +
      '<button type="button" id="edit-entry-btn" class="btn-secondary">Edit</button> ' +
      '<button type="button" id="delete-entry-btn" class="btn-secondary">Delete</button>' +
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
      '<button type="submit">Save</button> <button type="button" id="edit-cancel-btn" class="btn-secondary">Cancel</button>' +
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

  /** Only allow http/https in href to prevent javascript: or data: XSS. Returns '#' for unsafe schemes. */
  function safeUrlForHref(url) {
    if (!url || typeof url !== 'string') return '#';
    var trimmed = url.trim().toLowerCase();
    if (trimmed.indexOf('http://') === 0 || trimmed.indexOf('https://') === 0) return url.trim();
    return '#';
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
        if (document.getElementById('username')) document.getElementById('username').value = '';
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
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    if (!username) {
      loginError.textContent = 'Enter your username.';
      loginError.classList.remove('hidden');
      return;
    }
    if (!password.trim()) {
      loginError.textContent = 'Enter your master password.';
      loginError.classList.remove('hidden');
      return;
    }
    unlockWithPayload({ username: username, password: password });
  });

  document.getElementById('show-recovery-unlock').addEventListener('click', function () {
    unlockPasswordArea.classList.add('hidden');
    unlockRecoveryArea.classList.remove('hidden');
    var u = document.getElementById('username');
    var ru = document.getElementById('recovery-username-input');
    if (u && ru) ru.value = u.value;
    loginError.classList.add('hidden');
    recoveryKeyInput.value = '';
    if (ru) ru.focus(); else recoveryKeyInput.focus();
  });

  document.getElementById('back-to-password-btn').addEventListener('click', function () {
    unlockRecoveryArea.classList.add('hidden');
    unlockPasswordArea.classList.remove('hidden');
    recoveryKeyInput.value = '';
    loginError.classList.add('hidden');
  });

  document.getElementById('unlock-with-recovery-btn').addEventListener('click', function () {
    var ru = document.getElementById('recovery-username-input');
    var username = ru ? ru.value.trim() : '';
    var key = recoveryKeyInput.value.trim();
    if (!username) {
      loginError.textContent = 'Enter your username.';
      loginError.classList.remove('hidden');
      return;
    }
    if (!key) {
      loginError.textContent = 'Paste your recovery key.';
      loginError.classList.remove('hidden');
      return;
    }
    unlockWithPayload({ username: username, recovery_key: key });
  });

  document.getElementById('show-recovery-questions-unlock').addEventListener('click', function () {
    var ru = document.getElementById('recovery-username-input');
    var username = (ru ? ru.value.trim() : '') || (document.getElementById('username') ? document.getElementById('username').value.trim() : '');
    if (!username) {
      loginError.textContent = 'Enter your username first.';
      loginError.classList.remove('hidden');
      return;
    }
    unlockRecoveryArea.classList.add('hidden');
    unlockQuestionsArea.classList.remove('hidden');
    var qu = document.getElementById('questions-username-input');
    if (qu) qu.value = username;
    loginError.classList.add('hidden');
    fetch('/recovery/questions?username=' + encodeURIComponent(username))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.questions_configured || !data.questions || data.questions.length !== 3) {
          loginError.textContent = 'Security questions are not set up for this account.';
          loginError.classList.remove('hidden');
          return;
        }
        unlockQuestionsFormContainer.innerHTML = '';
        data.questions.forEach(function (q, i) {
          var label = document.createElement('label');
          label.setAttribute('for', 'unlock-answer-' + (i + 1));
          label.textContent = q || 'Question ' + (i + 1);
          var input = document.createElement('input');
          input.type = 'password';
          input.id = 'unlock-answer-' + (i + 1);
          input.placeholder = 'Your answer';
          input.dataset.index = String(i);
          unlockQuestionsFormContainer.appendChild(label);
          unlockQuestionsFormContainer.appendChild(input);
        });
      })
      .catch(function () {
        loginError.textContent = 'Could not load recovery questions.';
        loginError.classList.remove('hidden');
      });
  });

  document.getElementById('back-from-questions-btn').addEventListener('click', function () {
    unlockQuestionsArea.classList.add('hidden');
    unlockRecoveryArea.classList.remove('hidden');
    unlockQuestionsFormContainer.innerHTML = '';
    loginError.classList.add('hidden');
  });

  document.getElementById('unlock-with-questions-btn').addEventListener('click', function () {
    var qu = document.getElementById('questions-username-input');
    var username = qu ? qu.value.trim() : '';
    var inputs = unlockQuestionsFormContainer.querySelectorAll('input[type="password"]');
    if (!username) {
      loginError.textContent = 'Enter your username.';
      loginError.classList.remove('hidden');
      return;
    }
    if (!inputs || inputs.length !== 3) {
      loginError.textContent = 'Answer all three questions.';
      loginError.classList.remove('hidden');
      return;
    }
    var answers = [inputs[0].value, inputs[1].value, inputs[2].value];
    if (answers.some(function (a) { return !a.trim(); })) {
      loginError.textContent = 'Answer all three questions.';
      loginError.classList.remove('hidden');
      return;
    }
    loginError.classList.add('hidden');
    unlockWithPayload({ username: username, recovery_answers: answers });
  });

  /**
   * Submit auth form (setup or signup). Validates username, password, confirm; POSTs to endpoint; on success shows vault.
   * @param {string} endpoint - '/setup' or '/signup'
   * @param {string} usernameId - id of username input
   * @param {string} passwordId - id of password input
   * @param {string} confirmId - id of confirm input
   * @param {string} errorMsg - e.g. 'Setup failed' or 'Signup failed'
   * @param {function} [onSuccess] - optional cleanup (e.g. hide signup area, clear fields)
   */
  function submitAuthForm(endpoint, usernameId, passwordId, confirmId, errorMsg, onSuccess) {
    var username = document.getElementById(usernameId).value.trim();
    var pwd = document.getElementById(passwordId).value;
    var confirmVal = document.getElementById(confirmId).value;
    loginError.classList.add('hidden');
    if (!username) {
      loginError.textContent = 'Enter a username.';
      loginError.classList.remove('hidden');
      return;
    }
    if (pwd !== confirmVal) {
      loginError.textContent = 'Passwords do not match.';
      loginError.classList.remove('hidden');
      return;
    }
    if (!pwd.trim()) {
      loginError.textContent = 'Enter a password.';
      loginError.classList.remove('hidden');
      return;
    }
    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username, password: pwd }),
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || errorMsg); });
        return r.json();
      })
      .then(function (data) {
        setSessionId(data.session_id);
        document.getElementById(usernameId).value = '';
        document.getElementById(passwordId).value = '';
        document.getElementById(confirmId).value = '';
        if (onSuccess) onSuccess();
        showVault();
        loadFolders().then(function () { loadRecoveryStatus(); });
      })
      .catch(function (err) {
        loginError.textContent = err.message || errorMsg;
        loginError.classList.remove('hidden');
      });
  }

  setupForm.addEventListener('submit', function (e) {
    e.preventDefault();
    submitAuthForm('/setup', 'setup-username', 'setup-password', 'setup-confirm', 'Setup failed');
  });

  if (document.getElementById('show-signup')) {
    document.getElementById('show-signup').addEventListener('click', function () {
      unlockPasswordArea.classList.add('hidden');
      document.getElementById('signup-area').classList.remove('hidden');
      loginError.classList.add('hidden');
    });
  }
  if (document.getElementById('back-from-signup')) {
    document.getElementById('back-from-signup').addEventListener('click', function () {
      document.getElementById('signup-area').classList.add('hidden');
      unlockPasswordArea.classList.remove('hidden');
      loginError.classList.add('hidden');
    });
  }
  if (document.getElementById('signup-form')) {
    document.getElementById('signup-form').addEventListener('submit', function (e) {
      e.preventDefault();
      submitAuthForm('/signup', 'signup-username', 'signup-password', 'signup-confirm', 'Signup failed', function () {
        document.getElementById('signup-area').classList.add('hidden');
        unlockPasswordArea.classList.remove('hidden');
      });
    });
  }

  document.getElementById('reset-vault-btn').addEventListener('click', function () {
    var username = prompt('Enter your username to reset the vault (for testing). This will delete all data.');
    if (username === null || username === '') return;
    var pwd = prompt('Enter your master password to confirm.');
    if (pwd === null || pwd === '') return;
    fetch('/vault/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username, password: pwd }),
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || 'Reset failed'); });
        return r.json();
      })
      .then(function () {
        setSessionId(null);
        showLogin('Vault reset. You can create a new vault below.');
      })
      .catch(function (err) {
        showVaultError(err.message || 'Reset failed.');
      });
  });

  lockBtn.addEventListener('click', function () {
    lock();
  });

  addFolderBtn.addEventListener('click', function () {
    addFolderForm.classList.add('visible');
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
    addEntryForm.classList.add('visible');
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
        addEntryForm.classList.remove('visible');
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

  if (document.getElementById('recovery-required-key')) {
    document.getElementById('recovery-required-key').addEventListener('click', function () {
      recoveryRequiredChoices.classList.add('hidden');
      api('/recovery/setup', { method: 'POST' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          recoveryRequiredKeyDisplay.textContent = data.recovery_key;
          recoveryRequiredKeyFlow.classList.remove('hidden');
          resetInactivityTimer();
        })
        .catch(function (err) {
          if (err.message !== 'Unauthorized') showVaultError(err.message || 'Failed to set up recovery key.');
        });
    });
  }
  if (document.getElementById('recovery-required-copy-btn')) {
    document.getElementById('recovery-required-copy-btn').addEventListener('click', function () {
      const key = recoveryRequiredKeyDisplay.textContent;
      if (key) copyPassword(key);
      resetInactivityTimer();
    });
  }
  if (document.getElementById('recovery-required-saved-btn')) {
    document.getElementById('recovery-required-saved-btn').addEventListener('click', function () {
      recoveryRequiredKeyDisplay.textContent = '';
      recoveryRequiredKeyFlow.classList.add('hidden');
      recoveryRequiredChoices.classList.remove('hidden');
      loadRecoveryStatus();
      resetInactivityTimer();
    });
  }
  if (document.getElementById('recovery-required-questions')) {
    document.getElementById('recovery-required-questions').addEventListener('click', function () {
      recoveryRequiredChoices.classList.add('hidden');
      recoveryRequiredQuestionsFlow.classList.remove('hidden');
      resetInactivityTimer();
    });
  }
  if (document.getElementById('recovery-questions-setup-form')) {
    document.getElementById('recovery-questions-setup-form').addEventListener('submit', function (e) {
      e.preventDefault();
      const payload = {
        question_1: document.getElementById('req-q1').value.trim(),
        question_2: document.getElementById('req-q2').value.trim(),
        question_3: document.getElementById('req-q3').value.trim(),
        answer_1: document.getElementById('req-a1').value,
        answer_2: document.getElementById('req-a2').value,
        answer_3: document.getElementById('req-a3').value,
      };
      if (!payload.question_1 || !payload.question_2 || !payload.question_3 || !payload.answer_1 || !payload.answer_2 || !payload.answer_3) {
        showVaultError('Fill in all three questions and answers.');
        return;
      }
      api('/recovery/setup-questions', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
        .then(function (r) {
          if (r.status !== 204) return r.json().then(function () { throw new Error('Setup failed'); });
        })
        .then(function () {
          recoveryRequiredQuestionsFlow.classList.add('hidden');
          recoveryRequiredChoices.classList.remove('hidden');
          document.getElementById('req-q1').value = '';
          document.getElementById('req-q2').value = '';
          document.getElementById('req-q3').value = '';
          document.getElementById('req-a1').value = '';
          document.getElementById('req-a2').value = '';
          document.getElementById('req-a3').value = '';
          hideRecoveryRequiredOverlay();
          loadRecoveryStatus();
          resetInactivityTimer();
        })
        .catch(function (err) {
          if (err.message !== 'Unauthorized') showVaultError(err.message || 'Failed to save recovery questions.');
        });
    });
  }

  // Load side-panel quote once per day (per browser).
  loadQuoteOfDay();

  // On load: if we have a session, try to use it; else show login/setup and fetch vault status
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
  } else {
    loadLoginScreen();
  }
})();
