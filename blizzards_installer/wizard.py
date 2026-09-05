"""The interactive wizard - asks the questions and orchestrates everything
the user picked (jar download, plugins, config patching, start scripts)."""

from __future__ import annotations

from pathlib import Path

from .config import apply_gameplay_config, write_server_properties, write_eula
from .plugins import (
    install_plugins,
    load_plugin_registry,
    resolve_dependencies,
    write_tab_placeholder,
)
from .public import install_agent, open_claim_console, write_public_files
from .scripts import write_start_scripts
from .serverjar import SERVER_TYPES, download_server_jar
from .ui import ask_choice, ask_int, ask_text, ask_yes_no, error, info, ok, section, warn
from .versions import choose_minecraft_version

DIFFICULTIES = ["peaceful", "easy", "normal", "hard"]


def run_wizard() -> None:
    section("Server basics")
    type_keys = list(SERVER_TYPES.keys())
    type_labels = [SERVER_TYPES[k]["label"] for k in type_keys]
    type_idx = ask_choice("Which server software do you want to install?", type_labels, default_index=0)
    server_type = type_keys[type_idx]
    server = SERVER_TYPES[server_type]
    info(f"Server software: {server['label']}")
    if server_type == "folia":
        warn(
            "Folia uses a regionized multithreading model - most Bukkit/Paper plugins "
            "(including several in this wizard) are NOT compatible with it unless the "
            "plugin author has explicitly added Folia support. Only pick plugins you know "
            "are Folia-ready."
        )
    mc_version = choose_minecraft_version()

    default_dir = str(Path.cwd() / "server")
    server_dir = Path(ask_text("Install directory", default_dir)).expanduser().resolve()
    if server_dir.exists() and any(server_dir.iterdir()):
        if not ask_yes_no(f"'{server_dir}' already exists and isn't empty. Continue anyway?", default=False):
            info("Aborted.")
            return
    server_dir.mkdir(parents=True, exist_ok=True)

    section("Basic server settings")
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
    plugins_by_id = {p["id"]: p for p in plugins}
    selected_ids: set[str] = set()
    current_category = None
    for plugin in plugins:
        if plugin["category"] != current_category:
            current_category = plugin["category"]
            print(f"\n  -- {categories.get(current_category, current_category)} --")
        if ask_yes_no(plugin["question"], plugin.get("default", False)):
            selected_ids.add(plugin["id"])
    selected_ids = resolve_dependencies(selected_ids, plugins_by_id)
    chosen_plugins = [p for p in plugins if p["id"] in selected_ids]
    chosen_has_tab = any(p["id"] == "tab" for p in chosen_plugins)

    ram_mb = ask_int("How much RAM (in MB) should the start script allocate?", 4096)

    section("Summary")
    print(f"  Server software : {server['label']}")
    print(f"  MC version      : {mc_version}")
    print(f"  Install dir     : {server_dir}")
    print(f"  RAM             : {ram_mb} MB")
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
        },
    )
    ok("Wrote eula.txt and server.properties")

    plugins_dir = server_dir / "plugins"
    plugins_dir.mkdir(exist_ok=True)
    if chosen_plugins:
        install_plugins(chosen_plugins, mc_version, server["modrinth_loader"], plugins_dir)
    if chosen_has_tab:
        write_tab_placeholder(server_dir)

    section("Generating Paper config")
    apply_gameplay_config(server_dir, jar_path, answers)

    section("Start scripts")
    write_start_scripts(server_dir, jar_name, ram_mb)

    section("Public access (optional)")
    if ask_yes_no("Make this server joinable by others without port forwarding (playit.gg)?", False):
        try:
            agent_path = install_agent(server_dir)
            write_public_files(server_dir, jar_name, ram_mb)
            open_claim_console(agent_path)
        except Exception as exc:
            error(f"Could not set up playit.gg: {exc}")
            warn("Your server still works locally - run start.bat / ./start.sh to launch it.")

    section("Done")
    ok(f"Server installed at: {server_dir}")
    info("Run start.bat (Windows) or ./start.sh (Linux/Mac) inside that folder to launch it.")
    if chosen_has_tab:
        info("Remember to drop your real TAB config into plugins/TAB/config.yml.")
