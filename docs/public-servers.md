# Public servers without port forwarding (playit.gg)

Status: MVP implemented in `blizzards_installer/public.py` and wired into the
wizard as an opt-in step. Facts below were verified live on 2026-09-05
against playit.gg and its v1.0.10 agent (downloaded and run once on Windows).

## Goal

After an install, optionally make the server joinable by anyone on the
internet without the user having to port-forward or own a public IP. Players
should get a normal Minecraft server address (`hostname:port`) they can type
into the multiplayer screen.

## Why playit.gg

The roadmap said "play.gg or similar". The service that actually fits is
**playit.gg** (play.gg is not a tunnel service; the two names get confused in
forum posts). playit is a proxy network purpose-built for game servers.

How it works:

- The user runs a small agent binary on the server machine. The agent keeps an
  outbound connection to playit's proxy network open. Nothing ever connects
  into the user's network, so no router changes are needed and it works behind
  CGNAT.
- Players connect to a public address playit assigns (a hostname plus a port).
  playit relays to the agent, which forwards to `127.0.0.1:25565`.
- Java Edition needs TCP only, which is on the free tier. Bedrock needs UDP,
  which requires playit Premium ($3/month). Custom domains and a dedicated IP
  are also Premium.

### Alternatives considered

- ngrok: TCP works but needs an authtoken, free URLs are random and not
  gaming-oriented. Poor fit.
- Cloudflare Tunnel: quick tunnels are HTTP only; arbitrary TCP needs a named
  tunnel with your own domain, and DDoS-protected TCP (Spectrum) is paid per
  usage. Poor fit for the free tier.
- Tailscale / ZeroTier / Hamachi: VPNs. Every player has to install the client
  and join the network. Wrong model for "anyone can join".
- Hosting provider: machines with a real public IP do not need a tunnel at all.
  This feature targets home/self-host users; on machines with a public IP it
  is irrelevant.

Decision: build against playit.gg.

## Verified facts (2026-09-05)

- Agent binaries are published on GitHub:
  `github.com/playit-cloud/playit-agent/releases`. Current release: v1.0.10.
- Relevant assets: `playit-windows-x86_64-signed.exe` (4.8 MB),
  `playit-linux-amd64` (5.9 MB), plus aarch64/armv7/i686 Linux builds and
  Windows `.msi`. Resolve the current version via the GitHub API
  (`/repos/playit-cloud/playit-agent/releases/latest`) rather than pinning a
  version number.
- `playit.gg/download` and `/download/windows` are HTML pages, not direct
  links, so the GitHub API is the machine-friendly source.
- No macOS assets exist on the GitHub release as of v1.0.10 even though the
  site advertises macOS. macOS is unsupported by the MVP (see below).
- The v1.0.x agent is a daemon (`playitd`). On Windows it reports
  `secret_path = %LOCALAPPDATA%\playit_gg\playit.toml` and waits for a
  "frontend" to provision the secret over IPC. Run without a console it
  prints nothing claim-related and just waits, so claiming needs the agent's
  console UI (or a secret key supplied some other way).
- Claiming routes (any one links the machine to a playit account):
  1. Run the agent interactively once; its console shows a login/claim flow.
  2. Dashboard: Agents -> Add Agent, copy the secret key, link the machine.
  3. Linux packages also expose `playit claim` / `playit setup`.
- Tunnels are created in the playit dashboard and point at the local server
  (Minecraft Java, TCP, `127.0.0.1:25565`). The agent then serves the
  assigned public address.

## Caveats to communicate to users

- Adds roughly 10-50 ms latency through playit's relays.
- The host machine must stay on and the agent and server must keep running.
- Free tier is fine for small friend groups, not a public 24/7 server.
- Anyone with the address can attempt to join: recommend enabling the
  whitelist, which the wizard already asks about.
- First run of the agent is interactive (account login/claim); it cannot be
  fully automated without the user's playit credentials.

## Implemented MVP

Opt-in question at the end of the wizard: "Make this server joinable by
others without port forwarding (playit.gg)?" Default no. If yes:

1. Resolve the latest agent via the GitHub API and download the platform
   binary into `server/playit/` (`net` helpers, so it shows progress and can
   be mocked in tests). Windows picks the signed x64 exe; Linux picks the
   amd64/aarch64/armv7/i686 binary by CPU. Unsupported platforms (macOS)
   fail cleanly with instructions.
2. On Windows, launch the agent in its own console window so the user can
   claim it (login or create a free account once). On other platforms, print
   instructions to run the agent once from a terminal. The dashboard "Add
   Agent" secret route is documented as an alternative.
3. Write `start-public.bat` / `start-public.sh` that start the playit agent
   and then the server, plus a `PUBLIC_SERVER.txt` with the remaining steps:
   create the tunnel in the dashboard (Minecraft Java, TCP,
   `127.0.0.1:25565`) and share the assigned address.
4. The normal `start.bat` / `start.sh` stay untouched. Declining the question
   creates no extra files. Any failure warns and the install still completes.

Module: `blizzards_installer/public.py`. Wizard hook in `run_wizard`, after
the start scripts and before the done banner. Covered by unit tests (asset
selection per OS, download path, script contents, claim launcher behavior,
decline path).

### Acceptance criteria (MVP)

- Opting in downloads the agent, opens/points at the claim screen, and writes
  the public launchers and instructions.
- Declining changes nothing and produces no extra files.
- Failing at any step (no network, GitHub down, unsupported OS) warns and
  completes the install normally.
- No port forwarding is performed or required.
- Manual end-to-end check (still to be done on a NATed machine): claim the
  agent, create the tunnel, join from another network via the playit address.

## Open questions / later work

- macOS: find where playit publishes macOS agents (site download only?) and
  add support.
- Read the `%LOCALAPPDATA%\playit_gg\playit.toml` schema and test whether we
  can link an agent by writing the dashboard's "Add Agent" secret key into it
  directly, which would remove the interactive claim step.
- Whether the agent can report its assigned public address to stdout (so a
  launcher could print "share this address" instead of pointing at the
  dashboard).
- Check playit's terms for bundling/automating agent setup before scaling the
  feature up.
