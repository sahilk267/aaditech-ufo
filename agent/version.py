"""Single source of truth for the agent's running version.

The PyInstaller build script (`scripts/build_agent_windows.ps1`) overwrites this
file with the version supplied on the command line so the bundled .exe always
reports the version it was packaged as.
"""

AGENT_VERSION = "0.0.0-dev"
