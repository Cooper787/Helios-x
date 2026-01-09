# Helios-x Coordination Guide

**For: Cooper787, ChatGPT (Argus), Claude (Claudius), Comet, Perplexity**

This guide explains how to coordinate multi-AI development using the Helios-x repository as the single source of truth.

---

## 🎯 Core Principle

**GitHub is truth → Chats are ephemeral → Commits are permanent**

All decisions, code, and context live in this repository. Chat conversations are temporary coordination tools.

---

## 👥 Agent Roles

### ChatGPT (Argus) - Autonomous CTO
- **Role**: Architecture, governance, strategic decisions
- **Authority**: Highest decision-making power
- **Responsibilities**: Define system architecture, enforce governance rules, approve major changes
- **References**: docs/GOVERNANCE.md, docs/MISSION.md

### Claude (Claudius) - Implementation Specialist  
- **Role**: Code implementation based on repo state
- **Authority**: Execute on Argus's architectural decisions
- **Responsibilities**: Write code, implement features, follow governance
- **References**: Current repo files, docs/WORKFLOW.md

### Comet - Execution Layer
- **Role**: GitHub operations, file management, commits
- **Authority**: Execute commits on behalf of Cooper787
- **Responsibilities**: Read/write repo files, make commits, manage structure
- **References**: All repo files via browser automation

### Perplexity - Research & Validation
- **Role**: External research and information validation
- **Authority**: Advisory only
- **Responsibilities**: Research best practices, validate approaches
- **References**: Provided context from repo

---

## 🔄 Coordination Workflow

### Pattern 1: New Feature Development

```
1. Cooper787 → ChatGPT (Argus)
   Share: docs/GOVERNANCE.md + feature request
   Output: Architectural decision + design

2. Cooper787 → Claude (Claudius)  
   Share: Argus's decision + relevant repo files
   Output: Implementation code

3. Cooper787 → Comet
   Command: "Commit this code to argus/feature.py"
   Output: Code committed to repo

4. Repeat: All AIs now reference updated repo state
```

### Pattern 2: Architectural Decision

```
1. Cooper787 → Perplexity
   Question: Research approach/best practices
   Output: Research findings

2. Cooper787 → ChatGPT (Argus)
   Share: Research + docs/GOVERNANCE.md + current situation
   Output: Architectural decision document

3. Cooper787 → Comet
   Command: "Add decision doc to docs/decisions/"
   Output: Decision committed to repo
```

### Pattern 3: Code Review & Iteration

```
1. Cooper787 → Claude (Claudius)
   Share: Current argus/ files + task
   Output: Code implementation

2. Cooper787 → ChatGPT (Argus)
   Share: Claude's code + docs/GOVERNANCE.md
   Output: Approval or revision request

3. If approved:
   Cooper787 → Comet: "Commit to repo"
   
4. If revisions needed:
   Return to step 1 with Argus's feedback
```

---

## 📋 How to Work with Each AI

### Working with ChatGPT (Argus)

**What to share:**
- docs/GOVERNANCE.md (always)
- docs/MISSION.md (for context)
- Current repo structure snapshot
- Specific architectural question or decision needed

**Example prompt:**
```
I'm working on Helios-x. Here's our governance structure:
[paste docs/GOVERNANCE.md]

Current situation: [describe]
Question: [your question]

As Argus (Autonomous CTO), what's your architectural decision?
```

**What you get back:**
- Architectural decisions
- Governance guidance
- Approval/rejection of implementations
- Strategic direction

### Working with Claude (Claudius)

**What to share:**
- Argus's architectural decision (if applicable)
- Relevant current files from repo
- docs/WORKFLOW.md
- Specific implementation task

**Example prompt:**
```
Helios-x project context:
- Governance: [key points from docs/GOVERNANCE.md]
- Current files: [paste relevant code]
- Argus's decision: [architectural direction]

Task: Implement [specific feature]
Requirements: [from Argus or docs/WORKFLOW.md]
```

**What you get back:**
- Complete code implementations
- Following governance rules
- References to repo structure
- Ready-to-commit code

