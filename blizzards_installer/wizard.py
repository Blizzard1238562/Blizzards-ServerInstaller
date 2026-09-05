"""The interactive wizard - asks the questions and orchestrates everything
the user picked (jar download, plugins, config patching, start scripts).

Three modes: Quick start installs the latest Paper with a small set of
"essential" plugins (flagged in plugins.json) and sensible defaults, asking
only for the server name, install directory and RAM. Full setup is the
original step-by-step wizard with every choice exposed. Update an existing
server refreshes a previously installed server's jar and plugins, keeping the
world and configs the user has since changed.
"""

from __future__ import annotations

from pathlib import Path

from .config import apply_gameplay_config, write_eula, write_server_properties
from .manifest import MANIFEST_NAME, read_manifest, touch_manifest, write_manifest
from .plugins import (
    install_plugins,
    load_plugin_registry,
    plugins_for_server,
    resolve_dependencies,
    write_tab_config,
)
from .presets import write_plugin_presets
from .public import install_agent, open_claim_console, store_secret, write_public_files
from .scripts import write_start_scripts
from .serverjar import SERVER_TYPES, download_server_jar
from .sysinfo import recommended_ram_mb
from .ui import ask_choice, ask_int, ask_text, ask_yes_no, error, info, ok, section, warn
from .versions import choose_minecraft_version, get_recent_release_versions

DIFFICULTIES = ["peaceful", "easy", "normal", "hard"]
GAMEMODES = ["survival", "creative", "adventure", "spectator"]

# (label, legacy color code) for the TAB tablist header. Empty code = plain
# white, i.e. no color prefix.
TAB_NAME_COLORS = [
    ("White", ""),
    ("Gray", "&7"),
    ("Gold", "&6"),
    ("Yellow", "&e"),
    ("Green", "&a"),
    ("Aqua", "&b"),
    ("Light blue", "&9"),
    ("Red", "&c"),
    ("Light purple", "&d"),
]

MODE_LABELS = [
    "Quick start - essentials only (recommended)",
    "Full setup - customize everything",
    "Update an existing server",
]


def run_wizard() -> None:
    section("Setup mode")
    mode = ask_choice("What do you want to do?", MODE_LABELS, default_index=0)
    if mode == 0:
        run_quick_wizard()
    elif mode == 1:
        run_full_wizard()
    else:
        run_update_wizard()


def _choose_install_dir() -> Path | None:
    """Ask for the install directory; None means the user aborted."""
    default_dir = str(Path.cwd() / "server")
    server_dir = Path(ask_text("Install directory", default_dir)).expanduser().resolve()
    if server_dir.exists() and any(server_dir.iterdir()):
        if read_manifest(server_dir) is not None:
            warn(
                "This folder was installed by the Blizzards installer - to refresh an existing "
                "server, pick 'Update an existing server' in the Setup mode menu instead."
            )
        if not ask_yes_no(f"'{server_dir}' already exists and isn't empty. Continue anyway?", default=False):
            info("Aborted.")
            return None
    server_dir.mkdir(parents=True, exist_ok=True)
    return server_dir


def _latest_release_or_manual() -> str:
    """Latest stable Minecraft release; falls back to a manual entry when the
    Mojang manifest cannot be reached (offline installs still work)."""
    try:
        recent = get_recent_release_versions(limit=1)
        if recent:
            return recent[0]
    except Exception as exc:
        warn(f"Could not reach Mojang's version list ({exc}).")
    return ask_text("Enter the Minecraft version (e.g. 1.21.4)")


def run_quick_wizard() -> None:
    """Bare-bones setup: latest Paper, name + RAM, and the essential plugins
    only (flagged `"essential": true` in plugins.json). No per-plugin or
    gameplay questions, no config bootstrap - Paper generates its config on
    the first real start. RAM is still asked, prefilled with a value based on
    the machine's memory."""
    info(
        "Quick start installs the latest Paper with a small set of essentials "
        "(TAB, ViaVersion, SimpleTPA) and sensible defaults. Pick Full setup "
        "to customize everything."
    )
    server_name = ask_text("Server name", "Minecraft Server")
    server_dir = _choose_install_dir()
    if server_dir is None:
        return
    ram_mb = ask_int("How much RAM (in MB) should the start script allocate?", recommended_ram_mb())
    mc_version = _latest_release_or_manual()
    _quick_install(server_name, server_dir, ram_mb, mc_version)


