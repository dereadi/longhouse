#!/usr/bin/env python3
"""
Longhouse — Open-Source Governance Harness for Multi-Agent AI Systems

The core council engine. This is the product.

    from longhouse import Council
    council = Council()
    result = council.vote("Should we deploy this change to production?")
    if result.approved:
        deploy()
    else:
        print(result.concerns)

Inspired by the Haudenosaunee Great Law of Peace — the oldest living
participatory democracy. Council structure, mandatory adversarial dissent,
consensus through governed disagreement.

Provisional Patents:
- Governance Topology for Multi-Agent AI Systems (63/999,913)
- Sycophancy Detection in AI Agent Collectives (63/999,926)

License: Apache 2.0
For Seven Generations.
"""

import json
import hashlib
import math
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger('longhouse')


# ============================================================
# Core Data Types
# ============================================================

class Vote(Enum):
    CONSENT = "consent"
    DISSENT = "dissent"
    CONCERN = "concern"
    ABSTAIN = "abstain"


@dataclass
class SpecialistResponse:
    """A single specialist's response to a proposal."""
    specialist_id: str
    role: str
    vote: Vote
    reasoning: str
    concerns: List[str] = field(default_factory=list)
    confidence: float = 0.5
    response_time_ms: float = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class CouncilResult:
    """The outcome of a council vote."""
    proposal: str
    audit_hash: str
    timestamp: str
    approved: bool
    recommendation: str
    confidence: float
    responses: List[SpecialistResponse]
    concerns: List[str]
    dissents: List[str]
    diversity_score: float
    sycophancy_pairs: List[tuple]
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['responses'] = [asdict(r) for r in self.responses]
        for r in d['responses']:
            r['vote'] = r['vote'].value if isinstance(r['vote'], Vote) else r['vote']
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


# ============================================================
# Specialist Roles
# ============================================================

@dataclass
class SpecialistRole:
    """Definition of a specialist role in the council."""
    id: str
    name: str
    role_description: str
    system_prompt: str
    is_adversarial: bool = False
    vote_weight: float = 1.0


# Default roles inspired by the Haudenosaunee council structure
DEFAULT_ROLES = [
    SpecialistRole(
        id="skeptic",
        name="Skeptic",
        role_description="Security and risk evaluation",
        system_prompt="""You are the Skeptic. Your role is to evaluate security risks,
identify vulnerabilities, and assess potential for harm. You look for what could go wrong.
Be specific about risks. Cite concrete failure modes, not vague warnings.
Vote CONSENT if risks are acceptable, CONCERN if risks need mitigation, DISSENT if risks are unacceptable.""",
    ),
    SpecialistRole(
        id="engineer",
        name="Engineer",
        role_description="Technical feasibility and architecture",
        system_prompt="""You are the Engineer. Your role is to assess technical feasibility,
resource requirements, and architectural implications. You evaluate whether the proposal
can actually be built and operated reliably.
Vote CONSENT if feasible, CONCERN if there are technical challenges, DISSENT if technically unsound.""",
    ),
    SpecialistRole(
        id="adversary",
        name="Adversary",
        role_description="Mandatory dissent — challenges every proposal",
        system_prompt="""You are the Adversary. Your role is MANDATORY DISSENT. You MUST find
at least one flaw, risk, or overlooked consequence in every proposal. This is not negativity —
it is error correction. Like stochastic rounding in numerical computation, your dissent
prevents systematic drift toward groupthink.
You may vote CONSENT only if you genuinely cannot find any flaw after rigorous examination.
Default to DISSENT or CONCERN. Explain specifically what could go wrong.""",
        is_adversarial=True,
    ),
    SpecialistRole(
        id="guardian",
        name="Guardian",
        role_description="Long-term impact — the 7-generation test",
        system_prompt="""You are the Guardian. Your role is to evaluate long-term consequences.
For every proposal, ask: will this still be valid and beneficial in 175 years?
Does it create irreversible dependencies? Does it compromise sovereignty?
Does it serve future generations or only the present?
Vote CONSENT if long-term impact is positive, CONCERN if uncertain, DISSENT if harmful long-term.""",
    ),
    SpecialistRole(
        id="sentinel",
        name="Sentinel",
        role_description="Failure mode detection and recovery",
        system_prompt="""You are the Sentinel. Your role is to identify specific failure modes
and evaluate recovery paths. For each failure mode: how do we detect it? How do we recover?
What is the blast radius? Can we roll back?
Vote CONSENT if recovery is feasible, CONCERN if recovery is difficult, DISSENT if failure is catastrophic and unrecoverable.""",
    ),
    SpecialistRole(
        id="chief",
        name="Chief",
        role_description="Consensus synthesis and recommendation",
        system_prompt="""You are the Chief. Your role is to synthesize all specialist responses
into a coherent recommendation. You do NOT override dissent — you integrate it.
Summarize: what does the council agree on? Where do they disagree? What concerns persist?
Your recommendation should reflect the FULL council perspective, not just the majority.
Always note standing dissents even if the majority consents.""",
        vote_weight=0.5,  # Chief synthesizes, doesn't dominate
    ),
]


