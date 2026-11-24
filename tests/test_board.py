import json
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
GLOBALS = caffe["update"].__globals__


def bar(live):
    return {
        "live": live,
        "first_seen": dict.fromkeys(live, 0.0),
        "activity": {},
        "cat": caffe["Cat"](0, caffe["HOME_X"]),
    }


class BoardSnapshotTest(unittest.TestCase):
    def test_sends_only_agent_state_and_time(self):
        state = bar({101: ("claude", "ttys001", 0, 0.0, 0)})
        state["cwds"] = {101: "/Users/me/code/secret-project"}
        state["projects"] = {101: "secret-project"}
        snapshot = caffe["board_snapshot"](state, 120.0)
        self.assertEqual(
            snapshot, {"sessions": [{"agent": "claude", "state": "idle", "since": 120}]}
        )
        self.assertNotIn("secret", json.dumps(snapshot))

    def test_brewing_session_reports_when_it_started(self):
        state = bar({101: ("codex", "ttys001", 0, 50.0, 0)})
        state["activity"] = {101: (90.0, 100.0)}
        snapshot = caffe["board_snapshot"](state, 110.0)
        self.assertEqual(
            snapshot["sessions"], [{"agent": "codex", "state": "brewing", "since": 20}]
        )

    def test_copilot_app_sessions_count_as_copilot(self):
        kind = caffe["COPILOT_SESSION_KIND"]
        state = bar({"copilot:abc": (kind, "Fix the build", 0, 0.0, 0)})
        sessions = caffe["board_snapshot"](state, 10.0)["sessions"]
        self.assertEqual([s["agent"] for s in sessions], ["copilot"])

    def test_open_apps_come_after_sessions_as_busy_or_open(self):
        state = bar(
            {
                (7, "vscode"): ("vscode", "app:VS Code", 0, 5.0, 1100),
                (8, "codex"): ("codex", "app:Codex", 40, 0.0, 1200),
                101: ("claude", "ttys001", 0, 0.0, 0),
            }
        )
        sessions = caffe["board_snapshot"](state, 100.0)["sessions"]
        self.assertEqual(
            sessions[1:],
            [
                {"kind": "app", "agent": "vscode", "state": "busy", "since": 100},
                {"kind": "app", "agent": "codex", "state": "open", "since": 60},
            ],
        )
        self.assertEqual(sessions[0]["agent"], "claude")
        self.assertNotIn("kind", sessions[0])

    def test_unknown_agents_stay_off_the_board(self):
        state = bar({"t3:x": ("t3", "ttys002", 0, 0.0, 0)})
        self.assertEqual(caffe["board_snapshot"](state, 10.0), {"sessions": []})


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
        self.assertEqual(calls[0], ("PUT", state["cat"].name, {"sessions": []}))
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
