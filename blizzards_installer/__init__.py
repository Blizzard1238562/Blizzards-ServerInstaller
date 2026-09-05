"""Blizzards Server Installer - interactive Minecraft server setup wizard.

Split by concern so each module stays small and testable:
  meta      - version/contact/User-Agent constants
  ui        - console prompts and output helpers
  net       - HTTP requests + file downloads
  versions  - Minecraft version discovery (Mojang manifest)
  serverjar - server-software registry + jar download logic
  plugins   - plugin registry + Modrinth downloads
  config    - server.properties/eula + Paper config generation/patching
  scripts   - start.bat/start.sh generation
  wizard    - the interactive question flow that ties it all together

The entry point is installer.py at the repository root.
"""

__version__ = "1.1.0"
