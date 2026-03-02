# How the Password Vault Application Works

This guide gives **plain-language, step-by-step instructions** for running and using the vault. It is written so that someone who has never used the app (or the command line much) can follow it. **The guide is updated whenever we add features**—new sections are added at the bottom and the "What’s included" list is updated.

---

## What’s included (as of this version)

- **First-time setup** — When you open the app and no vault exists yet, you see a **Create your vault** form: choose a master password (and confirm it), then click **Create vault**. You are then logged in. No command line required.
- **Unlock / lock** — You type one master password to open the vault; the app remembers you’re logged in until you click Lock or leave it idle for 15 minutes.
- **Folders** — You can see a list of folders (like "Personal"). Each folder holds a list of saved logins.
- **Entries** — Each entry is one saved login: a title, username, password, optional website URL, and optional notes. You can view them and copy the password. The app clears the password from your clipboard 30 seconds after you copy it.
- **Add entry** — You can create a new saved login: type in the details and click Save. There is a **Generate** button that creates a random password for you.
- **Audit log** — The app writes a log file of actions (like "user unlocked" or "user created an entry") for your records. Passwords are never written to this log.
- **Recovery (required after first login)** — Right after you create the vault or log in for the first time, the app asks you to set up recovery. You must choose one: **recovery key** (a long one-time key to save offline) or **3 security questions** (three questions and answers you’ll remember). If you forget your master password later, you can unlock using either the recovery key or by answering the three questions.
- **Create folder** — You can create new folders from the web page.
- **Edit and delete entry** — You can edit or delete a saved login from its detail view.
- **Search** — You can search entries by title, username, URL, or notes.

*Not yet: file attachments, or separate logins for different people.*

---

## Before you begin: what you need

- The **password-vault-app** folder on your computer (the one that contains files like `README.md`, `requirements.txt`, and a folder named `src`).
- A **terminal** (also called command line): on Ubuntu you can open it with Ctrl+Alt+T, or from your menu search for "Terminal." On Windows, use "Command Prompt" or "PowerShell."
- A **web browser** (Chrome, Firefox, Edge, Safari, etc.).
- **First time only:** You must have already run the one-time setup so that a vault database exists and you have a master password. If you haven’t, follow the section **"First-time setup: create the vault and a master password"** below before starting the server.

---

## How to run the application (start the server)

Follow these steps **every time** you want to use the vault in your browser. The server is the program that runs in the background and talks to your browser.

### Step 1: Open the terminal and go to the project folder

1. Open your **terminal** (see "Before you begin" above).
2. Type this **exactly** (including the quotes), then press **Enter**:
   ```text
   cd "/home/sean/Cursor Projects/password-vault-app"
   ```
   - **What this does:** It moves you into the folder where the vault app lives. If your project is in a different place (for example on another computer), change the path to match. For example, if the folder is on your Desktop, it might be: `cd ~/Desktop/password-vault-app`
3. **You should see:** The line of text that appears before your cursor (the "prompt") might now show something like `password-vault-app` or the path to that folder. You are now "in" the project folder.

### Step 2: Turn on the virtual environment

1. In the **same terminal window**, type this and press **Enter**:
   ```text
   source .venv/bin/activate
   ```
   - **On Windows**, use this instead: ` .venv\Scripts\activate `
2. **What this does:** It activates a small, isolated set of Python packages used only for this project (the "virtual environment"), so the next command can find the right program to start the server.
3. **You should see:** The start of each line in the terminal may now show `(.venv)`, meaning the environment is active.

### Step 3: Start the server

1. In the **same terminal**, type this **entire line** and press **Enter**:
   ```text
   VAULT_DB_PATH=demo_vault.db uvicorn vault.api.main:app --host 127.0.0.1 --port 8001
   ```
   - **What this does:** It starts the vault server. `VAULT_DB_PATH=demo_vault.db` tells the app to use the database file named `demo_vault.db` in the project folder (this is the file created by the first-time setup). The rest of the command starts the web server on port 8001 on your own computer only (127.0.0.1).
2. **You should see:** Several lines of text, and then a line that says something like: **"Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)"**. That means the server is running.
3. **Important:** **Do not close this terminal window** and **do not press Ctrl+C** while you want to use the vault. If you close the terminal or press Ctrl+C, the server stops and the vault will not load in the browser.

### Step 4: Open the vault in your browser

1. Open your **web browser** (Chrome, Firefox, Edge, Safari, etc.).
2. In the **address bar** at the top, type exactly:
   ```text
   http://127.0.0.1:8001/
   ```
   Then press **Enter**.
3. **You should see:** A page with the title **"Vault"** and a box asking for **"Master password"** with an **Unlock** button. This is the vault login page. If you see an error like "Cannot connect" or "This site can’t be reached," the server is not running—go back to Step 3 and make sure the terminal still shows "Uvicorn running" and that you did not close it.