# ============================================================
# LLM Backend Interface
# ============================================================

class LLMBackend:
    """
    Abstract interface for LLM calls. Implement this for your model.

    Longhouse is model-agnostic (DC-15). The governance works regardless
    of what LLM is underneath.
    """

    def generate(self, system_prompt: str, user_prompt: str,
                 max_tokens: int = 500, temperature: float = 0.7) -> str:
        """Generate a response from the LLM."""
        raise NotImplementedError("Implement generate() for your LLM backend")


class OpenAICompatibleBackend(LLMBackend):
    """Backend for any OpenAI-compatible API (vLLM, Ollama, OpenAI, etc.)."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000/v1",
                 model: str = "default", api_key: str = "not-needed"):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_key = api_key

    def generate(self, system_prompt: str, user_prompt: str,
                 max_tokens: int = 500, temperature: float = 0.7) -> str:
        import requests
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[LLM ERROR: {e}]"


class EchoBackend(LLMBackend):
    """Simple backend for testing — echoes the role with a default vote."""

    def generate(self, system_prompt: str, user_prompt: str,
                 max_tokens: int = 500, temperature: float = 0.7) -> str:
        if "Adversary" in system_prompt or "MANDATORY DISSENT" in system_prompt:
            return "DISSENT: This proposal needs more scrutiny before proceeding. Specific concern: insufficient risk analysis for edge cases."
        elif "Guardian" in system_prompt:
            return "CONCERN: Long-term implications need evaluation. Will this create dependencies that future generations cannot undo?"
        elif "Chief" in system_prompt:
            return "SYNTHESIS: The council has mixed views. Majority consents with concerns noted. Adversary raises valid points about edge cases. Recommend proceeding with caution and monitoring."
        else:
            return "CONSENT: The proposal is technically sound and within acceptable risk parameters. No blocking concerns identified."


# ============================================================
# Diversity Checker (Sycophancy Detection)
# ============================================================

class DiversityChecker:
    """
    Detects sycophantic agreement between specialists.

    Patent: Sycophancy Detection in AI Agent Collectives (63/999,926)

    If specialists are just echoing each other, the council provides
    no value over a single model. Diversity checking ensures that
    the council's multi-perspective design actually produces
    multiple perspectives.
    """

    def __init__(self, similarity_threshold: float = 0.85,
                 diversity_floor: float = 0.60):
        self.similarity_threshold = similarity_threshold
        self.diversity_floor = diversity_floor

    def check(self, responses: List[SpecialistResponse]) -> Dict:
        """Check pairwise diversity of specialist responses."""
        if len(responses) < 2:
            return {"diversity_score": 1.0, "sycophantic_pairs": [], "flagged": False}

        # Simple word-overlap similarity (production would use embeddings)
        pairs = []
        similarities = []

        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                sim = self._text_similarity(
                    responses[i].reasoning,
                    responses[j].reasoning
                )
                similarities.append(sim)
                if sim > self.similarity_threshold:
                    pairs.append((
                        responses[i].specialist_id,
                        responses[j].specialist_id,
                        round(sim, 4)
                    ))

        avg_similarity = sum(similarities) / len(similarities) if similarities else 0
        diversity_score = 1.0 - avg_similarity

        return {
            "diversity_score": round(diversity_score, 4),
            "sycophantic_pairs": pairs,
            "flagged": diversity_score < self.diversity_floor,
            "pair_count": len(pairs),
        }

    def _text_similarity(self, text_a: str, text_b: str) -> float:
        """Simple Jaccard similarity on word sets."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union) if union else 0.0


