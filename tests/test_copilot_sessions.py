import contextlib
import io
import runpy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
GLOBALS = caffe["update"].__globals__
KEY = "copilot-session:active"


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
        "order": 42,
        "longest": (0, ""),
        "cat": caffe["Cat"](0, caffe["HOME_X"]),
        "toast": None,
        "initialized": True,
        "gfx": True,
        "rush": False,
    }


class CopilotSessionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "data.db"
        self.database_patch = patch.dict(GLOBALS, COPILOT_SESSION_DB=self.database)
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """CREATE TABLE sessions (
                    id TEXT, title TEXT, session_type TEXT, execution_location TEXT,
                    is_running INTEGER, created_at TEXT, archived_at TEXT
                )"""
            )

    def insert(self, session_id="active", title="Fix widget", **changes):
        row = {
            "id": session_id,
            "title": title,
            "session_type": "project",
            "execution_location": "local",
            "is_running": 1,
            "created_at": "2026-11-05T12:00:00Z",
            "archived_at": None,
        }
        row.update(changes)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)", tuple(row.values())
            )

    def update(self, state, agents=None):
        with (
            patch.dict(GLOBALS, scan_agents=lambda: dict(agents or {})),
            patch("time.time", return_value=100),
        ):
            caffe["update"](state)

    def test_only_running_local_unarchived_sessions_and_chats_are_read(self):
        for kind in ("project", "agent", "general_chat"):
            self.insert(kind, session_type=kind)
        self.insert("idle", is_running=0)
        self.insert("cloud", execution_location="cloud")
        self.insert("archived", archived_at="2026-11-05T12:00:00Z")
        self.insert("unknown", session_type="unknown")
        before = self.database.read_bytes()

        found = caffe["scan_copilot_sessions"]()

        self.assertEqual(
            set(found), {f"copilot-session:{kind}" for kind in ("project", "agent", "general_chat")}
        )
        self.assertEqual(found["copilot-session:project"][:2], ("copilot-session", "Fix widget"))
        self.assertEqual(found["copilot-session:project"][2], 1793880000)
        self.assertEqual(self.database.read_bytes(), before)

    def test_titles_are_sanitized_and_unnamed_sessions_have_a_fallback(self):
        self.insert(title="  Fix\nwidget\033[31m  ")
        self.insert("unnamed-session", title=None)
        found = caffe["scan_copilot_sessions"]()
        self.assertEqual(found[KEY][1], "Fix widget[31m")
        self.assertEqual(found["copilot-session:unnamed-session"][1], "Session unnamed-")

    def test_missing_database_and_changed_schema_are_unavailable(self):
        with patch.dict(GLOBALS, COPILOT_SESSION_DB=self.database.with_name("missing.db")):
            self.assertIsNone(caffe["scan_copilot_sessions"]())
        self.assertFalse(self.database.with_name("missing.db").exists())
        with sqlite3.connect(self.database) as connection:
            connection.execute("DROP TABLE sessions")
        self.assertIsNone(caffe["scan_copilot_sessions"]())

    def test_session_cards_use_agent_label_in_app_color_in_every_size(self):
        state = bar()
        name, color, glaze = caffe["DRINKS"]["copilot"]
        for title in ("Fix widget", "Investigate ambiguous session labels"):
            self.insert(title=title)
            self.update(state)
            for size, (card_w, _, k, n_lines) in caffe["CARDS"].items():
                with self.subTest(title=title, size=size):
                    width = card_w - (0 if k is None else 8) - 1
                    lines = caffe["card_lines"](state, KEY, 100, width)[:n_lines]
                    self.assertTrue(lines[0].startswith(f"{color}{caffe['BOLD']}Agent"))
                    self.assertTrue(all(caffe["visible_len"](line) <= width for line in lines))
                    plain = lines[0].split(caffe["DIM"])[1].removesuffix(caffe["RESET"])
                    self.assertTrue(plain == title or title.startswith(plain.removesuffix("…")))
                    self.assertIn("brewing", lines[1])
                    look = caffe["cup_look"](state, KEY, 100, k or 1.0)
                    self.assertEqual(look[:3], ("cup", glaze, "brewing"))
                    caffe["SPRITES"][look[0]](*look[1:])
            with sqlite3.connect(self.database) as connection:
                connection.execute("DELETE FROM sessions")

    def test_title_changes_refresh_without_spawning_a_new_mug(self):
        self.insert()
        state = bar()
        self.update(state)
        first_seen = dict(state["first_seen"])
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE sessions SET title = 'New title'")
        self.update(state)
        self.assertEqual(state["live"][KEY][1], "New title")
        self.assertEqual(state["first_seen"], first_seen)

    def test_idle_sessions_disappear_without_a_served_cup_or_receipt_order(self):
        self.insert()
        state = bar()
        self.update(state)
        state["cat"].target = KEY
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE sessions SET is_running = 0")
        self.update(state)
        self.assertNotIn(KEY, state["live"])
        self.assertNotIn(KEY, state["leaving"])
        self.assertNotIn(KEY, state["first_seen"])
        self.assertIsNone(state["cat"].target)
        self.assertEqual(state["orders"], {})
        self.assertEqual(state["agent_time"], 0)

    def test_failed_database_scan_keeps_existing_sessions(self):
        self.insert()
        state = bar()
        self.update(state)
        previous = dict(state["live"])
        with sqlite3.connect(self.database) as connection:
            connection.execute("DROP TABLE sessions")
        self.update(state)
        self.assertEqual(state["live"], previous)
        self.assertEqual(state["leaving"], {})

    def test_sessions_coexist_with_upstream_apps_cli_rendering_and_receipts(self):
        self.insert()
        state = bar()
        agents = {
            1: ("codex", "ttys001", 0, 4, 64),
            (40, "copilot"): ("copilot", "app:Copilot", 0, 10, 512),
            (50, "vscode"): ("vscode", "app:VS Code", 0, 0, 64),
        }
        self.update(state, agents)
        self.assertEqual(set(state["live"]), {*agents, KEY})
        lines, pics = caffe["render"](state, 105, (96, 30))
        self.assertGreater(pics["cat"][3], pics["cup", KEY][3])  # the cat walks over the table
        drinks = {key[1]: pics[key][0][0] for key in pics if key[0] == "cup"}
        self.assertEqual(
            drinks, {1: "cup", KEY: "cup", (40, "copilot"): "latte", (50, "vscode"): "latte"}
        )
        self.assertTrue(any("Agent" in line for line in lines))
        self.assertTrue(any("512M" in line for line in lines))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            caffe["receipt"](state, 105)
        self.assertIn("Still brewing", output.getvalue())
        self.assertNotIn("Fix widget", output.getvalue())
        self.update(state)
        self.assertEqual(state["orders"], {"Codex": 1})  # the apps' lattes are no orders
        self.assertIn((40, "copilot"), state["leaving"])
        self.assertNotIn(KEY, state["leaving"])


if __name__ == "__main__":
    unittest.main()
