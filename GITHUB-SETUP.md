# Putting the music on GitHub's machines, step by step

**Written for someone who does not write code.** Every step says what to click and what
to type. If a screen does not look like what is described here, stop and say so rather
than carrying on.

**What this achieves:** the music sets itself every fifteen minutes, forever, with nothing
in your house switched on and nothing for you to type. About forty minutes, once.

⚠️ **The folder to upload is `store-music-for-github`, NOT `store-music`.** The second one
holds your key and your access. Those must never leave the laptop. The first one is a copy
with them removed, which is the only reason it exists.

---

## Part 1: make the place it will live

**1.** Go to **github.com** and sign in with the same account your Toast job uses.

**2.** Top right, click the **+** sign, then **New repository**.

**3.** In **Repository name** type:

```
store-music
```

**4.** ⚠️ **Click Private.** Not Public. This is not secret work, but there is no reason
for it to be readable by the world.

**5.** Leave every other box alone. Click the green **Create repository** at the bottom.

**What you should see:** a nearly empty page with the words "Quick setup" near the top.

---

## Part 2: put the files in it

**1.** On that page, find and click **uploading an existing file**. It is a blue link in
the sentence about uploading.

**2.** Open File Explorer in another window and go to:

```
C:\Users\16176\Documents\OWN THE ORDER - CLAUDE\store-music-for-github
```

**3.** Press **Ctrl and A together** to select everything in that folder, then drag it all
onto the GitHub page where it says to drag files.

**4.** ⚠️ **Check what it lists before going on.** You should see twelve files. If you see
anything called **secrets.json** or a folder called **tokens**, stop, remove them, and tell
me, because you have the wrong folder.

**5.** Click the green **Commit changes** at the bottom.

---

## Part 3: give it the three things it needs to sign in

These are stored by GitHub in a way that even you cannot read back afterwards, only replace.

**1.** On your repository page, click **Settings** in the row of tabs at the top.

**2.** Down the left side, click **Secrets and variables**, then **Actions** underneath it.

**3.** Click the green **New repository secret**.

Now three times, once for each row of this table.

| Name to type | What to paste as the value |
|---|---|
| `SONOS_CLIENT_ID` | the `client_id` line from `secrets.json` |
| `SONOS_CLIENT_SECRET` | the `client_secret` line from `secrets.json` |
| `SONOS_TOKEN_HOME` | the **whole contents** of `tokens\home.json` |

**To read those files:** in File Explorer, in the `store-music` folder, right-click the
file, choose **Open with**, then **Notepad**.

⚠️ **For the first two, paste only what is between the quote marks.** Not the quote marks,
not the name, not the comma. Just the long string of letters, numbers and dashes.

⚠️ **For the third, paste everything in the file**, including the curly brackets at the top
and bottom. All of it.

**4.** Each time: type the name in the **Name** box, paste into the **Secret** box, click
**Add secret**.

**What you should see:** three names listed, with no values shown next to them. That is
correct, they are meant to be unreadable from here.

---

## Part 4: try it without letting it touch anything

**1.** Click the **Actions** tab at the top of your repository.

**2.** If it asks whether to enable workflows, click the green button to say yes.

**3.** Down the left side, click **Store music**.

**4.** On the right, click **Run workflow**. A small panel opens with a box that says **no**.
**Leave it saying no.** Click the green **Run workflow** in that panel.

**5.** Wait about a minute, then refresh the page. A line appears with a tick or a cross.

**6.** Click that line, then click **music**, then click the arrow next to **Set the music**
to open it.

**What you should see:** the same words as on your laptop, ending in either
`all stores as expected` or `CHANGES OUTSTANDING`. Either is fine here. It changed nothing.

❌ **A cross rather than a tick** usually means one of the three secrets is wrong. The most
common cause is a stray space or a missing curly bracket. Copy the error and send it to me.

---

## Part 5: let it act, still by hand

Same as Part 4, but at step 4 **change the box from no to yes** before clicking the green
button.

This is the first time GitHub's machines touch your speakers. Be somewhere you can hear it.

---

## Part 6: turn the clock on

✅ **DONE 2026-09-06.** The schedule is live and runs every fifteen minutes. The steps below are
kept only for reference, or for switching it back off.

**To switch it off again:** open `.github/workflows/store-music.yml`, click the pencil, and delete
the part that reads `,"schedule":[{"cron":"*/15 * * * *"}]`. Commit. It then only runs when you
press the button.

Only once Part 5 has worked at least twice.

**1.** In your repository, click the file path **.github**, then **workflows**, then
**store-music.yml**.

**2.** Click the **pencil icon** near the top right to edit it.

**3.** Find these two lines:

```
  # schedule:
  #   - cron: "*/15 * * * *"
```

**4.** Delete the `#` and the space at the start of each of those two lines, so they read:

```
  schedule:
    - cron: "*/15 * * * *"
```

⚠️ **The spaces at the start of each line matter.** The second line must sit further in
than the first. Remove only the `#` and the single space after it.

**5.** Click the green **Commit changes**, then **Commit changes** again in the panel.

**That is the end. It now runs itself every fifteen minutes.**

---

## What it will do from then on

Almost always, nothing. It looks, finds everything already correct, and stops without
saying anything. **A run with nothing to report is meant to be silent.**

It speaks up in two cases: something needed changing and it changed it, or something is
wrong that it cannot fix.

**Why fifteen minutes and not once per slot.** Because it is not really a timetable, it is
a repair. A power cut, a staff member nudging a volume, a speaker rejoining after dropping
off, all get put right within a quarter of an hour without anybody noticing.

---

## Adding the three stores later

Each store, once:

**1.** On your laptop, in the black window:

```
python connect.py west-harlem
```

Then sign in with **that store's** Sonos account. It prints two ids.

**2.** Open `tokens\west-harlem.json` in Notepad and add its whole contents to GitHub as a
new secret named `SONOS_TOKEN_WEST_HARLEM`. The workflow already expects that name.

**3.** Put the two ids into `config.json`, set that store's `enabled` to `true`, and upload
`config.json` again the same way as Part 2.

**4.** In that store's Sonos app, add the playlists as favourites with names matching
`config.json` exactly.

⚠️ **Step 4 may need someone standing in the store**, because the Sonos app only reaches
speakers on the same wifi. Playing a favourite works from anywhere, which is proven.
Creating one may not. Untested.

The other two stores are the same with `central-harlem` and `hells-kitchen` in place of
`west-harlem`.
