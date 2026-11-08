import contextlib
import io
import math
import runpy
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
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
        "activity": {1: (0, math.inf)},  # brewing the whole time
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


def play(state, start, end, size=(80, 24)):
    """Render frames from `start` to `end`; returns the last one's lines and pictures."""
    now, lines, pics = start, [], {}
    while now < end:
        lines, pics = caffe["render"](state, now, size)
        now += 0.12
    return SimpleNamespace(lines=lines, pics=pics)


class BatteryTests(unittest.TestCase):
    def test_pmset_output_is_parsed(self):
        on_battery = "Now drawing from 'Battery Power'\n -InternalBattery-0\t18%; discharging;"
        self.assertEqual(caffe["parse_battery"](on_battery), (True, 18))
        self.assertEqual(caffe["parse_battery"]("Now drawing from 'AC Power'\n"), (False, None))

    def test_low_battery_lets_the_display_sleep_until_plugged_in(self):
        state, caf, started = bar(), Mock(), []
        first = caf
        fake_start = lambda saver=False: started.append(saver) or Mock()  # noqa: E731
        for battery, saver in (((True, 50), False), ((True, 19), True), ((False, 19), False)):
            with patch.dict(GLOBALS, read_battery=lambda b=battery: b, start_caffeinate=fake_start):
                caf = caffe["check_power"](state, caf)
            self.assertEqual(state.get("saver", False), saver)
        self.assertEqual(started, [True, False])
        first.terminate.assert_called_once()  # or -dimsu would keep the display on
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
        self.assertEqual(frame.pics["bun"][0], ("bun", "kanelbulle", 0))
        frame = play(state, at(14, 31, month=12), at(14, 31, month=12) + 0.2)
        self.assertEqual(frame.pics["bun"][0], ("bun", "lussekatt", 0))

    def test_cat_nibbles_the_bun_until_it_is_gone(self):
        state = bar(due={"nibble"})
        frame = play(state, at(14, 40), at(14, 40) + 8)
        self.assertEqual(state["bun_bites"], 1)
        self.assertEqual(frame.pics["bun"][0], ("bun", "kanelbulle", 1))
        self.assertIn("takes a bite", state["toast"][0])
        state["bun_bites"] = caffe["BUN_BITES"]
        self.assertNotIn("bun", play(state, at(14, 50), at(14, 50) + 0.2).pics)

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
        play(state, 0, 0.5)
        state["due"] = {"mouse"}
        with patch("random.uniform", side_effect=lambda a, b: b):
            play(state, 0.5, 6)
        self.assertNotIn("mouse", state)
        self.assertNotIn("mice", state)
        self.assertIn("got away", state["toast"][0])

    def test_sleeping_cat_ignores_mice(self):
        state = bar(due={"mouse"})
        state["cat"].mode = "nap"
        play(state, 1, 1.2)
        self.assertIn("sleeps right through it", state["toast"][0])
        self.assertFalse(state["cat"].chasing)

    def test_mice_come_out_on_an_empty_bar_after_the_last_cup_is_knocked(self):
        state = bar(due={"mouse"}, live={})
        state["cat"].target = 1  # the cup it swatted, now gone
        play(state, 1, 1.2)
        self.assertIn("mouse", state)

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
        state, now = bar(due={"guest"}), 1.0
        with patch("random.random", return_value=0.7):
            while state.get("guest", {}).get("phase") != "leave" and now < 20:
                play(state, now, now + 0.1)
                now += 0.12
        self.assertEqual(state["cat"].mode, "hiss")
        self.assertIn("bolts", state["toast"][0])
        self.assertIsNone(self.visit(state, 0.7))
        self.assertEqual(state["visitors"], 1)

    def test_a_stray_that_starts_close_stops_instead_of_walking_onto_the_cat(self):
        state = bar()
        state["cat"].pet(0.5)
        guest = caffe["Cat"](0, 44, key="guest")
        state["guest"] = {"cat": guest, "phase": "enter"}
        with patch("random.random", return_value=0.7):
            play(state, 1, 3)
        self.assertEqual(state["guest"]["phase"], "stay")
        self.assertEqual(guest.x, 44.0)

    def test_a_shared_visit_is_not_a_pet(self):
        state = bar(due={"guest"})
        state["cat"].pet(0)
        self.visit(state, 0.7)
        self.assertFalse(state["cat"].pampered(603))  # 10 min after the pet, not the visit


class ReceiptTests(unittest.TestCase):
    def test_mice_visitors_and_treats_are_itemized(self):
        state = bar(live={}, orders={}, agent_time=0.0, order=1, longest=(0, ""))
        state.update(mice=2, visitors=1)
        state["cat"].feed(0)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            caffe["receipt"](state, 60)
        for line in ("Mice caught by", "Visiting cats", "Tip for", "1 treat"):
            self.assertIn(line, out.getvalue())


class SpriteTests(unittest.TestCase):
    def test_new_sprites_draw_something(self):
        for key in (("mouse", 1, True, 2 / 3), ("treat", 2, 1.0), ("bun", "lussekatt")):
            img = caffe["SPRITES"][key[0]](*key[1:])
            self.assertTrue(any(img.buf[3::4]), key)

    def test_every_cup_look_cat_pose_and_coat_draws(self):
        glaze = caffe["DRINKS"]["claude"][2]
        for look in caffe["LOOKS"]:
            for k in (1.0, 2 / 3):
                self.assertTrue(any(caffe["cup_sprite"](glaze, look, 3, k).buf[3::4]), look)
        poses = (("sit", 2, True), ("groom", 1), ("slap", 2), ("yawn",), ("hiss",))
        for coat in range(len(caffe["COATS"])):
            for pose in (*poses, ("walk", 3), ("nap", 1)):
                img = caffe["cat_sprite"](coat, pose, True, 1.0)
                self.assertTrue(any(img.buf[3::4]), (coat, pose))

    def test_a_knocked_cup_slides_away_and_fades(self):
        glaze = caffe["SERVED_GLAZE"]
        first, last = (caffe["knock_sprite"](glaze, f) for f in (0, caffe["KNOCK_FRAMES"] - 1))
        self.assertGreater(sum(first.buf[3::4]), 4 * sum(last.buf[3::4]))

    def test_a_bitten_bun_shows_more_of_its_plate(self):
        def brightness(bites):
            buf = caffe["bun_sprite"]("kanelbulle", bites).buf
            return sum(buf) - sum(buf[3::4])

        self.assertGreater(brightness(3), brightness(0))


if __name__ == "__main__":
    unittest.main()
