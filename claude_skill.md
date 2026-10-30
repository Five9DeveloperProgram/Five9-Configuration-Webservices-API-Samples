---
name: five9-config-api
description: For Cowork users. Set up and use the Five9 Configuration Webservices Python wrapper (Five9DeveloperProgram/Five9-Configuration-Webservices-API-Samples) to manage Five9 Contact Center domains. Walks the user through installing Python and git on Windows or macOS, cloning the repo, creating a virtual environment, and storing credentials. Then helps create users and skill assignments, upload contacts and list data, and run the domain documentation utilities, always with a dry run and confirmation before any write. Use this skill whenever the user mentions Five9 admin API, Five9 domain configuration, bulk user or skill creation, uploading contacts or lists to Five9, Five9 domain documentation, the Five9 Python wrapper, or wants to script Five9 administration, even if they never name the repo.
---

# Five9 Configuration Webservices helper

This skill gets a user from a bare machine to running Five9 domain administration tasks with the official Python wrapper. Many users are admins, not developers, so explain each step in plain language and confirm each step worked before moving on.

The repo is unsupported by Five9 and provided as-is under the MIT license. Say so once, briefly, during setup, and remind the user to try changes in a non-production domain when one is available.

## Where things run (Cowork)

Our team uses Cowork, not Claude Code. Two facts shape everything below:

- **Claude's shell is a sandbox, not the user's computer.** Anything Claude runs (python, pip, git) happens in an isolated Linux environment. Python, git, the virtual environment, and credentials the user sets up on their own machine are separate from it, and the sandbox may not be able to reach Five9 at all.
- **Claude can only see folders the user shares.** Without a shared folder, Claude cannot read the cloned repo or save scripts where the user can find them.

So the working model is: Claude guides and writes, the user runs locally. Claude reads the repo and writes scripts into the shared folder. The user runs those scripts in their own terminal, where Python and credentials live, then pastes back output or errors. Credentials never leave the user's machine.

### Step 0: Get a folder into the chat

Do this before anything else. If no folder is connected, request one with the folder access tool (`mcp__cowork__request_cowork_directory`, load via ToolSearch if needed) and ask the user to pick or create a folder such as `Five9-Admin` in Documents. The repo gets cloned inside it, and generated scripts, CSV inputs, and logs live beside it.

Then offer a one-time convenience: a project that points at this folder, so future sessions start with it already attached. Mention it once; do not insist. If they want it, give these steps:

1. In the navigation panel in Claude, click the "+" icon next to Projects.
2. In the "Create a project" dialog, name it "Five9 Configuration Webservices APIs" under "What are you working on?".
3. Click "Use a folder" and choose the folder where the repository was cloned (or its parent, such as `Five9-Admin`).
4. Leave "What are you trying to achieve?" blank. It looks optional, and this skill plus the repo's README already say what the project is for.
5. Leave Visibility on "Private" (public projects are disabled by the organization, and the folder holds credentials-adjacent files).
6. Click "Create project", then start new chats from inside that project.

## Source of truth

The repo changes. Do not rely on memory for module names, function signatures, or install commands. After cloning, read the repo's `README.md` and skim its top-level layout and examples, then follow what they say. Use the steps below as the scaffold and let the README override them on any conflict.

Repo: https://github.com/Five9DeveloperProgram/Five9-Configuration-Webservices-API-Samples

## Part 1: Environment setup

Complete Step 0 first. Detect the user's OS (ask if unclear). Every command in this part is for the user to run in their own terminal (**PowerShell 7 on Windows**, Terminal on macOS), one at a time. Ask them to paste the output so you can confirm it worked. Check what is already installed before telling them to install anything.

### Windows: use PowerShell 7, not PowerShell ISE

**Do not run this library or its scripts in Windows PowerShell ISE.** The library does not work well there, especially when interactive terminal input is needed. ISE is a legacy editor tied to Windows PowerShell 5.1; installing PowerShell 7 does not upgrade ISE. Use a separate PowerShell 7 terminal for all setup and script execution.

Do not assume the user knows which app they have open. Guide them through these checks one at a time, waiting for each result:

1. **Identify the current shell.** If the window title says "Windows PowerShell ISE", they are in ISE. If unsure, have them run these harmless checks in their current PowerShell command pane:
   ```powershell
   $Host.Name
   $PSVersionTable.PSVersion
   ```
   `Windows PowerShell ISE Host` means ISE. A version whose `Major` is `5` means legacy Windows PowerShell, even if it is not ISE. For this guide, use PowerShell 7 (`Major` is `7`) in a non-ISE terminal. Windows Terminal and VS Code can host different shells; their window titles alone do not prove PowerShell 7 is running.