You have now started the application. Use the sections below to log in and use the vault.

---

## First-time setup: create the vault and a master password

Do this **only once**, when you have never created a vault on this device (no existing vault database).

**Option A — In the browser (recommended):**

1. Start the server (see "How to run the application", Steps 1–3) and open **http://127.0.0.1:8001/** in your browser.
2. If the vault has not been set up yet, you will see **"First time here?"** with a short explanation and two fields: **Choose master password** and **Confirm master password**.
3. Enter a **master password** in both fields (they must match). Choose something strong; you will use this every time you unlock the vault.
4. Click **Create vault**.
5. **You should see:** The vault opens and a **“Set up recovery (required)”** screen appears. You must choose one option before you can use the vault:
   - **Use recovery key** — The app shows a long one-time key. Copy or print it and store it somewhere safe. You will not see it again. If you forget your master password, you can unlock by pasting this key.
   - **Use 3 security questions** — Enter three questions (e.g. “What was your first pet’s name?”) and the answers. Choose questions only you know; avoid answers that others could guess or find online. If you forget your master password, you can unlock by answering these three questions.
6. After you complete one of these, the recovery screen closes and you can create folders, add entries, and use the vault. **Remember your master password**—you need it to unlock next time (unless you use the recovery key or security questions).

**Option B — Using the command-line script:**

1. Open the terminal and go to the project folder (see **Step 1** under "How to run the application").
2. Activate the virtual environment (see **Step 2**).
3. Run: `VAULT_DB_PATH=demo_vault.db python scripts/phase2_demo.py`
4. When prompted, type a master password and press **Enter**. The script creates the vault and a sample folder and entry.
5. Start the server and open the app in the browser; use that same password to unlock.

**Reset vault (for testing only):** If you created a test vault (e.g. with password "test") and want to start over, click **Reset vault (for testing)** below the Lock button, enter your master password when prompted, and confirm. The vault will be deleted and the next time you open the app you will see the first-time setup form again.

---

## Step-by-step: Unlock (log in)

1. Make sure the **server is running** (see "How to run the application") and you have opened **http://127.0.0.1:8001/** in your browser.
2. **You should see:** A page titled **Vault** with a field labeled **"Master password"** and a button labeled **Unlock**.
3. Click inside the **Master password** box and type the same master password you used when you ran the first-time setup (or the one you chose for this vault). The characters may appear as dots or asterisks; that is normal.
4. Click the **Unlock** button (or press Enter).
5. **If the password is correct:** The page will change. You will no longer see the password box. Instead you will see:
   - A **Lock** button at the top
   - A heading **Folders** and under it at least one folder name (e.g. **Personal**)
   - A heading **Entries** and a list of entries (or "Entries" with nothing under it until you click a folder)
   - An **Add entry** button
   This is your **vault view**—you are now logged in.
6. **If the password is wrong:** You will stay on the same page and may see an error message. Check that you typed the correct master password and try again. If you never ran the first-time setup, do that first (see the section above).
7. **If you forgot your password:** You can unlock using **recovery** (if you set it up):
   - **Recovery key:** Click **"Forgot your password? Use your recovery key instead."** A text box will appear. Paste the long recovery key you saved when you set it up, then click **Unlock with recovery key**. You can click **"Back to password"** to return to the password box.
   - **3 security questions:** Click **"Or unlock with 3 security questions."** The app will show the three questions you chose. Type your three answers (they are case-sensitive), then click **Unlock with answers**. You can click **Back** to return to the recovery key or password options.

---

## Recovery: set up and use

- **Mandatory after first login:** Right after you create the vault or the first time you unlock, the app shows a **"Set up recovery (required)"** screen. You must choose one option before you can use the vault: **Use recovery key** (long key to save offline) or **Use 3 security questions** (three questions and answers you’ll remember). You cannot skip this step.
- **Recovery key option:** If you choose **Use recovery key**, the app shows a long key **once**. Copy it and store it somewhere safe offline, then click **"I've saved it"**. You can use this key later to unlock if you forget your master password (see step 7 under "Unlock" above).
- **3 security questions option:** If you choose **Use 3 security questions**, type three questions (e.g. “What was your first pet’s name?”) and the answers. Pick questions only you know; avoid answers that others could guess or find online. Click **Save recovery questions**. You can unlock later by answering these three questions (see step 7 under "Unlock" above).
- **Already set:** If you have already set up recovery (key or questions), the **"Set up recovery key"** button appears only when you have not set recovery yet. Once recovery is set, you will see **"Recovery is set (key or questions)."**

---

## Step-by-step: Use the vault

### View your folders and entries

