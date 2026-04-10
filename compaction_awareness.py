#!/usr/bin/env python3
"""
Longhouse Compaction Awareness — Mechanical Memory Management

Inspired by NotNative/Shanz Moore's compaction trigger design.
Adapted for federation-level operation across the Ganuda cluster.

The problem: When a Claude Code session hits context limits and compacts,
critical knowledge is lost. The TPM forgets the 5070 is in bluefin.
The council forgets yesterday's decisions. The Jr forgets what it learned.

The solution: Mechanical triggers that store before compaction and
recall after, without the model needing to decide.

Terminal level (Shanz's pattern):
- 70% capacity: warn model to store important context
- 80% capacity: forced memory-store before compaction
- Post-compaction: auto-recall from memory

Federation level (our extension):
- Session start: context_reload.py fires automatically
- Significant event: thermal write with structured metadata
- Session end: summary thermal with session highlights
- Cross-session: thermal search by file, topic, or timeline

For Seven Generations.
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, '/ganuda/lib')


class SessionMemory:
    """
    Tracks significant events during a session for pre-compaction storage.

    This is the federation-level equivalent of Shanz's mechanical triggers.
    Instead of watching token count (terminal level), we watch for
    significant events (federation level) and store them as thermals.
    """

    def __init__(self, session_id: str = None):
        self.session_id = session_id or hashlib.sha256(
            datetime.now().isoformat().encode()
        ).hexdigest()[:16]
        self.events: List[Dict] = []
        self.files_touched: set = set()
        self.decisions_made: List[str] = []
        self.corrections: List[str] = []
        self.discoveries: List[str] = []
        self.started_at = datetime.now()

    def record_event(self, event_type: str, content: str, metadata: dict = None):
        """Record a significant event for potential storage."""
        self.events.append({
            "type": event_type,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        })

    def record_file_touch(self, filepath: str, action: str = "modified"):
        """Record that a file was touched — enables per-file recall."""
        self.files_touched.add(filepath)
        self.record_event("file_touch", f"{action}: {filepath}")

    def record_decision(self, decision: str):
        """Record a significant decision for session summary."""
        self.decisions_made.append(decision)
        self.record_event("decision", decision)

    def record_correction(self, correction: str):
        """Record when the operator corrects the model — high-value learning."""
        self.corrections.append(correction)
        self.record_event("correction", correction)

    def record_discovery(self, discovery: str):
        """Record when something unexpected is found — build/test failure, bug, insight."""
        self.discoveries.append(discovery)
        self.record_event("discovery", discovery)

    def generate_session_summary(self) -> str:
        """Generate a structured session summary for thermal storage."""
        duration = (datetime.now() - self.started_at).total_seconds() / 60

        summary = f"SESSION SUMMARY — {self.session_id}\n"
        summary += f"Duration: {duration:.0f} minutes\n"
        summary += f"Started: {self.started_at.isoformat()}\n\n"

        if self.decisions_made:
            summary += "DECISIONS:\n"
            for d in self.decisions_made:
                summary += f"  - {d}\n"
            summary += "\n"

        if self.corrections:
            summary += "CORRECTIONS (high-value learning):\n"
            for c in self.corrections:
                summary += f"  - {c}\n"
            summary += "\n"

        if self.discoveries:
            summary += "DISCOVERIES:\n"
            for d in self.discoveries:
                summary += f"  - {d}\n"
            summary += "\n"

        if self.files_touched:
            summary += f"FILES TOUCHED ({len(self.files_touched)}):\n"
            for f in sorted(self.files_touched):
                summary += f"  - {f}\n"
            summary += "\n"

        summary += f"Total events: {len(self.events)}\n"
        return summary

    def store_to_thermal(self, temperature: float = 70.0):
        """Store session summary to thermal memory."""
        try:
            from ganuda_db import safe_thermal_write
            summary = self.generate_session_summary()
            safe_thermal_write(
                content=summary,
                temperature=temperature,
                sacred=False,
                metadata={
                    "type": "session_summary",
                    "session_id": self.session_id,
                    "decisions_count": len(self.decisions_made),
                    "corrections_count": len(self.corrections),
                    "discoveries_count": len(self.discoveries),
                    "files_touched": len(self.files_touched),
                    "duration_minutes": (datetime.now() - self.started_at).total_seconds() / 60,
                }
            )
            return True
        except Exception as e:
            print(f"[CompactionAwareness] Thermal store failed: {e}")
            return False


class FileMemory:
    """
    Per-file thermal memory — "have I worked on this before?"

    When a file is opened, automatically search thermals mentioning
    that file to restore context about previous work.
    """

    @staticmethod
    def recall_file_context(filepath: str, limit: int = 5) -> List[Dict]:
        """Search thermal memory for previous context about a file."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            conn = psycopg2.connect(
                host=os.environ.get('CHEROKEE_DB_HOST', '10.100.0.2'),
                database=os.environ.get('CHEROKEE_DB_NAME', 'zammad_production'),
                user=os.environ.get('CHEROKEE_DB_USER', 'claude'),
                password=os.environ.get('CHEROKEE_DB_PASS', '')
            )
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Search for the filename in thermal memory
            filename = os.path.basename(filepath)
            cur.execute("""
                SELECT id, LEFT(original_content, 300) as content,
                       temperature_score, created_at, sacred_pattern
                FROM thermal_memory_archive
                WHERE original_content ILIKE %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (f"%{filename}%", limit))

            results = cur.fetchall()
            conn.close()
            return [dict(r) for r in results]
        except Exception as e:
            return [{"error": str(e)}]

    @staticmethod
    def recall_topic_context(topic: str, limit: int = 5) -> List[Dict]:
        """Search thermal memory for context about a topic."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            conn = psycopg2.connect(
                host=os.environ.get('CHEROKEE_DB_HOST', '10.100.0.2'),
                database=os.environ.get('CHEROKEE_DB_NAME', 'zammad_production'),
                user=os.environ.get('CHEROKEE_DB_USER', 'claude'),
                password=os.environ.get('CHEROKEE_DB_PASS', '')
            )
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT id, LEFT(original_content, 300) as content,
                       temperature_score, created_at, sacred_pattern
                FROM thermal_memory_archive
                WHERE original_content ILIKE %s
                ORDER BY temperature_score DESC, created_at DESC
                LIMIT %s
            """, (f"%{topic}%", limit))

            results = cur.fetchall()
            conn.close()
            return [dict(r) for r in results]
        except Exception as e:
            return [{"error": str(e)}]


class CompactionGuard:
    """
    Pre-compaction awareness at the federation level.

    Since we can't directly monitor Claude Code's context window from
    outside, we use time-based and event-based heuristics:

    - Long sessions (>2 hours) → likely approaching compaction
    - High event count (>50 events) → lots of context to preserve
    - Significant decisions → store immediately, don't wait
    - Corrections → store immediately (highest value learning)
    """

    def __init__(self, session: SessionMemory):
        self.session = session
        self.auto_store_threshold_minutes = 120  # 2 hours
        self.auto_store_threshold_events = 50
        self.last_auto_store = datetime.now()

    def check_and_store(self) -> bool:
        """Check if auto-store should fire based on heuristics."""
        now = datetime.now()
        minutes_elapsed = (now - self.last_auto_store).total_seconds() / 60
        event_count = len(self.session.events)

        should_store = False
        reason = ""

        if minutes_elapsed >= self.auto_store_threshold_minutes:
            should_store = True
            reason = f"Time-based: {minutes_elapsed:.0f} min since last store"

        if event_count >= self.auto_store_threshold_events:
            should_store = True
            reason = f"Event-based: {event_count} events accumulated"

        if len(self.session.corrections) > 0:
            # Corrections are highest value — always store immediately
            should_store = True
            reason = f"Correction recorded: {self.session.corrections[-1][:50]}"

        if should_store:
            print(f"[CompactionGuard] Auto-storing session ({reason})")
            success = self.session.store_to_thermal()
            if success:
                self.last_auto_store = now
            return success

        return False


# Convenience functions for quick integration

def start_session(session_id: str = None) -> SessionMemory:
    """Start a new session with compaction awareness."""
    session = SessionMemory(session_id)
    print(f"[CompactionAwareness] Session {session.session_id} started")
    return session


def recall_for_file(filepath: str) -> List[Dict]:
    """Quick recall: what do we know about this file?"""
    return FileMemory.recall_file_context(filepath)


def recall_for_topic(topic: str) -> List[Dict]:
    """Quick recall: what do we know about this topic?"""
    return FileMemory.recall_topic_context(topic)


if __name__ == "__main__":
    # Demo / test
    print("=== Compaction Awareness Demo ===\n")

    # Start session
    session = start_session("demo-session")

    # Record some events
    session.record_decision("Adopted NotNative compaction pattern")
    session.record_file_touch("/ganuda/longhouse/thermal_mcp_server.py", "created")
    session.record_correction("RTX 5070 is in bluefin, NOT redfin")
    session.record_discovery("Shanz's NotNativeCoord is prompt-only, zero custom code")

    # Generate summary
    print(session.generate_session_summary())

    # Test file recall
    print("\n=== File Recall: thermal_mcp_server.py ===")
    results = recall_for_file("thermal_mcp_server.py")
    for r in results[:3]:
        print(f"  #{r.get('id', '?')}: {str(r.get('content', ''))[:100]}")

    # Test topic recall
    print("\n=== Topic Recall: Longhouse ===")
    results = recall_for_topic("Longhouse")
    for r in results[:3]:
        print(f"  #{r.get('id', '?')}: {str(r.get('content', ''))[:100]}")

    print("\nFor Seven Generations.")
