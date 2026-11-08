import contextlib
import io
import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
GLOBALS = caffe["update"].__globals__
DIM, RESET = caffe["DIM"], caffe["RESET"]


def bar():
    return {
        "start": 0,
        "live": {},
        "leaving": {},
        "knocked": {},
        "first_seen": {},
        "orders": {},
        "agent_time": 0.0,
        "broken": 0,
        "longest": (0, ""),
        "cat": caffe["Cat"](0, caffe["HOME_X"]),
        "toast": None,
        "initialized": True,
        "gfx": True,
        "rush": False,
    }


def claude(cpu):
    return ("claude", "ttys001", 0, cpu, 0)


def poll(state, now, agents, cwds=None):
    with (
        patch.dict(
            GLOBALS,
            scan_agents=lambda: dict(agents),
            scan_copilot_sessions=lambda: {},
            scan_cwds=lambda pids: {p: path for p, path in (cwds or {}).items() if p in pids},
        ),
        patch("time.time", return_value=now),
    ):
        caffe["update"](state)


def cup(state, pid, now):
    """The cup's pictures and its name, project and status lines."""
    return caffe["cup_cell"](state, pid, now, caffe["LAYOUTS"][0], (2, 0))


class CupStatusTests(unittest.TestCase):
    def test_sessions_brew_then_idle_then_go_cold(self):
        state = bar()
        poll(state, 100, {1: claude(20)})
        pics, (_, _, status) = cup(state, 1, 110)
        self.assertEqual(status, "brewing 10s")
        self.assertEqual(pics["steam", 1][0][1], 1)

        # Waiting on the model uses little CPU; a short lull is still brewing.
        poll(state, 115, {1: claude(0.5)})
        poll(state, 125, {1: claude(30)})
        pics, (_, _, status) = cup(state, 1, 130)
        self.assertEqual(status, "brewing 30s")
        self.assertEqual(pics["steam", 1][0][1], 2)

        poll(state, 200, {1: claude(0)})
        pics, (_, _, status) = cup(state, 1, 200)
        self.assertEqual(status, f"{DIM}idle 1m{RESET}")
        self.assertEqual(pics["steam", 1][0][1], 0)
        self.assertEqual(pics["mug", 1][0][2], 2)

        cold = 125 + caffe["COLD_S"]
        pics, (_, _, status) = cup(state, 1, cold)
        self.assertEqual(status, f"{DIM}cold 15m{RESET}")
        self.assertNotIn(("steam", 1), pics)
        self.assertEqual(pics["mug", 1][0][2], 1)  # flat: no crema
        for sprite, *_ in pics.values():
            caffe["SPRITES"][sprite[0]](*sprite[1:])

        poll(state, cold + 10, {1: claude(10)})
        _, (_, _, status) = cup(state, 1, cold + 15)
        self.assertEqual(status, "brewing 5s")

    def test_mini_cups_show_just_the_state(self):
        state = bar()
        poll(state, 100, {1: claude(20)})
        mini = caffe["LAYOUTS"][2]
        _, lines = caffe["cup_cell"](state, 1, 110, mini, (2, 0))
        self.assertEqual(lines[2], "brewing")
        self.assertTrue(all(caffe["visible_len"](line) < mini[1] for line in lines))

    def test_sessions_already_running_at_startup_start_out_idle(self):
        state = bar()
        poll(state, 100, {1: claude(0)})
        _, (_, _, status) = cup(state, 1, 160)
        self.assertEqual(status, f"{DIM}idle 1m{RESET}")

    def test_header_and_tab_title_sum_up_the_bar(self):
        state = bar()
        agents = {
            1: claude(20),
            2: claude(10),
            3: claude(0),
            (40, "codex"): ("codex", "app:Codex", 0, 0, 2048),
        }
        poll(state, 100, agents)
        header = caffe["header"](state, 100, 96)
        self.assertIn("2 brewing · 1 idle", header)
        self.assertIn("p to pet", header)
        # In a narrow pane, the summary outlasts the key hints.
        narrow = caffe["header"](state, 100, 60)
        self.assertIn("2 brewing · 1 idle", narrow)
        self.assertNotIn("pet", narrow)

        state["gfx"] = False
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            shown = caffe["draw"](state, 100, None, [])
        self.assertIn("\033]2;☕ 2 brewing · 1 idle\007", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            caffe["draw"](state, 100, None, shown)
        self.assertNotIn("\033]2;", out.getvalue())  # unchanged: not sent again

        poll(state, 101, {k: v for k, v in agents.items() if k != 1})
        self.assertIn("1 served", caffe["tally"](state, 101))

    def test_an_empty_bar_has_no_summary(self):
        state = bar()
        poll(state, 100, {(40, "codex"): ("codex", "app:Codex", 0, 30, 2048)})
        self.assertEqual(caffe["tally"](state, 100), "")
        self.assertNotIn("brewing", caffe["header"](state, 100, 96))

    def test_rush_hour_counts_brewing_sessions_not_open_apps(self):
        state = bar()
        apps = {(40 + i, "codex"): ("codex", "app:Codex", 0, 50, 2048) for i in range(4)}
        poll(state, 100, {1: claude(20), **apps})
        self.assertFalse(state["rush"])
        poll(state, 103, {p: claude(20) for p in range(1, 5)})
        self.assertTrue(state["rush"])
        self.assertIn("Rush hour! 4", state["toast"][0])

    def test_project_names_are_read_once_and_forgotten_with_the_cup(self):
        state, calls = bar(), []

        def cwds(pids):
            calls.append(set(pids))
            return {p: f"/Users/me/code/project-{p}" for p in pids}

        app = {(40, "codex"): ("codex", "app:Codex", 0, 0, 0)}
        with (
            patch.dict(
                GLOBALS,
                scan_copilot_sessions=lambda: {},
                scan_cwds=cwds,
                scan_agents=lambda: {1: claude(0), **app},
            ),
            patch("time.time", return_value=100),
        ):
            caffe["update"](state)
            caffe["update"](state)
        self.assertEqual(calls, [{1}, set()])  # apps have no project
        self.assertEqual(state["projects"], {1: "project-1"})
        _, (_, where, _) = cup(state, 1, 105)
        self.assertEqual(where, f"{DIM}project-1{RESET}")

        poll(state, 110, app)
        self.assertIn("Order up: Claude in project-1", state["toast"][0])
        state["knocked"][1] = 111
        poll(state, 120, app)
        self.assertEqual(state["projects"], {})


class ProjectTests(unittest.TestCase):
    def test_lsof_output_is_parsed(self):
        out = "p10\nfcwd\nn/Users/me/code/caffe\np11\nfcwd\nn/Users/me\n"
        with patch("subprocess.run", return_value=SimpleNamespace(stdout=out)) as run:
            self.assertEqual(
                caffe["scan_cwds"]([11, 10]), {10: "/Users/me/code/caffe", 11: "/Users/me"}
            )
        self.assertEqual(run.call_args.args[0][-2:], ["-p", "10,11"])
        self.assertEqual(caffe["scan_cwds"]([]), {})

    def test_project_names(self):
        name = caffe["project_name"]
        self.assertEqual(name(str(Path.home())), "~")
        self.assertEqual(name("/Users/me/code/caffe/"), "caffe")
        self.assertEqual(name("/"), "/")
        self.assertEqual(name("/Users/me/bad\033[31mname"), "bad[31mname")


class DurationTests(unittest.TestCase):
    def test_long_durations_count_days(self):
        self.assertEqual(caffe["fmt_dur"](2 * 86400 + 3 * 3600 + 5), "2d 3h")
        self.assertEqual(caffe["fmt_dur"](3600 + 5 * 60), "1h 05m")

    def test_status_durations_fit_a_cup(self):
        since = caffe["fmt_since"]
        self.assertEqual(
            [since(s) for s in (-1, 45, 600, 7200, 3 * 86400)], ["0s", "45s", "10m", "2h", "3d"]
        )
        self.assertLess(len(f"brewing {since(99 * 86400)}"), 14)


if __name__ == "__main__":
    unittest.main()
