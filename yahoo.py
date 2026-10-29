"""Small read-only Yahoo Fantasy client and XML-to-dashboard mapping."""

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

API = "https://fantasysports.yahooapis.com/fantasy/v2/"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
CALLBACK = "http://127.0.0.1:8765/auth/callback"


def tag(element):
    return element.tag.rsplit("}", 1)[-1]


def children(element, name):
    return [child for child in element if tag(child) == name]


def child(element, name):
    return next(iter(children(element, name)), None) if element is not None else None


def value(element, name, default=""):
    node = child(element, name)
    return (node.text or "").strip() if node is not None else default


def descendants(element, name):
    return [node for node in element.iter() if tag(node) == name]


def stat_map(element):
    result = {}
    for stat in descendants(element, "stat"):
        key = value(stat, "stat_id")
        if key:
            result[key] = value(stat, "value")
    return result


def optional_child(element, name):
    found = child(element, name)
    return found if found is not None else element


def number(text):
    try:
        return float(str(text).replace(",", ""))
    except (ValueError, TypeError):
        return None


def category_result(mine, theirs, category):
    left, right = number(mine), number(theirs)
    if left is None or right is None:
        return "pending"
    if left == right:
        return "tied"
    lower = category["lower"]
    return "winning" if (left < right if lower else left > right) else "losing"


def categories_from_settings(root):
    settings = next(iter(descendants(root, "settings")), None)
    result = []
    if settings is None:
        return result
    category_root = child(settings, "stat_categories")
    if category_root is None:
        return result
    for stat in descendants(category_root, "stat"):
        stat_id = value(stat, "stat_id")
        if not stat_id or value(stat, "is_only_display_stat") == "1":
            continue
        name = value(stat, "display_name") or value(stat, "name") or stat_id
        result.append({"id": stat_id, "name": name, "lower": "turnover" in name.lower() or name.upper() in ("TO", "TOV")})
    return result


def teams_from_user(root):
    teams = []
    for game in descendants(root, "game"):
        if value(game, "game_code") != "nba":
            continue
        for team in descendants(game, "team"):
            key = value(team, "team_key")
            if key:
                teams.append({"key": key, "name": value(team, "name"), "league_key": key.rsplit(".t.", 1)[0], "season": value(game, "season")})
    return teams


def matchup_from_scoreboard(root, my_key):
    for matchup in descendants(root, "matchup"):
        teams = descendants(matchup, "team")
        if len(teams) != 2 or my_key not in [value(team, "team_key") for team in teams]:
            continue
        mine = next(team for team in teams if value(team, "team_key") == my_key)
        other = next(team for team in teams if value(team, "team_key") != my_key)
        return {"week": value(matchup, "week"), "mine": {"key": my_key, "name": value(mine, "name"), "stats": stat_map(optional_child(mine, "team_stats"))}, "opponent": {"key": value(other, "team_key"), "name": value(other, "name"), "stats": stat_map(optional_child(other, "team_stats"))}}
    return None


def players_from_root(root):
    result = []
    for player in descendants(root, "player"):
        key = value(player, "player_key")
        if not key:
            continue
        name_node = child(player, "name")
        result.append({"key": key, "name": value(name_node, "full") or value(player, "name"), "team": value(player, "editorial_team_abbr"), "positions": ", ".join(node.text or "" for node in descendants(optional_child(player, "eligible_positions"), "position")), "stats": stat_map(optional_child(player, "player_stats"))})
    return result


class YahooError(Exception):
    pass


