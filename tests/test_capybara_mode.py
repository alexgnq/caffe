import contextlib
import io
import math
import runpy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
GLOBALS = caffe["main"].__globals__


def bar(species="capybara", **changes):
    state = {
        "start": 0,
        "cat": caffe["Cat"](0, caffe["HOME_X"], species=species),
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
            for args, selected in (([], "cat"), (["--capybara"], "capybara")):
                with self.subTest(args=args), patch("sys.argv", ["caffe", *args]):
                    self.assertEqual(caffe["check_args"](), selected)
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
                for text in ("--capybara", "turtle", "Press c", "caffe update"):
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
        for args, selected in (([], "cat"), (["--capybara"], "capybara")):
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
                self.assertEqual(resident.species, selected)
                self.assertEqual(place(resident)["cat"][0][0], selected)
                self.assertIn(selected, resident.title)
                self.assertIn(resident.title, states[0]["toast"][0])
                starter.assert_called_once_with()
                caf.terminate.assert_called_once_with()
                receipt.assert_called_once_with(states[0], 100)
                restore.assert_called_once()
                popen.assert_not_called()
                run.assert_not_called()

    def test_c_swaps_the_barista_and_back(self):
        state = bar("cat")
        cat = state["cat"]
        self.assertIn("c for a capybara", caffe["bottom_edge"](state, 120))
        with patch("time.time", return_value=0):
            self.assertFalse(caffe["on_key"](state, "c"))
            self.assertEqual(cat.species, "capybara")
            self.assertEqual(state["toast"][0], f"{cat.name} the capybara takes over the bar.")
            self.assertEqual(place(cat)["cat"][0][:2], ("capybara", cat.coat))
            self.assertIn("c for a cat", caffe["bottom_edge"](state, 120))
            caffe["on_key"](state, "c")
        self.assertEqual(cat.species, "cat")
        self.assertIn(caffe["COATS"][cat.coat][0], state["toast"][0])
        self.assertEqual(place(cat)["cat"][0], ("cat", cat.coat, *cat.pose(0), 1.0))

    def test_visitors_are_the_baristas_kind(self):
        for species in ("cat", "capybara"):
            with self.subTest(species=species):
                state = bar(species, due={"guest"})
                state["cat"].x, state["cat"].mode, state["cat"].until = 40, "sit", 100
                with patch("random.random", return_value=0.99):
                    _, pics = caffe["render"](state, 1, (80, 24))
                guest = state["guest"]["cat"]
                self.assertEqual(guest.species, species)
                self.assertEqual(pics["guest"][0][0], species)
                self.assertNotEqual(pics["guest"][0][1], pics["cat"][0][1])  # another coat or shell
                self.assertIn(species, guest.title)
                self.assertIn(guest.title, state["toast"][0])

    def test_turtle_walks_at_half_speed_in_short_steps_and_leaps_like_the_cat(self):
        cat, capy = caffe["Cat"](0, 20), caffe["Cat"](0, 20, species="capybara")
        for animal in (cat, capy):
            animal.go(60)
            for tick in range(1, 6):
                animal.step(tick / 10, 80, False, 5)
        self.assertAlmostEqual(capy.x - 20, (cat.x - 20) / 2)
        self.assertEqual(capy.pose(0.5), cat.pose(0.5))  # its legs keep the cat's rhythm
        for animal in (cat, capy):
            animal.go(animal.x, -4)
            animal.step(0.6, 80, False, 5)
        self.assertEqual(capy.leap["time"], cat.leap["time"])

    def test_capybara_faces_its_way_and_the_cup_it_swats(self):
        capy = caffe["Cat"](0, 20, species="capybara")
        capy.mode, capy.until = "sit", 10
        for direction in (-1, 1):
            capy.dir = direction
            self.assertEqual(capy.pose(0)[1], direction < 0)
        capy.slap(0)
        self.assertTrue(capy.pose(0)[1])

    def test_all_capybara_poses_include_rider_and_turtle(self):
        expected = {
            *(("walk", i) for i in range(8)),
            *(("nap", i) for i in range(8)),
            *(("look", i) for i in range(8)),
            *(("sit", i, closed) for i in range(8) for closed in (False, True)),
            *(("groom", i) for i in (1, 2)),
            *(("slap", i) for i in (1, 2, 3)),
            *(("leap", up, i) for up in (False, True) for i in range(4)),
            *(("eat", bites, chew) for bites in range(4) for chew in (0, 1)),
            ("yawn",),
            ("hiss",),
            ("meow",),
            ("crouch",),
        }
        cat, emitted = caffe["Cat"](0, 20, species="capybara"), set()
        cat.fed = [0]
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
                    images = [
                        caffe["SPRITES"]["capybara"](0, pose, flip, k) for flip in (False, True)
                    ]
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
                                rider += unit_y < 31 and r > g * 1.2 and g > b * 1.2
                                turtle += 28 < unit_y < 47 and g > r * 1.15 and g > b * 1.2
                        self.assertGreater(rider, 200 * k * k)
                        self.assertGreater(turtle, 100 * k * k)
        self.assertNotEqual(
            caffe["capybara_sprite"](0, ("nap", 0), False, 1).buf,
            caffe["capybara_sprite"](0, ("sit", 0, False), False, 1).buf,
        )
        self.assertNotEqual(  # each shell is its own
            caffe["capybara_sprite"](0, ("sit", 0, False), False, 1).buf,
            caffe["capybara_sprite"](1, ("sit", 0, False), False, 1).buf,
        )

    def test_feeding_gives_an_apple_and_preserves_limits(self):
        state = bar()
        cat = state["cat"]
        for now in (0, 10, 20):
            with patch("time.time", return_value=now):
                self.assertFalse(caffe["on_key"](state, "f"))
            self.assertEqual(cat.mode, "eat")
            self.assertEqual(cat.until, now + 2.4)
            self.assertEqual(cat.plan, [("sit", 1.5)])
            self.assertEqual(state["toast"][0], f"{cat.name} munches an apple.")
            for bites in range(4):
                pics = place(cat, now + bites * 0.6 + 0.01)
                self.assertEqual(pics["cat"][0][2][:2], ("eat", bites))  # the apple in its paw
                self.assertNotIn(("cat", "treat"), pics)  # no fish on the table
        with patch("time.time", return_value=30):
            caffe["on_key"](state, "f")
        self.assertEqual(cat.fed, [0, 10, 20])
        self.assertIn("is full", state["toast"][0])
        cat.step(22.4, 80, False, 5)
        self.assertEqual(cat.mode, "sit")
        self.assertEqual(place(cat, 22.4)["cat"][0][2][0], "sit")
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

    def test_apps_get_boba_tea_in_their_colour(self):
        app = (40, "vscode")
        state = bar(live={app: ("vscode", "app:VS Code", 0, 4, 64)})
        glaze = caffe["DRINKS"]["vscode"][2]
        self.assertEqual(caffe["cup_look"](state, app, 5, 1.0)[:3], ("boba", glaze, "busy"))
        state["cat"].species = "cat"
        self.assertEqual(caffe["cup_look"](state, app, 5, 1.0)[0], "latte")
        state["cat"].species = "capybara"
        teas = {}
        for kind in ("vscode", "codex"):
            img = caffe["boba_sprite"](caffe["DRINKS"][kind][2], "open", 0)
            i = (int(30 * 2) * img.w + int(caffe["CUP_X"] * 2) - 6) * 4  # mid-glass tea
            teas[kind] = tuple(img.buf[i : i + 3])
        self.assertNotEqual(teas["vscode"], teas["codex"])
        self.assertGreater(teas["codex"][2], teas["codex"][0])  # Codex's tea is blue
        for look in ("open", "busy", "pour", "drain", "empty"):
            self.assertTrue(any(caffe["boba_sprite"](glaze, look, 4).buf[3::4]), look)
        state["live"] = {}
        state["leaving"][app] = ("vscode", "app:VS Code", 5, 0)
        state["knocked"][app] = 6
        knock = caffe["cup_look"](state, app, 6.5, 1.0)
        self.assertEqual((knock[0], knock[-1]), ("knock", "boba"))
        caffe["SPRITES"][knock[0]](*knock[1:])
        state["cat"].target, state["cat"].errand, state["cat"].mode = app, "knock", "sit"
        del state["knocked"][app]
        caffe["cat_visit"](state, 7)
        self.assertIn("knocked VS Code's boba tea off", state["toast"][0])

    def test_a_closed_apps_drink_stays_what_it_was_served(self):
        app = (40, "vscode")
        state = bar(
            live={app: ("vscode", "app:VS Code", 0, 4, 64)},
            initialized=True,
            orders={},
            agent_time=0,
            longest=(0, ""),
        )
        caffe["take_orders"](state, {}, 5)
        state["live"] = {}
        state["cat"].species = "cat"  # the barista changes while the glass drains
        self.assertEqual(caffe["cup_look"](state, app, 5.5, 1.0)[0], "boba")
        state["knocked"][app] = 6
        self.assertEqual(caffe["cup_look"](state, app, 6.5, 1.0)[-1], "boba")
        with (
            patch.dict(GLOBALS, scan_agents=lambda: {}, scan_copilot_sessions=lambda: {}),
            patch("time.time", return_value=60),
        ):
            caffe["update"](state)
        self.assertNotIn(app, state["leaving"])
        self.assertEqual(state["drinks"], {})

    def test_apple_disappears_progressively_with_bites(self):
        def red(bites):
            img = caffe["capybara_sprite"](0, ("eat", bites, 0), False, 1.0)
            px = [img.buf[i : i + 4] for i in range(0, len(img.buf), 4)]
            return sum(a > 200 and r > 200 and g < 90 and b < 90 for r, g, b, a in px)

        areas = [red(bites) for bites in range(4)]
        self.assertGreater(areas[-1], 0)
        self.assertTrue(all(a > b for a, b in zip(areas, areas[1:])), areas)

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
                    self.assertEqual(pics["cat"][0][2][0], "eat")
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
