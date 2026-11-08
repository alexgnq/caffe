import runpy
import unittest
from pathlib import Path
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

    def test_apps_are_listed_below_the_cards_not_served_as_cups(self):
        app = (40, "vscode")
        state = bar(live={app: ("vscode", "app:VS Code", 0, 4, 64), 1: ("codex", "ttys1", 0, 0, 0)})
        lines, pics = caffe["render"](state, 5, (96, 24))
        footer = next(line for line in lines if "apps" in line)
        self.assertIn("VS Code", footer)
        self.assertIn("4% · 64M", footer)
        self.assertNotIn(("cup", app), pics)
        self.assertIn(("cup", 1), pics)
        self.assertNotIn("app", caffe["tally"](state, 5))

    def test_opening_and_closing_an_app_is_quiet(self):
        app = (40, "vscode")
        state = bar()
        poll(state, 5, {app: ("vscode", "app:VS Code", 0, 4, 64)})
        self.assertIsNone(state["toast"])
        poll(state, 8, {})
        self.assertNotIn(app, state["leaving"])
        self.assertEqual(state["orders"], {})
        self.assertIsNone(state["toast"])

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


if __name__ == "__main__":
    unittest.main()
