import json
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
GLOBALS = caffe["update"].__globals__


def bar(live):
    return {
        "start": 0.0,
        "order": 42,
        "live": live,
        "leaving": {},
        "knocked": {},
        "gfx": True,
        "first_seen": dict.fromkeys(live, 0.0),
        "activity": {},
        "cat": caffe["Cat"](0, caffe["HOME_X"]),
    }


class BoardSnapshotTest(unittest.TestCase):
    def test_mirrors_the_card_without_project_names(self):
        state = bar({101: ("claude", "ttys001", 0, 0.0, 0)})
        state["cwds"] = {101: "/Users/me/code/secret-project"}
        state["projects"] = {101: "secret-project"}
        snapshot = caffe["board_snapshot"](state, 120.0)
        card = snapshot["cards"][0]
        self.assertEqual(
            (card["kind"], card["agent"], card["name"], card["where"], card["state"]),
            ("session", "claude", "Claude", "", "idle"),
        )
        self.assertTrue(card["status"].startswith("idle "))
        self.assertTrue(card["note"].startswith("quiet since "))
        self.assertNotIn("secret", json.dumps(snapshot))
        self.assertNotIn("\\u001b", json.dumps(snapshot))  # no terminal colours

    def test_sends_project_names_when_asked(self):
        state = bar({101: ("claude", "ttys001", 0, 0.0, 0)})
        state["projects"] = {101: "caffe"}
        with patch.dict(GLOBALS, BOARD_PROJECTS=True):
            card = caffe["board_snapshot"](state, 120.0)["cards"][0]
        self.assertEqual(card["where"], "caffe")

    def test_brewing_session(self):
        state = bar({101: ("codex", "ttys001", 0, 50.0, 0)})
        state["activity"] = {101: (90.0, 100.0)}
        card = caffe["board_snapshot"](state, 110.0)["cards"][0]
        self.assertEqual(card["state"], "brewing")
        self.assertTrue(card["status"].startswith("brewing "))
        self.assertEqual(card["note"], "50% cpu")

    def test_copilot_app_sessions_keep_their_titles_private(self):
        kind = caffe["COPILOT_SESSION_KIND"]
        state = bar({"copilot:abc": (kind, "Fix the build", 0, 0.0, 0)})
        card = caffe["board_snapshot"](state, 10.0)["cards"][0]
        self.assertEqual((card["agent"], card["name"], card["where"]), ("copilot", "Agent", ""))

    def test_open_apps_come_after_sessions_as_busy_or_open(self):
        state = bar(
            {
                (7, "vscode"): ("vscode", "app:VS Code", 0, 5.0, 1100),
                (8, "codex"): ("codex", "app:Codex", 40, 0.0, 1200),
                101: ("claude", "ttys001", 0, 0.0, 0),
            }
        )
        cards = caffe["board_snapshot"](state, 100.0)["cards"]
        self.assertEqual(
            [(c["kind"], c["name"], c["where"], c["state"]) for c in cards],
            [
                ("session", "Claude", "", "idle"),
                ("app", "VS Code", "app", "busy"),
                ("app", "Codex", "app", "open"),
            ],
        )
        self.assertTrue(cards[1]["status"].startswith("busy 5% · "))

    def test_served_cups_stay_until_they_are_cleared(self):
        state = bar({})
        state["leaving"] = {101: ("claude", "ttys001", 95.0, 0.0)}
        card = caffe["board_snapshot"](state, 100.0)["cards"][0]
        self.assertEqual(card["state"], "served")
        self.assertTrue(card["status"].startswith("✔ served"))

    def test_capybara_mode_sends_the_capybara_and_its_turtle(self):
        state = bar({101: ("claude", "ttys001", 0, 0.0, 0)})
        state["cat"].species = "capybara"
        sent = caffe["board_snapshot"](state, 30.0)["cat"]
        self.assertEqual(sent["kind"], "capybara")
        self.assertEqual(sent["title"], f"{state['cat'].name} the capybara")
        self.assertRegex(sent["shell"], r"^#[0-9a-f]{6}$")

    def test_the_cat_tally_and_card_ids_match_the_terminal(self):
        state = bar({101: ("claude", "ttys001", 0, 0.0, 0), 102: ("pi", "ttys002", 0, 0.0, 0)})
        first = caffe["board_snapshot"](state, 30.0)
        again = caffe["board_snapshot"](state, 40.0)
        self.assertEqual(first["cat"]["name"], state["cat"].name)
        self.assertEqual(first["cat"]["title"], state["cat"].title)
        self.assertRegex(first["cat"]["coat"], r"^#[0-9a-f]{6}$")
        self.assertEqual(first["cat"]["kind"], "cat")
        self.assertEqual(first["tally"], caffe["tally"](state, 30.0))
        self.assertEqual(first["awake"], 30)
        ids = [c["id"] for c in first["cards"]]
        self.assertEqual(ids, [c["id"] for c in again["cards"]])
        self.assertEqual(len(set(ids)), 2)


