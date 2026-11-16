import contextlib
import io
import math
import runpy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
GLOBALS = caffe["main"].__globals__


def bar(capybara=True, **changes):
    state = {
        "start": 0,
        "cat": caffe["Cat"](0, caffe["HOME_X"], capybara=capybara),
        "live": {},
        "leaving": {},
        "knocked": {},
        "first_seen": {},
        "broken": 0,
        "toast": None,
        "gfx": True,
        "rush": False,
    }
    state.update(changes)
    return state


def place(cat, now=0, k=1.0):
    frame = caffe["Frame"](79, True)
    cat.place(frame, frame.art(3), 7, k, now)
    return frame.pics


def mirror_bytes(img):
    return b"".join(
        img.buf[(y * img.w + x) * 4 : (y * img.w + x + 1) * 4]
        for y in range(img.h)
        for x in reversed(range(img.w))
    )


class CapybaraModeTests(unittest.TestCase):
    def test_cli_modes_help_and_invalid_arguments(self):
        stdin, updater = Mock(), Mock(return_value=7)
        stdin.isatty.return_value = True
        with (
            patch("sys.stdin", stdin),
            patch("subprocess.Popen") as popen,
            patch("subprocess.run") as run,
            patch.dict(GLOBALS, self_update=updater),
        ):
            for args, selected in (([], False), (["--capybara"], True)):
                with self.subTest(args=args), patch("sys.argv", ["caffe", *args]):
                    self.assertIs(caffe["check_args"](), selected)
            for alias in ("-h", "--help"):
                out = io.StringIO()
                with (
                    self.subTest(alias=alias),
                    patch("sys.argv", ["caffe", alias]),
                    contextlib.redirect_stdout(out),
                    self.assertRaises(SystemExit) as exited,
                ):
                    caffe["check_args"]()
                self.assertEqual(exited.exception.code, 0)
                for text in ("--capybara", "turtle", "half", "lettuce", "caffe update"):
                    self.assertIn(text, out.getvalue())
            for args in (
                ["--unknown"],
                ["capybara"],
                ["--capybara", "extra"],
                ["--capybara", "--capybara"],
                ["--capybara", "--help"],
                ["update", "--capybara"],
            ):
                with (
                    self.subTest(args=args),
                    patch("sys.argv", ["caffe", *args]),
                    self.assertRaises(SystemExit) as exited,
                ):
                    caffe["main"]()
                self.assertIn("usage: caffe", exited.exception.code)
                self.assertIn("--capybara", exited.exception.code)
            stdin.isatty.return_value = False
            for args in ([], ["--capybara"]):
                with (
                    patch("sys.argv", ["caffe", *args]),
                    self.assertRaises(SystemExit) as exited,
                ):
                    caffe["main"]()
                self.assertEqual(exited.exception.code, "caffe needs an interactive terminal.")
            # Help and update are available even without a terminal.
            with (
                patch("sys.argv", ["caffe", "--help"]),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as exited,
            ):
                caffe["main"]()
            self.assertEqual(exited.exception.code, 0)
            with (
                patch("sys.argv", ["caffe", "update"]),
                self.assertRaises(SystemExit) as exited,
            ):
                caffe["main"]()
            self.assertEqual(exited.exception.code, 7)
            updater.assert_called_once_with()
            popen.assert_not_called()
            run.assert_not_called()

    def test_startup_uses_selected_mode(self):
        for args, selected in (([], False), (["--capybara"], True)):
            with self.subTest(args=args):
                stdin, caf, states = Mock(), Mock(), []
                stdin.isatty.return_value, stdin.fileno.return_value = True, 10
                stdin.read.return_value = "q"
                starter, receipt = Mock(return_value=caf), Mock()

                def draw(state, *_, states=states):
                    states.append(state)
                    return []

                with (
                    patch("sys.argv", ["caffe", *args]),
                    patch("sys.stdin", stdin),
                    contextlib.redirect_stdout(io.StringIO()),
                    patch("signal.signal"),
                    patch("termios.tcgetattr", return_value=[0] * 7),
                    patch("termios.tcsetattr") as restore,
                    patch("tty.setcbreak"),
                    patch("select.select", return_value=([stdin], [], [])),
                    patch("time.time", return_value=100),
                    patch("subprocess.Popen") as popen,
                    patch("subprocess.run") as run,
                    patch.dict(
                        GLOBALS,
                        start_caffeinate=starter,
                        update=Mock(),
                        check_power=lambda _, process: process,
                        kitty_graphics=lambda _: True,
                        cell_pixels=lambda _: (8, 16),
                        draw=draw,
                        receipt=receipt,
                    ),
                ):
                    caffe["main"]()
                self.assertEqual(len(states), 1)
                resident = states[0]["cat"]
                self.assertIs(resident.capybara, selected)
                self.assertEqual(place(resident)["cat"][0][0], "capybara" if selected else "cat")
                self.assertIn("capybara riding a turtle" if selected else "cat", resident.title)
                self.assertIn(resident.title, states[0]["toast"][0])
                starter.assert_called_once_with()
                caf.terminate.assert_called_once_with()
                receipt.assert_called_once_with(states[0], 100)
                restore.assert_called_once()
                popen.assert_not_called()
                run.assert_not_called()

    def test_default_cat_and_visitors_stay_cats(self):
        cat = caffe["Cat"](0, 40)
        self.assertFalse(cat.capybara)
        self.assertEqual(cat.speed, 7)
        self.assertIn(caffe["COATS"][cat.coat][0], cat.title)
        self.assertEqual(place(cat)["cat"][0], ("cat", cat.coat, *cat.pose(0), 1.0))
        self.assertTrue(cat.feed(0))
        self.assertEqual(place(cat)[("cat", "treat")][0], ("treat", 0, 1.0))
        state = bar(due={"guest"})
        state["cat"].x, state["cat"].mode, state["cat"].until = 40, "sit", 100
        with patch("random.random", return_value=0.99):
            _, pics = caffe["render"](state, 1, (80, 24))
        guest = state["guest"]["cat"]
        self.assertFalse(guest.capybara)
        self.assertEqual(pics["cat"][0][0], "capybara")
        self.assertEqual(pics["guest"][0][0], "cat")
        self.assertIn("cat", guest.title)
        self.assertTrue(guest.feed(1))
        self.assertEqual(place(guest, 1)[("guest", "treat")][0], ("treat", 0, 1.0))
        state = bar(capybara=False)
        with patch("time.time", return_value=0):
            caffe["on_key"](state, "f")
        self.assertEqual(state["toast"][0], f"{state['cat'].name} munches a treat.")

    def test_capybara_moves_at_half_speed_in_all_contexts(self):
        for part in ("day", "night"):
            for rush in (False, True):
                for chasing in (False, True):
                    for errand in (None, "new", "ready", "biscuit", "knock"):
                        with self.subTest(part=part, rush=rush, chasing=chasing, errand=errand):
                            states = [bar(capybara=mode, rush=rush) for mode in (False, True)]
                            base = 12 if rush else 5 if part == "night" else 7
                            speed = caffe["CHASE_SPEED"] if chasing else base
                            if errand:
                                speed = max(speed, caffe["ERRAND_SPEED"])
                            with (
                                patch.dict(GLOBALS, daypart=Mock(return_value=part)),
                                patch("random.random", return_value=0.99),
                            ):
                                for state in states:
                                    cat = state["cat"]
                                    cat.x = 20
                                    cat.go(160)
                                    cat.chasing = chasing
                                    cat.target, cat.errand = (1, errand) if errand else (None, None)
                                    for tick in range(1, 6):
                                        now = tick / 10
                                        caffe["bar_clock"](state, now)
                                        caffe["bar_clock"](state, now)
                                        cat.step(now, 200, False, 5)
                                    self.assertEqual(cat.speed, base)
                            normal, capy = (state["cat"] for state in states)
                            self.assertAlmostEqual(normal.x - 20, speed * 0.5)
                            self.assertAlmostEqual(capy.x - 20, speed * 0.25)
                            self.assertAlmostEqual(normal.distance, capy.distance * 2)
        # Animation still follows distance, not time or the choice of animal.
        cat, capy = caffe["Cat"](0, 10), caffe["Cat"](0, 10, capybara=True)
        for animal in (cat, capy):
            animal.go(30)
            before = animal.pose(0)
            self.assertEqual(animal.pose(0.1), before)
        cat.step(0.2, 80, False, 5)
        capy.step(0.4, 80, False, 5)
        self.assertEqual(cat.x, capy.x)
        self.assertEqual(cat.pose(0.2), capy.pose(0.4))
        capy.go(capy.x + 0.1)
        capy.target = 1
        capy.step(0.5, 80, False, 5)
        self.assertEqual(capy.x, capy.goal)
        self.assertEqual(capy.mode, "look")

    def test_capybara_leaps_slower_and_lands_on_target(self):
        for start, end in ((0, -4), (-4, 0)):
            animals = [caffe["Cat"](0, 20, capybara=mode) for mode in (False, True)]
            for animal in animals:
                animal.y = start
                animal.go(20, end)
                animal.step(0, 80, False, 5)
                self.assertEqual(animal.mode, "crouch")
                animal.step(caffe["CROUCH_S"], 80, False, 5)
                self.assertEqual(animal.mode, "leap")
            normal, capy = animals
            self.assertAlmostEqual(capy.leap["time"], normal.leap["time"] * 2)
            launch, duration = capy.leap["start"], capy.leap["time"]
            normal.step(launch + duration / 2, 80, False, 5)
            capy.step(launch + duration / 2, 80, False, 5)
            self.assertEqual((normal.x, normal.y), (20, end))
            self.assertEqual(normal.mode, "walk")
            self.assertEqual(capy.mode, "leap")
            self.assertLess(capy.y, (start + end) / 2)
            capy.step(launch + duration, 80, False, 5)
            self.assertEqual((capy.x, capy.y), (20, end))
            self.assertIsNone(capy.leap)
            capy.step(launch + duration + 0.1, 80, False, 5)
            self.assertEqual(capy.y, end)

    def test_all_capybara_poses_include_rider_and_turtle(self):
        expected = {
            *(("walk", i) for i in range(8)),
            *(("nap", i) for i in range(8)),
            *(("look", i) for i in range(8)),
            *(("sit", i, closed) for i in range(8) for closed in (False, True)),
            *(("groom", i) for i in (1, 2)),
            *(("slap", i) for i in (1, 2, 3)),
            *(("leap", up, i) for up in (False, True) for i in range(4)),
            ("yawn",),
            ("hiss",),
            ("meow",),
            ("crouch",),
        }
        cat, emitted = caffe["Cat"](0, 20, capybara=True), set()
        modes = ("sit", "walk", "nap", "look", "groom", "purr", "eat", "nibble", "yawn")
        for mode in (*modes, "hiss", "meow", "crouch", "slap", "leap"):
            cat.mode, cat.until = mode, 1.6
            for up in (False, True):
                cat.leap = {"start": 0, "time": 4, "up": up}
                for tick in range(240):
                    cat.distance = tick * 0.8
                    for direction in (-1, 1):
                        cat.dir = direction
                        emitted.add(cat.pose(tick / 24)[0])
        self.assertEqual(emitted, expected)
        for pose in sorted(emitted):
            for k in (1.0, 2 / 3):
                with self.subTest(pose=pose, scale=k):
                    images = [caffe["SPRITES"]["capybara"](pose, flip, k) for flip in (False, True)]
                    self.assertEqual(images[1].buf, mirror_bytes(images[0]))
                    self.assertNotEqual(images[0].buf, images[1].buf)
                    for img in images:
                        self.assertEqual((img.cols, img.rows), (math.ceil(7 * k), math.ceil(3 * k)))
                        self.assertEqual((img.w, img.h), (img.cols * 16, img.rows * 32))
                        rider, turtle = 0, 0
                        for y in range(img.h):
                            for x in range(img.w):
                                i = (y * img.w + x) * 4
                                r, g, b, a = img.buf[i : i + 4]
                                if a < 200:
                                    continue
                                unit_y = (y + 0.5) / (2 * k)
                                rider += 8 < unit_y < 34 and r > g * 1.2 and g > b * 1.2
                                turtle += 34 < unit_y < 46 and g > r * 1.15 and g > b * 1.2
                        self.assertGreater(rider, 200 * k * k)
                        self.assertGreater(turtle, 100 * k * k)
        self.assertNotEqual(
            caffe["capybara_sprite"](("nap", 0), False, 1).buf,
            caffe["capybara_sprite"](("sit", 0, False), False, 1).buf,
        )

    def test_feeding_selects_lettuce_and_preserves_limits(self):
        state = bar()
        cat = state["cat"]
        for now in (0, 10, 20):
            with patch("time.time", return_value=now):
                self.assertFalse(caffe["on_key"](state, "f"))
            self.assertEqual(cat.mode, "eat")
            self.assertEqual(cat.until, now + 2.4)
            self.assertEqual(cat.plan, [("sit", 1.5)])
            self.assertEqual(state["toast"][0], f"{cat.name} munches lettuce.")
            for bites in range(4):
                self.assertEqual(
                    place(cat, now + bites * 0.6 + 0.01)[("cat", "treat")][0],
                    ("lettuce", bites, 1.0),
                )
        with patch("time.time", return_value=30):
            caffe["on_key"](state, "f")
        self.assertEqual(cat.fed, [0, 10, 20])
        self.assertIn("is full", state["toast"][0])
        cat.step(22.4, 80, False, 5)
        self.assertEqual(cat.mode, "sit")
        self.assertNotIn(("cat", "treat"), place(cat, 22.4))
        self.assertFalse(cat.feed(599.99))
        self.assertTrue(cat.feed(600))
        self.assertEqual(cat.fed, [0, 10, 20, 600])
        with patch("time.time", return_value=601):
            caffe["on_key"](state, "p")
        self.assertEqual(cat.pets, 1)
        self.assertEqual(cat.mode, "purr")
        self.assertEqual(cat.until, 604)
        self.assertIn(("cat", "hearts"), place(cat, 601))
        state.update(orders={}, agent_time=0, order=1, longest=(0, ""))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            caffe["receipt"](state, 602)
        for text in (f"Tip for {cat.name}", "1 pet", "4 treats"):
            self.assertIn(text, out.getvalue())

    def test_lettuce_disappears_progressively_with_bites(self):
        for k in (1.0, 2 / 3):
            images = [caffe["SPRITES"]["lettuce"](bites, k) for bites in range(4)]
            for img in images:
                self.assertEqual((img.cols, img.rows), (math.ceil(2 * k), 1))
            areas = [sum(a > 200 for a in img.buf[3::4]) for img in images]
            self.assertGreater(areas[-1], 0)
            self.assertTrue(all(a > b for a, b in zip(areas, areas[1:])), areas)
            for before, after in zip(images, images[1:]):
                self.assertTrue(all(b <= a for a, b in zip(before.buf[3::4], after.buf[3::4])))
            self.assertNotEqual(images[0].buf, caffe["treat_sprite"](0, k).buf)

    def test_capybara_completes_cup_cleanup(self):
        state = bar(
            live={1: ("codex", "ttys001", 0, 30, 0)},
            initialized=True,
            orders={},
            agent_time=0,
            longest=(0, ""),
        )
        caffe["take_orders"](state, {}, 1)
        state["live"] = {}
        self.assertIn(1, state["leaving"])
        self.assertEqual(state["orders"], {"Codex": 1})
        climbed = landed = False
        cat = state["cat"]
        with patch("random.random", return_value=0.99):
            for tick in range(1, 401):
                now = 1 + tick * 0.12
                _, pics = caffe["render"](state, now, (80, 24))
                climbed |= cat.y < 0
                self.assertEqual(pics["cat"][0][0], "capybara")
                if 1 in state["knocked"] and cat.mode == "slap":
                    self.assertEqual(pics["cat"][2], pics["cup", 1][2])
                if climbed and 1 in state["knocked"] and cat.y == 0 and cat.leap is None:
                    landed = True
                    break
        self.assertTrue(climbed)
        self.assertTrue(landed)
        self.assertEqual(state["broken"], 1)
        self.assertTrue(caffe["gone"](state, 1, now))
        self.assertNotIn(("cup", 1), pics)
        with (
            patch("time.time", return_value=now),
            patch.dict(GLOBALS, scan_agents=lambda: {}, scan_copilot_sessions=lambda: {}),
        ):
            caffe["update"](state)
        self.assertFalse(state["leaving"])

    def test_rendering_fits_and_text_only_has_no_pictures(self):
        live = {pid: ("codex", f"ttys{pid:03}", 0, 30, 0) for pid in range(1, 6)}
        for size in ((24, 16), (40, 12), (80, 24), (160, 40)):
            for gfx in (False, True):
                with self.subTest(size=size, gfx=gfx):
                    state = bar(live=live, gfx=gfx)
                    state["cat"].feed(0)
                    with patch("random.random", return_value=0.99):
                        lines, pics = caffe["render"](state, 0.7, size)
                    self.assertLessEqual(len(lines), size[1] - 1)
                    self.assertTrue(
                        all(caffe["visible_len"](line) <= size[0] - 1 for line in lines)
                    )
                    if not gfx:
                        self.assertEqual(pics, {})
                        continue
                    self.assertEqual(pics["cat"][0][0], "capybara")
                    self.assertEqual(pics[("cat", "treat")][0][0], "lettuce")
                    for key, x, y, _ in pics.values():
                        img = caffe["SPRITES"][key[0]](*key[1:])
                        self.assertGreaterEqual(x, 0)
                        self.assertGreaterEqual(y, caffe["TOP_ROWS"])
                        self.assertLessEqual(x + img.cols, size[0] - 1)
                        self.assertLessEqual(y + img.rows, len(lines) - 1)
                    gallery = caffe["Gallery"]((8, 16))
                    codes = gallery.sync(pics)
                    self.assertIn("\033_Ga=t", codes)
                    self.assertIn("\033_Ga=p", codes)
                    self.assertEqual(gallery.sync(pics), "")


if __name__ == "__main__":
    unittest.main()