def run_quick_unattended(
    server_name: str | None = None,
    server_dir: Path | None = None,
    ram_mb: int | None = None,
) -> None:
    """Non-interactive Quick start (used by the CLI flags).

    Never prompts: missing values fall back to the same defaults the wizard
    would offer. Raises RuntimeError instead of asking when something needs a
    decision (unreachable version list). If the target folder already holds an
    install made by this tool, the existing server is updated (jar + plugins
    refreshed) instead; a non-empty folder without one is refused."""
    section("Setup mode")
    info("Running an unattended Quick start install.")
    target = (server_dir or Path.cwd() / "server").expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()):
        manifest = read_manifest(target)
        if manifest is None:
            raise RuntimeError(f"Install directory is not empty - refusing to touch it: {target}")
        info("Found an existing Blizzards install - refreshing the server jar and plugins.")
        update_existing_server(target, manifest)
        return
    name = server_name or "Minecraft Server"
    ram = ram_mb or recommended_ram_mb()
    try:
        recent = get_recent_release_versions(limit=1)
        mc_version = recent[0] if recent else ""
        if not mc_version:
            raise RuntimeError("version list was empty")
    except Exception as exc:
        raise RuntimeError(f"Could not determine the latest Minecraft version ({exc}).") from exc
    _quick_install(name, target, ram, mc_version)


def _quick_install(server_name: str, server_dir: Path, ram_mb: int, mc_version: str) -> None:
    """Install latest Paper + the essential plugins. No prompts; the caller
    decides on name/folder/RAM/version."""
    plugins, _categories = load_plugin_registry()
    plugins_by_id = {p["id"]: p for p in plugins}
    essential_ids = {p["id"] for p in plugins if p.get("essential")}
    essential_ids = resolve_dependencies(essential_ids, plugins_by_id)
    chosen_plugins = [p for p in plugins if p["id"] in essential_ids]
    chosen_has_tab = any(p["id"] == "tab" for p in chosen_plugins)

    section("Summary")
    print(f"  Server software : {SERVER_TYPES['paper']['label']}")
    print(f"  Server name     : {server_name}")
    print(f"  MC version      : {mc_version}")
    print(f"  Install dir     : {server_dir}")
    print(f"  RAM             : {ram_mb} MB")
    print(f"  Plugins         : {', '.join(p['name'] for p in chosen_plugins)}")

    section("Downloading server jar")
    jar_name = f"paper-{mc_version}.jar"
    jar_path = server_dir / jar_name
    download_server_jar("paper", mc_version, jar_path)

    section("Writing base config")
    write_eula(server_dir)
    write_server_properties(server_dir, {"motd": server_name})
    ok("Wrote eula.txt and server.properties (MOTD is your server name)")

    plugins_dir = server_dir / "plugins"
    plugins_dir.mkdir(exist_ok=True)
    install_plugins(chosen_plugins, mc_version, SERVER_TYPES["paper"]["modrinth_loader"], plugins_dir)
    if chosen_has_tab:
        write_tab_config(server_dir, server_name, "")
    write_plugin_presets(server_dir, chosen_plugins)

    section("Start scripts")
    write_start_scripts(server_dir, jar_name, ram_mb)
    write_manifest(
        server_dir,
        server_type="paper",
        mc_version=mc_version,
        ram_mb=ram_mb,
        plugin_ids=[p["id"] for p in chosen_plugins],
    )

    section("Done")
    ok(f"Server installed at: {server_dir}")
    info("Run start.bat (Windows) or ./start.sh (Linux/Mac) inside that folder to launch it.")
    if chosen_has_tab:
        info("TAB tablist set to your server name - edit plugins/TAB/config.yml to tweak it (then /tab reload).")


