# Fantasy Office

A local, read-only Yahoo Fantasy Basketball dashboard for head-to-head category leagues. It discovers your basketball teams, shows the current and next matchups, compares category totals, and ranks available players for the closest categories.

## Run

1. [Request Yahoo Fantasy API access](https://sports.yahoo.com/developer/). Yahoo says applications are reviewed before access is granted. Once approved, create or obtain a **Web Application** with **Fantasy Sports Read** access and set its callback URL to `http://127.0.0.1:8765/auth/callback`.
2. Set `YAHOO_CLIENT_ID` and `YAHOO_CLIENT_SECRET` in your shell, or copy `.env.example` to `.env` and fill it in.
3. Run `python3 app.py`, then open `http://127.0.0.1:8765`.
4. Click **Connect Yahoo** and approve Yahoo's authorization screen.

No Python packages need to be installed. The app binds to localhost and stores the refresh token in `instance/token.json` with owner-only file permissions. Keep that directory private.

The recommendations use Yahoo season totals and the current weekly category gap. They are category-fit ideas, not win probabilities: injuries, NBA game schedules, lineup slots, and games remaining are not included yet. The app never makes roster moves or trades.

## Developer check

```sh
python3 -m unittest discover -s tests
```

API references: [Yahoo Fantasy Sports API](https://sports.yahoo.com/developer/docs/) and [Yahoo OAuth authorization code flow](https://developer.yahoo.com/oauth2/guide/flows_authcode/).