class BoardRequestTest(unittest.TestCase):
    def test_puts_the_bar_with_the_token(self):
        sent = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def urlopen(request, timeout):
            sent.append((request, timeout))
            return Response()

        with (
            patch.dict(GLOBALS, BOARD_URL="https://board.example", BOARD_TOKEN="t0k"),  # noqa: S106
            patch.object(GLOBALS["urllib"].request, "urlopen", urlopen),
        ):
            ok = caffe["board_request"]("PUT", "Miso the cat", {"sessions": []})
        self.assertTrue(ok)
        request, timeout = sent[0]
        self.assertEqual(request.get_method(), "PUT")
        self.assertEqual(request.full_url, "https://board.example/api/bars/Miso%20the%20cat")
        self.assertEqual(request.get_header("Authorization"), "Bearer t0k")
        self.assertEqual(json.loads(request.data), {"sessions": []})
        self.assertEqual(timeout, 5.0)

    def test_an_unreachable_board_is_not_an_error(self):
        def urlopen(request, timeout):
            raise OSError("no route to host")

        with (
            patch.dict(GLOBALS, BOARD_URL="https://board.example"),
            patch.object(GLOBALS["urllib"].request, "urlopen", urlopen),
        ):
            self.assertFalse(caffe["board_request"]("PUT", "Miso", {"sessions": []}))

    def test_only_http_urls_are_opened(self):
        with (
            patch.dict(GLOBALS, BOARD_URL="file:///etc"),
            patch.object(GLOBALS["urllib"].request, "urlopen") as urlopen,
        ):
            self.assertFalse(caffe["board_request"]("PUT", "Miso", {"sessions": []}))
        urlopen.assert_not_called()


class ReportToBoardTest(unittest.TestCase):
    def test_reports_every_ten_seconds_and_says_when_live(self):
        state = bar({})
        state["toast"] = None
        calls = []

        def request(method, name, body=None, timeout=5.0):
            calls.append((method, name, body))
            return True

        with patch.dict(GLOBALS, BOARD_URL="https://board.example", board_request=request):
            caffe["report_to_board"](state, 100.0)
            state["board_thread"].join()
            caffe["report_to_board"](state, 105.0)  # too soon
            caffe["report_to_board"](state, 111.0)
            state["board_thread"].join()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][:2], ("PUT", state["cat"].name))
        self.assertEqual(calls[0][2]["cards"], [])
        self.assertEqual(state["toast"][0], "Your bar is on the board ☕")

    def test_does_nothing_without_a_board(self):
        state = bar({})
        with patch.dict(GLOBALS, BOARD_URL=""):
            caffe["report_to_board"](state, 100.0)
        self.assertNotIn("board_thread", state)

    def test_bar_name_can_be_set(self):
        state = bar({})
        with patch.dict(GLOBALS["os"].environ, {"CAFFE_BOARD_NAME": "Alex"}):
            self.assertEqual(caffe["board_name"](state), "Alex")


if __name__ == "__main__":
    unittest.main()
