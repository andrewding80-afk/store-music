# Setting up the store music, step by step

**Written for someone who does not write code.** Every step says exactly what to click, exactly
what to type, and what you should see if it worked. If a step does not look like what is described
here, stop at that step and say so rather than carrying on.

Do this on your laptop at home first. **Home is the only Sonos system you can reach right now**,
and if this does not work there it will not work in a store either. Better to find out tonight.

Total time: about half an hour, most of it waiting.

---

## First: open the window you will be typing into

**Do not skip this part.** Everything below is typed into this window.

**1.** Open File Explorer and go to:

```
C:\Users\16176\Documents\OWN THE ORDER - CLAUDE\store-music
```

**2.** Click once in the **address bar** at the top, where the folder path is written. The path
will highlight in blue.

**3.** Type this over it and press Enter:

```
cmd
```

A black window opens. That is the command prompt, and it is already pointing at the right folder,
which is what matters. **Leave it open, you will use it several times.**

⚠️ **If you close it and come back later, do steps 1 to 3 again** rather than opening the command
prompt from the Start menu. Opening it any other way points it at the wrong folder and nothing
works.

---

## Checking Python (Andrew has it, so skip this)

Confirmed installed 2026-09-05. Left here only for setting up a different machine later.

Type `python --version` and press Enter. Anything starting with `Python 3` is fine. If the
Microsoft Store opens instead, install from **python.org/downloads** and ⚠️ **tick the box that
says "Add python.exe to PATH" before clicking Install.**

---

## Step 1: check the schedule works

This proves the timetable part is correct. It needs no Sonos account and touches nothing.

**1.** In the black window, type this and press Enter:

```
python test_schedule.py
```

**What you should see:** about 26 lines each starting with `PASS`, and at the bottom:

```
All checks passed.
```

**If you see any line starting with `FAIL`**, tell me which one and stop here.

---

## Step 2: get a Key and a Secret from Sonos

These are like a username and password that let the software talk to your speakers.

**1.** Go to **developer.sonos.com** in your browser.

**2.** Click **Sign in** at the top right, then sign in with the same Sonos account you use at
home. If it asks you to create a developer account, do that. It is free.

**3.** Once signed in, find **Control Integrations** in the menu and click **Create Integration**
(the wording may be slightly different, look for anything about creating a new integration).

**4.** Give it a name. **Store Music** is fine. The name does not matter.

**5.** It will ask for a **Redirect URI** or **Redirect URL**. Type exactly this, including the
`http://` at the front:

```
http://localhost:8765/callback
```

⚠️ **This must match character for character.** One wrong character and step 4 fails with a
confusing message.

**6.** Save it. The page now shows a **Key** and a **Secret**. The Secret may be hidden behind a
"show" link.

**7.** Leave that page open. You need to copy both in the next step.

---

## Step 3: put the Key and Secret in a file

This is the fiddly one because of how Windows saves files. Follow it exactly.

**1.** Press the Windows key, type **Notepad**, press Enter.

**2.** Copy the text below into Notepad exactly as it is:

```
{
  "client_id": "PASTE THE KEY HERE",
  "client_secret": "PASTE THE SECRET HERE"
}
```

**3.** Replace `PASTE THE KEY HERE` with your Key from the Sonos page. **Keep the quote marks
around it.** Do the same with the Secret.

It should end up looking like this, with your own long strings of letters and numbers:

```
{
  "client_id": "b3f1c2d4-aaaa-bbbb-cccc-1234567890ab",
  "client_secret": "9f8e7d6c-5b4a-3210-fedc-ba9876543210"
}
```

**4.** In Notepad click **File**, then **Save As**.

**5.** Navigate to:

```
C:\Users\16176\Documents\OWN THE ORDER - CLAUDE\store-music
```

**6.** ⚠️ **This is the part that catches everyone.** Before typing the name, find the dropdown at
the bottom labelled **Save as type** and change it from "Text Documents (*.txt)" to
**All Files (*.\*)**.

**7.** Now in the File name box type exactly:

```
secrets.json
```

**8.** Click Save.

**How to check it worked:** in File Explorer the file should be called `secrets.json`. If it says
`secrets.json.txt`, step 6 was missed. Delete it and do steps 4 to 8 again.

⚠️ **Never email this file, never put it in a shared folder, never send it to anyone.** It is the
password to your speakers. It is already set to be excluded from any backup to GitHub.

---

## Step 4: connect your home Sonos

**This step is the real test.** It answers whether any of this can work without a computer sitting
in each store.

**1.** Back in the black command window, type this and press Enter:

```
python connect.py home
```

**2.** Your browser opens to a Sonos sign-in page. Sign in and click to approve.

**3.** The browser tab says **"Connected. You can close this tab and go back."** Close it.