2. **Open PowerShell 7 if already installed.** Search the Windows Start menu for **PowerShell 7** and open it, not "Windows PowerShell" or "Windows PowerShell ISE". Alternatively, press **Win+R**, enter `pwsh`, and press Enter to launch it separately. Do not try to run `pwsh` inside ISE's command pane.
3. **Install PowerShell 7 only if it is missing.** Open ordinary **Windows PowerShell** from Start (not ISE) for this installation step only, and run:
   ```powershell
   winget install --id Microsoft.PowerShell --source winget
   ```
   If `winget` is unavailable, guide them through the stable Windows installer appropriate for their machine using [Microsoft's PowerShell installation instructions](https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows). If company policy or administrator approval blocks installation, ask them to contact IT rather than bypassing the restriction. PowerShell 7 installs alongside Windows PowerShell; they do not need to remove the old version.
4. **Verify the new terminal before continuing.** Open PowerShell 7 from Start or by entering `pwsh` in **Win+R**, then repeat both checks from step 1 there. Confirm `Major` is `7` and the host is not ISE. In Windows Terminal, select the **PowerShell 7** profile from the tab dropdown if available, then verify; an existing "Windows PowerShell" tab stays on the old version.
5. **Keep using that terminal.** Run the remaining setup and Python scripts in PowerShell 7, not ISE's Run button. When opening a new terminal or switching from ISE, navigate back to the repository with `cd` and reactivate the virtual environment if it already exists, using the path chosen during setup. Do not assume the new terminal retains the old terminal's working directory or activated environment.

If a Windows user later reports a stuck prompt, missing password input, or unusual terminal behavior, recheck the host and version before changing Python code. A password prompt normally shows no characters as they type; that alone is not a failure. Never ask them to paste their password.

### Install and configure the Python environment

1. **Check for Python and git.**
   - Windows: `python --version` and `git --version` in the verified PowerShell 7 terminal. If `python` opens the Microsoft Store, Python is not installed.
   - macOS: `python3 --version` and `git --version` in Terminal. macOS may prompt to install Xcode command line tools for git; that is fine.
2. **Install what is missing.**
   - Python: current stable 3.x from https://www.python.org/downloads/. On Windows, tell them to tick "Add python.exe to PATH" in the installer. On macOS, the python.org installer or `brew install python` both work.
   - git: Windows from https://git-scm.com/download/win (defaults are fine). macOS via `xcode-select --install` or `brew install git`.
   - Ask them to open a new terminal afterward (PowerShell 7 on Windows, not ISE), since PATH changes only apply to new sessions.
3. **Clone the repo** into the shared folder from Step 0. Have the user `cd` into it first, since Claude cannot clone to their machine. Once cloned, Claude can read the README and code through the shared folder.
   `git clone https://github.com/Five9DeveloperProgram/Five9-Configuration-Webservices-API-Samples.git`
   If git is a blocker, the repo's "Download ZIP" option works too.
4. **Create and activate a virtual environment** inside the repo folder, using the commands in the README. Typical forms:
   - Windows: `python -m venv venv` then `venv\Scripts\Activate.ps1` (if PowerShell blocks scripts, suggest `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, and explain what it does).
   - macOS: `python3 -m venv venv` then `source venv/bin/activate`.
5. **Install dependencies** with whatever the README specifies (usually `pip install -r requirements.txt`). Confirm it finishes without errors.
6. **Credentials: prompt at run time, store nothing.** Do not create a `credentials.py` or any file, environment variable, or script argument that holds a username or password. The Five9 client in the library asks for the username and password in the terminal, and the password field is hidden as the user types. Every script you write must rely on that prompt, with no hardcoded or saved credentials. Tell the user to expect the prompt each run and to use a dedicated admin API user. Never ask them to paste a password into chat.
7. **Smoke test.** Give the user a harmless read-only call to run in their own terminal (for example, fetching domain info, using the entry point the README describes). They type their credentials at the prompt and paste back the output. This proves credentials and connectivity work.

If anything fails, read the error, explain it plainly, and fix it before continuing. Common causes: Python not on PATH, venv not activated, wrong data center or API user permissions.

## Part 2: Using the wrapper

Supported task areas, in order of priority:

- **Users and skills.** Create users, set roles, assign skills and skill levels, in bulk from a CSV when the user has many.
- **Contacts and lists.** Upload contact records to lists, map CSV columns to Five9 contact fields, and check results.
- **Domain documentation utilities.** Run the repo's utilities that export or document domain configuration.

For each task, read the relevant module or example in the cloned repo (through the shared folder), then write a short script into a `scripts/` folder beside the repo, not inside it, so a `git pull` never collides with the user's work. Scripts must never contain credentials; they rely on the library's run-time prompt, which cannot work in Claude's sandbox anyway because it needs an interactive terminal and a route to Five9. Give the user the exact command to run it from their activated virtual environment, and ask them to paste back the output. Do not run Five9 calls from the sandbox.

## Which domain? The username decides

Users often say things like "I need to do this on a customer domain." The Five9 username they type at the login prompt determines which domain the script works in, so there is no domain name to ask about or configure. Do not quiz the user about domain names. Instead:

- **Geography is the one exception.** The library defaults to the US API hostname. If the user's domain is outside the US (for example EU, Canada, or another region), the script must point at that region's API hostname, or login will fail or hit the wrong place. Ask one short question the first time: "Is this domain in the US, or another region?" Skip it if they have already said. For non-US domains, read the README and code to find how the library sets the hostname or region, and set it in the script. Do not guess the hostname or the setting name. If a login fails with a connection or authentication error on a domain the user says is valid, check the region first.
- Tell them to log in with a username that belongs to the target domain and has API permissions (an admin user with access to the Configuration Web Services API). If login fails with a permissions error, that is the first thing to check.
- For several domains, they run the script once per domain and enter that domain's username each time.
- Because this is the only guard against writing to the wrong domain, ask them to confirm the target during the dry run ("this will run against the domain your login belongs to") and to say whether it is production. Ask once, in one line, not as an interview.

## Safety: dry run, then confirm

Every write to a live domain (creating or modifying users, skills, lists, contacts) follows this order:

1. **Validate the input.** Check the CSV or data for missing required fields, duplicates, and malformed values. Report problems and stop.
2. **Dry run.** Read the current domain state, compare it with the requested change, and show a plain summary: what will be created, updated, or skipped, with counts and a sample.
3. **Confirm.** Wait for an explicit yes. A vague reply is not a yes.
4. **Execute**, logging each result to a file.
5. **Verify.** Re-read the domain and confirm the changes landed. Report any failures with the reason.

Reads (including documentation utilities) need no confirmation. Deletions get an extra, separate confirmation naming exactly what will be removed.

## Style

Keep replies short and concrete. Give one step at a time during setup and wait for the result. Show exact commands in code blocks, matched to the user's OS.