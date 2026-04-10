#!/usr/bin/env python3
"""
Longhouse Guidance Injection — Context Engineering for Agent Tasks

Inspired by NotNative/Shanz Moore's NotNativeCoder guidance pattern.
Adapted for multi-agent governance at federation level.

Shanz's pattern: hardcoded guidance files (Power of 10, security patterns,
language idioms) injected into every system prompt based on file extension.
Simple, static, effective.

Our extension: guidance injected based on TASK TYPE, not just file type.
Combined with SkillRL learned patterns and council design constraints.

Three tiers of guidance (Shanz's distinction applied):
1. ALWAYS — Design Constraints (DCs), security rules, constitutional principles.
   Injected every session. Never decay. Like Shanz's guidance/always/.
2. DOMAIN — Task-type-specific guidance (Python patterns, DB operations,
   content writing, research methodology). Like Shanz's language-specific files.
3. LEARNED — SkillRL execution traces, council voting patterns, past corrections.
   Dynamic, earned through production use. What Shanz doesn't have yet.

For Seven Generations.
"""

import os
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger('longhouse.guidance')

# Default guidance directory
GUIDANCE_DIR = os.environ.get('LONGHOUSE_GUIDANCE_DIR',
    os.path.join(os.path.dirname(__file__), 'guidance'))


class GuidanceLibrary:
    """
    Manages guidance documents organized by tier and domain.

    Directory structure:
    guidance/
    ├── always/           # Tier 1: Always injected
    │   ├── design_constraints.md
    │   ├── security_rules.md
    │   └── sovereignty.md
    ├── domain/           # Tier 2: Injected by task type
    │   ├── python.md
    │   ├── database.md
    │   ├── content.md
    │   ├── research.md
    │   ├── infrastructure.md
    │   └── security_ops.md
    └── learned/          # Tier 3: Injected from SkillRL
        └── (populated dynamically)
    """

    def __init__(self, guidance_dir: str = GUIDANCE_DIR):
        self.guidance_dir = Path(guidance_dir)
        self._ensure_structure()

    def _ensure_structure(self):
        """Create guidance directory structure if it doesn't exist."""
        for tier in ['always', 'domain', 'learned']:
            (self.guidance_dir / tier).mkdir(parents=True, exist_ok=True)

    def get_always_guidance(self) -> List[Dict]:
        """Get Tier 1 guidance — always injected regardless of task."""
        return self._load_tier('always')

    def get_domain_guidance(self, task_type: str) -> List[Dict]:
        """Get Tier 2 guidance — specific to task type."""
        # Map task types to guidance files
        domain_map = {
            'python': ['python.md'],
            'code': ['python.md'],
            'database': ['database.md'],
            'db': ['database.md'],
            'sql': ['database.md'],
            'content': ['content.md'],
            'writing': ['content.md'],
            'substack': ['content.md'],
            'research': ['research.md'],
            'paper': ['research.md'],
            'infrastructure': ['infrastructure.md'],
            'deploy': ['infrastructure.md'],
            'systemd': ['infrastructure.md'],
            'security': ['security_ops.md'],
            'audit': ['security_ops.md'],
            'shield': ['security_ops.md'],
        }

        files = domain_map.get(task_type.lower(), [])
        results = []
        for filename in files:
            filepath = self.guidance_dir / 'domain' / filename
            if filepath.exists():
                results.append({
                    'source': f'domain/{filename}',
                    'content': filepath.read_text(),
                    'tier': 'domain',
                })
        return results

    def get_learned_guidance(self, task_description: str, max_skills: int = 3) -> List[Dict]:
        """Get Tier 3 guidance — from SkillRL execution traces."""
        try:
            from skill_selector import SkillSelector
            from ganuda_db import get_connection

            conn = get_connection()
            selector = SkillSelector(conn)
            skills = selector.select_skills_semantic(task_description, max_skills=max_skills)
            conn.close()

            results = []
            for skill in skills:
                results.append({
                    'source': f'learned/skill:{skill.get("name", "unknown")}',
                    'content': skill.get('method', '') or skill.get('intent', ''),
                    'tier': 'learned',
                    'similarity': skill.get('semantic_similarity', 0),
                })
            return results
        except Exception as e:
            logger.debug(f"SkillRL guidance unavailable: {e}")
            return []

    def _load_tier(self, tier: str) -> List[Dict]:
        """Load all guidance files from a tier directory."""
        tier_dir = self.guidance_dir / tier
        results = []
        if tier_dir.exists():
            for filepath in sorted(tier_dir.glob('*.md')):
                results.append({
                    'source': f'{tier}/{filepath.name}',
                    'content': filepath.read_text(),
                    'tier': tier,
                })
        return results


