import contextlib
import io
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
GLOBALS = caffe["update"].__globals__


def printed(state, now):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        caffe["receipt"](state, now)
    return out.getvalue()


def bar(**changes):
    cat = caffe["Cat"](0, caffe["HOME_X"])
    cat.name = "Miso"
    state = {
        "start": 0,
        "live": {},
        "orders": {},
        "agent_time": 0.0,
        "broken": 0,
        "order": 42,
        "longest": (0, ""),
        "cat": cat,
    }
    state.update(changes)
    return state


class ReceiptTests(unittest.TestCase):
    def test_busy_bar_itemizes_orders_breakage_agent_time_and_tip(self):
        state = bar(
            live={
                7: ("claude", "ttys007", 3000, 0, 0),
                (40, "vscode"): ("vscode", "app:VS Code", 0, 0, 0),
            },
            orders={"Claude": 1, "Codex": 3},
            agent_time=4800.0,
            broken=2,
            longest=(2400, "Claude"),
        )
        state["cat"].pets = 3
        text = printed(state, 3600)
        lines = [line.strip() for line in text.splitlines()]
        self.assertIn("Order #0042", text)
        self.assertLess(text.index("Espresso · Codex"), text.index("Espresso · Claude"))
        self.assertIn("×3", next(line for line in lines if "Codex" in line))
        self.assertIn("Cups broken by Miso", text)
        # 4800 s served plus 600 s still brewing, over an hour awake; the open app doesn't count.
        self.assertIn("Agent time", text)
        self.assertIn("1h 30m (1.5×)", text)
        self.assertIn("Still brewing", next(line for line in lines if line.endswith(" 1")))
        self.assertIn("Tip for Miso", text)
        self.assertIn("3 pets ♥", text)
        self.assertTrue(all(len(line) <= 34 for line in lines if "☕" not in line))

    def test_quiet_bar_keeps_it_short(self):
        text = printed(bar(), 60)
        self.assertIn("Cups served", text)
        for missing in ("Espresso", "broken", "Agent time", "Still brewing", "Tip for"):
            self.assertNotIn(missing, text)

    def test_one_pet_is_singular(self):
        state = bar()
        state["cat"].pets = 1
        self.assertIn("1 pet ♥", printed(state, 60))

    def test_agent_time_only_counts_while_the_bar_was_open(self):
        # The bar opened at 1000. Both sessions were already running; Codex ends at 1500.
        claude, codex = ("claude", "ttys007", 0, 0, 0), ("codex", "ttys008", 0, 0, 0)
        state = bar(start=1000, live={7: claude, 8: codex})
        state.update(leaving={}, knocked={}, first_seen={}, initialized=True, rush=False)
        with (
            patch.dict(
                GLOBALS,
                scan_agents=lambda: {7: claude},
                scan_copilot_sessions=lambda: {},
                scan_cwds=lambda pids: {},
            ),
            patch("time.time", return_value=1500),
        ):
            caffe["update"](state)
        self.assertEqual(state["agent_time"], 500)
        self.assertEqual(state["longest"], (1500, "Codex"))  # the whole session
        # 500 s for Codex and 1000 s for Claude, over 1000 s awake.
        self.assertIn("25m 00s (1.5×)", printed(state, 2000))


if __name__ == "__main__":
    unittest.main()