# ============================================================
# Audit Trail
# ============================================================

class AuditTrail:
    """
    Immutable audit trail for council votes.

    Every vote gets a hash, a timestamp, and full specialist responses.
    This is governance you can PROVE happened.
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path
        self.entries: List[Dict] = []

    def record(self, result: CouncilResult):
        """Record a council vote to the audit trail."""
        entry = result.to_dict()
        self.entries.append(entry)

        if self.storage_path:
            try:
                with open(self.storage_path, 'a') as f:
                    f.write(json.dumps(entry, default=str) + '\n')
            except Exception as e:
                logger.warning(f"Audit trail write failed: {e}")

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get recent audit entries."""
        return self.entries[-limit:]


# ============================================================
# The Council — The Core Engine
# ============================================================

class Council:
    """
    The Longhouse Council — governance harness for multi-agent AI systems.

    Usage:
        council = Council()
        result = council.vote("Should we deploy this change?")
        if result.approved:
            deploy()

    With custom LLM:
        backend = OpenAICompatibleBackend(base_url="http://localhost:8000/v1")
        council = Council(backend=backend)

    With custom roles:
        roles = [SpecialistRole(id="custom", name="Custom", ...)]
        council = Council(roles=roles)
    """

    def __init__(
        self,
        backend: LLMBackend = None,
        roles: List[SpecialistRole] = None,
        diversity_threshold: float = 0.85,
        diversity_floor: float = 0.60,
        max_tokens: int = 300,
        audit_path: str = None,
        require_adversary: bool = True,
    ):
        self.backend = backend or EchoBackend()
        self.roles = roles or DEFAULT_ROLES
        self.max_tokens = max_tokens
        self.require_adversary = require_adversary
        self.diversity_checker = DiversityChecker(diversity_threshold, diversity_floor)
        self.audit_trail = AuditTrail(audit_path)

        # Validate: at least one adversarial role if required
        if require_adversary:
            adversaries = [r for r in self.roles if r.is_adversarial]
            if not adversaries:
                logger.warning("No adversarial role defined. Adding default Adversary.")
                self.roles.append(DEFAULT_ROLES[2])  # Adversary

    def vote(self, proposal: str, context: str = "",
             metadata: Dict = None) -> CouncilResult:
        """
        Submit a proposal for council deliberation.

        Args:
            proposal: The question or proposal to evaluate
            context: Optional additional context
            metadata: Optional metadata to attach to the vote

        Returns:
            CouncilResult with approval status, concerns, and full specialist responses
        """
        start_time = time.time()
        timestamp = datetime.now().isoformat()

        # Generate audit hash
        hash_input = f"{proposal}{timestamp}{json.dumps(metadata or {})}"
        audit_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

        logger.info(f"Council vote {audit_hash} starting: {proposal[:80]}...")

        # Collect specialist responses
        responses = []
        for role in self.roles:
            if role.id == "chief":
                continue  # Chief goes last after seeing all responses

            resp = self._get_specialist_response(role, proposal, context)
            responses.append(resp)

        # Chief synthesizes (if present)
        chief_roles = [r for r in self.roles if r.id == "chief"]
        if chief_roles:
            chief_context = self._format_responses_for_chief(responses)
            chief_resp = self._get_specialist_response(
                chief_roles[0], proposal, chief_context
            )
            responses.append(chief_resp)

        # Check diversity
        diversity = self.diversity_checker.check(responses)

        # Determine outcome
        concerns = []
        dissents = []
        consent_count = 0
        total_weight = 0

        for resp in responses:
            role = next((r for r in self.roles if r.id == resp.specialist_id), None)
            weight = role.vote_weight if role else 1.0

            if resp.vote == Vote.CONSENT:
                consent_count += weight
            elif resp.vote == Vote.DISSENT:
                dissents.append(f"{resp.specialist_id}: {resp.reasoning[:200]}")
            elif resp.vote == Vote.CONCERN:
                concerns.extend(resp.concerns or [resp.reasoning[:200]])

            total_weight += weight

        # Calculate confidence
        consent_ratio = consent_count / total_weight if total_weight > 0 else 0
        confidence = consent_ratio * diversity['diversity_score']

        # Approval logic
        has_blocking_dissent = len(dissents) > 0 and self.require_adversary
        low_diversity = diversity['flagged']

        if confidence >= 0.7 and not has_blocking_dissent:
            approved = True
            recommendation = "APPROVED"
        elif confidence >= 0.5:
            approved = True
            recommendation = f"PROCEED WITH CAUTION: {len(concerns)} concern(s)"
            if dissents:
                recommendation += f", {len(dissents)} dissent(s) noted"
        else:
            approved = False
            recommendation = f"REVIEW REQUIRED: {len(concerns)} concern(s), {len(dissents)} dissent(s)"

        if low_diversity:
            recommendation += " [LOW DIVERSITY WARNING]"

        elapsed_ms = (time.time() - start_time) * 1000

        result = CouncilResult(
            proposal=proposal,
            audit_hash=audit_hash,
            timestamp=timestamp,
            approved=approved,
            recommendation=recommendation,
            confidence=round(confidence, 4),
            responses=responses,
            concerns=concerns,
            dissents=dissents,
            diversity_score=diversity['diversity_score'],
            sycophancy_pairs=diversity['sycophantic_pairs'],
            metadata={
                **(metadata or {}),
                "elapsed_ms": round(elapsed_ms, 2),
                "specialist_count": len(responses),
                "diversity_flagged": low_diversity,
            },
        )

        # Record to audit trail
        self.audit_trail.record(result)

        logger.info(
            f"Council vote {audit_hash}: {recommendation} "
            f"(confidence={confidence:.2f}, diversity={diversity['diversity_score']:.2f})"
        )

        return result

    def _get_specialist_response(self, role: SpecialistRole, proposal: str,
                                  context: str = "") -> SpecialistResponse:
        """Get a single specialist's response."""
        start = time.time()

        user_prompt = f"PROPOSAL: {proposal}"
        if context:
            user_prompt += f"\n\nCONTEXT:\n{context}"

        raw_response = self.backend.generate(
            system_prompt=role.system_prompt,
            user_prompt=user_prompt,
            max_tokens=self.max_tokens,
        )

        elapsed_ms = (time.time() - start) * 1000

        # Parse vote from response
        vote, reasoning, concerns = self._parse_response(raw_response, role)

        return SpecialistResponse(
            specialist_id=role.id,
            role=role.role_description,
            vote=vote,
            reasoning=reasoning,
            concerns=concerns,
            confidence=0.5,  # Could be extracted from response
            response_time_ms=round(elapsed_ms, 2),
        )

    def _parse_response(self, response: str, role: SpecialistRole) -> tuple:
        """Parse vote, reasoning, and concerns from raw LLM response."""
        response_upper = response.upper()
        concerns = []

        # Detect vote
        if "DISSENT" in response_upper:
            vote = Vote.DISSENT
        elif "CONCERN" in response_upper:
            vote = Vote.CONCERN
            concerns = [response[:200]]
        elif "CONSENT" in response_upper or "APPROVE" in response_upper:
            vote = Vote.CONSENT
        elif "ABSTAIN" in response_upper:
            vote = Vote.ABSTAIN
        else:
            # Default: adversarial roles default to CONCERN, others to CONSENT
            vote = Vote.CONCERN if role.is_adversarial else Vote.CONSENT

        return vote, response, concerns

    def _format_responses_for_chief(self, responses: List[SpecialistResponse]) -> str:
        """Format specialist responses for the Chief to synthesize."""
        lines = ["Previous specialist responses:\n"]
        for resp in responses:
            lines.append(f"**{resp.specialist_id}** ({resp.vote.value}): {resp.reasoning[:300]}")
            lines.append("")
        return '\n'.join(lines)