class GuidanceInjector:
    """
    Injects relevant guidance into task context before execution.

    This is the snap-on that sits between task assignment and task execution.
    The Jr executor calls inject() before processing any task, and gets back
    a context-enriched task with relevant guidance prepended.
    """

    def __init__(self, library: GuidanceLibrary = None):
        self.library = library or GuidanceLibrary()

    def inject(self, task: Dict, include_learned: bool = True) -> str:
        """
        Generate guidance context for a task.

        Returns a formatted string to prepend to the task instructions.
        """
        sections = []

        # Tier 1: Always
        always = self.library.get_always_guidance()
        if always:
            sections.append("## GOVERNANCE GUIDANCE (always applies)")
            for g in always:
                sections.append(f"### {g['source']}")
                sections.append(g['content'])

        # Tier 2: Domain — detect from task metadata
        task_type = self._detect_task_type(task)
        if task_type:
            domain = self.library.get_domain_guidance(task_type)
            if domain:
                sections.append(f"\n## DOMAIN GUIDANCE ({task_type})")
                for g in domain:
                    sections.append(f"### {g['source']}")
                    sections.append(g['content'])

        # Tier 3: Learned — from SkillRL
        if include_learned:
            description = task.get('description', '') or task.get('title', '')
            learned = self.library.get_learned_guidance(description)
            if learned:
                sections.append("\n## LEARNED PATTERNS (from previous successful tasks)")
                for g in learned:
                    sim = g.get('similarity', 0)
                    sections.append(f"### {g['source']} (similarity: {sim:.2f})")
                    sections.append(g['content'])

        return '\n\n'.join(sections) if sections else ''

    def _detect_task_type(self, task: Dict) -> Optional[str]:
        """Detect task type from title, description, tags, or file paths."""
        title = (task.get('title', '') or '').lower()
        description = (task.get('description', '') or '').lower()
        tags = task.get('tags', []) or []
        instruction_file = (task.get('instruction_file', '') or '').lower()

        combined = f"{title} {description} {' '.join(str(t) for t in tags)} {instruction_file}"

        # Priority-ordered detection
        if any(kw in combined for kw in ['security', 'audit', 'shield', 'vulnerability', 'canary']):
            return 'security'
        if any(kw in combined for kw in ['database', 'sql', 'postgres', 'index', 'migration', 'rollback']):
            return 'database'
        if any(kw in combined for kw in ['deploy', 'systemd', 'service', 'infrastructure', 'node', 'network']):
            return 'infrastructure'
        if any(kw in combined for kw in ['research', 'paper', 'arxiv', 'study', 'survey', 'analysis']):
            return 'research'
        if any(kw in combined for kw in ['substack', 'article', 'blog', 'content', 'linkedin', 'write']):
            return 'content'
        if any(kw in combined for kw in ['python', '.py', 'code', 'function', 'class', 'module', 'script']):
            return 'python'

        return None

    def inject_for_file(self, filepath: str) -> str:
        """Generate guidance based on file extension — Shanz's original pattern."""
        ext = Path(filepath).suffix.lower()

        ext_map = {
            '.py': 'python',
            '.sql': 'database',
            '.md': 'content',
            '.sh': 'infrastructure',
            '.yaml': 'infrastructure',
            '.yml': 'infrastructure',
            '.json': 'python',
            '.ts': 'python',  # close enough for guidance
            '.js': 'python',
        }

        task_type = ext_map.get(ext)
        if task_type:
            domain = self.library.get_domain_guidance(task_type)
            if domain:
                sections = [f"## GUIDANCE FOR {ext} FILES"]
                for g in domain:
                    sections.append(g['content'])
                return '\n\n'.join(sections)
        return ''


