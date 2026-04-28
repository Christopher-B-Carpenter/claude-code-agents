# Claude Agent Framework

A multi-agent system for [Claude Code](https://claude.com/claude-code), organized as slash commands. Drop the `.claude/` directory and `CLAUDE.md` into a repo and you get a coordinated set of role-specific agents (PM, Developer, Architect, Security, Tester, UI Tester) that share state via the local filesystem and integrate with Jira and Bitbucket through MCP servers.

This repo contains **only the structure** — agent prompts, config templates, and the bundled Bitbucket MCP server. No credentials, no project-specific values. You wire those up locally during setup.

---

## What's in here

```
claude-agent-framework/
├── CLAUDE.md                              # Top-level project instructions, loaded automatically by Claude Code
├── README.md                              # This file
├── .gitignore
└── .claude/
    ├── commands/                          # The agents — each becomes a /<name> slash command
    │   ├── arch.md                        # Architect: design + code review
    │   ├── dev.md                         # Developer: implementation
    │   ├── pm.md                          # PM: branch/worktree setup, planning, ticket coordination
    │   ├── sec.md                         # Security: vulns, data, compliance
    │   ├── test.md                        # Tester: unit/integration test planning + runs
    │   └── ui-test.md                     # UI Tester: browser automation via Playwright MCP
    ├── mcp-servers.json                   # Description of the MCP servers each agent expects
    ├── mcp-servers/
    │   └── bitbucket-extended/            # Bundled Python MCP server for Bitbucket
    │       ├── main.py
    │       └── requirements.txt
    ├── project-config.template.json       # Copy → project-config.json and fill in
    └── ui-test-profiles/                  # Playwright tuning for common UI stacks
        ├── angular.json
        ├── generic.json
        ├── react.json
        ├── salesforce-lightning.json
        └── vue.json
```

`.agent-state/` is created per-worktree at runtime and is git-ignored. It holds plans, status files, and the activity log.

---

## Agents

| Command   | Role                                          |
|-----------|-----------------------------------------------|
| `/pm`     | Branch/worktree setup, ticket triage, planning |
| `/dev`    | Implements changes                             |
| `/arch`   | Reviews design and code                        |
| `/sec`    | Security, data privacy, compliance review      |
| `/test`   | Runs and writes tests                          |
| `/ui-test`| Drives the UI in a browser via Playwright MCP  |

The intended order on a non-trivial change is:

```
/pm  →  /dev  →  /sec  →  /arch  →  /test  (→ /ui-test if UI work)
```

See `CLAUDE.md` for the full workflow, including the master/worktree split.

---

## Installation

```bash
# 1. Clone next to your repo
git clone <this-repo> ~/src/claude-agent-framework

# 2. Copy the agent files into your repo's master branch
cd ~/src/your-repo
cp -r ~/src/claude-agent-framework/.claude .
cp ~/src/claude-agent-framework/CLAUDE.md .

# 3. Make a project config from the template
cp .claude/project-config.template.json .claude/project-config.json
# edit .claude/project-config.json — see "Project config" below

# 4. Commit
git add .claude CLAUDE.md
git commit -m "Add Claude agent framework"
```

After that, every worktree cut from master inherits the commands and config automatically.

---

## Required MCP servers

The agents call out to MCP servers for Jira, Confluence, and Bitbucket. The full schema lives in `.claude/mcp-servers.json`; here's the short version.

### 1. Atlassian (Jira + Confluence) — required

OAuth, no credentials to manage.

Add to `~/.claude.json` under your project's `mcpServers`:

```json
"atlassian": {
  "type": "sse",
  "url": "https://mcp.atlassian.com/v1/sse"
}
```

The first time an agent calls a Jira/Confluence tool, Claude Code opens a browser window to authenticate. Pick your workspace and approve.

### 2. Bitbucket (bundled, custom) — required

This repo ships a Python MCP server at `.claude/mcp-servers/bitbucket-extended/`. Set up a venv:

```bash
python3 -m venv ~/.claude-agents/venvs/bitbucket-extended
source ~/.claude-agents/venvs/bitbucket-extended/bin/activate
pip install -r .claude/mcp-servers/bitbucket-extended/requirements.txt
deactivate
```

Then register it in `~/.claude.json`:

```json
"bitbucket-extended": {
  "type": "stdio",
  "command": "/Users/<you>/.claude-agents/venvs/bitbucket-extended/bin/python3",
  "args": ["/Users/<you>/src/your-repo/.claude/mcp-servers/bitbucket-extended/main.py"]
}
```

**Auth.** The server reads credentials from `~/.claude-agents/credentials.env`:

```bash
mkdir -p ~/.claude-agents
chmod 700 ~/.claude-agents
cat > ~/.claude-agents/credentials.env <<'EOF'
BITBUCKET_WORKSPACE=your-workspace-slug
BITBUCKET_EMAIL=you@example.com
BITBUCKET_API_TOKEN=<token>
BITBUCKET_USERNAME=your-username
EOF
chmod 600 ~/.claude-agents/credentials.env
```

Generate the API token at <https://bitbucket.org/account/settings/app-passwords/>. Bitbucket's newer API uses **Basic auth with `email:token`** (not `username:token`) — both fields are required.

If you only have a legacy app password, set `BITBUCKET_APP_PASSWORD` instead of `BITBUCKET_API_TOKEN`. The server prefers the API token when both are set.

### 3. Playwright — required only for `/ui-test`

```bash
npx playwright install chromium
```

Register in `~/.claude.json`:

```json
"playwright": {
  "type": "stdio",
  "command": "npx",
  "args": ["@playwright/mcp@latest"]
}
```

### 4. AWS Bedrock — optional

If you want Claude Code to talk to Claude via AWS Bedrock instead of the Anthropic API, set these in your shell or in Claude Code's `env` block:

| Variable                    | Value                                                          |
|-----------------------------|----------------------------------------------------------------|
| `CLAUDE_CODE_USE_BEDROCK`   | `1`                                                            |
| `AWS_PROFILE`               | An SSO profile from `~/.aws/config`                            |
| `AWS_REGION`                | e.g. `us-east-1`                                               |
| `ANTHROPIC_MODEL`           | Inference profile ARN for the Claude model you want to use     |

Refresh credentials with `aws sso login --profile <profile>` (they expire roughly every 12 hours). Claude Code will call `awsAuthRefresh` automatically if you configure it.

---

## Project config

Copy `.claude/project-config.template.json` → `.claude/project-config.json` and fill in your values. The agents read this file at runtime — it tells them your Jira project key, your Bitbucket workspace, who your default reviewer is, and so on.

Key fields to set:

- **`repository`** — Bitbucket workspace, repo slug, default branch, and the branch PRs target.
- **`jira`** — Cloud ID (find via `mcp__atlassian__getAccessibleAtlassianResources` or your Atlassian admin), domain, project key.
- **`team.developer`** — Your Atlassian account ID. Look up via `mcp__atlassian__lookupJiraAccountId` or your Jira profile URL.
- **`team.default_reviewer`** — Default PR reviewer's Bitbucket UUID and Atlassian account ID.
- **`branching_strategy`** — Where feature branches are cut from, which branch gets review, which branches are promotions.
- **`jira_statuses`** — Map of logical states (`in_progress`, `pr_review`, `testing`, `done`) to your project's actual Jira status names.
- **`ui_testing`** — Base URL, login URL, and which platform profile to use (matches a file in `.claude/ui-test-profiles/`).

Don't commit `.claude/project-config.json` if it contains anything sensitive — but if it's just IDs and URLs that already live in your team's wiki, committing it makes onboarding easier. Decide per-team.

---

## Verifying setup

After registering MCP servers, restart Claude Code, then in your repo:

```bash
claude
/pm
```

The PM agent prints its banner with the project name and current branch, plus a status line. If MCP isn't wired up, you'll see errors when it tries to read Jira — fix those before moving on.

A quick MCP smoke test:

```
> what jira projects can I see?
```

That exercises the Atlassian server. For Bitbucket:

```
> list open PRs in <workspace>/<repo>
```

---

## Notes

- **No credentials in this repo.** The framework reads credentials from `~/.claude-agents/credentials.env` and from `~/.claude.json` (which Claude Code manages). Both live outside the project tree.
- **`.agent-state/` is per-worktree.** When you create a worktree via `/pm`, it gets its own state directory. Don't share state across worktrees.
- **The agents assume a specific layout.** Read `CLAUDE.md` before you start changing things — the master/worktree split and the `.agent-state/` filenames are load-bearing for the prompts.
