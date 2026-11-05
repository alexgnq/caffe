# ☕ caffe

`caffeinate`, but with a coffee bar. Keeps your Mac awake and serves a steaming
cup for every AI coding agent you have running.

![caffe in action](caffe.gif)

- **Keeps the Mac awake** until you quit (`caffeinate -dimsu` under the hood).
- **One cup per agent session.** Copilot CLI, Codex CLI and Claude Code sessions
  running in a terminal show up on the counter. New ones pour in.
- **Loyalty card.** Every finished session earns a stamp. Ten stamps and you've
  earned a free (real) coffee.
- **Receipt on quit:** time awake, cups served, longest session.

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

- Every 2 seconds, `ps` is checked for `copilot`, `codex` and `claude` processes
  attached to a terminal. Background daemons and editor extensions are ignored.
- `caffeinate` is tied to caffe's process ID, so the Mac can sleep again as soon
  as caffe exits, even if it's killed.
- Lifetime stats are stored in `~/.local/state/caffe/stats.json` (override with
  `CAFFE_STATS`).

## Uninstall

```sh
rm ~/.local/bin/caffe
rm -rf ~/.local/state/caffe
```

## License

[MIT](LICENSE)
