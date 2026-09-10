#!/bin/bash
# Sets up the Mac mini so it can do the jobs that need a machine of Andrew's own.
#
# Run it as many times as you like. It changes nothing that is already right, and
# it ends by telling you exactly what is done and what is still waiting.
#
# Written 2026-09-07.
# 2026-09-09: step 4 rewritten. It can now put the code into a folder you made
#             yourself and already dropped the keys into, which is what actually
#             happened on the first real machine. It also repairs a copy that has
#             lost track of where it came from, and it no longer blames the
#             internet for problems that have nothing to do with the internet.
# 2026-09-09: step 2 no longer invents a job. Apple silicon will not report the
#             power-cut restart setting back, and the file was reading that
#             silence as the setting being off, then telling Andrew to go and
#             turn on something that was already on.

READY=()
LEFT=()

ok()   { echo "   DONE   $1"; READY+=("$1"); }
todo() { echo "   TO DO  $1"; LEFT+=("$1"); }
note() { echo "   NOTE   $1"; }
line() { echo "  --------------------------------------------------------------------"; }
head2() { echo; line; echo "  $1"; line; }

FOLDER="$HOME/Documents/store-music"
REPO="https://github.com/andrewding80-afk/store-music.git"

echo
echo "  ===================================================================="
echo "    SETTING UP THE MAC MINI"
echo "  ===================================================================="
echo
echo "  This machine exists to do the two kinds of job that cannot run on a"
echo "  rented machine in the cloud: the ones that need a browser which stays"
echo "  signed in, and the ones that have to be on your home wifi."
echo
echo "  Nothing here is destructive. It can be run again at any time."
echo
read -r -p "  Press Enter to start, or Ctrl and C to stop. " _

# ------------------------------------------------------------------ 1. the machine
head2 "STEP 1 of 6.  The machine itself"

if [ "$(uname)" != "Darwin" ]; then
  echo "  This is not a Mac. Nothing here applies. Stopping."
  exit 1
fi
echo "  Computer name:  $(scutil --get ComputerName 2>/dev/null || echo unknown)"
echo "  macOS version:  $(sw_vers -productVersion 2>/dev/null || echo unknown)"

if ifconfig en0 2>/dev/null | grep -q "status: active" && \
   networksetup -listallhardwareports 2>/dev/null | grep -A1 "Ethernet" | grep -q en0; then
  ok "wired to the router"
else
  if route get default 2>/dev/null | grep -q "interface: en"; then
    echo "   NOTE   cannot tell whether this is wired or on wifi."
  fi
  todo "plug an ethernet cable from this machine to the router, if you have not"
fi

# ------------------------------------------------------------------ 2. never sleep
head2 "STEP 2 of 6.  Never sleep, and come back on its own after a power cut"

echo "  A sleeping machine is a job that silently stops, and a machine that stays"
echo "  dark after a power cut is the same thing for longer."
echo
echo "  This needs your Mac password. Nothing else here does."
echo

# Both settings below are applied first, then read back. The read back is the
# part that has to be careful. On Apple silicon, pmset will not report the
# power-cut restart setting at all, and on 2026-09-09 that silence was being
# read as the setting being off, which put a job on Andrew's list that he had
# already done. Nothing read back means nothing is known. It does not mean off.
if sudo -n true 2>/dev/null || sudo -v; then
  sudo pmset -a sleep 0 >/dev/null 2>&1
  sudo pmset -a disksleep 0 >/dev/null 2>&1
  sudo pmset -a autorestart 1 >/dev/null 2>&1
  sudo pmset -a womp 1 >/dev/null 2>&1
  SLEEPVAL=$(pmset -g custom 2>/dev/null | awk '/ sleep/{print $2; exit}')
  # Match the field name exactly. A loose /autorestart/ matches the line
  # "autorestartatconnect 0" first and exits, so this read 0 while the real
  # setting was 1, and the script told Andrew to go and turn on something that
  # had been on for days. Found 2026-09-10.
  AUTOVAL=$(pmset -g custom 2>/dev/null | awk '$1=="autorestart"{print $2; exit}')

  if [ "$SLEEPVAL" = "0" ]; then
    ok "set never to sleep"
  elif [ -z "$SLEEPVAL" ]; then
    ok "set never to sleep"
    note "this machine will not say the sleep setting back, so it cannot be double checked here"
  else
    todo "set it never to sleep by hand, in System Settings, Energy"
  fi

  if [ "$AUTOVAL" = "1" ]; then
    ok "set to start itself again after a power cut"
  elif [ -z "$AUTOVAL" ]; then
    ok "set to start itself again after a power cut"
    note "this machine will not say that setting back, which is normal on Apple silicon."
    note "to see it for yourself: System Settings, Energy, Start up when power is connected"
  else
    todo "turn on Start up automatically after a power failure, in System Settings, Energy"
  fi
