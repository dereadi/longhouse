# Longhouse

Open-source governance framework for multi-agent AI systems.

> "The topology is free. The organism is sovereign."

## What is this?

Multi-agent AI systems without governance produce noise, not intelligence. Adding more agents doesn't reliably improve outcomes (ICML 2024). What's missing is the orchestration layer — structured deliberation, adversarial challenge, and institutional memory.

Longhouse provides that layer. It is model-agnostic, framework-agnostic, and designed to integrate with any multi-agent system including CORAL, LangGraph, CrewAI, and custom architectures.

## Inspired by

The Haudenosaunee (Iroquois) Great Law of Peace — the oldest living participatory democracy on Earth. Council structure, consensus protocols, adversarial checks, and seven-generations thinking. Benjamin Franklin studied this system. It partially inspired the US Constitution. Now it inspires AI governance.

## Architecture

Longhouse implements a configurable council of specialist roles:

| Role | Function |
|---|---|
| **Skeptic** | Security risk evaluation |
| **Engineer** | Technical feasibility assessment |
| **Adversary** | Mandatory dissent — challenges every proposal |
| **Guardian** | Long-term impact (7-generation test) |
| **Sentinel** | Failure mode detection and recovery paths |
| **Chief** | Consensus synthesis and recommendation |

Additional roles (Mapper, Strategist) are configurable for domain-specific needs.

## Core Principles

1. **No action without governance** — agents cannot execute without council approval
2. **Mandatory dissent** — at least one role must challenge every proposal
3. **Diversity enforcement** — sycophantic agreement is detected and flagged
4. **Audit trail** — every vote is hashed, timestamped, and stored
5. **Model agnostic** — works on any LLM (cloud or local, any provider)
6. **Reversible decisions** — the Guardian ensures no irreversible lock-in

## Status

Under development. Private until v1 release.

## License

Apache 2.0

---

*For Seven Generations.*