1. **You should see** a list of **Folders** (e.g. **Personal**). Each folder name is a **button** you can click.
2. **Click one folder name** (e.g. **Personal**). The list under **Entries** will update to show all the saved logins in that folder. If the folder is empty, the entries list will be empty.
3. **Click one entry** (one of the titles in the Entries list). A **detail box** will appear below showing that entry’s **title**, **username**, **password**, **URL** (if any), and **notes** (if any).
4. To **copy the password** for that entry to your computer’s clipboard (so you can paste it into a website or app), click the **Copy password** button in that detail box. The app will copy it. **Important:** For your security, the app will **clear your clipboard** (remove the password from it) **30 seconds** after you copy. So paste the password where you need it within 30 seconds. Do not rely on it still being in the clipboard later.

### Add a new entry (save a new login)

1. **First, click a folder** so the app knows which folder to put the new entry in. The folder you clicked is the one that will get the new entry.
2. Click the **Add entry** button.
3. **You should see** a form with boxes: **Title**, **Username**, **Password**, **URL**, **Notes**, and buttons **Generate** and **Save**.
4. Type a **Title** (required). For example: "Bank website" or "Netflix." This is the label you’ll see in the list.
5. Optionally fill in **Username**, **Password**, **URL**, and **Notes**.
6. **Optional:** If you want a random password, click the **Generate** button. The **Password** box will be filled with a new random password. You can then copy it and use it when signing up or changing a password on a site.
7. Click the **Save** button.
8. **You should see:** The form will disappear and the **Entries** list will refresh. Your new entry will appear. You can click it to view it or to copy its password.

### Lock (log out)

1. When you are done using the vault, click the **Lock** button at the top of the page.
2. **You should see:** The page will return to the **login** screen (the one with the Master password box and Unlock button). You are now logged out. No one can see your entries until they enter the master password again. To use the vault again, type your master password and click Unlock.

---

## Step-by-step: What happens if you leave the vault idle (session timeout)

1. After you have **unlocked** the vault, if you **do nothing**—no clicking, no typing—for **15 minutes**, the app will **automatically lock** you out.
2. The next time you **click or type** on the page, the app will notice that your session has expired. The page will switch back to the **login** screen and you may see a message like "Session expired or invalid."
3. To continue, **enter your master password again** and click **Unlock**. Your folders and entries are still there; you just have to log in again. This behavior is for security so that if you walk away from the computer, the vault locks itself after a short time.

*(If you want to change how many minutes of inactivity before lock-out, you can set an environment variable when starting the server; see the "Configuration (optional)" section at the end.)*

---

## How the pieces fit together (for the curious)

| Part | What it does in simple terms |
|------|------------------------------|
| **Your browser** | Shows you the login page and the vault page. It keeps a small "session" token so the server knows it’s you. When you click "Copy password," it copies to the clipboard and then clears the clipboard 30 seconds later. |
| **The server (the program you start with uvicorn)** | Runs on your computer and does the real work: it checks your password, reads and writes your saved logins, and encrypts or decrypts them. It also sends the web pages (login and vault) to your browser. |
| **The database file (e.g. demo_vault.db)** | A single file on your computer that stores all your folders and entries. The sensitive parts (passwords, usernames, etc.) are stored in an encrypted form so that only someone with the correct master password can read them. |
| **The audit log (e.g. audit.log)** | A separate file that records *that* something happened (e.g. "user unlocked," "user created an entry") and when. It does **not** record your password or the contents of your entries. |

---

## Configuration (optional)

If you want to change where the app looks for the database, how long before it locks you out, or where it writes the audit log, you can set these **before** the `uvicorn` command when you start the server:

- **VAULT_DB_PATH** — The path to the database file. Example: `demo_vault.db` (in the current folder). Default if you don’t set it: `vault.db`.
- **VAULT_SESSION_TIMEOUT_MINUTES** — How many minutes of no activity before the vault locks. Default: `15`.
- **VAULT_AUDIT_LOG_PATH** — The path to the audit log file. Default: `audit.log`.

**Example:** To use the database file `demo_vault.db` and the audit log file `audit.log` in the current folder, you would run:

```text
VAULT_DB_PATH=demo_vault.db VAULT_AUDIT_LOG_PATH=./audit.log uvicorn vault.api.main:app --host 127.0.0.1 --port 8001
```

You can type that as one long line in the terminal (after activating the virtual environment) and press Enter.

---

For a **line-by-line and block-by-block explanation** of the code (what each part does, where it connects, and which standards and algorithms we use), see **[EDUCATIONAL_CODE_WALKTHROUGH.md](EDUCATIONAL_CODE_WALKTHROUGH.md)**. That document is updated whenever we add or change code.

*Last updated: after adding mandatory recovery setup (key or 3 security questions) and unlock by questions.*