else
  todo "set never to sleep, and start up after a power failure, in System Settings, Energy"
fi

# ------------------------------------------------------------------ 3. tools
head2 "STEP 3 of 6.  The two tools everything is built on"

MISSING_TOOLS=0
if command -v git >/dev/null 2>&1; then ok "git is installed"; else MISSING_TOOLS=1; fi
if command -v python3 >/dev/null 2>&1; then
  ok "python is installed, version $(python3 -V 2>&1 | awk '{print $2}')"
else
  MISSING_TOOLS=1
fi

if [ "$MISSING_TOOLS" = "1" ]; then
  echo
  echo "  One or both are missing. Apple ships them, they just are not unpacked yet."
  echo "  A grey window is about to appear asking to install them. Click Install,"
  echo "  wait for it to finish, then run this file again."
  echo
  xcode-select --install 2>/dev/null
  todo "install Apple's developer tools from the window that appeared, then run this again"
  echo
  echo "  Stopping here until that is done."
  exit 1
fi

# ------------------------------------------------------------------ 4. the code
head2 "STEP 4 of 6.  The music code"

# Puts the code into a folder that is already there and already has things in it,
# without touching anything sitting in it. This is the case where the keys were
# carried across by hand before the code was ever downloaded, which is exactly
# what happened on the first real machine on 2026-09-09.
adopt_existing_folder() {
  (
    cd "$FOLDER" || exit 1
    git init -q -b main >/dev/null 2>&1 || git init -q >/dev/null 2>&1
    git remote remove origin >/dev/null 2>&1
    git remote add origin "$REPO" >/dev/null 2>&1
    git fetch -q origin >/dev/null 2>&1 || exit 1
    git reset --hard origin/main >/dev/null 2>&1 || exit 1
    git branch -M main >/dev/null 2>&1
    git branch --set-upstream-to=origin/main main >/dev/null 2>&1
    exit 0
  )
}

if [ -d "$FOLDER/.git" ]; then
  echo "  Already here. Fetching anything new."
  if ( cd "$FOLDER" && git pull --ff-only >/dev/null 2>&1 ); then
    ok "the code is here and up to date"
  elif ( cd "$FOLDER" && git remote remove origin >/dev/null 2>&1; \
         git remote add origin "$REPO" >/dev/null 2>&1; \
         git fetch -q origin >/dev/null 2>&1 && \
         git branch --set-upstream-to=origin/main main >/dev/null 2>&1 && \
         git pull --ff-only >/dev/null 2>&1 ); then
    # The copy was there but had lost track of where it came from. Now repaired.
    ok "the code is here and up to date"
  else
    todo "the code is here but could not be updated, tell Claude"
  fi
elif [ -d "$FOLDER" ] && [ -n "$(ls -A "$FOLDER" 2>/dev/null)" ]; then
  echo "  This folder is already here with things in it, most likely the keys you"
  echo "  copied across by hand. Putting the code in around them. Nothing already"
  echo "  in the folder is touched."
  if adopt_existing_folder; then
    ok "the code is on this machine, alongside what you had already put in the folder"
  else
    todo "the folder already has things in it and the code could not be added around them, tell Claude"
  fi