def create_default_guidance():
    """Create default guidance files for a fresh installation."""
    library = GuidanceLibrary()

    # Tier 1: Always — Design Constraints
    always_dc = library.guidance_dir / 'always' / 'design_constraints.md'
    if not always_dc.exists():
        always_dc.write_text("""# Design Constraints (Always Apply)

- **DC-15 Model Agnosticism**: Governance works on ANY underlying LLM. No vendor lock-in.
- **DC-16 Institutional Memory as Moat**: Code can be open-sourced. Experience cannot be replicated.
- **DC-17 Stochastic Governance**: Adversarial dissent = error correction. Calibrated noise prevents systematic drift.
- **DC-18 Path Anchoring**: All file paths must root in the approved directory tree.
- **DC-19 Context Reload**: On new session, orient before acting.
- **DC-20 Lever Not Crutch**: The system augments the human, doesn't replace.
""")

    always_security = library.guidance_dir / 'always' / 'security_rules.md'
    if not always_security.exists():
        always_security.write_text("""# Security Rules (Always Apply)

- No credentials in source code. Use secrets_loader or environment variables.
- No PII in logs, thermals, or commit messages.
- All inter-node communication over WireGuard encrypted mesh.
- Pre-flight gate: validate outputs before writing to production paths.
- Protected paths list: never overwrite without governance approval.
""")

    # Tier 2: Domain — Python
    domain_python = library.guidance_dir / 'domain' / 'python.md'
    if not domain_python.exists():
        domain_python.write_text("""# Python Guidance

- Use `float()` for any value from PostgreSQL that might be `Decimal` type.
- Always `conn.commit()` after writes. Log before `conn.rollback()`.
- Prefer `psycopg2.extras.RealDictCursor` for readable results.
- Use `sys.path.insert(0, '/ganuda/lib')` for library imports.
- File paths must be absolute and within /ganuda/, /tmp/, or /home/dereadi/.
- Use cherokee_venv for dependencies: `/home/dereadi/cherokee_venv/bin/python`.
""")

    # Tier 2: Domain — Database
    domain_db = library.guidance_dir / 'domain' / 'database.md'
    if not domain_db.exists():
        domain_db.write_text("""# Database Guidance

- Primary DB: zammad_production on bluefin (10.100.0.2:5432)
- PgBouncer: port 6432 on bluefin (transaction mode)
- Use `get_db_config()` from `ganuda_db` for connection params
- CREATE INDEX CONCURRENTLY for production indexes
- Check index selectivity before creating (100% same value = useless index)
- thermal_memory_archive: 97K+ rows, temperature_score, sacred_pattern, original_content
- Always log before rollback: `logger.warning(f"ROLLBACK: {e}")`
""")

    # Tier 2: Domain — Content
    domain_content = library.guidance_dir / 'domain' / 'content.md'
    if not domain_content.exists():
        domain_content.write_text("""# Content Guidance

- Partner voice: calm, competent, wondering. Jimmy the Tulip energy.
- No emojis unless Partner requests.
- Technical but accessible. Show don't tell.
- The Tulip test: don't explain the architecture, let them discover they're inside it.
- Substack publisher: SubstackPublisher class via bmasass SSH proxy.
- LinkedIn: FARA posts via Brave Browser on sasass.
- All content goes through Deer editorial authority.
""")

    # Tier 2: Domain — Research
    domain_research = library.guidance_dir / 'domain' / 'research.md'
    if not domain_research.exists():
        domain_research.write_text("""# Research Guidance

- Coyote test: every claim must be falsifiable. What would disprove this?
- Cite sources. No unsourced claims in papers.
- Separate what's COMPUTED from what's INTERPRETED.
- Owl verification: run computation on owlfin independently before claiming results.
- DERsnTt²: two substrates, compare the delta. 9/10 produce contradictions.
- The null hypothesis gets equal space in the paper.
""")

    # Tier 2: Domain — Infrastructure
    domain_infra = library.guidance_dir / 'domain' / 'infrastructure.md'
    if not domain_infra.exists():
        domain_infra.write_text("""# Infrastructure Guidance

- Use FreeIPA NOPASSWD sudo: systemctl, tee, cat, cp, chmod, mkdir available.
- WireGuard IPs: bluefin=10.100.0.2, greenfin=10.100.0.3, owlfin=10.100.0.5, eaglefin=10.100.0.6
- Silverfin (FreeIPA server): 192.168.10.10
- Deploy services via: sudo tee for service files, sudo systemctl daemon-reload + start.
- RTX 6000 (96GB) is in redfin. RTX 5070 (12GB) is in bluefin. Do NOT confuse them.
- Greenfin runs BitNet ternary reflex (DC-10) + Cherokee 8B. No GPU.
- bmasass: M4 Max 128GB, Llama 70B (8801), Qwen3 30B (8800).
""")

    # Tier 2: Domain — Security Operations
    domain_secops = library.guidance_dir / 'domain' / 'security_ops.md'
    if not domain_secops.exists():
        domain_secops.write_text("""# Security Operations Guidance

- Shield: consent-first monitoring. Agent WILL NOT START without recorded consent.
- Evidence vault: immutable, encrypted, chain of custody on every access.
- Canary: port scanning, credential detection, config checking.
- Fire Guard: service watchdog every 2 minutes, known-down suppression.
- Medicine Woman: health monitoring every 15 minutes, phi-based assessment.
- No credentials in source code. Pre-commit hook blocks secrets.
- Crawdad audit requirement on all security-adjacent code.
""")

    print(f"Default guidance created in {library.guidance_dir}")
    return library


if __name__ == "__main__":
    # Create default guidance and demo injection
    print("=== Creating Default Guidance ===\n")
    library = create_default_guidance()

    print("\n=== Demo: Injection for a Python task ===\n")
    injector = GuidanceInjector(library)
    task = {
        'title': 'Fix database rollback rate',
        'description': 'Add indexes and log rollbacks in Python daemons',
        'tags': ['database', 'python', 'performance'],
    }
    guidance = injector.inject(task, include_learned=False)
    print(guidance[:1500] if guidance else "No guidance generated")

    print("\n\n=== Demo: Injection for a content task ===\n")
    task2 = {
        'title': 'Write Substack article on Longhouse',
        'description': 'Article about open-source governance framework',
    }
    guidance2 = injector.inject(task2, include_learned=False)
    print(guidance2[:1500] if guidance2 else "No guidance generated")

    print("\n\nFor Seven Generations.")
