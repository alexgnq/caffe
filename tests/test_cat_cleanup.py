import io
import os
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))


def bar(**changes):
    state = {
        "start": 0,
        "cat": caffe["Cat"](0, caffe["HOME_X"]),
        "live": {},
        "leaving": {},
        "knocked": {},
        "first_seen": {},
        "broken": 0,
        "toast": None,
        "gfx": True,
    }
    state.update(changes)
    return state


class CatCleanupTests(unittest.TestCase):
    def test_the_cat_climbs_to_a_finished_cup_and_knocks_it_off(self):
        state = bar(leaving={1: ("codex", "ttys001", 0, -10)}, visit=1)
        climbed = False
        with patch("random.random", return_value=0.99):
            for tick in range(1, 201):
                _, pics = caffe["render"](state, tick * 0.12, (80, 24))
                climbed = climbed or state["cat"].y < 0
                if 1 in state["knocked"]:
                    break
        self.assertTrue(climbed)
        self.assertIn(1, state["knocked"])
        self.assertEqual(state["cat"].mode, "slap")
        self.assertEqual(pics["cat"][2], pics["cup", 1][2])  # beside the cup, on its row
        self.assertIn("off the table", state["toast"][0])
        self.assertEqual(state["broken"], 1)
        # Then it comes back down to its strip of table.
        for tick in range(201, 401):
            caffe["render"](state, tick * 0.12, (80, 24))
        self.assertEqual(state["cat"].y, 0)

    def test_cleanup_survives_a_pet_and_a_new_order(self):
        state = bar(
            live={99: ("codex", "ttys099", 0, 0, 0)},
            leaving={pid: ("codex", "ttys001", 0, -pid) for pid in range(1, 6)},
            visit=99,
        )
        state["cat"].pet(0)
        finished = set(state["leaving"])
        with patch("random.random", return_value=0.99):
            for tick in range(1, 801):
                now = tick * 0.12
                knocked = set(state["knocked"])
                _, pics = caffe["render"](state, now, (80, 24))
                # As cups go and the cards close up, the cat never ends up on the header.
                self.assertGreaterEqual(pics["cat"][2], caffe["TOP_ROWS"])
                for pid in state["knocked"].keys() - knocked:
                    self.assertEqual(pics["cat"][2], pics["cup", pid][2])
                if now < 3:
                    self.assertEqual(state["cat"].mode, "purr")
                    self.assertFalse(state["knocked"])
                if finished <= state["knocked"].keys():
                    break
        self.assertEqual(finished, state["knocked"].keys())

    def test_the_cat_knocks_a_closed_apps_latte_off_too(self):
        app = (40, "codex")
        state = bar(leaving={app: ("codex", "app:Codex", 0, -10)})
        with patch("random.random", return_value=0.99):
            for tick in range(1, 201):
                _, pics = caffe["render"](state, tick * 0.12, (80, 24))
                if app in state["knocked"]:
                    break
        self.assertIn(app, state["knocked"])
        self.assertIn("knocked Codex's latte off", state["toast"][0])

    def test_the_cat_only_leaps_between_the_table_and_the_cards(self):
        state = bar(leaving={1: ("codex", "ttys001", 0, -10)})
        cat, last, moves = state["cat"], None, []
        with patch("random.random", return_value=0.99):
            for tick in range(1, 400):
                caffe["render"](state, tick * 0.12, (80, 24))
                if last is not None and cat.y != last[1]:
                    moves.append((cat.mode, last[2]))
                last = (cat.x, cat.y, cat.mode)
        self.assertIn(1, state["knocked"])
        self.assertTrue(moves)
        # Height only changes mid-leap, and every leap starts with a crouch.
        self.assertEqual({mode for mode, _ in moves}, {"leap", "walk"})
        self.assertTrue(all(before in ("crouch", "leap") for _, before in moves))
        self.assertEqual(cat.y, 0)  # back down on its strip

    def test_pictures_are_placed_between_cells_when_the_terminal_says_how_big_they_are(self):
        gallery = caffe["Gallery"]()
        self.assertEqual(gallery.cell_at(10.6, 3.4), (11, 3, 0, 0))  # the nearest cell
        gallery.cell = (8, 16)
        self.assertEqual(gallery.cell_at(10.5, 3.25), (10, 3, 4, 4))
        self.assertEqual(gallery.cell_at(-2, 0.999), (0, 0, 0, 15))
        with patch.dict(caffe["SPRITES"], cat=lambda *_: caffe["Img"](1, 1)):
            out = gallery.sync({"cat": (("cat", 0), 10.5, 3.25, 3)})
            self.assertIn("X=4,Y=4,", out)
            self.assertIn("\033[4;11H", out)
            self.assertNotIn("X=", gallery.sync({"cat": (("cat", 0), 12, 3, 3)}))

    def test_the_cell_size_comes_from_the_terminal(self):
        for reply, size in (
            (b"\033[6;16;8t\033[?62;22c", (8, 16)),
            (b"\033[6;0;0t\033[?62c", None),
            (b"\033[?62c", None),
        ):
            read, write = os.pipe()
            os.write(write, reply)
            with patch("sys.stdout", io.StringIO()) as out:
                self.assertEqual(caffe["cell_pixels"](read), size)
            self.assertIn("\033[16t", out.getvalue())
            os.close(read)
            os.close(write)

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
        state = bar(live=live, leaving={99: ("codex", "ttys099", 0, 1000)})
        lines, _ = caffe["render"](state, 1, (40, 12))
        self.assertIn(99, state["hidden"])
        self.assertTrue(any("more orders" in line for line in lines))
        self.assertFalse(caffe["gone"](state, 99, caffe["SERVED_S"] - 1))
        self.assertTrue(caffe["gone"](state, 99, caffe["SERVED_S"] + 1))

    def test_a_backwards_clock_does_not_send_the_cat_off_the_table(self):
        cat = caffe["Cat"](100, 40)
        cat.go(60, -4)
        cat.step(90, 80, False, 4)  # ten seconds back in time
        self.assertEqual((cat.x, cat.y), (40.0, 0.0))


if __name__ == "__main__":
    unittest.main()
