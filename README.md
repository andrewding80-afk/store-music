# status branch

Machine-written. Nothing here is source code and nothing here is edited by hand.

The store-music workflow writes `status.json` to this branch after every run, but only
commits when the status has actually changed, or once a day so that a stale file means
"the job has stopped running" rather than "nothing changed".

It lives on its own branch so `main` keeps only Andrew's work. Deleting this branch turns
the whole thing off and breaks nothing.

Created 2026-09-10.