class YahooClient:
    def __init__(self, instance_dir):
        self.path = Path(instance_dir) / "token.json"
        self.client_id = os.getenv("YAHOO_CLIENT_ID", "")
        self.client_secret = os.getenv("YAHOO_CLIENT_SECRET", "")

    def connected(self):
        return self.path.exists()

    def _token(self, fields):
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        request = urllib.request.Request(TOKEN_URL, data=urllib.parse.urlencode(fields).encode(), headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            raise YahooError(f"Yahoo authorization failed: {exc}") from exc

    def save_token(self, token):
        token["expires_at"] = time.time() + int(token.get("expires_in", 3600)) - 60
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(token, handle)
        os.chmod(self.path, 0o600)

    def exchange(self, code):
        token = self._token({"grant_type": "authorization_code", "code": code, "redirect_uri": CALLBACK})
        self.save_token(token)

    def access_token(self):
        if not self.connected():
            raise YahooError("Connect Yahoo first.")
        token = json.loads(self.path.read_text())
        if time.time() >= token.get("expires_at", 0):
            refreshed = self._token({"grant_type": "refresh_token", "refresh_token": token["refresh_token"], "redirect_uri": CALLBACK})
            refreshed.setdefault("refresh_token", token["refresh_token"])
            self.save_token(refreshed)
            token = refreshed
        return token["access_token"]

    def get(self, path):
        request = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {self.access_token()}", "Accept": "application/xml"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return ET.fromstring(response.read())
        except (urllib.error.HTTPError, urllib.error.URLError, ET.ParseError) as exc:
            raise YahooError(f"Yahoo data request failed: {exc}") from exc

    def owned_teams(self):
        return teams_from_user(self.get("users;use_login=1/games;game_keys=nba/teams"))

    def league(self, owned_team):
        key = owned_team["league_key"]
        root = self.get(f"league/{key};out=settings")
        league_node = next(iter(descendants(root, "league")), None)
        if league_node is None:
            raise YahooError(f"Yahoo returned no league for {key}.")
        current_week = int(value(league_node, "current_week") or "0")
        if not current_week:
            raise YahooError(f"No current matchup week for {key}.")
        categories = categories_from_settings(root)
        current = matchup_from_scoreboard(self.get(f"league/{key}/scoreboard;week={current_week}"), owned_team["key"])
        next_matchup = None
        if current_week < int(value(league_node, "end_week") or "99"):
            try:
                next_matchup = matchup_from_scoreboard(self.get(f"league/{key}/scoreboard;week={current_week + 1}"), owned_team["key"])
            except YahooError:
                pass
        if current:
            for cat in categories:
                cat["mine"] = current["mine"]["stats"].get(cat["id"], "—")
                cat["theirs"] = current["opponent"]["stats"].get(cat["id"], "—")
                cat["result"] = category_result(cat["mine"], cat["theirs"], cat)
        next_categories = []
        if next_matchup:
            try:
                my_season = stat_map(self.get(f"team/{owned_team['key']}/stats"))
                their_season = stat_map(self.get(f"team/{next_matchup['opponent']['key']}/stats"))
                for cat in categories:
                    mine, theirs = my_season.get(cat["id"], "—"), their_season.get(cat["id"], "—")
                    next_categories.append({"name": cat["name"], "mine": mine, "theirs": theirs, "result": category_result(mine, theirs, cat)})
            except YahooError:
                pass
        targets = [cat for cat in categories if cat.get("result") in ("losing", "tied")]
        targets.sort(key=lambda cat: abs((number(cat.get("mine")) or 0) - (number(cat.get("theirs")) or 0)) / max(abs(number(cat.get("theirs")) or 0), 1))
        suggestions = []
        for cat in targets[:3]:
            if cat["lower"]:
                continue  # A low-turnover strategy cannot be solved by adding a player.
            try:
                players = players_from_root(self.get(f"league/{key}/players;status=FA;sort={cat['id']};sort_type=season;count=6/stats"))
            except YahooError:
                continue
            suggestions.append({"category": cat["name"], "players": [{"name": p["name"], "team": p["team"], "positions": p["positions"], "value": p["stats"].get(cat["id"], "—")} for p in players[:5]]})
        return {"key": key, "name": value(league_node, "name"), "team": owned_team["name"], "scoring": value(league_node, "scoring_type"), "week": current_week, "current": current, "next": next_matchup, "next_categories": next_categories, "categories": categories, "suggestions": suggestions}
