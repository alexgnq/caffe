import runpy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
GLOBALS = caffe["update"].__globals__
T3_APP = (7917, "t3")
NOW = 1_800_000_000.0


def iso(t):
    return caffe["datetime"].datetime.fromtimestamp(t, caffe["datetime"].timezone.utc).isoformat()


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


class T3SessionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "statev2.sqlite"
        patcher = patch.dict(GLOBALS, T3_SESSION_DB=self.database)
        patcher.start()
        self.addCleanup(patcher.stop)
        with sqlite3.connect(self.database) as db:
            db.executescript(
                """
                CREATE TABLE orchestration_v2_projection_threads (
                    thread_id TEXT, title TEXT, created_at TEXT, archived_at TEXT, deleted_at TEXT);
                CREATE TABLE orchestration_v2_projection_provider_sessions (
                    thread_id TEXT, provider TEXT, status TEXT, updated_at TEXT);
                CREATE TABLE orchestration_v2_projection_runs (
                    thread_id TEXT, ordinal INTEGER, status TEXT,
                    requested_at TEXT, completed_at TEXT);
                CREATE TABLE orchestration_v2_projection_runtime_requests (
                    thread_id TEXT, resolved_at TEXT);
                """
            )

    def thread(self, thread, provider="claudeAgent", status="ready", runs=(), asks=False, **extra):
        with sqlite3.connect(self.database) as db:
            db.execute(
                "INSERT INTO orchestration_v2_projection_threads VALUES (?, ?, ?, ?, ?)",
                (
                    thread,
                    extra.get("title", f"Fix {thread}"),
                    iso(NOW - 3000),
                    extra.get("archived"),
                    None,
                ),
            )
            db.execute(
                "INSERT INTO orchestration_v2_projection_provider_sessions VALUES (?, ?, ?, ?)",
                (thread, provider, status, iso(extra.get("updated", NOW - 60))),
            )
            for ordinal, (run, requested, completed) in enumerate(runs):
                db.execute(
                    "INSERT INTO orchestration_v2_projection_runs VALUES (?, ?, ?, ?, ?)",
                    (thread, ordinal, run, iso(requested), completed and iso(completed)),
                )
            if asks:
                db.execute(
                    "INSERT INTO orchestration_v2_projection_runtime_requests VALUES (?, NULL)",
                    (thread,),
                )

    def poll(self, state, now, agents=None):
        agents = {T3_APP: ("t3", "app:T3 Code", 0, 0, 512)} if agents is None else agents
        with (
            patch.dict(
                GLOBALS,
                scan_agents=lambda: dict(agents),
                scan_copilot_sessions=lambda: {},
                scan_cwds=lambda pids: {},
            ),
            patch("time.time", return_value=now),
        ):
            caffe["update"](state)

    def test_each_session_says_exactly_what_it_is_doing(self):
        self.thread(
            "busy", "codex", runs=[("completed", NOW - 900, NOW - 800), ("running", NOW - 30, None)]
        )
        self.thread("done", "acpRegistry_copilot", runs=[("completed", NOW - 300, NOW - 120)])
        self.thread("asking", runs=[("running", NOW - 50, None)], asks=True)
        self.thread("asking-after", runs=[("completed", NOW - 50, NOW - 40)], asks=True)
        self.thread("broke", runs=[("failed", NOW - 90, NOW - 80)])
        self.thread("fresh")
        self.thread("closed", status="stopped", runs=[("completed", NOW - 90, NOW - 80)])
        self.thread("archived", archived=iso(NOW), runs=[("running", NOW - 90, None)])
        self.thread("long-ago", runs=[("completed", NOW - 9000, NOW - 8000)], updated=NOW - 8000)
        sessions, told = caffe["scan_t3_sessions"](NOW)
        self.assertEqual(
            {key: (sessions[key][0], word, note) for key, (word, _, note) in told.items()},
            {
                "t3:busy": ("codex", "brewing", "in T3 Code"),
                "t3:done": ("copilot", "ready", "waiting for you"),
                "t3:asking": ("claude", "brewing", "in T3 Code"),
                "t3:asking-after": ("claude", "ready", "needs your approval"),
                "t3:broke": ("claude", "ready", "run failed"),
                "t3:fresh": ("claude", "idle", "in T3 Code"),
            },
        )
        self.assertEqual(sessions["t3:done"][1], "Fix done")
        self.assertEqual(told["t3:done"][1], NOW - 120)  # ready since its run completed

    def test_sessions_are_only_read_while_t3_code_is_open(self):
        self.thread("done", runs=[("completed", NOW - 300, NOW - 120)])
        state = bar()
        self.poll(state, NOW, agents={})
        self.assertNotIn("t3:done", state["live"])
        self.poll(state, NOW + 3)
        self.assertIn("t3:done", state["live"])
        self.assertEqual(caffe["session_state"](state, "t3:done", NOW + 3), ("ready", NOW - 120))
        self.assertEqual(caffe["card_order"](state, NOW + 3)[0], "t3:done")  # waiting for you
        title, status, note = caffe["card_lines"](state, "t3:done", NOW + 6, 22)  # poured
        self.assertIn("Claude", title)
        self.assertIn("Fix done", title)
        self.assertIn("ready", status)
        self.assertIn("waiting for you", note)

    def test_a_finished_turn_is_an_order_up_without_any_guessing(self):
        self.thread("work", "codex", runs=[("running", NOW - 30, None)])
        state = bar()
        self.poll(state, NOW)
        self.assertIn("New order: Codex in T3 Code", state["toast"][0])
        self.assertEqual(caffe["session_state"](state, "t3:work", NOW)[0], "brewing")
        with sqlite3.connect(self.database) as db:
            db.execute(
                "UPDATE orchestration_v2_projection_runs"
                " SET status = 'completed', completed_at = ?",
                (iso(NOW + 4),),
            )
        self.poll(state, NOW + 5)  # seconds later, not 30: T3 Code said so
        self.assertEqual(caffe["session_state"](state, "t3:work", NOW + 5)[0], "ready")
        self.assertIn("Order up! Codex is waiting for you", state["toast"][0])
        self.assertEqual(state["visit"], ("t3:work", "ready"))

    def test_closing_a_session_serves_it_but_a_forgotten_one_just_leaves(self):
        self.thread("work", "codex", runs=[("running", NOW - 30, None)])
        self.thread(
            "old", "codex", runs=[("completed", NOW - 1300, NOW - 1200)], updated=NOW - 1200
        )
        state = bar()
        self.poll(state, NOW)
        self.assertEqual(caffe["session_state"](state, "t3:old", NOW)[0], "cold")
        with sqlite3.connect(self.database) as db:
            db.execute(
                "UPDATE orchestration_v2_projection_provider_sessions SET status = 'stopped'"
            )
        self.poll(state, NOW + 3)
        self.assertIn("t3:work", state["leaving"])
        self.assertNotIn("t3:old", state["leaving"])
        self.assertEqual(state["orders"], {"Codex": 1})

    def test_unreadable_records_keep_the_sessions_already_on_the_table(self):
        self.thread("work", "codex", runs=[("running", NOW - 30, None)])
        state = bar()
        self.poll(state, NOW)
        with sqlite3.connect(self.database) as db:
            db.execute("DROP TABLE orchestration_v2_projection_runs")
        self.assertIsNone(caffe["scan_t3_sessions"](NOW))
        self.poll(state, NOW + 3)
        self.assertIn("t3:work", state["live"])
        self.assertEqual(caffe["session_state"](state, "t3:work", NOW + 3)[0], "brewing")
        self.assertEqual(state["leaving"], {})

    def test_providers_map_to_their_agents(self):
        agent = caffe["t3_agent"]
        self.assertEqual(
            [
                agent(p)
                for p in ("codex", "acpRegistry_copilot", "claudeAgent", "opencode", "other")
            ],
            ["codex", "copilot", "claude", "opencode", "t3"],
        )


if __name__ == "__main__":
    unittest.main()