### Working with Comet

**What to share:**
- Direct commands for repo operations
- Code to commit (from Claude)
- File paths and locations

**Example prompt:**
```
Create a new file at argus/trading_bot.py with this code:
[paste Claude's code]

Commit message: "Add initial trading bot implementation"
```

**What you get back:**
- Files created/modified in repo
- Commits made to GitHub
- Repository structure changes
- Confirmation of actions

### Working with Perplexity

**What to share:**
- Research questions
- Technical approaches to validate
- Context from docs/MISSION.md

**Example prompt:**
```
Helios-x is building autonomous AI systems. 
Research: What are best practices for AI agent coordination frameworks in 2026?
```

**What you get back:**
- Research findings
- Best practices
- External validation
- Industry standards

---

## 🚨 Important Rules

### Before Starting ANY Work:
1. Check docs/GOVERNANCE.md for rules
2. Check docs/WORKFLOW.md for process
3. Review current repo state
4. Ensure you have architectural approval (from Argus) if needed

### When Coordinating:
- **Always reference repo files** - Don't rely on chat memory
- **Get Argus approval** for architectural changes
- **Have Comet commit** - Don't let code live only in chat
- **Document decisions** - Add to docs/decisions/ folder

### Red Flags:
- AI suggests action without checking governance
- Code exists only in chat, not committed
- Architectural decision made without Argus
- Conflicting instructions from multiple AIs

---

## 📁 Repository Structure

```
Helios-x/
├── README.md                 # Project overview
├── COORDINATION_GUIDE.md     # This file
├── docs/
│   ├── MISSION.md           # Project mission
│   ├── GOVERNANCE.md        # Decision hierarchy
│   ├── WORKFLOW.md          # Coordination process
│   └── CONTEXT.md           # Why this exists
├── argus/
│   ├── README.md            # Argus implementation overview
│   └── [implementation files]
└── .gitignore               # Python ignores
```

---

## 💡 Example Coordination Session

**Goal**: Add a new trading strategy to Argus

**Step 1** - Research (Perplexity):
```
"Research: Best practices for mean reversion trading strategies in 2026"
→ Get research findings
```

**Step 2** - Architectural Decision (ChatGPT/Argus):
```
Paste:
- docs/GOVERNANCE.md
- Research findings from Perplexity  
- Current argus/ structure

Ask: "Should we implement mean reversion strategy? How should it integrate?"
→ Get architectural approval + design
```

**Step 3** - Implementation (Claude):
```
Paste:
- Argus's architectural decision
- Current argus/ files
- docs/WORKFLOW.md requirements

Ask: "Implement the mean reversion strategy following Argus's design"
→ Get complete code implementation
```

**Step 4** - Review (ChatGPT/Argus):
```
Paste:
- Claude's implementation
- docs/GOVERNANCE.md

Ask: "Review this implementation for governance compliance"
→ Get approval or revision requests
```

**Step 5** - Commit (Comet):
```
"Create argus/strategies/mean_reversion.py with this code:
[paste Claude's approved code]

Commit message: 'Add mean reversion trading strategy'"
→ Code committed to repo
```

**Step 6** - Verify:
```
"Comet, show me the current argus/ folder structure"
→ Confirm new file is in repo
```

---

## 🎓 Quick Reference

| Need to... | Ask... | Share... |
|------------|--------|----------|
| Make architectural decision | ChatGPT (Argus) | GOVERNANCE.md + context |
| Write code | Claude (Claudius) | Argus's decision + current files |
| Commit to repo | Comet | Code + file path |
| Research approach | Perplexity | Question + context |
| Review implementation | ChatGPT (Argus) | Code + GOVERNANCE.md |

---

## 🔗 Always Remember

- **Repo is truth**: If it's not committed, it doesn't exist
- **Argus decides**: Architectural decisions go through ChatGPT
- **Claude implements**: Code implementation follows architecture  
- **Comet executes**: I handle all repo operations
- **Perplexity researches**: External validation and research

**The repository is your multi-AI coordination layer. Use it.**