# ============================================================
# Convenience Functions
# ============================================================

def quick_vote(proposal: str, backend: LLMBackend = None) -> CouncilResult:
    """One-liner council vote."""
    council = Council(backend=backend)
    return council.vote(proposal)


def create_council(
    base_url: str = "http://127.0.0.1:8000/v1",
    model: str = "default",
    roles: List[SpecialistRole] = None,
    audit_path: str = None,
) -> Council:
    """Create a council with an OpenAI-compatible backend."""
    backend = OpenAICompatibleBackend(base_url=base_url, model=model)
    return Council(backend=backend, roles=roles, audit_path=audit_path)


# ============================================================
# CLI / Demo
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Longhouse Council — Governance for AI")
    parser.add_argument("proposal", nargs="?", default="Should we deploy this change to production?",
                        help="The proposal to vote on")
    parser.add_argument("--backend", choices=["echo", "local", "openai"], default="echo",
                        help="LLM backend to use")
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1",
                        help="Base URL for OpenAI-compatible backend")
    parser.add_argument("--model", default="default", help="Model name")
    parser.add_argument("--audit", default=None, help="Path to audit trail file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Select backend
    if args.backend == "echo":
        backend = EchoBackend()
    elif args.backend in ("local", "openai"):
        backend = OpenAICompatibleBackend(base_url=args.url, model=args.model)
    else:
        backend = EchoBackend()

    # Create council and vote
    council = Council(backend=backend, audit_path=args.audit)
    result = council.vote(args.proposal)

    if args.json:
        print(result.to_json())
    else:
        print(f"\n{'='*60}")
        print(f"  LONGHOUSE COUNCIL VOTE")
        print(f"  Audit: {result.audit_hash}")
        print(f"{'='*60}")
        print(f"\n  Proposal: {result.proposal}")
        print(f"\n  Decision: {result.recommendation}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Diversity: {result.diversity_score}")
        print(f"\n  Specialist Responses:")
        for resp in result.responses:
            marker = "⚔️" if resp.vote == Vote.DISSENT else "⚠️" if resp.vote == Vote.CONCERN else "✅"
            print(f"    {marker} {resp.specialist_id} ({resp.vote.value}): {resp.reasoning[:100]}")

        if result.concerns:
            print(f"\n  Concerns ({len(result.concerns)}):")
            for c in result.concerns:
                print(f"    - {c[:100]}")

        if result.dissents:
            print(f"\n  Dissents ({len(result.dissents)}):")
            for d in result.dissents:
                print(f"    - {d[:100]}")

        if result.sycophancy_pairs:
            print(f"\n  ⚠️ Sycophancy detected: {result.sycophancy_pairs}")

        print(f"\n  {'APPROVED ✅' if result.approved else 'NOT APPROVED ❌'}")
        print(f"\n{'='*60}")
        print(f"  For Seven Generations.")
        print(f"{'='*60}\n")
