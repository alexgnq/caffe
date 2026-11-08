# ☕ caffe

`caffeinate`, but with a coffee bar. Keeps your Mac awake and sets a cup on the
table for every AI coding agent you have running, with a barista cat to look
after them.

![caffe in action](caffe.gif)

- **Keeps the Mac awake** until you quit (`caffeinate -dimsu` under the hood).
- **Battery aware.** Unplugged at 20% or less, the display may sleep while the
  system stays awake, so your agents keep running. Plug in and the display
  stays on again. The header shows the charge while you're on battery.
- **A table of orders, seen from above.** Every Copilot CLI, Codex CLI, Claude
  Code, Pi and OpenCode session running in a terminal is a card: a cup on its
  saucer in the agent's colour, the project folder it runs in, what it's doing
  and for how long.
- **The coffee shows the state.**
  - **Brewing:** the crema swirls as it's stirred, faster when the agent works
    harder.
  - **Ready:** a heart in the foam and a biscuit on the saucer. The session
    worked and then went quiet, so it's probably waiting for you. Ready orders
    come first.
  - **Idle:** a still heart, for a session that hasn't been seen working.
  - **Cold:** dark coffee with a skin on it, after 15 quiet minutes.

  A session counts as brewing until it has been quiet for 30 seconds, so a
  pause to wait on the model isn't idling. Its CPU includes the tools, builds and
  tests it runs. New orders pour in. Finished ones drain, turn grey and get
  knocked off the table.
- **Copilot app sessions.** Running local Copilot app sessions and chats get
  their own cards, labelled `Agent` with the session's title. They brew while
  running; idle sessions disappear without being served.
- **Open apps.** The Codex, Copilot, Claude and VS Code apps are listed below
  the cards, each with its own icon, read from the app, and the CPU and RAM of
  the app and everything it runs.
- **At a glance.** The header and the terminal tab's title count what's ready,
  brewing, idle and just served, such as `☕ 1 ready · 2 brewing`, so you can
  keep an eye on your agents from another tab.
- **A barista cat.** A random name and coat each launch. It lives on the strip
  of table below the cards: it walks about, grooms, yawns and naps when things
  are quiet. It climbs up to sniff each new order and to check on ready ones,
  and while an order is ready it sits up and looks at you instead of napping.
  It knocks every finished cup off the table, and if you leave a ready order
  until it goes cold, it eats the biscuit.
- **Pet the cat** with `p`. It purrs.
- **Feed the cat** with `f`. It munches a fish treat, up to three every ten
  minutes before it's full.
- **Mice.** Now and then a mouse dashes across the table and the cat gives
  chase. A slow mouse gets caught (and let go); a fast one escapes. A napping
  cat sleeps right through it. Mice come out more at night.
- **Visiting cats.** A stray wanders in every so often. A cat that's been
  petted or fed lately shares the table for a while; a grumpy one usually
  hisses it out.
- **Time of day.** Mornings open with a greeting. From 23:00 the cat takes the
  night shift: it walks slower, naps more and gets its own quips. At 14:30
  there's fika: a kanelbulle on a plate, or a lussekatt in December. While
  agents work, the cat sneaks a bite now and then.
- **Rush hour.** With four or more sessions brewing at once, the cat hurries.
- **Lots of agents?** Cards shrink to fit the screen, four to a row. Anything
  that still doesn't fit is counted below them.
- **Receipt on quit:** an order number, your espressos per agent, the cups the
  cat broke, the mice it caught, time awake against total agent time, the
  longest session, visiting cats, and the cat's tip in pets and treats. Open
  apps and Copilot app sessions don't count.

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

Press `p` to pet the cat, `f` to feed it, and `q` or `Ctrl-C` to close the bar.
`caffe --help` prints a short summary.

To update to the latest version:

```sh
caffe update
```

`caffe update` installs the upstream version and replaces local customizations,
including Copilot session tracking and app resource reporting.

## How it works

- Every 3 seconds, `ps` is checked for `copilot`, `codex`, `claude`, `pi` and
  `opencode` processes attached to a terminal, and for the Codex, Copilot, Claude and
  VS Code apps. An app's helpers and agent backends count towards the app. A
  terminal session's processes count towards its card, except another agent
  session started inside it, which gets its own card.
- When a terminal session first appears, `lsof` reads its working directory
  once, for the project name.
- "Ready" is a guess from CPU use: a session that worked for at least 15
  seconds and then went quiet for 30. An agent waiting on a very slow model
  reply can look ready early.
- OpenCode runs its tools in a shared background server, so an OpenCode card
  only counts the work its terminal does.
- Copilot's local, running, unarchived project, agent and general-chat sessions
  are read from `~/.copilot/data.db` in read-only mode. Only session metadata
  is read, never conversation history. This optional integration uses an
  undocumented schema; if a read fails, existing session cards are kept until
  the next successful read.
- `caffeinate` is tied to caffe's process ID, so the Mac can sleep again as soon
  as caffe exits, even if it's killed.
- Every 30 seconds, `pmset -g batt` is read. On a low battery caffe restarts
  `caffeinate` as `-ims`, without the display (`-d`) and user-activity (`-u`)
  assertions.
- The art is drawn in Python when it's first needed and sent to the terminal
  once. After that caffe only moves the pictures around, redraws only the text
  that changed, and slows down when nothing is stirring or moving, so it uses
  very little CPU.
- caffe stores nothing on disk.

## Uninstall

```sh
rm ~/.local/bin/caffe
```

## License

[MIT](LICENSE)
