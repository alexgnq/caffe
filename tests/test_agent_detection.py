import runpy
import unittest
from pathlib import Path


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))


def sessions(rows):
    output, names = [], []
    for pid, parent, tty, cpu, command, args in rows:
        output.append(f"{pid} {parent} {tty} {cpu} 01:00 {args}")
        names.append(f"{pid} {command}")
    return caffe["agent_sessions"]("\n".join(output), "\n".join(names), 1000)


class AgentDetectionTests(unittest.TestCase):
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
        self.assertEqual(found[10], ("codex", "ttys001", 940, 5))

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
                self.assertEqual(found[20, kind][3], 7)

    def test_claude_app_is_visible_without_a_local_cli(self):
        found = sessions(
            [
                (20, 1, "??", 0, "/Applications/Claude.app/Contents/MacOS/Claude", "Claude"),
            ]
        )
        self.assertEqual(found, {(20, "claude"): ("claude", "app:Claude", 940, 0)})

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
        self.assertEqual(found[30, "vscode"], ("vscode", "app:VS Code", 940, 6))
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
                self.assertEqual(found[42], ("codex", "ttys004", 940, 2))


if __name__ == "__main__":
    unittest.main()