else
  echo "  Getting a fresh copy from GitHub into:"
  echo "      $FOLDER"
  mkdir -p "$HOME/Documents"
  if git clone --quiet "$REPO" "$FOLDER"; then
    ok "the code is on this machine"
  else
    todo "could not download the code from GitHub, tell Claude"
  fi
fi

echo
echo "  NOTE, and it matters. This copy comes straight from GitHub and is NOT the"
echo "  one in your Google Drive folder. Two machines syncing the same code through"
echo "  Drive is how the two copies quietly stop matching. Documents and data can"
echo "  sync. Code comes from GitHub."

# ------------------------------------------------------------------ 5. the keys
head2 "STEP 5 of 6.  The keys, which have to be carried by hand"

echo "  These are the only things that cannot be downloaded. They are copied from"
echo "  the same folder on your Windows machine, on a memory stick or through"
echo "  Google Drive, and never emailed."
echo

NEEDKEYS=0
for f in secrets.json github-key.txt; do
  if [ -s "$FOLDER/$f" ]; then ok "$f is here"; else
    NEEDKEYS=1
    todo "copy $f into $FOLDER"
  fi
done
if [ -s "$FOLDER/tokens/home.json" ]; then
  ok "the saved Sonos sign-ins are here"
else
  NEEDKEYS=1
  todo "copy the whole tokens folder into $FOLDER"
fi

# ------------------------------------------------------------------ 6. prove it
head2 "STEP 6 of 6.  Proving it actually works, rather than assuming"

cd "$FOLDER" 2>/dev/null || { echo "  The folder is not there. Stopping."; exit 1; }

if [ ! -f test_schedule.py ] || [ ! -f test_instore.py ]; then
  todo "the code is not in the folder yet, so nothing below could be tested. Fix step 4 first"
else
  if python3 test_schedule.py >/dev/null 2>&1 && python3 test_instore.py >/dev/null 2>&1; then
    ok "the built-in checks all pass on this machine"
  else
    todo "the built-in checks did not pass here, tell Claude before running anything"
  fi

  if [ "$NEEDKEYS" = "0" ]; then
    if python3 whoami.py home 2>/dev/null | grep -q "SYSTEM"; then
      ok "this machine can reach your Sonos system from the internet"
    else
      todo "this machine could not reach Sonos, tell Claude"
    fi

    if git -c credential.helper= \
         -c credential.helper='!f(){ echo username=andrewding80-afk; echo "password=$(tr -d "\r\n" < github-key.txt)"; };f' \
         ls-remote "$REPO" >/dev/null 2>&1; then
      ok "this machine can save changes back to GitHub"
    else
      todo "the GitHub key here did not work, tell Claude"
    fi
  else
    echo "  Skipping the live tests until the keys above are in place."
  fi
fi

# --------------------------------------------------------- a way back in later
SHORTCUT="$HOME/Desktop/Check the mini.command"
{
  echo '#!/bin/bash'
  echo "cd \"$FOLDER\" || exit 1"
  echo 'bash setup-mini.sh'
} > "$SHORTCUT" 2>/dev/null
chmod +x "$SHORTCUT" 2>/dev/null && ok "a file called Check the mini is on the desktop, to run all this again"

# ------------------------------------------------------------------ the report
echo
echo "  ===================================================================="
echo "    WHERE THIS MACHINE STANDS"
echo "  ===================================================================="
echo
echo "  READY, ${#READY[@]} things:"
for r in "${READY[@]}"; do echo "      $r"; done
echo
if [ ${#LEFT[@]} -eq 0 ]; then
  echo "  NOTHING LEFT that this file can do."
else
  echo "  STILL TO DO, ${#LEFT[@]} things:"
  for l in "${LEFT[@]}"; do echo "      $l"; done
fi
echo
echo "  TWO THINGS THIS FILE CANNOT DO, and they are yours:"
echo "      Install the Claude desktop app, sign in, and set it to open on login."
echo "      Say the word onboard in a chat once it is signed in."
echo
echo "  After that, everything else happens without you."
echo
