import contextlib
import io
import os
import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))
GLOBALS = caffe["update"].__globals__
DIM, RESET, GOLD = caffe["DIM"], caffe["RESET"], caffe["GOLD"]
SIZE = os.terminal_size((96, 24))


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


def status(state, pid, now):
    return caffe["card_lines"](state, pid, now, 22)[1]


def look(state, pid, now):
    return caffe["cup_look"](state, pid, now, 1.0)[2:4]


class CupStatusTests(unittest.TestCase):
    def test_a_session_brews_finishes_its_turn_then_goes_cold(self):
        state = bar()
        poll(state, 100, {1: claude(20)})
        self.assertEqual(status(state, 1, 110), f"brewing {DIM}10s{RESET}")
        self.assertEqual(look(state, 1, 110)[0], "brewing")
        # Waiting on the model uses little CPU; a short lull is still brewing.
        poll(state, 115, {1: claude(0.5)})
        poll(state, 125, {1: claude(30)})
        self.assertEqual(status(state, 1, 130), f"brewing {DIM}30s{RESET}")
        # The coffee is stirred faster while the agent works harder.
        stirs = {look(state, 1, 130 + t * 0.075)[1] for t in range(4)}
        self.assertEqual(len(stirs), 4)

        poll(state, 200, {1: claude(0)})
        self.assertEqual(status(state, 1, 200), f"{GOLD}{caffe['BOLD']}ready{RESET} {DIM}1m{RESET}")
        self.assertEqual(look(state, 1, 200), ("ready", 0))
        self.assertEqual(caffe["card_lines"](state, 1, 200, 22)[2], f"{GOLD}waiting for you{RESET}")
        self.assertIn("Order up! Claude", state["toast"][0])
        self.assertEqual(state["visit"], 1)  # the cat goes to look

        cold = 125 + caffe["COLD_S"]
        poll(state, cold, {1: claude(0)})
        self.assertEqual(status(state, 1, cold), f"{caffe['COLD']}cold{RESET} {DIM}15m{RESET}")
        self.assertEqual(look(state, 1, cold), ("cold", 0))
        self.assertEqual(state["biscuits"], {1})  # left too long: the cat has the biscuit

        poll(state, cold + 10, {1: claude(10)})
        self.assertEqual(status(state, 1, cold + 15), f"brewing {DIM}5s{RESET}")

    def test_a_short_burst_of_cpu_is_not_a_finished_turn(self):
        state = bar()
        poll(state, 100, {1: claude(0)})
        poll(state, 103, {1: claude(10)})  # someone typing
        poll(state, 140, {1: claude(0)})
        self.assertEqual(status(state, 1, 140), f"{DIM}idle 37s{RESET}")
        self.assertNotIn("Order up", (state["toast"] or ("",))[0])

    def test_sessions_already_running_at_startup_start_out_idle(self):
        state = bar()
        poll(state, 100, {1: claude(0)})
        self.assertEqual(status(state, 1, 160), f"{DIM}idle 1m{RESET}")
        self.assertIn("quiet since", caffe["card_lines"](state, 1, 160, 22)[2])

    def test_ready_orders_come_first(self):
        state = bar()
        agents = {1: claude(20), 2: ("codex", "ttys002", 0, 20, 0), 3: ("pi", "ttys003", 0, 0, 0)}
        quiet_codex = {**agents, 2: ("codex", "ttys002", 0, 0, 0)}
        for now, seen in ((100, agents), (120, agents), (125, quiet_codex), (160, quiet_codex)):
            poll(state, now, seen)
        self.assertEqual(caffe["card_order"](state, 160), [2, 1, 3])

    def test_the_cat_checks_on_a_ready_order_and_eats_a_cold_ones_biscuit(self):
        state = bar()
        state["live"] = {1: claude(0)}
        state["projects"] = {1: "caffe"}
        state["visit"], state["biscuits"] = 1, {1}
        cat = state["cat"]
        with patch("random.random", return_value=0.99):
            for tick in range(300):
                caffe["render"](state, tick * 0.12, (80, 24))
                if cat.mode == "nibble":
                    break
        self.assertLess(cat.y, 0)  # up among the cards
        self.assertIn("ate the biscuit off Claude's saucer", state["toast"][0])
        self.assertEqual(state["biscuits"], set())
        for tick in range(300, 500):
            caffe["render"](state, tick * 0.12, (80, 24))
        self.assertEqual(cat.y, 0)  # and back down again

    def test_the_cat_waits_up_instead_of_napping_while_an_order_is_ready(self):
        cat = caffe["Cat"](0, 40)
        cat.mode, cat.until = "sit", 0
        with patch("random.random", return_value=0.0):  # it would nap if it could
            for tick in range(1, 300):
                cat.step(tick * 0.12, 80, True, 4, waiting=True)
                self.assertNotEqual(cat.mode, "nap")

    def test_header_and_tab_title_sum_up_the_bar(self):
        state = bar()
        agents = {
            1: claude(20),
            2: claude(10),
            3: claude(0),
            (40, "codex"): ("codex", "app:Codex", 0, 0, 2048),
        }
        poll(state, 100, agents)
        header = caffe["header"](state, 100, 120)
        self.assertIn("2 brewing", header)
        self.assertIn("1 idle", header)
        self.assertIn("p to pet", header)
        # In a narrow pane, the tally outlasts the key hints.
        narrow = caffe["header"](state, 100, 60)
        self.assertIn("brewing", narrow)
        self.assertNotIn("pet", narrow)

        state["gfx"] = False
        out = io.StringIO()
        with contextlib.redirect_stdout(out), patch("shutil.get_terminal_size", return_value=SIZE):
            shown = caffe["draw"](state, 100, None, [])
        self.assertIn("\033]2;☕ 2 brewing · 1 idle\007", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out), patch("shutil.get_terminal_size", return_value=SIZE):
            caffe["draw"](state, 100, None, shown)
        self.assertNotIn("\033]2;", out.getvalue())  # unchanged: not sent again

        poll(state, 101, {k: v for k, v in agents.items() if k != 1})
        self.assertIn("1 served", caffe["tally"](state, 101))

    def test_an_empty_bar_has_no_tally(self):
        state = bar()
        poll(state, 100, {(40, "codex"): ("codex", "app:Codex", 0, 30, 2048)})
        self.assertEqual(caffe["tally"](state, 100), "")
        lines, pics = caffe["render"](state, 100, (96, 24))
        self.assertNotIn("brewing", lines[0])
        self.assertTrue(any("No orders yet" in line for line in lines))
        self.assertEqual(pics["idle"][0][2], "empty")

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
        self.assertTrue(
            caffe["card_lines"](state, 1, 105, 22)[0].endswith(f"{DIM}project-1{RESET}")
        )

        poll(state, 110, app)
        self.assertIn("Served: Claude in project-1", state["toast"][0])
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

    def test_status_durations_are_short(self):
        since = caffe["fmt_since"]
        self.assertEqual(
            [since(s) for s in (-1, 45, 600, 7200, 3 * 86400)], ["0s", "45s", "10m", "2h", "3d"]
        )


if __name__ == "__main__":
    unittest.main()
