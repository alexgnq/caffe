import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))


def sessions(rows):
    output, names = [], []
    for pid, parent, tty, cpu, command, args in rows:
        output.append(f"{pid} {parent} {tty} {cpu} 0 01:00 {args}")
        names.append(f"{pid} {command}")
    return caffe["agent_sessions"]("\n".join(output), "\n".join(names), 1000)


class AgentDetectionTests(unittest.TestCase):
    def test_orphaned_crash_reporters_do_not_become_apps(self):
        helper = (
            "/Applications/ChatGPT.app/Contents/Frameworks/Codex Framework.framework/"
            "Versions/156.0/Helpers/browser_crashpad_handler"
        )
        found = sessions(
            [
                (20, 1, "??", 2, "/Applications/ChatGPT.app/Contents/MacOS/ChatGPT", "ChatGPT"),
                (21, 20, "??", 3, helper, "browser_crashpad_handler"),
                (22, 1, "??", 4, helper, "browser_crashpad_handler"),
            ]
        )
        self.assertEqual(found, {(20, "codex"): ("codex", "app:Codex", 940, 5, 0)})
        self.assertEqual(sessions([(22, 1, "??", 4, helper, "browser_crashpad_handler")]), {})

    def test_scanner_totals_cpu_and_ram_for_the_whole_app_tree(self):
        output = "\n".join(
            (
                "20 1 ?? 2.0 102400 01:00 Codex",
                "21 20 ?? 4.0 51200 00:30 renderer",
                "22 21 ?? 3.0 25600 00:20 codex app-server",
                "30 1 ?? 90.0 1048576 01:00 unrelated",
            )
        )
        names = "\n".join(
            (
                "20 /Applications/Codex.app/Contents/MacOS/Codex",
                "21 /Applications/Codex.app/Contents/Frameworks/Helper",
                "22 /bin/codex",
                "30 /bin/unrelated",
            )
        )
        with (
            patch(
                "subprocess.run",
                side_effect=[SimpleNamespace(stdout=output), SimpleNamespace(stdout=names)],
            ) as run,
            patch("time.time", return_value=1000),
        ):
            found = caffe["scan_agents"]()
        self.assertIn("rss=", run.call_args_list[0].args[0][-1])
        self.assertEqual(found, {(20, "codex"): ("codex", "app:Codex", 940, 9.0, 175.0)})

    def test_ui_drinks_represent_apps_instead_of_their_agent_backends(self):
        found = sessions(
            [
                (20, 1, "??", 0, "/Applications/Codex.app/Contents/MacOS/Codex", "Codex"),
                (21, 20, "??", 0, "/bin/codex", "codex app-server"),
                (
                    30,
                    1,
                    "??",
                    0,
                    "/Applications/GitHub Copilot.app/Contents/MacOS/github",
                    "github",
                ),
                (31, 30, "??", 0, "/bin/copilot-runtime", "copilot-runtime"),
                (
                    40,
                    1,
                    "??",
                    0,
                    "/Applications/Visual Studio Code.app/Contents/MacOS/Code",
                    "Code",
                ),
                (41, 40, "??", 0, "/bin/codex", "codex app-server"),
                (42, 40, "??", 0, "/bin/copilot-runtime", "copilot-runtime"),
            ]
        )
        self.assertEqual(
            sorted(session[0] for session in found.values()), ["codex", "copilot", "vscode"]
        )
        self.assertEqual(found[40, "vscode"][1], "app:VS Code")

    def test_cli_sessions_and_helpers(self):
        found = sessions(
            [
                (10, 1, "ttys001", 2, "/usr/local/bin/codex", "codex"),
                (11, 10, "ttys001", 3, "/usr/local/bin/codex", "codex"),
                (12, 1, "ttys002", 4, "claude", "claude"),
                (13, 1, "??", 5, "codex", "codex app-server"),
            ]
        )
        self.assertEqual(set(found), {10, 12})
        self.assertEqual(found[10], ("codex", "ttys001", 940, 5, 0))

    def test_a_sessions_cup_counts_the_tools_it_runs_but_not_nested_sessions(self):
        found = sessions(
            [
                (10, 1, "ttys001", 2, "/bin/claude", "claude"),
                (11, 10, "ttys001", 1, "/bin/zsh", "zsh -c npm test"),
                (12, 11, "ttys001", 40, "/bin/node", "node jest"),
                (13, 11, "ttys001", 5, "/bin/codex", "codex exec"),  # an agent the agent started
                (14, 13, "ttys001", 7, "/bin/cargo", "cargo build"),
                (20, 1, "ttys002", 90, "/bin/node", "node server.js"),  # not an agent's
            ]
        )
        self.assertEqual(set(found), {10, 13})
        self.assertEqual(found[10][3], 43)
        self.assertEqual(found[13][3], 12)

    def test_opencode_sessions_get_espressos_but_its_service_does_not(self):
        native = "/opt/homebrew/Cellar/opencode/2.2.6/bin/opencode"
        npm = "/usr/local/lib/node_modules/opencode-ai"
        found = sessions(
            [
                (10, 1, "ttys004", 3, "opencode", "opencode"),
                (20, 1, "ttys005", 1, "node", f"node {npm}/bin/opencode"),
                (
                    21,
                    20,
                    "ttys005",
                    4,
                    f"{npm}/node_modules/opencode-darwin-arm64/bin/opencode",
                    "opencode",
                ),
                (30, 1, "??", 6, native, f"{native} serve --service"),
            ]
        )
        self.assertEqual(set(found), {10, 20})
        self.assertEqual(found[10], ("opencode", "ttys004", 940, 3, 0))
        self.assertEqual(found[20][0], "opencode")
        self.assertEqual(found[20][3], 5)

    def test_vscode_identity_survives_agent_backend_changes(self):
        editor = [
            (30, 1, "??", 0, "/Applications/Visual Studio Code.app/Contents/MacOS/Code", "Code"),
        ]
        codex = [(31, 30, "??", 4, "/bin/codex", "codex app-server")]
        copilot = [(32, 30, "??", 3, "/bin/copilot-runtime", "copilot-runtime")]
        for backends in ([], codex, copilot, codex + copilot):
            found = sessions(editor + backends)
            self.assertEqual(set(found), {(30, "vscode")})
            self.assertEqual(found[30, "vscode"][0:2], ("vscode", "app:VS Code"))
        self.assertEqual(sessions(editor + codex + copilot)[30, "vscode"][3], 7)

    def test_desktop_helpers_make_one_latte_per_app(self):
        for app, kind, binary in (
            ("Codex", "codex", "Codex"),
            ("ChatGPT", "codex", "ChatGPT"),
            ("Claude", "claude", "Claude"),
            ("GitHub Copilot", "copilot", "github"),
        ):
            with self.subTest(app=app):
                found = sessions(
                    [
                        (20, 1, "??", 1, f"/Applications/{app}.app/Contents/MacOS/{binary}", app),
                        (
                            21,
                            20,
                            "??",
                            0,
                            f"/Applications/{app}.app/Contents/Frameworks/Helper",
                            "helper",
                        ),
                        (22, 21, "??", 3, f"/bin/{kind}", kind),
                        (23, 21, "??", 4, f"/bin/{kind}", kind),
                    ]
                )
                self.assertEqual(set(found), {(20, kind)})
                self.assertTrue(found[20, kind][1].startswith("app:"))
                self.assertEqual(found[20, kind][3], 8)

    def test_claude_app_is_visible_without_a_local_cli(self):
        found = sessions(
            [
                (20, 1, "??", 0, "/Applications/Claude.app/Contents/MacOS/Claude", "Claude"),
            ]
        )
        self.assertEqual(found, {(20, "claude"): ("claude", "app:Claude", 940, 0, 0)})

    def test_editor_app_and_terminal_sessions_stay_separate(self):
        base = "/Applications/Visual Studio Code.app/Contents"
        found = sessions(
            [
                (30, 1, "??", 0, f"{base}/MacOS/Code", "Code"),
                (31, 30, "??", 0, f"{base}/Frameworks/Code Helper", "helper"),
                (32, 31, "??", 4, "/extension/copilot-runtime", "copilot-runtime"),
                (33, 31, "??", 2, "/extension/copilot-runtime", "copilot-runtime"),
                (34, 31, "ttys003", 3, "/bin/copilot", "copilot"),
            ]
        )
        self.assertEqual(set(found), {(30, "vscode"), 34})
        self.assertEqual(found[30, "vscode"], ("vscode", "app:VS Code", 940, 9, 0))
        self.assertEqual(found[34][1], "ttys003")
        self.assertEqual(
            set(sessions([(30, 1, "??", 0, f"{base}/MacOS/Code", "Code")])), {(30, "vscode")}
        )

    def test_orchestrators_use_normal_cli_rules(self):
        for app in ("Orca", "T3 Code", "T3 Code (Beta)"):
            with self.subTest(app=app):
                found = sessions(
                    [
                        (40, 1, "??", 0, f"/Applications/{app}.app/Contents/MacOS/{app}", app),
                        (41, 40, "??", 0, "/bin/node", "node server.js"),
                        (42, 41, "ttys004", 2, "/bin/codex", "codex"),
                        (43, 41, "ttys005", 3, "/bin/codex", "codex"),
                        (44, 41, "ttys006", 4, "/bin/claude", "claude"),
                    ]
                )
                self.assertEqual(set(found), {42, 43, 44})
                self.assertEqual(found[42], ("codex", "ttys004", 940, 2, 0))


if __name__ == "__main__":
    unittest.main()
