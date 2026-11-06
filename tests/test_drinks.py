import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))


class DrinkTests(unittest.TestCase):
    def test_app_and_terminal_labels_keep_their_names(self):
        for kind in ("codex", "copilot", "vscode"):
            name, color, _ = caffe["DRINKS"][kind]
            self.assertEqual(
                caffe["cup_label"](kind, f"app:{name}", 1),
                f"{color}{name}{caffe['RESET']}",
            )
        for kind in caffe["AGENTS"]:
            name, color, _ = caffe["DRINKS"][kind]
            self.assertEqual(
                caffe["cup_label"](kind, "ttys001", 1),
                f"{color}{name}{caffe['RESET']} {caffe['DIM']}s001{caffe['RESET']}",
            )

    def test_latte_steam_and_working_state_follow_cpu_or_memory(self):
        for cpu, memory, level in ((0, 64, 0), (3, 0, 1), (0, 256, 1), (25, 0, 2), (0, 1024, 2)):
            with self.subTest(cpu=cpu, memory=memory):
                session = ("codex", "app:Codex", 0, cpu, memory)
                state = {"live": {1: session}, "leaving": {}, "first_seen": {}, "start": 0}
                pics, _, status = caffe["cup_cell"](state, 1, 5, caffe["LAYOUTS"][0], (2, 0))
                self.assertEqual(pics["steam", 1][0][1], level)
                self.assertEqual(caffe["is_working"](session), level > 0)
                self.assertIn(f"{cpu}%", status)
                self.assertIn(caffe["fmt_mem"](memory), status)
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
                _, label, status = caffe["cup_cell"](state, (40, "vscode"), 5, layout, (2, 0))
                self.assertEqual(status, f"{caffe['DIM']}0% · 64M{caffe['RESET']}")
                self.assertNotIn("app:", label)

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
            pics, label, status = caffe["cup_cell"](state, key, now, layout, (2, 0))
            self.assertEqual(pics["mug", key][0][4][0], "latte")
            self.assertIn("VS Code", label)
            if now == 5:
                self.assertEqual(status, f"{caffe['DIM']}4% · 64M{caffe['RESET']}")
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
            pics, _, _ = caffe["cup_cell"](state, key, 7.2, layout, (2, 0))
            sprite = pics["mug", key][0]
            self.assertEqual(sprite[0], "knock")
            self.assertEqual(sprite[4][0], "latte")
            caffe["SPRITES"][sprite[0]](*sprite[1:])

    def test_new_order_toast_names_the_terminal_but_not_the_app(self):
        for source, toast in (
            ("ttys001", "New order: Codex on ttys001 ☕"),
            ("app:Codex", "New order: Codex ☕"),
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
                pics, _, _ = caffe["cup_cell"](state, 1, 3, layout, (2, 0))
                mug, pour = pics["mug", 1], pics["pour", 1]
                rows = pour[0][2]
                rim = (rows - 1) * caffe["CH"] + caffe["DRINK_RIMS"][drink] % caffe["CH"]
                self.assertLess(rim, rows * caffe["CH"])
                self.assertEqual(
                    pour[2] * caffe["CH"] + rim, mug[2] * caffe["CH"] + caffe["DRINK_RIMS"][drink]
                )


if __name__ == "__main__":
    unittest.main()
