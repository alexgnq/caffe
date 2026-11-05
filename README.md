# ☕ caffe

`caffeinate`, but with a coffee bar. Keeps your Mac awake and serves a steaming
cup for every AI coding agent you have running.

![caffe in action](caffe.gif)

- **Keeps the Mac awake** until you quit (`caffeinate -dimsu` under the hood).
- **One cup per agent session.** Copilot CLI, Codex CLI, Claude Code and Pi
  sessions running in a terminal show up on the counter, each in its own
  colour. New ones pour in, and finished ones drain and turn grey.
- **Steam follows the work.** The more CPU an agent uses, the more its cup
  steams.
- **A barista cat.** A random name and coat each launch. It walks behind the
  cups, checks on new ones, grooms, yawns and naps when things are quiet. It
  likes to knock finished cups off the bar.
- **Pet the cat** with `p`. It purrs.
- **Rush hour.** With four or more agents working at once, the cat hurries.
- **Lots of agents?** Cups shrink to fit the screen. Anything that still
  doesn't fit is counted below the counter.
- **Receipt on quit:** time awake, cups served, cups still brewing, the
  barista's name, times petted and the longest session.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/alexgnq/caffe/main/install.sh | sh
```

Installs to `~/.local/bin/caffe`. Set `CAFFE_BIN_DIR` to install somewhere else.
Requires macOS and `python3` (included with the Xcode Command Line Tools). No
other dependencies.

The pictures need a terminal that supports the
[kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/),
such as Ghostty, kitty, WezTerm or a recent iTerm2. In other terminals, and
inside tmux, caffe still keeps the Mac awake and lists your agents, just without
pictures.

## Usage

```sh
caffe
```

Press `p` to pet the cat, and `q` or `Ctrl-C` to close the bar. `caffe --help`
prints a short summary.

## How it works

- Every 3 seconds, `ps` is checked for `copilot`, `codex`, `claude` and `pi`
  processes attached to a terminal. Background daemons and editor extensions
  are ignored.
- `caffeinate` is tied to caffe's process ID, so the Mac can sleep again as soon
  as caffe exits, even if it's killed.
- The art is drawn in Python when it's first needed and sent to the terminal
  once. After that caffe only moves the pictures around, redraws only the text
  that changed, and slows down when nothing is moving, so it uses very little
  CPU.
- caffe stores nothing on disk.

## Uninstall

```sh
rm ~/.local/bin/caffe
```

## License

[MIT](LICENSE)