**4.** Look at the black window. It should now print a list: a household id, your speaker groups
with their names, and the favourites it can see.

**What you should see:** something like

```
  household id: Sonos_abc123...
    group: Living Room                id: RINCON_xxx:1
    group: Kitchen                    id: RINCON_yyy:2

  favourites on this system:
    Feel Good Jazz
    ...
```

✅ **If you see your speakers listed, cloud control works.** That means no computer is needed in
any store, and the whole thing can run by itself.

❌ **If it cannot reach them**, copy whatever error appears and send it to me. That answers the
question the other way, and a small computer in each store becomes the plan, which was your idea
first.

**5.** Copy the **household id** and the **group id** of whichever speaker group you want the music
on. You need them in the next step.

---

## Step 5: put those two ids into the settings file

**1.** In File Explorer, right-click `config.json`, choose **Open with**, then **Notepad**.

**2.** Near the top you will see this:

```
    {
      "id": "home",
      "name": "Home (test system)",
      "household": "PENDING_AUTHORISATION",
      "group": "",
      "enabled": true
    },
```

**3.** Replace `PENDING_AUTHORISATION` with your household id, keeping the quote marks. Put your
group id between the empty quote marks after `"group":`.

**4.** Click File, then Save. **Do not use Save As here**, just Save.

---

## Step 6: add the playlists to Sonos as favourites

The software plays favourites, so each playlist has to exist as one.

**1.** Open the Sonos app on your phone or laptop.

**2.** Find each playlist in Spotify inside the Sonos app, and add it to **My Sonos** or
**Favourites** (the wording depends on your app version).

**3.** ⚠️ **Pick the copies you own, not Spotify's originals.** The names are almost identical. The
ones you own have `(2)`, `(copy)` or `(From Joel)` in the name. If you pick Spotify's, the music can
still change under you.

**4.** The favourite name has to match what is written in `config.json` exactly. Right now the
file expects these names:

- `Jazz Trumpet (copy)`
- `Instrumental Jazz Standards (2)`
- `FOH Jazz (From Joel)`
- `Feel Good Jazz (copy)`

If your copies are called something else, either rename them in Spotify or tell me and I will
change the settings file.

---

## Step 7: watch it decide, without letting it touch anything

**1.** In the black window, type this and press Enter:

```
python run.py
```

**What you should see:** it prints what should be playing right now, what actually is playing, and
what it would change. **It changes nothing.** The word "dry run" appears at the top.

**2.** To see what it would do at any other moment, type this, changing the date and time:

```
python run.py --at 2026-12-20T19:30
```

Run this a few times over a day or two and read what it says. **Do not go to step 8 until it has
looked right several times.**

---

## Step 8: let it actually change the music

Only when step 7 has been correct for a while.

```
python run.py --live
```

That is the only difference: `--live` on the end. Everything else is the same.

---

## Adding a store, once home works

For each store, four things:

**1.** Open `config.json` in Notepad, find that store, change `"enabled": false` to
`"enabled": true`, save.

**2.** In the black window, type one of these depending on the store:

```
python connect.py west-harlem
python connect.py central-harlem
python connect.py hells-kitchen
```

**3.** Sign in with **that store's** Sonos account when the browser opens, and paste the two ids it
prints into `config.json` the same way as step 5.

**4.** Add the same favourites in that store's Sonos app, with the same names.

**That is the whole thing. No code changes.** If adding a store ever seems to need a `.py` file
edited, something is built wrong. Tell me rather than editing it.

---

## If you move to the Mac mini later

Everything works the same. Two differences:

- Python is already installed on a Mac, so the check at the top is not needed
- Instead of the black command window, you open **Terminal**, type `cd ` (with a space), drag the
  `store-music` folder onto the Terminal window, and press Enter

Everything you type after that is identical.

---

## What each file is for

| File | What it does |
|---|---|
| `config.json` | **The whole timetable.** Slots, times, playlists, volumes, seasons, holidays. Changing the music means changing this and nothing else |
| `schedule.py` | Works out what should be playing. Talks to nothing. Fully tested |
| `test_schedule.py` | The 26 checks. Run it after any change to `config.json` |
| `sonos.py` | Talks to the speakers. **Unproven until step 4 works** |
| `connect.py` | Connects one Sonos system. Run once per store |
| `run.py` | The thing that actually runs |
| `secrets.json` | Your Key and Secret. **Never share this** |
| `tokens` folder | Made automatically. One file per store. **Never share these** |

---

## Two things it deliberately will not do

**It only plays music.** It cannot change an offer, a price, or anything else.

**It never reports a quiet success.** Every run ends with either "all stores as expected" or
"something needs attention". A scheduled job that silently stops working is the failure that
actually happens, so this one cannot fail quietly.
