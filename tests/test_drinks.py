import io
import os
import plistlib
import re
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
DIM, RESET, BOLD = caffe["DIM"], caffe["RESET"], caffe["BOLD"]


def bar(**changes):
    state = {
        "start": 0,
        "live": {},
        "leaving": {},
        "knocked": {},
        "first_seen": {},
        "initialized": True,
        "rush": False,
        "orders": {},
        "agent_time": 0.0,
        "longest": (0, ""),
        "broken": 0,
        "toast": None,
        "gfx": True,
        "cat": caffe["Cat"](0, caffe["HOME_X"]),
    }
    state.update(changes)
    return state


def poll(state, now, agents, cwds=None):
    with (
        patch.dict(
            caffe["update"].__globals__,
            scan_agents=lambda: dict(agents),
            scan_copilot_sessions=lambda: {},
            scan_cwds=lambda pids: {p: path for p, path in (cwds or {}).items() if p in pids},
        ),
        patch("time.time", return_value=now),
    ):
        caffe["update"](state)


class CardTests(unittest.TestCase):
    def test_a_card_names_the_agent_then_its_project_or_terminal(self):
        state = bar(
            live={
                1: ("claude", "ttys001", 0, 0, 0),
                2: ("codex", "ttys002", 0, 0, 0),
                3: ("pi", "ttys003", 0, 0, 0),
            },
            projects={1: "caffe", 3: "a-rather-long-project-name"},
        )
        for kind in caffe["AGENTS"]:
            name, color, _ = caffe["DRINKS"][kind]
            state["live"][9] = (kind, "ttys009", 0, 0, 0)
            title = caffe["card_lines"](state, 9, 5, 22)[0]
            self.assertTrue(title.startswith(f"{color}{BOLD}{name}{RESET}"), kind)
        titles = {pid: caffe["card_lines"](state, pid, 5, 22)[0] for pid in (1, 2, 3)}
        self.assertTrue(titles[1].endswith(f" {DIM}caffe{RESET}"))
        self.assertTrue(titles[2].endswith(f" {DIM}s002{RESET}"))  # no project: its terminal
        self.assertTrue(titles[3].endswith(f" {DIM}a-rather-long-proj…{RESET}"))
        for width in (22, 17):  # full and compact cards' room for words
            for pid in (1, 2, 3):
                lines = caffe["card_lines"](state, pid, 5, width)
                self.assertTrue(all(caffe["visible_len"](line) <= width for line in lines))

    def test_apps_get_a_latte_after_the_sessions(self):
        app, quiet = (40, "vscode"), (41, "copilot")
        state = bar(
            live={
                app: ("vscode", "app:VS Code", 0, 4, 64),
                quiet: ("copilot", "app:Copilot", 1, 0, 128),
                1: ("codex", "ttys1", 5, 0, 0),
            }
        )
        self.assertEqual(caffe["card_order"](state, 5), [1, app, quiet])
        _, pics = caffe["render"](state, 5, (96, 24))
        self.assertEqual(pics["cup", app][0][:3], ("latte", caffe["DRINKS"]["vscode"][2], "busy"))
        self.assertEqual(pics["cup", quiet][0][2], "open")
        self.assertEqual(pics["cup", 1][0][0], "cup")
        title, usage, _ = caffe["card_lines"](state, app, 5, 22)
        self.assertIn("VS Code", title)
        self.assertTrue(title.endswith(f"{DIM}app{RESET}"))
        self.assertEqual(usage, f"{DIM}busy 4% · 64M{RESET}")
        self.assertIn("open 0% · 128M", caffe["card_lines"](state, quiet, 5, 22)[1])
        self.assertNotIn("app", caffe["tally"](state, 5))
        for look in ("open", "busy", "pour", "drain", "empty"):
            self.assertTrue(any(caffe["latte_sprite"]((1, 2, 3), look, 4).buf[3::4]), look)

    def test_an_app_opens_a_tab_and_settles_it_when_it_closes(self):
        app = (40, "vscode")
        state = bar()
        poll(state, 5, {app: ("vscode", "app:VS Code", 0, 4, 64)})
        self.assertEqual(state["toast"][0], "VS Code opened a tab ☕")
        self.assertEqual(state["visit"], app)  # the cat goes to sniff it
        self.assertEqual(
            caffe["cup_look"](state, app, 6, 1.0)[:3],
            ("latte", caffe["DRINKS"]["vscode"][2], "pour"),
        )
        poll(state, 8, {})
        self.assertIn(app, state["leaving"])  # its latte drains, and the cat knocks it off
        self.assertEqual(state["orders"], {})  # but it's no order
        self.assertEqual(state["agent_time"], 0.0)
        self.assertEqual(state["toast"][0], "VS Code settled its tab ✔")
        self.assertEqual(
            caffe["cup_look"](state, app, 9, 1.0)[:3], ("latte", caffe["SERVED_GLAZE"], "drain")
        )
        self.assertIn("✔ closed", caffe["card_lines"](state, app, 9, 22)[1])
        state["knocked"][app] = 10
        knock = caffe["cup_look"](state, app, 10.5, 1.0)
        self.assertEqual((knock[0], knock[-1]), ("knock", "latte"))
        caffe["SPRITES"][knock[0]](*knock[1:])

    def test_new_order_toast_names_the_project_or_terminal(self):
        for cwds, toast in (
            ({}, "New order: Codex on ttys001 ☕"),
            ({1: "/Users/me/code/caffe"}, "New order: Codex in caffe ☕"),
        ):
            state = bar()
            poll(state, 6, {1: ("codex", "ttys001", 0, 0, 0)}, cwds)
            self.assertEqual(state["toast"][0], toast)
            self.assertEqual(state["visit"], 1)  # the cat goes to have a look

    def test_a_finished_session_is_served_and_counted(self):
        state = bar(live={1: ("codex", "ttys001", 5, 0, 0)}, projects={1: "caffe"})
        poll(state, 100, {})
        self.assertEqual(state["orders"], {"Codex": 1})
        self.assertEqual(state["longest"], (95, "Codex"))
        self.assertIn(1, state["leaving"])
        self.assertEqual(state["toast"][0], "Served: Codex in caffe, after 1m 35s ✔")
        lines = caffe["card_lines"](state, 1, 101, 22)
        self.assertIn("✔ served", lines[1])
        self.assertEqual(caffe["cup_look"](state, 1, 101, 1.0)[2], "drain")

    def test_a_new_session_pours_in(self):
        state = bar(live={1: ("codex", "ttys001", 0, 0, 0)}, first_seen={1: 10})
        looks = [caffe["cup_look"](state, 1, now, 1.0) for now in (10.1, 11, 11.9, 12.5)]
        self.assertEqual([look[2] for look in looks], ["pour", "pour", "pour", "idle"])
        self.assertLess(looks[0][3], looks[2][3])  # the cup fills up
        self.assertIn("pouring", caffe["card_lines"](state, 1, 11, 22)[1])
        # Sessions already running when caffe starts are served full.
        state["first_seen"][1] = 0.5
        self.assertEqual(caffe["cup_look"](state, 1, 1, 1.0)[2], "idle")

    def test_cards_shrink_to_fit_and_spill_over_below(self):
        live = {pid: ("codex", f"ttys{pid:03}", pid, 0, 0) for pid in range(1, 17)}
        sizes = {}
        for size in ((96, 40), (96, 24), (60, 14)):
            state = bar(live=live)
            lines, pics = caffe["render"](state, 5, size)
            cup = next(p[0] for key, p in pics.items() if key[0] == "cup")
            sizes[size] = cup[4], len(state["hidden"])
            self.assertLessEqual(len(lines), size[1] - 1 + 1)
        self.assertEqual(sizes[96, 40], (1.0, 0))  # full cards
        self.assertEqual(sizes[96, 24], (2 / 3, 0))  # compact cards, four to a row
        self.assertGreater(sizes[60, 14][1], 0)  # and some don't fit at all

    def test_text_only_cards_have_no_pictures_and_no_cat(self):
        state = bar(live={1: ("claude", "ttys001", 0, 0, 0)}, gfx=False, projects={1: "caffe"})
        lines, pics = caffe["render"](state, 5, (80, 24))
        self.assertEqual(pics, {})
        self.assertTrue(lines[3].startswith(f"  {caffe['DRINKS']['claude'][1]}{BOLD}Claude"))
        self.assertIn("idle", lines[4])


