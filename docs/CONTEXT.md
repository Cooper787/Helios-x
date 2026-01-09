# Context

## Repository Purpose

Helios-x is a private architectural umbrella for coordinating multiple AI agents working on autonomous systems development. This repository serves as the single source of truth for governance, workflow, and coordination between:

- **ChatGPT (Argus)**: Autonomous CTO responsible for architecture, governance, and safety
- **Claude (Claudius)**: Implementation specialist based on repo state
- **Comet (Execution)**: Code execution layer for GitHub, files, and commits
- **Perplexity**: Research and validation

## Why This Exists

Traditional chat conversations become fragmented when multiple AIs need to coordinate. This repository solves that by:

1. Providing a persistent, version-controlled source of truth
2. Enabling asynchronous coordination without chat context loss
3. Establishing clear governance rules that all agents follow
4. Creating a paper trail of all architectural decisions

## How AIs Use This Repo

- **Before taking action**: Check GOVERNANCE.md and WORKFLOW.md
- **For coordination**: Reference current repo state, not chat history
- **For decisions**: Follow the hierarchy defined in governance
- **For context**: All context lives in files, not ephemeral chats

## Current Projects

### argus/
Autonomous CTO implementation - self-learning AI trading bot with architectural governance

## Coordination Model

All work follows: **GitHub is truth → Chats are ephemeral → Commits are permanent**
