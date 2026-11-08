import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))


class DrinkTests(unittest.TestCase):
    def test_cups_show_their_name_then_project_or_terminal(self):
        for kind, (name, color, _) in caffe["DRINKS"].items():
            self.assertEqual(caffe["cup_label"](kind), f"{color}{name}{caffe['RESET']}")
        self.assertEqual(
            caffe["cup_label"]("opencode", 8),
            f"{caffe['DRINKS']['opencode'][1]}OpenCo…{caffe['RESET']}",
        )
        state = {
            "live": {
                1: ("claude", "ttys001", 0, 0, 0),
                2: ("codex", "ttys002", 0, 0, 0),
                3: ("pi", "ttys003", 0, 0, 0),
            },
            "leaving": {},
            "projects": {1: "caffe", 3: "a-rather-long-project-name"},
        }
        lines = {
            (pid, cell): caffe["cup_where"](state, pid, state["live"][pid], 1.0, cell)
            for pid in (1, 2, 3)
            for cell in (14, 8)
        }
        dim, reset = caffe["DIM"], caffe["RESET"]
        self.assertEqual(lines[1, 14], f"{dim}caffe{reset}")
        self.assertEqual(lines[2, 14], f"{dim}s002{reset}")  # no project: its terminal
        self.assertEqual(lines[3, 14], f"{dim}a-rather-lon…{reset}")
        self.assertEqual(lines[3, 8], f"{dim}a-rath…{reset}")

    def test_latte_steam_and_working_state_follow_cpu_or_memory(self):
        for cpu, memory, level in ((0, 64, 0), (3, 0, 1), (0, 256, 1), (25, 0, 2), (0, 1024, 2)):
            with self.subTest(cpu=cpu, memory=memory):
                session = ("codex", "app:Codex", 0, cpu, memory)
                state = {"live": {1: session}, "leaving": {}, "first_seen": {}, "start": 0}
                pics, (_, where, status) = caffe["cup_cell"](
                    state, 1, 5, caffe["LAYOUTS"][0], (2, 0)
                )
                self.assertEqual(pics["steam", 1][0][1], level)
                self.assertEqual(caffe["is_working"](session), level > 0)
                self.assertIn(f"{cpu}%", where)
                self.assertIn(caffe["fmt_mem"](memory), where)
                self.assertEqual(status, f"{caffe['DIM']}open{caffe['RESET']}")
        self.assertEqual(caffe["fmt_mem"](1536), "1.5G")
        self.assertFalse(caffe["is_working"](("codex", "ttys001", 0, 0, 2048)))

    def test_settled_latte_shows_resources_without_runtime_or_source_label(self):
        state = {
            "live": {(40, "vscode"): ("vscode", "app:VS Code", 0, 0, 64)},
            "leaving": {},
            "first_seen": {},
            "start": 0,
        }
        for layout in caffe["LAYOUTS"]:
            with self.subTest(layout=layout[0]):
                _, lines = caffe["cup_cell"](state, (40, "vscode"), 5, layout, (2, 0))
                usage = "0% · 64M" if layout[3] == 1 else "0%"  # mini cups are narrow
                self.assertEqual(lines[1], f"{caffe['DIM']}{usage}{caffe['RESET']}")
                self.assertTrue(all("app:" not in line for line in lines))

    def test_app_identity_survives_pouring_closing_and_knocking(self):
        key = (100, "vscode")
        state = {
            "live": {key: ("vscode", "app:VS Code", 0, 4, 64)},
            "leaving": {},
            "knocked": {},
            "first_seen": {key: 2},
            "start": 0,
            "cat": caffe["Cat"](0, caffe["HOME_X"]),
            "initialized": True,
            "orders": {},
            "agent_time": 0.0,
            "longest": (0, ""),
            "rush": False,
            "gfx": True,
        }
        layout = caffe["LAYOUTS"][0]
        for now in (2.1, 4.1, 5):
            pics, (label, where, _) = caffe["cup_cell"](state, key, now, layout, (2, 0))
            self.assertEqual(pics["mug", key][0][4][0], "latte")
            self.assertIn("VS Code", label)
            if now == 5:
                self.assertEqual(where, f"{caffe['DIM']}4% · 64M{caffe['RESET']}")
            for sprite, *_ in pics.values():
                caffe["SPRITES"][sprite[0]](*sprite[1:])
        with (
            patch.dict(
                caffe["update"].__globals__,
                scan_agents=lambda: {},
                scan_copilot_sessions=lambda: {},
            ),
            patch("time.time", return_value=6),
        ):
            caffe["update"](state)
        self.assertIn(key, state["leaving"])
        state["knocked"][key] = 7
        for layout in caffe["LAYOUTS"]:
            pics, _ = caffe["cup_cell"](state, key, 7.2, layout, (2, 0))
            sprite = pics["mug", key][0]
            self.assertEqual(sprite[0], "knock")
            self.assertEqual(sprite[4][0], "latte")
            caffe["SPRITES"][sprite[0]](*sprite[1:])

    def test_new_order_toast_names_the_project_or_terminal_but_not_the_app(self):
        for source, cwds, toast in (
            ("ttys001", {}, "New order: Codex on ttys001 ☕"),
            ("ttys001", {1: "/Users/me/code/caffe"}, "New order: Codex in caffe ☕"),
            ("app:Codex", {}, "New order: Codex ☕"),
        ):
            state = {
                "live": {},
                "leaving": {},
                "knocked": {},
                "first_seen": {},
                "initialized": True,
                "rush": False,
                "cat": caffe["Cat"](0, caffe["HOME_X"]),
            }
            with (
                patch.dict(
                    caffe["update"].__globals__,
                    scan_agents=lambda source=source: {1: ("codex", source, 0, 0, 0)},
                    scan_copilot_sessions=lambda: {},
                    scan_cwds=lambda pids, cwds=cwds: {p: cwds[p] for p in pids if p in cwds},
                ),
                patch("time.time", return_value=6),
            ):
                caffe["update"](state)
            self.assertEqual(state["toast"][0], toast)

    def test_closing_an_app_is_not_a_served_cup(self):
        state = {
            "live": {
                (40, "vscode"): ("vscode", "app:VS Code", 0, 0, 0),
                1: ("codex", "ttys001", 5, 0, 0),
            },
            "leaving": {},
            "knocked": {},
            "first_seen": {},
            "initialized": True,
            "rush": False,
            "orders": {},
            "agent_time": 0.0,
            "longest": (0, ""),
            "cat": caffe["Cat"](0, caffe["HOME_X"]),
        }
        with (
            patch.dict(
                caffe["update"].__globals__,
                scan_agents=lambda: {},
                scan_copilot_sessions=lambda: {},
            ),
            patch("time.time", return_value=100),
        ):
            caffe["update"](state)
        self.assertEqual(state["orders"], {"Codex": 1})
        self.assertEqual(state["longest"], (95, "Codex"))
        self.assertIn((40, "vscode"), state["leaving"])

    def test_pour_lands_at_each_drinks_rim(self):
        for source, drink in (("ttys001", "espresso"), ("app:Codex", "latte")):
            state = {
                "live": {1: ("codex", source, 0, 0, 0)},
                "leaving": {},
                "first_seen": {1: 2},
                "start": 0,
            }
            for layout in caffe["LAYOUTS"][:2]:
                pics, _ = caffe["cup_cell"](state, 1, 3, layout, (2, 0))
                mug, pour = pics["mug", 1], pics["pour", 1]
                rows = pour[0][2]
                rim = (rows - 1) * caffe["CH"] + caffe["DRINK_RIMS"][drink] % caffe["CH"]
                self.assertLess(rim, rows * caffe["CH"])
                self.assertEqual(
                    pour[2] * caffe["CH"] + rim, mug[2] * caffe["CH"] + caffe["DRINK_RIMS"][drink]
                )


if __name__ == "__main__":
    unittest.main()
