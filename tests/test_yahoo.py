import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yahoo import categories_from_settings, category_result, matchup_from_scoreboard, players_from_root, teams_from_user


class MappingTests(unittest.TestCase):
    def test_discovers_basketball_teams_only(self):
        root = ET.fromstring('''<fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng"><users><user><games><game><game_code>nba</game_code><season>2026</season><teams><team><team_key>500.l.12.t.4</team_key><name>My Team</name></team></teams></game><game><game_code>nfl</game_code><teams><team><team_key>499.l.2.t.3</team_key></team></teams></game></games></user></users></fantasy_content>''')
        self.assertEqual(teams_from_user(root), [{"key": "500.l.12.t.4", "name": "My Team", "league_key": "500.l.12", "season": "2026"}])

    def test_maps_categories_and_matchup(self):
        settings = ET.fromstring('''<fantasy_content><league><settings><stat_categories><stats><stat><stat_id>12</stat_id><display_name>PTS</display_name></stat><stat><stat_id>19</stat_id><display_name>TO</display_name></stat></stats></stat_categories></settings></league></fantasy_content>''')
        categories = categories_from_settings(settings)
        self.assertEqual([(c["id"], c["lower"]) for c in categories], [("12", False), ("19", True)])
        board = ET.fromstring('''<fantasy_content><league><scoreboard><matchups><matchup><week>3</week><teams><team><team_key>500.l.12.t.4</team_key><name>Mine</name><team_stats><stats><stat><stat_id>12</stat_id><value>420</value></stat></stats></team_stats></team><team><team_key>500.l.12.t.5</team_key><name>Theirs</name><team_stats><stats><stat><stat_id>12</stat_id><value>450</value></stat></stats></team_stats></team></teams></matchup></matchups></scoreboard></league></fantasy_content>''')
        matchup = matchup_from_scoreboard(board, "500.l.12.t.4")
        self.assertEqual(matchup["opponent"]["name"], "Theirs")
        self.assertEqual(matchup["mine"]["stats"]["12"], "420")
        self.assertEqual(category_result("5", "8", categories[1]), "winning")
        self.assertEqual(category_result("420", "450", categories[0]), "losing")

    def test_reads_free_agent_stats(self):
        root = ET.fromstring('''<fantasy_content><league><players><player><player_key>500.p.1</player_key><name><full>Player One</full></name><editorial_team_abbr>BOS</editorial_team_abbr><eligible_positions><position>PG</position><position>SG</position></eligible_positions><player_stats><stats><stat><stat_id>16</stat_id><value>102</value></stat></stats></player_stats></player></players></league></fantasy_content>''')
        self.assertEqual(players_from_root(root)[0]["stats"]["16"], "102")
        self.assertEqual(players_from_root(root)[0]["positions"], "PG, SG")


if __name__ == "__main__":
    unittest.main()