def run_update_wizard() -> None:
    """Update a server this installer created: refresh the server jar and
    plugin jars to their newest builds, keeping worlds, configs and start
    scripts untouched (the user may have customized them since)."""
    section("Update an existing server")
    info("Point me at the folder of a server that was installed with the Blizzards installer.")
    default_dir = str(Path.cwd() / "server")
    server_dir = Path(ask_text("Server folder", default_dir)).expanduser().resolve()
    manifest = read_manifest(server_dir)
    if manifest is None:
        warn(f"No Blizzards install found in '{server_dir}' (no {MANIFEST_NAME} manifest). "
             "Run Quick start or Full setup to install a new server instead.")
        return
    server_type = manifest.get("server_type")
    mc_version = manifest.get("mc_version")
    server = SERVER_TYPES.get(server_type) if isinstance(server_type, str) else None
    if server is None or not isinstance(mc_version, str) or not mc_version:
        error("The install manifest in that folder is incomplete - install a fresh server instead.")
        return
    plugin_ids = manifest.get("plugins") or []
    plugins, _categories = load_plugin_registry()
    by_id = {p["id"]: p for p in plugins}
    known = [by_id[i] for i in plugin_ids if i in by_id]

    section("Found an existing server")
    print(f"  Server software : {server['label']}")
    print(f"  MC version      : {mc_version}")
    print(f"  Plugins         : {', '.join(p['name'] for p in known) or '(none recorded)'}")
    print(f"  Server folder   : {server_dir}")
    if not ask_yes_no(
        f"Refresh the {server['label']} {mc_version} server jar and its plugins to the newest "
        "builds? Your world, configs and start scripts will be kept.",
        True,
    ):
        info("Aborted.")
        return
    try:
        update_existing_server(server_dir, manifest)
    except RuntimeError as exc:
        error(str(exc))


def update_existing_server(server_dir: Path, manifest: dict) -> None:
    """Refresh an existing install: re-download the newest server jar build
    and each recorded plugin jar. Never touches worlds, configs or start
    scripts. Raises RuntimeError on a locked jar or an unusable manifest."""
    server_type = manifest.get("server_type")
    mc_version = manifest.get("mc_version")
    plugin_ids = manifest.get("plugins") or []
    if not isinstance(server_type, str) or server_type not in SERVER_TYPES \
            or not isinstance(mc_version, str) or not mc_version:
        raise RuntimeError("The install manifest in this folder is incomplete - "
                           "install a fresh server instead (Quick start / Full setup).")
    server = SERVER_TYPES[server_type]

    plugins, _categories = load_plugin_registry()
    by_id = {p["id"]: p for p in plugins}
    known = [by_id[i] for i in plugin_ids if i in by_id]
    stale = [str(i) for i in plugin_ids if i not in by_id]
    if stale:
        warn(f"{len(stale)} recorded plugin(s) are no longer offered and were left as-is: "
             f"{', '.join(stale)}.")

    section("Updating server jar")
    jar_name = f"{server_type}-{mc_version}.jar"
    try:
        download_server_jar(server_type, mc_version, server_dir / jar_name)
    except PermissionError as exc:
        raise RuntimeError("Could not overwrite the server jar - is the server still running? "
                           "Type 'stop' in its console (or close it) and try again.") from exc

    section("Updating plugins")
    plugins_dir = server_dir / "plugins"
    plugins_dir.mkdir(exist_ok=True)
    if known:
        install_plugins(known, mc_version, server["modrinth_loader"], plugins_dir)

    touch_manifest(server_dir, manifest)

    section("Done")
    ok(f"Updated {server['label']} {mc_version}: server jar and {len(known)} plugin(s) refreshed.")
    info("Your world, configs and start scripts were kept. Restart the server to apply the updates.")


