import contextlib
import io
import runpy
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
GLOBALS = caffe["main"].__globals__


def at(hour, minute=0, month=11):
    return time.mktime((2026, month, 6, hour, minute, 0, 0, 0, -1))


def bar(**changes):
    cat = caffe["Cat"](0, caffe["HOME_X"])
    cat.x, cat.mode, cat.until = 40.0, "sit", 1000
    state = {
        "start": 0,
        "live": {1: ("codex", "ttys001", 0, 30, 0)},
        "leaving": {},
        "knocked": {},
        "first_seen": {},
        "broken": 0,
        "gfx": True,
        "toast": None,
        "cat": cat,
    }
    state.update(changes)
    return state


def play(state, start, end, pids=(1,)):
    """Render frames from `start` to `end`; returns the last frame."""
    now = start
    while now < end:
        frame = caffe["Frame"](80, True)
        if pids:
            caffe["render_cups"](state, now, list(pids), frame, 20)
        else:
            caffe["render_idle"](state, now, frame)
        now += 0.12
    return frame


class BatteryTests(unittest.TestCase):
    def test_pmset_output_is_parsed(self):
        on_battery = "Now drawing from 'Battery Power'\n -InternalBattery-0\t18%; discharging;"
        self.assertEqual(caffe["parse_battery"](on_battery), (True, 18))
        self.assertEqual(caffe["parse_battery"]("Now drawing from 'AC Power'\n"), (False, None))

    def test_low_battery_lets_the_display_sleep_until_plugged_in(self):
        state, caf, started = bar(), Mock(), []
        fake_start = lambda saver=False: started.append(saver) or Mock()  # noqa: E731
        for battery, saver in (((True, 50), False), ((True, 19), True), ((False, 19), False)):
            with patch.dict(GLOBALS, read_battery=lambda b=battery: b, start_caffeinate=fake_start):
                caf = caffe["check_power"](state, caf)
            self.assertEqual(state.get("saver", False), saver)
        self.assertEqual(started, [True, False])
        self.assertIn("Plugged in", state["toast"][0])
        self.assertIn("battery 19%", caffe["header"]({**state, "battery": (True, 19)}, 0, 120))


class TimeOfDayTests(unittest.TestCase):
    def test_dayparts(self):
        part = caffe["daypart"]
        self.assertEqual(part(at(2)), "night")
        self.assertEqual(part(at(23, 30)), "night")
        self.assertEqual(part(at(7)), "morning")
        self.assertEqual(part(at(14, 29)), "day")
        self.assertEqual(part(at(14, 30)), "fika")
        self.assertEqual(part(at(15)), "day")

    def test_fika_sets_out_a_bun_lussekatt_in_december(self):
        state = bar(rush=False, daypart="day")
        caffe["bar_clock"](state, at(14, 30))
        self.assertIn("kanelbulle", state["toast"][0])
        frame = play(state, at(14, 31), at(14, 31) + 0.2)
        self.assertEqual(frame.pics["bun"][0], ("bun", "kanelbulle"))
        frame = play(state, at(14, 31, month=12), at(14, 31, month=12) + 0.2)
        self.assertEqual(frame.pics["bun"][0], ("bun", "lussekatt"))

    def test_night_cat_is_sleepy_and_slow(self):
        state = bar(rush=False)
        caffe["bar_clock"](state, at(2))
        self.assertTrue(state["cat"].sleepy)
        self.assertEqual(state["cat"].speed, 5.0)


class MischiefTests(unittest.TestCase):
    def test_cat_chases_and_catches_a_slow_mouse(self):
        state = bar()
        play(state, 0, 0.5)
        state["due"] = {"mouse"}
        with patch("random.uniform", side_effect=lambda a, b: a):
            play(state, 0.5, 4)
        self.assertNotIn("mouse", state)
        self.assertEqual(state["mice"], 1)
        self.assertFalse(state["cat"].chasing)

    def test_fast_mouse_escapes(self):
        state = bar()
        state["cat"].x = 60.0
        play(state, 0, 0.5)
        state["due"] = {"mouse"}
        with patch("random.uniform", side_effect=lambda a, b: b):
            play(state, 0.5, 6)
        self.assertNotIn("mouse", state)
        self.assertNotIn("mice", state)
        self.assertIn("got away", state["toast"][0])

    def test_sleeping_cat_ignores_mice(self):
        state = bar(due={"mouse"}, live={})
        play(state, 1, 1.2, pids=())
        self.assertIn("sleeps right through it", state["toast"][0])
        self.assertFalse(state["cat"].chasing)

    def test_treats_are_limited(self):
        cat = caffe["Cat"](0, caffe["HOME_X"])
        self.assertTrue(all(cat.feed(t) for t in (0, 10, 20)))
        self.assertFalse(cat.feed(30))
        self.assertTrue(cat.feed(700))
        frame = play(bar(cat=cat), 700.7, 700.8)
        self.assertEqual(frame.pics[("cat", "treat")][0][:2], ("treat", 1))


class GuestTests(unittest.TestCase):
    def visit(self, state, roll):
        with patch("random.random", return_value=roll):
            play(state, 1, 20)
            seen = state.get("guest", {}).get("phase")
            play(state, 20, 60)
        return seen

    def test_pampered_cat_shares_the_counter(self):
        state = bar(due={"guest"})
        state["cat"].pet(0.5)
        self.assertEqual(self.visit(state, 0.7), "stay")
        self.assertNotIn("guest", state)
        self.assertEqual(state["visitors"], 1)

    def test_grumpy_cat_hisses_the_stray_out(self):
        state = bar(due={"guest"})
        self.assertIsNone(self.visit(state, 0.7))
        self.assertIn("bolts", state["toast"][0])
        self.assertEqual(state["visitors"], 1)


class ReceiptTests(unittest.TestCase):
    def test_mice_visitors_and_treats_are_itemized(self):
        state = bar(live={}, orders={}, agent_time=0.0, order=1, longest=(0, ""))
        state.update(mice=2, visitors=1)
        state["cat"].feed(0)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            caffe["receipt"](state, 60)
        for line in ("Mice caught by", "Visiting cats", "Treats"):
            self.assertIn(line, out.getvalue())


class SpriteTests(unittest.TestCase):
    def test_new_sprites_draw_something(self):
        for key in (("mouse", 1, True, 2 / 3), ("treat", 2, 1.0), ("bun", "lussekatt")):
            img = caffe["SPRITES"][key[0]](*key[1:])
            self.assertTrue(any(img.buf[3::4]), key)


if __name__ == "__main__":
    unittest.main()
