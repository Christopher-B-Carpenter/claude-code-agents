# Claude Agent Framework

A multi-agent system for Claude Code with branch/worktree management.

---

## Quick Start

```bash
cd ~/your-repo    # On master/main
claude
/pm                   # PM detects master, offers branch setup
> "new XXX-1234"      # Creates branch + worktree
# Follow instructions to cd to worktree
```

---

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  ~/ (master)                                               │
│    │                                                                │
│    ├── /pm "new XXX-1234"                                           │
│    │     └── Creates: feature/XXX-1234 branch                       │
│    │     └── Creates: ../xxxx/ worktree            │
│    │     └── Copies: .claude/ commands                              │
│    │     └── Says: "cd ../xxxx && claude"          │
│    │                                                                │
│    └── /pm "continue feature/XXX-9999"                              │
│          └── Creates worktree for existing branch                   │
│          └── Says: "cd ../xxxx && claude"          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ~/feature-XXX-1234/ (worktree)                            │
│    │                                                                │
│    ├── /pm      → Describe ticket, plan work                        │
│    ├── /dev     → Implement changes                                 │
│    ├── /arch    → Review code and design                            │
│    ├── /sec     → Security and compliance review                    │
│    ├── /test    → Run tests                                         │
│    │                                                                │
│    └── Each has isolated .agent-state/                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Agents

| Agent | Command | Icon | Color | Role |
|-------|---------|------|-------|------|
| **PM** | `/pm` | 🎯 | Magenta | Branch setup, planning, coordination |
| **Developer** | `/dev` | 🔧 | Green | Code implementation |
| **Architect** | `/arch` | 🏗️ | Blue | Code review and design |
| **Security** | `/sec` | 🛡️ | Red | Security, data, and compliance review |
| **Tester** | `/test` | 🧪 | Yellow | Testing and validation |

---

## PM Commands

**On master/main (protected):**

| Command | Action |
|---------|--------|
| `new [TICKET]` | Create branch + worktree, e.g. `new XXX-1234` |
| `continue [BRANCH]` | Create worktree for existing branch |
| `list` | Show all branches and worktrees |
| `cleanup [BRANCH]` | Remove worktree and delete branch (if merged) |

**On feature branch:**

| Command | Action |
|---------|--------|
| `status` | Show project status and recommendations |
| `plan` | Create/update the plan |
| `next` | Get next step recommendations |

---

## Security Agent Commands

| Command | Action |
|---------|--------|
| `review` | Review uncommitted changes for security issues |
| `review [file]` | Review specific file |
| `scan secrets` | Check for hardcoded secrets/credentials |
| `compliance [type]` | Check specific compliance (GDPR, SOC2, HIPAA, PCI) |
| `data` | Review data handling and privacy |

**Findings Severity:** Critical → High → Medium → Low → Info

---

## Visual Identity

Each agent shows **project name AND branch**:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🔧  DEVELOPER AGENT                                               ┃
┃      XXXX (feature/XXX-1234)                      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

⚠️  Git: 3 uncommitted changes
 M XX...
```

**On master:**
```
┃      branch (master) ⚠️  PROTECTED                                   ┃
```

---

## Git Awareness

All agents check git status:

- **Startup:** Shows uncommitted changes
- **Before changes:** Warns if dirty working tree
- **Completion:** Shows files changed
- **Status files:** Record branch and git state

---

## Directory Structure

```
~/src/
├── main/                           # Master - stays clean
│   ├── .claude/commands/           # Agent commands (template)
│   └── (no .agent-state/)          # No work done here
│
├── feature/          # Worktree for ticket
│   ├── .claude/commands/           # Copied from master
│   ├── .agent-state/               # Isolated state
│   │   ├── project.md              # Ticket description
│   │   ├── plan.md                 # Implementation plan
│   │   ├── pm-status.md
│   │   ├── dev-status.md
│   │   ├── arch-status.md
│   │   ├── sec-status.md           # Security findings
│   │   ├── test-status.md
│   │   └── activity.log
│   └── (feature/XXX-1234 branch)
│
└── feature/          # Another ticket (parallel)
    ├── .agent-state/               # Separate state
    └── (feature/XXX-5678 branch)
```

---

## Typical Session

```bash
# 1. Start from master
cd ~/
claude
/pm

# PM shows: "You're on master - this branch should stay clean"
# PM shows existing worktrees and branches

> "new XXX-1234"

# PM creates branch + worktree
# PM says: "cd ../feature-XXX-1234 && claude"

# 2. Work in worktree
cd ../feature-XXX-1234
claude
/pm

# PM asks for ticket details
> "XXX-1234: Add validation rule for Opportunity stage changes..."

# PM creates project.md and plan.md

/dev
> "implement the validation rule"

# Dev implements, shows git status on completion

/sec
> "review"

# Security reviews for vulnerabilities, data issues, compliance

/arch
> "review"

# Arch reviews git diff, approves

# 3. Commit and PR (you do this)
git add -A
git commit -m "XXX-1234: Add stage change validation"
git push origin feature/XXX-1234

# 4. Cleanup after merge
cd ~/src/sfdc
/pm
> "cleanup feature/XXX-1234"

# PM removes worktree and branch
```

---

## Recommended Review Order

```
/dev (implement) → /sec (security) → /arch (design) → /test (validate)
```

Security review before architecture review catches issues early.

---

## Parallel Work

Run multiple tickets simultaneously:

**Terminal 1:**
```bash
cd ~/src/feature-XXX-1234
claude
/dev   # Shows: feature-XXX-1234 (feature/XXX-1234)
```

**Terminal 2:**
```bash
cd ~/feature-XXX-5678
claude
/dev   # Shows: feature-XXX-5678 (feature/XXX-5678)
```

Each worktree has isolated state - no conflicts.

---

## Installation

Copy to your repository's master branch:

```bash
cd ~/your-repo
git checkout master
cp -r /path/to/claude-agents/.claude .
cp /path/to/claude-agents/CLAUDE.md .
git add .claude CLAUDE.md
git commit -m "Add Claude agent framework"
```

Then worktrees inherit the commands automatically.
