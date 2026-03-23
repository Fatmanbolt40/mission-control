# Mission Control Dashboard

Real-time AI agent mission control dashboard for MEV flash loan operations on Base L2.

## Features

- **Task Board** — Kanban-style task management (Backlog → Todo → In Progress → Done)
- **Command Center** — Send tasks to CLAWD agent
- **MEV Bot** — Live MEV bot status, scan results, gas tracking
- **Trades** — Trade history and P&L
- **Calendar** — Monthly task calendar
- **Projects** — Project tracking with progress bars
- **Sessions** — Session history viewer
- **Memory** — AI agent memory journal + long-term memory
- **Docs** — Searchable document browser with markdown rendering
- **Team** — Org chart with agent roles and capabilities  
- **Office** — **Animated 2D office** with walking AI agent sprites, speech bubbles, room navigation
- **System** — System health monitoring

## Live Mode

To connect to your running Mission Control backend:

```
https://YOUR-USERNAME.github.io/mission-control/?api=http://localhost:8062
```

Or via Cloudflare tunnel:
```
https://YOUR-USERNAME.github.io/mission-control/?api=https://your-tunnel.trycloudflare.com
```

## Demo Mode

Without an `?api=` parameter, the dashboard runs in demo mode with sample data.

## Tech Stack

- Pure HTML/CSS/JavaScript — zero dependencies
- Canvas-based 2D animated office with requestAnimationFrame
- aiohttp Python backend (for live mode)
- SQLite persistent storage

## Setup

1. Fork this repo
2. Enable GitHub Pages in Settings → Pages → Deploy from branch `main`
3. Visit `https://YOUR-USERNAME.github.io/mission-control/`
