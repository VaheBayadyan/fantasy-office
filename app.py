"""Local Yahoo Fantasy Basketball dashboard. Run: python3 app.py"""

import json
import os
import secrets
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from yahoo import CALLBACK, YahooClient, YahooError

ROOT = Path(__file__).resolve().parent
HOST, PORT = "127.0.0.1", 8765


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"\''))


load_env()
client = YahooClient(ROOT / "instance")


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type="text/html; charset=utf-8", headers=None):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, url, headers=None):
        self.respond(302, b"", headers={"Location": url, **(headers or {})})

    def json(self, status, value):
        self.respond(status, json.dumps(value), "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        if path == "/":
            return self.respond(200, (ROOT / "static" / "index.html").read_bytes())
        if path in ("/static/app.css", "/static/app.js"):
            mime = "text/css" if path.endswith(".css") else "text/javascript"
            return self.respond(200, (ROOT / path.lstrip("/")).read_bytes(), mime)
        if path == "/auth/start":
            if not client.client_id or not client.client_secret:
                return self.redirect("/?error=Set+YAHOO_CLIENT_ID+and+YAHOO_CLIENT_SECRET+first")
            state = secrets.token_urlsafe(32)
            query = urllib.parse.urlencode({"client_id": client.client_id, "redirect_uri": CALLBACK, "response_type": "code", "state": state})
            return self.redirect("https://api.login.yahoo.com/oauth2/request_auth?" + query, {"Set-Cookie": f"fantasy_state={state}; HttpOnly; SameSite=Lax; Path=/auth; Max-Age=600"})
        if path == "/auth/callback":
            query = urllib.parse.parse_qs(parsed.query)
            jar = cookies.SimpleCookie()
            try:
                jar.load(self.headers.get("Cookie", ""))
                expected = jar["fantasy_state"].value
            except (KeyError, cookies.CookieError):
                expected = ""
            if not expected or not secrets.compare_digest(expected, query.get("state", [""])[0]):
                return self.redirect("/?error=Authorization+state+did+not+match")
            if "error" in query:
                return self.redirect("/?error=Yahoo+authorization+was+declined", {"Set-Cookie": "fantasy_state=; Max-Age=0; Path=/auth"})
            try:
                client.exchange(query["code"][0])
            except (KeyError, IndexError, YahooError) as exc:
                return self.redirect("/?error=" + urllib.parse.quote(str(exc)), {"Set-Cookie": "fantasy_state=; Max-Age=0; Path=/auth"})
            return self.redirect("/", {"Set-Cookie": "fantasy_state=; Max-Age=0; Path=/auth"})
        if path == "/api/dashboard":
            if not client.connected():
                return self.json(200, {"connected": False, "configured": bool(client.client_id and client.client_secret), "leagues": []})
            try:
                teams = client.owned_teams()
                leagues = []
                for team in teams:
                    try:
                        leagues.append(client.league(team))
                    except YahooError as exc:
                        leagues.append({"key": team["league_key"], "name": team["name"], "error": str(exc)})
                return self.json(200, {"connected": True, "configured": True, "leagues": leagues})
            except YahooError as exc:
                return self.json(502, {"error": str(exc)})
        self.respond(404, "Not found", "text/plain; charset=utf-8")


if __name__ == "__main__":
    print(f"Fantasy Office running at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
