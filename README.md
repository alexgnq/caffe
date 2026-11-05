# ☕ caffe

`caffeinate`, but with a coffee bar. Keeps your Mac awake and serves a steaming
cup for every AI coding agent you have running.

![caffe in action](caffe.gif)

- **Keeps the Mac awake** until you quit (`caffeinate -dimsu` under the hood).
- **One cup per agent session.** Copilot CLI, Codex CLI and Claude Code sessions
  running in a terminal show up on the counter. New ones pour in, and finished
  ones drain and get marked as served.
- **Steam follows the work.** The more CPU an agent uses, the more its cup
  steams.
- **A barista cat.** A pixel-art cat with a random name and coat each launch. It
  walks the counter, checks on new and finished cups, grooms, yawns and naps
  when things are quiet.
- **Lots of agents?** Cups shrink to fit the screen. Anything that still
  doesn't fit is counted below the counter.
- **Receipt on quit:** time awake, cups served per agent, longest session.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/alexgnq/caffe/main/install.sh | sh
```

Installs to `~/.local/bin/caffe`. Set `CAFFE_BIN_DIR` to install somewhere else.
Requires macOS and `python3` (included with the Xcode Command Line Tools). No
other dependencies.

## Usage

```sh
caffe
```

Press `q` or `Ctrl-C` to close the bar.

## How it works

- Every 3 seconds, `ps` is checked for `copilot`, `codex` and `claude` processes
  attached to a terminal. Background daemons and editor extensions are ignored.
- `caffeinate` is tied to caffe's process ID, so the Mac can sleep again as soon
  as caffe exits, even if it's killed.
- caffe stores nothing on disk. It redraws only the lines that changed and slows
  its frame rate when nothing is moving, so it uses very little CPU.

## Uninstall

```sh
rm ~/.local/bin/caffe
```

## License

[MIT](LICENSE)
