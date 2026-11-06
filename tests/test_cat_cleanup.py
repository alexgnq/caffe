import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))


class CatCleanupTests(unittest.TestCase):
    def test_finished_cup_is_always_knocked(self):
        cat = caffe["Cat"](0, caffe["HOME_X"])
        state = {
            "cat": cat,
            "live": {},
            "leaving": {1: ("codex", "ttys001", 0, -10)},
            "knocked": {},
            "broken": 0,
            "visit": 1,
            "gfx": True,
        }
        with patch("random.random", return_value=0.99):
            for tick in range(1, 101):
                now = tick * 0.12
                frame = caffe["Frame"](80, True)
                caffe["render_cups"](state, now, [1], frame, 30)
                if 1 in state["knocked"]:
                    break
        self.assertIn(1, state["knocked"])
        self.assertEqual(cat.mode, "slap")
        self.assertEqual(state["broken"], 1)

    def test_cleanup_survives_pet_new_order_and_hidden_rows(self):
        cat = caffe["Cat"](0, 90)
        cat.pet(0)
        state = {
            "cat": cat,
            "live": {99: ("codex", "ttys099", 0, 0, 0)},
            "first_seen": {},
            "start": 0,
            "leaving": {pid: ("codex", "ttys001", 0, -pid) for pid in range(1, 13)},
            "knocked": {},
            "broken": 0,
            "visit": 99,
            "gfx": True,
        }
        finished = set(state["leaving"])
        with patch("random.random", return_value=0.99):
            for tick in range(1, 501):
                now = tick * 0.12
                pids = [pid for pid in state["leaving"] if not caffe["gone"](state, pid, now)]
                frame = caffe["Frame"](30, True)
                knocked = set(state["knocked"])
                caffe["render_cups"](state, now, pids + [99], frame, 20)
                for pid in state["knocked"].keys() - knocked:
                    self.assertEqual(frame.pics["cat"][2], frame.pics[("mug", pid)][2])
                if now < 3:
                    self.assertEqual(cat.mode, "purr")
                    self.assertFalse(state["knocked"])
                if finished <= state["knocked"].keys():
                    break
        self.assertEqual(finished, state["knocked"].keys())
        self.assertGreater(now, caffe["SERVED_S"])

    def test_graphics_cup_waits_for_swat_but_text_cup_expires(self):
        state = {"leaving": {1: ("codex", "ttys001", 0, -10)}, "knocked": {}, "gfx": True}
        self.assertFalse(caffe["gone"](state, 1, 100))
        state["gfx"] = False
        self.assertTrue(caffe["gone"](state, 1, 100))
        state["gfx"] = True
        state["knocked"][1] = 100
        self.assertFalse(caffe["gone"](state, 1, 100))
        self.assertTrue(caffe["gone"](state, 1, 100 + caffe["KNOCK_S"] + 0.01))

    def test_finished_cup_hidden_behind_live_cups_leaves_on_its_own(self):
        live = {pid: ("codex", f"ttys{pid:03}", pid, 0, 0) for pid in range(1, 41)}
        state = {
            "cat": caffe["Cat"](0, caffe["HOME_X"]),
            "live": live,
            "leaving": {99: ("codex", "ttys099", 0, 1000)},
            "knocked": {},
            "broken": 0,
            "first_seen": {},
            "start": 0,
            "gfx": True,
        }
        caffe["render_cups"](state, 1, [*live, 99], caffe["Frame"](40, True), 12)
        self.assertIn(99, state["hidden"])
        self.assertFalse(caffe["gone"](state, 99, caffe["SERVED_S"] - 1))
        self.assertTrue(caffe["gone"](state, 99, caffe["SERVED_S"] + 1))


if __name__ == "__main__":
    unittest.main()