class AppIconTests(unittest.TestCase):
    @staticmethod
    def png(width):
        return caffe["PNG_MAGIC"] + b"\0\0\0\rIHDR" + width.to_bytes(4, "big") * 2 + b"rest"

    def icns(self, *widths):
        entries = b"".join(
            b"ic%02d" % i + (8 + len(self.png(w))).to_bytes(4, "big") + self.png(w)
            for i, w in enumerate(widths)
        )
        entries += b"is32" + (12).to_bytes(4, "big") + b"\0" * 4  # an old, non-PNG entry
        return b"icns" + (8 + len(entries)).to_bytes(4, "big") + entries

    def test_the_smallest_big_enough_png_is_picked_from_an_icns(self):
        icns_png = caffe["icns_png"]
        self.assertEqual(icns_png(self.icns(1024, 32, 128, 64)), self.png(64))
        self.assertEqual(icns_png(self.icns(16, 32)), self.png(32))  # nothing big enough
        self.assertIsNone(icns_png(self.icns()))
        self.assertIsNone(icns_png(b"not an icns file"))

    def test_an_app_icon_comes_from_its_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp, "Tool.app", "Contents")
            (bundle / "Resources").mkdir(parents=True)
            with open(bundle / "Info.plist", "wb") as info:
                plistlib.dump({"CFBundleIconFile": "tool"}, info)
            (bundle / "Resources" / "tool.icns").write_bytes(self.icns(128, 64))
            exe = SimpleNamespace(stdout=f"{bundle}/MacOS/Tool\n")
            with patch("subprocess.run", return_value=exe):
                self.assertEqual(caffe["app_icon"](42), self.png(64))
                icon = caffe["icon_sprite"](42, "codex")
                self.assertEqual((icon.data, icon.cols, icon.rows), (self.png(64), 2, 1))
            with patch("subprocess.run", return_value=SimpleNamespace(stdout="/bin/gone\n")):
                self.assertIsNone(caffe["app_icon"](42))
                tile = caffe["icon_sprite"](42, "codex")  # a tile in the app's colour
                self.assertTrue(any(tile.buf[3::4]))
            with patch("subprocess.run", return_value=exe) as run:
                tile = caffe["icon_sprite"](42, "codex", False)  # the terminal can't show PNGs
                self.assertFalse(isinstance(tile, caffe["Png"]))
                run.assert_not_called()

    def test_the_terminal_is_asked_about_pictures_and_pngs(self):
        for reply, expected in (
            (b"\033_Gi=31;OK\033\\\033_Gi=32;OK\033\\\033[?62;22c", (True, True)),
            (b"\033_Gi=31;OK\033\\\033_Gi=32;EINVAL\033\\\033[?62c", (True, False)),
            (b"\033[?1;2c", (False, False)),
        ):
            read, write = os.pipe()
            os.write(write, reply)
            with patch("sys.stdout", io.StringIO()) as out, patch.dict(os.environ, {"TMUX": ""}):
                self.assertEqual(caffe["kitty_graphics"](read), expected)
            self.assertIn("f=100;", out.getvalue())
            os.close(read)
            os.close(write)

    def test_an_apps_icon_goes_before_its_name_with_graphics_only(self):
        app = (40, "vscode")
        for gfx in (True, False):
            state = bar(live={app: ("vscode", "app:VS Code", 0, 4, 64)}, gfx=gfx)
            lines, pics = caffe["render"](state, 5, (96, 24))
            line = next(line for line in lines if "VS Code" in line)
            plain = re.sub(r"\033\[[\d;]*m", "", line)
            if gfx:
                key, col, row, _ = pics["icon", app]
                self.assertEqual(key, ("icon", 40, "vscode", True))
                self.assertEqual(lines[row], line)
                self.assertEqual(row, pics["cup", app][2])  # on the latte's first row
                self.assertEqual(plain[col : col + 3], "   ")  # room for it
                self.assertEqual(plain[col + 3 :].split()[:3], ["VS", "Code", "app"])
            else:
                self.assertNotIn(("icon", app), pics)
                self.assertEqual(plain.split(), ["VS", "Code", "app"])

    def test_png_pictures_are_sent_for_the_terminal_to_decode(self):
        gallery = caffe["Gallery"]()
        png = caffe["Png"](b"PNG", 2, 1)
        with patch.dict(caffe["SPRITES"], icon=lambda *_: png):
            out = []
            self.assertEqual(gallery.image(("icon", 1, "codex"), out)[1:], (2, 1))
        self.assertIn("f=100", out[0])
        self.assertNotIn("o=z", out[0])


if __name__ == "__main__":
    unittest.main()
