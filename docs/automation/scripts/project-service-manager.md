# Project Service Manager

This script wraps the local frontend (`npm`) process and every Docker Compose backend service in a single tmux-powered workspace. It provides a menu-driven workflow for starting, stopping, restarting, and inspecting each component.

## Location

```
service-manager/manage_services.sh
```

Supplemental package mapping lives alongside the script in [`service-manager/requirements.txt`](../../../service-manager/requirements.txt). The manager reads this file at runtime to resolve the packages it should install for each supported package manager.

## Prerequisites

- The script checks for and, when possible, installs the following prerequisites automatically: `tmux`, Docker (with Compose support), and Node.js/npm.
- When prompted for elevated privileges, provide the password for your user so the installer can run `apt`, `dnf`, `yum`, or `brew` commands.
- If none of the supported package managers are found, install the requirements manually before running the manager.
- Run `npm install` in the repository root so the frontend dependencies are present.

## Usage

Run the script from the repository root:

```
./service-manager/manage_services.sh
```

The script automatically launches (or attaches to) a dedicated tmux session named `project-services` and presents the interactive menu. From there you can:

1. Start, stop, or restart the Next.js frontend (`npm run dev`).
2. Start, stop, or restart every Docker Compose backend service.
3. Open focused log panes for the frontend or any single Docker service.
4. Open a tiled view that streams logs from the frontend alongside all Compose services at once.
5. Close log windows, detach from tmux, or shut the entire session down.

The frontend logs are archived into `.service-manager/logs/frontend.log` so that the multi-pane view can tail the current output even while the main service window keeps running.

## Tips

- Use the tmux prefix (`Ctrl+b` by default) followed by `w` to switch windows quickly.
- Select option `11` in the menu to detach while leaving services running in the background.
- Select option `12` to stop the session (this closes every pane and terminates the menu).
