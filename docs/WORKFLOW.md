# Workflow (Single Source of Truth)

**Rule 1:** GitHub is the source of truth.  
**Rule 2:** This repository is authoritative for architecture and governance.  
**Rule 3:** Chats are ephemeral; commits are permanent.

## Roles

- **Argus (ChatGPT)**: architecture, governance, safety, review
- **Claude**: implementation based only on repo state
- **Perplexity**: research and validation
- **Comet**: execution layer (GitHub, files, commits)
- **Human**: final approval and merges

## No code changes without

- a clear goal
- reference to current repo files
- an explicit commit