def run_full_wizard() -> None:
    section("Server basics")
    type_keys = list(SERVER_TYPES.keys())
    type_labels = [SERVER_TYPES[k]["label"] for k in type_keys]
    type_idx = ask_choice("Which server software do you want to install?", type_labels, default_index=0)
    server_type = type_keys[type_idx]
    server = SERVER_TYPES[server_type]
    info(f"Server software: {server['label']}")
    if server_type == "folia":
        warn(
            "Folia uses a regionized multithreading model - the plugin list below only "
            "offers plugins whose authors ship Folia-compatible builds."
        )
    mc_version = choose_minecraft_version()

    server_dir = _choose_install_dir()
    if server_dir is None:
        return

    section("Basic server settings")
    server_name = ask_text("Server name", "Minecraft Server")
    name_color = TAB_NAME_COLORS[
        ask_choice(
            "Color for your server name in the TAB tablist (small-font header, only if you install TAB)",
            [f"{label} ({code})" if code else label for label, code in TAB_NAME_COLORS],
            default_index=0,
        )
    ][1]
    motd = ask_text("Server MOTD", "A Minecraft Server")
    max_players = ask_int("Max players", 20)
    difficulty = DIFFICULTIES[ask_choice("Difficulty", DIFFICULTIES, default_index=1)]
    online_mode = ask_yes_no("Online mode (require paid/premium Minecraft accounts)?", True)
    whitelist = ask_yes_no("Enable whitelist?", False)
    pvp = ask_yes_no("Enable PvP?", True)
    hardcore = ask_yes_no("Hardcore mode?", False)
    allow_flight = ask_yes_no("Allow flight (some minigame/creative plugins need this)?", False)
    view_distance = ask_int("View distance (chunks)", 10)
    sim_distance = ask_int("Simulation distance (chunks)", 10)
    world_seed = ask_text("World seed (blank = random)", "")
    gamemode = GAMEMODES[ask_choice("Default gamemode", GAMEMODES, default_index=0)]
    spawn_protection = ask_int("Spawn protection radius (blocks)", 16)
    allow_nether = ask_yes_no("Allow the Nether?", True)
    enable_command_blocks = ask_yes_no("Enable command blocks?", False)

    section("Gameplay & exploit settings (Paper)")
    info("These control vanilla bugs/exploits that Paper patches by default.")
    # The dict below is what apply_gameplay_config() / write_manual_config_notes() consume.
    answers = {
        "tnt_dupe": ask_yes_no("Allow TNT duplication (also re-enables carpet/rail duping via pistons)?", False),
        "block_break_exploits": ask_yes_no("Allow breaking unbreakable blocks (bedrock, end portal frames)?", False),
        "headless_pistons": ask_yes_no("Allow headless pistons?", False),
        "anti_xray": ask_yes_no("Enable Paper's built-in Anti-Xray?", True),
        "anti_xray_mode": 1,
    }
    if answers["anti_xray"]:
        answers["anti_xray_mode"] = ask_choice(
            "Anti-Xray engine mode",
            ["Mode 1 - lighter on performance", "Mode 2 - stronger, slightly heavier on performance"],
            default_index=0,
        ) + 1

    section("Plugins")
    plugins, categories = load_plugin_registry()
    offered_plugins, skipped_plugins = plugins_for_server(plugins, server_type)
    if skipped_plugins:
        names = ", ".join(p["name"] for p in skipped_plugins)
        warn(f"Skipping {len(skipped_plugins)} plugins without Folia support: {names}.")
    plugins_by_id = {p["id"]: p for p in offered_plugins}
    selected_ids: set[str] = set()
    current_category = None
    for plugin in offered_plugins:
        if plugin["category"] != current_category:
            current_category = plugin["category"]
            print(f"\n  -- {categories.get(current_category, current_category)} --")
        if ask_yes_no(plugin["question"], plugin.get("default", False)):
            selected_ids.add(plugin["id"])
    selected_ids = resolve_dependencies(selected_ids, plugins_by_id)
    chosen_plugins = [p for p in plugins if p["id"] in selected_ids]
    chosen_has_tab = any(p["id"] == "tab" for p in chosen_plugins)

    ram_mb = ask_int("How much RAM (in MB) should the start script allocate?", recommended_ram_mb())

    section("Summary")
    print(f"  Server software : {server['label']}")
    print(f"  Server name     : {server_name}")
    print(f"  MC version      : {mc_version}")
    print(f"  Install dir     : {server_dir}")
    print(f"  RAM             : {ram_mb} MB")
    print(f"  Gamemode        : {gamemode}")
    print(f"  World seed      : {world_seed or '(random)'}")
    print(f"  Plugins         : {', '.join(p['name'] for p in chosen_plugins) or '(none)'}")
    print(f"  TNT duplication : {answers['tnt_dupe']}")
    print(f"  Anti-Xray       : {answers['anti_xray']}" + (f" (mode {answers['anti_xray_mode']})" if answers["anti_xray"] else ""))
    if not ask_yes_no("Proceed with installation?", True):
        info("Aborted.")
        return

    section("Downloading server jar")
    jar_name = f"{server_type}-{mc_version}.jar"
    jar_path = server_dir / jar_name
    download_server_jar(server_type, mc_version, jar_path)

    section("Writing base config")
    write_eula(server_dir)
    write_server_properties(
        server_dir,
        {
            "motd": motd,
            "max-players": max_players,
            "difficulty": difficulty,
            "online-mode": online_mode,
            "white-list": whitelist,
            "pvp": pvp,
            "hardcore": hardcore,
            "allow-flight": allow_flight,
            "view-distance": view_distance,
            "simulation-distance": sim_distance,
            "level-seed": world_seed,
            "gamemode": gamemode,
            "spawn-protection": spawn_protection,
            "allow-nether": allow_nether,
            "enable-command-block": enable_command_blocks,
        },
    )
    ok("Wrote eula.txt and server.properties")

    plugins_dir = server_dir / "plugins"
    plugins_dir.mkdir(exist_ok=True)
    if chosen_plugins:
        install_plugins(chosen_plugins, mc_version, server["modrinth_loader"], plugins_dir)
    if chosen_has_tab:
        write_tab_config(server_dir, server_name, name_color)
    write_plugin_presets(server_dir, chosen_plugins)

    section("Generating Paper config")
    apply_gameplay_config(server_dir, jar_path, answers)

    section("Start scripts")
    write_start_scripts(server_dir, jar_name, ram_mb)
    write_manifest(
        server_dir,
        server_type=server_type,
        mc_version=mc_version,
        ram_mb=ram_mb,
        plugin_ids=[p["id"] for p in chosen_plugins],
    )

    section("Public access (optional)")
    if ask_yes_no("Make this server joinable by others without port forwarding (playit.gg)?", False):
        try:
            agent_path = install_agent(server_dir)
            linked = False
            if ask_yes_no(
                "Link automatically with an agent secret key? You can create one at "
                "playit.gg > Agents > Add Agent and paste it here (or say no to claim "
                "in a browser window instead).",
                False,
            ):
                secret = ask_text("Paste the playit.gg agent secret key")
                if secret.strip():
                    store_secret(server_dir, secret)
                    linked = True
                    ok("Secret saved to playit/secret.key - start-public.bat/sh will connect automatically.")
                else:
                    warn("No secret pasted - claiming via the agent window instead.")
            write_public_files(server_dir, jar_name, ram_mb)
            if linked:
                info("Open the playit dashboard, add a Minecraft Java tunnel (TCP, 127.0.0.1:25565) and share the address it shows.")
            else:
                open_claim_console(agent_path)
        except Exception as exc:
            error(f"Could not set up playit.gg: {exc}")
            warn("Your server still works locally - run start.bat / ./start.sh to launch it.")

    section("Done")
    ok(f"Server installed at: {server_dir}")
    info("Run start.bat (Windows) or ./start.sh (Linux/Mac) inside that folder to launch it.")
    if chosen_has_tab:
        info("TAB tablist set to your server name - edit plugins/TAB/config.yml to tweak it (then /tab reload).")
