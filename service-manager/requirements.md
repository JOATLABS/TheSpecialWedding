# Service Manager Dependencies

The service manager needs the following command-line tools. When the `manage_services.sh` script runs it checks for each tool
and attempts to install any missing ones using the detected package manager (`apt`, `dnf`, `yum`, or Homebrew).

| Dependency | Purpose | apt packages | dnf / yum packages | Homebrew formulae |
|------------|---------|--------------|--------------------|-------------------|
| tmux | Terminal multiplexer used for split-pane management | `tmux` | `tmux` | `tmux` |
| npm / Node.js | Runs the Next.js frontend dev server | `nodejs`, `npm` | `nodejs` | `node` |
| Docker Engine | Runs backend containers | `docker.io` | `docker` | `docker` |
| Docker Compose | Streams logs and manages multi-service workflows | `docker-compose-plugin` | `docker-compose` | `docker` |

If your workstation uses a different package manager, install equivalent packages manually before launching the service manager.
