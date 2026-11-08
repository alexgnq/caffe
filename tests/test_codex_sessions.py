import json
import runpy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
GLOBALS = caffe["update"].__globals__
NOW = 1_800_000_000.0
FOLDER = "/Users/me/code/caffe"


def iso(t):
    return caffe["datetime"].datetime.fromtimestamp(t, caffe["datetime"].timezone.utc).isoformat()


def event(t, kind, **payload):
    record = "event_msg" if kind.startswith(("task_", "turn_")) else "response_item"
    return {"timestamp": iso(t), "type": record, "payload": {"type": kind, **payload}}


def call(t, name="exec_command"):
    return event(t, "function_call", name=name, arguments="{}")


def output(t):
    return event(t, "function_call_output", output="done")


def bar():
    return {
        "start": 0,
        "live": {},
        "leaving": {},
        "knocked": {},
        "first_seen": {},
        "orders": {},
        "agent_time": 0.0,
        "broken": 0,
        "longest": (0, ""),
        "cat": caffe["Cat"](0, caffe["HOME_X"]),
        "toast": None,
        "initialized": True,
        "gfx": True,
        "rush": False,
    }


class CodexSessionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name)
        patcher = patch.dict(GLOBALS, CODEX_HOME=self.home)
        patcher.start()
        self.addCleanup(patcher.stop)
        with sqlite3.connect(self.home / "state_5.sqlite") as db:
            db.execute(
                "CREATE TABLE threads (rollout_path TEXT, cwd TEXT, updated_at INTEGER,"
                " originator TEXT, archived INTEGER, source TEXT)"
            )

    def thread(self, name, events, folder=FOLDER, updated=NOW - 5, **extra):
        log = self.home / f"rollout-{name}.jsonl"
        self.write(log, events)
        with sqlite3.connect(self.home / "state_5.sqlite") as db:
            db.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(log),
                    folder,
                    int(updated),
                    extra.get("originator", "codex-tui"),
                    extra.get("archived", 0),
                    extra.get("source", "vscode"),
                ),
            )
        return log

    def write(self, log, events):
        log.write_text("".join(json.dumps(e) + "\n" for e in events))

    def turns(self, clis=None):
        return caffe["scan_codex_turns"](clis or {1: (FOLDER, NOW - 600)})

    def test_a_turn_brews_then_is_ready_the_moment_it_ends(self):
        log = self.thread("a", [event(NOW - 60, "task_started"), call(NOW - 50), output(NOW - 45)])
        self.assertEqual(self.turns(), {1: ("brewing", NOW - 60, "")})
        self.write(
            log, [event(NOW - 60, "task_started"), call(NOW - 50), event(NOW - 2, "task_complete")]
        )
        self.assertEqual(self.turns(), {1: ("ready", NOW - 2, "waiting for you")})

    def test_a_turn_that_asks_you_something_has_a_question_for_you(self):
        self.thread(
            "a",
            [
                event(NOW - 90, "task_started"),
                call(NOW - 80, "request_user_input_async"),
                output(NOW - 80),
                event(NOW - 78, "task_complete"),
            ],
        )
        self.assertEqual(self.turns(), {1: ("ready", NOW - 78, "has a question for you")})

    def test_an_answered_question_is_no_longer_waiting(self):
        self.thread(
            "a",
            [
                event(NOW - 90, "task_started"),
                call(NOW - 80, "request_user_input_async"),
                event(NOW - 78, "task_complete"),
                event(NOW - 60, "task_started"),
                event(NOW - 50, "task_complete"),
            ],
        )
        self.assertEqual(self.turns(), {1: ("ready", NOW - 50, "waiting for you")})

    def test_mid_turn_only_an_unanswered_question_waits_on_you(self):
        log = self.thread(
            "a", [event(NOW - 90, "task_started"), call(NOW - 30, "request_user_input")]
        )
        self.assertEqual(self.turns(), {1: ("ready", NOW - 30, "has a question for you")})
        self.write(
            log,
            [
                event(NOW - 90, "task_started"),
                call(NOW - 30, "request_user_input_async"),  # it asks, then gets on with it
                output(NOW - 30),
                call(NOW - 20),
            ],
        )
        self.assertEqual(self.turns(), {1: ("brewing", NOW - 90, "")})

    def test_a_turn_you_stopped_is_idle(self):
        self.thread("a", [event(NOW - 90, "task_started"), event(NOW - 40, "turn_aborted")])
        self.assertEqual(self.turns(), {1: ("idle", NOW - 40, "stopped")})

    def test_each_cli_gets_the_latest_session_in_its_own_folder(self):
        self.thread("old", [event(NOW - 900, "task_complete")], updated=NOW - 900)
        self.thread("mine", [event(NOW - 60, "task_started")], updated=NOW - 10)
        self.thread("other", [event(NOW - 30, "task_complete")], updated=NOW - 5)
        self.thread(
            "elsewhere",
            [event(NOW - 1, "task_started")],
            folder="/Users/me/code/other",
            updated=NOW,
        )
        self.thread(
            "app", [event(NOW - 1, "task_started")], originator="Codex Desktop", updated=NOW
        )
        self.thread("gone", [event(NOW - 1, "task_started")], archived=1, updated=NOW)
        clis = {1: (FOLDER, NOW - 600), 2: (FOLDER, NOW - 100)}
        self.assertEqual(
            self.turns(clis),
            {2: ("ready", NOW - 30, "waiting for you"), 1: ("brewing", NOW - 60, "")},
        )
        # A session from before the CLI started isn't its.
        self.assertEqual(
            self.turns({3: (FOLDER, NOW - 60)}), {3: ("ready", NOW - 30, "waiting for you")}
        )

    def test_without_codex_records_the_bar_guesses_as_before(self):
        self.thread("a", [])  # no turns yet
        self.assertEqual(self.turns(), {})
        (self.home / "state_5.sqlite").unlink()
        self.assertEqual(self.turns(), {})

    def test_a_question_is_an_order_up_on_the_card_and_in_the_news(self):
        log = self.thread("a", [event(NOW - 10, "task_started")])
        state = bar()
        self.poll(state, NOW)
        self.assertEqual(caffe["session_state"](state, 1, NOW)[0], "brewing")
        self.write(
            log,
            [
                event(NOW - 10, "task_started"),
                call(NOW + 1, "request_user_input_async"),
                event(NOW + 2, "task_complete"),
            ],
        )
        self.poll(state, NOW + 3)  # after a 12-second turn: no guessing needed
        self.assertEqual(caffe["session_state"](state, 1, NOW + 3), ("ready", NOW + 2))
        self.assertEqual(state["toast"][0], "Order up! Codex in caffe has a question for you.")
        self.assertEqual(state["visit"], (1, "ready"))
        title, status, note = caffe["card_lines"](state, 1, NOW + 5, 22)
        self.assertIn("caffe", title)
        self.assertIn("has a question", note)

    def poll(self, state, now):
        agents = {1: ("codex", "ttys001", NOW - 600, 0, 0)}
        with (
            patch.dict(
                GLOBALS,
                scan_agents=lambda: dict(agents),
                scan_copilot_sessions=lambda: {},
                scan_cwds=lambda pids: {p: FOLDER for p in pids},
            ),
            patch("time.time", return_value=now),
        ):
            caffe["update"](state)


if __name__ == "__main__":
    unittest.main()
