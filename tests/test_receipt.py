import contextlib
import io
import runpy
import unittest
from pathlib import Path


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))


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
                7: ("claude", "ttys007", 3000, 0),
                (40, "vscode"): ("vscode", "app:VS Code", 0, 0),
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


if __name__ == "__main__":
    unittest.main()
