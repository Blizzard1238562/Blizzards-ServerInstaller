"""Blizzards Server Installer - interactive Minecraft server setup wizard.

Split by concern so each module stays small and testable:
  meta      - version/contact/User-Agent constants
  ui        - console prompts and output helpers
  net       - HTTP requests + file downloads
  versions  - Minecraft version discovery (Mojang manifest)
  serverjar - server-software registry + jar download logic
  plugins   - plugin registry + Modrinth downloads
  config    - server.properties/eula + Paper config generation/patching
  scripts   - start + stop/restart/backup script generation
  presets   - pinned default configs for selected plugins
  public    - playit.gg tunnel setup for public servers
  sysinfo   - RAM detection for the default suggestion
  update    - installer self-update hint (GitHub releases)
  manifest  - install manifest recording what went into a server folder
  wizard    - the interactive question flow that ties it all together

The entry point is installer.py at the repository root.
"""

__version__ = "1.2.0"
