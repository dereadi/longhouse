#!/usr/bin/env python3
"""
Longhouse Thermal Memory MCP Server — Snap-On Interface

A read-only (by default) MCP server that exposes the thermal memory archive
to any Claude Code terminal, MCP client, or external system.

Snap-on architecture:
- The Python internals remain unchanged
- This is a WINDOW into Postgres, not a new storage layer
- Remove this file, nothing breaks
- Write access requires governance approval (config toggle)

Concern → Feature:
- Coyote (single point of failure): stateless — Postgres is source of truth
- Turtle (sovereignty): read-only by default, write requires config toggle
- Spider (tight coupling): optional snap-on, zero coupling
- Coyote (97K scale): pagination + query limits on MCP, Python has no limits

Port: 9500 (matches NotNativeMemory convention)
Protocol: MCP over stdio or HTTP

For Seven Generations.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Optional
from datetime import datetime

# MCP SDK
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

import asyncpg

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [ThermalMCP] %(message)s')
logger = logging.getLogger('thermal_mcp')

# Configuration
DB_HOST = os.environ.get('CHEROKEE_DB_HOST', '10.100.0.2')
DB_NAME = os.environ.get('CHEROKEE_DB_NAME', 'zammad_production')
DB_USER = os.environ.get('CHEROKEE_DB_USER', 'claude')
DB_PASS = os.environ.get('CHEROKEE_DB_PASS', '')

# Snap-on controls
MCP_WRITE_ENABLED = os.environ.get('THERMAL_MCP_WRITE', 'false').lower() == 'true'
MCP_MAX_RESULTS = int(os.environ.get('THERMAL_MCP_MAX_RESULTS', '50'))
MCP_PORT = int(os.environ.get('THERMAL_MCP_PORT', '9500'))


class ThermalMCPServer:
    """Snap-on MCP interface to thermal memory archive."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.server = Server("longhouse-thermal-memory")
        self._register_tools()

    def _register_tools(self):
        """Register MCP tools."""

        @self.server.list_tools()
        async def list_tools():
            tools = [
                Tool(
                    name="memory_search",
                    description="Search thermal memory by keyword or semantic query. Returns matching memories with temperature scores.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query — keywords or natural language question"
                            },
                            "limit": {
                                "type": "integer",
                                "description": f"Max results (default 10, max {MCP_MAX_RESULTS})",
                                "default": 10
                            },
                            "min_temperature": {
                                "type": "number",
                                "description": "Minimum temperature score (0-100). Higher = more important.",
                                "default": 0
                            },
                            "sacred_only": {
                                "type": "boolean",
                                "description": "Only return sacred (constitutionally important) memories",
                                "default": False
                            },
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="memory_recent",
                    description="Get the most recent thermal memories. Useful for context on what just happened.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Number of recent memories to return (default 10)",
                                "default": 10
                            },
                            "hours": {
                                "type": "number",
                                "description": "Only memories from the last N hours",
                                "default": 24
                            },
                        },
                    }
                ),
                Tool(
                    name="memory_stats",
                    description="Get thermal memory statistics — total count, sacred count, temperature distribution.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    }
                ),
            ]

            if MCP_WRITE_ENABLED:
                tools.append(Tool(
                    name="memory_store",
                    description="Store a new thermal memory. Requires THERMAL_MCP_WRITE=true.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Memory content to store"
                            },
                            "temperature": {
                                "type": "number",
                                "description": "Temperature score 0-100 (default 60)",
                                "default": 60
                            },
                            "sacred": {
                                "type": "boolean",
                                "description": "Mark as sacred (never decays)",
                                "default": False
                            },
                            "metadata": {
                                "type": "object",
                                "description": "Optional metadata dict",
                                "default": {}
                            },
                        },
                        "required": ["content"]
                    }
                ))

            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            if not self.pool:
                await self._connect()

            if name == "memory_search":
                return await self._search(arguments)
            elif name == "memory_recent":
                return await self._recent(arguments)
            elif name == "memory_stats":
                return await self._stats()
            elif name == "memory_store" and MCP_WRITE_ENABLED:
                return await self._store(arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def _connect(self):
        """Connect to PostgreSQL."""
        self.pool = await asyncpg.create_pool(
            host=DB_HOST, database=DB_NAME,
            user=DB_USER, password=DB_PASS,
            min_size=2, max_size=5
        )
        logger.info(f"Connected to {DB_HOST}/{DB_NAME}")

    async def _search(self, args: dict) -> list:
        """Search thermal memory by keyword."""
        query = args.get("query", "")
        limit = min(args.get("limit", 10), MCP_MAX_RESULTS)
        min_temp = args.get("min_temperature", 0)
        sacred_only = args.get("sacred_only", False)

        sql = """
            SELECT id, LEFT(original_content, 500) as content,
                   temperature_score, sacred_pattern, created_at,
                   memory_type, domain_tag
            FROM thermal_memory_archive
            WHERE original_content ILIKE $1
        """
        params = [f"%{query}%"]
        param_idx = 2

        if min_temp > 0:
            sql += f" AND temperature_score >= ${param_idx}"
            params.append(min_temp)
            param_idx += 1

        if sacred_only:
            sql += " AND sacred_pattern = true"

        sql += f" ORDER BY temperature_score DESC, created_at DESC LIMIT ${param_idx}"
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "content": row["content"],
                "temperature": float(row["temperature_score"]) if row["temperature_score"] else 0,
                "sacred": row["sacred_pattern"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "type": row["memory_type"],
                "domain": row["domain_tag"],
            })

        return [TextContent(
            type="text",
            text=json.dumps({"query": query, "count": len(results), "results": results}, default=str, indent=2)
        )]

    async def _recent(self, args: dict) -> list:
        """Get recent thermal memories."""
        limit = min(args.get("limit", 10), MCP_MAX_RESULTS)
        hours = args.get("hours", 24)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, LEFT(original_content, 500) as content,
                       temperature_score, sacred_pattern, created_at,
                       memory_type, domain_tag
                FROM thermal_memory_archive
                WHERE created_at > NOW() - INTERVAL '1 hour' * $1
                ORDER BY created_at DESC
                LIMIT $2
            """, hours, limit)

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "content": row["content"],
                "temperature": float(row["temperature_score"]) if row["temperature_score"] else 0,
                "sacred": row["sacred_pattern"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "type": row["memory_type"],
                "domain": row["domain_tag"],
            })

        return [TextContent(
            type="text",
            text=json.dumps({"hours": hours, "count": len(results), "results": results}, default=str, indent=2)
        )]

    async def _stats(self) -> list:
        """Get thermal memory statistics."""
        async with self.pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM thermal_memory_archive")
            sacred = await conn.fetchval("SELECT COUNT(*) FROM thermal_memory_archive WHERE sacred_pattern = true")
            avg_temp = await conn.fetchval("SELECT AVG(temperature_score) FROM thermal_memory_archive")
            recent_1h = await conn.fetchval(
                "SELECT COUNT(*) FROM thermal_memory_archive WHERE created_at > NOW() - INTERVAL '1 hour'")

            # Temperature distribution
            dist = await conn.fetch("""
                SELECT
                    CASE
                        WHEN temperature_score >= 90 THEN 'hot (90-100)'
                        WHEN temperature_score >= 60 THEN 'warm (60-89)'
                        WHEN temperature_score >= 30 THEN 'cool (30-59)'
                        ELSE 'cold (0-29)'
                    END as tier,
                    COUNT(*) as count
                FROM thermal_memory_archive
                GROUP BY tier
                ORDER BY tier
            """)

        stats = {
            "total_memories": total,
            "sacred_memories": sacred,
            "average_temperature": round(float(avg_temp), 2) if avg_temp else 0,
            "memories_last_hour": recent_1h,
            "write_enabled": MCP_WRITE_ENABLED,
            "max_results_per_query": MCP_MAX_RESULTS,
            "temperature_distribution": {row["tier"]: row["count"] for row in dist},
        }

        return [TextContent(
            type="text",
            text=json.dumps(stats, indent=2)
        )]

    async def _store(self, args: dict) -> list:
        """Store a new thermal memory (only if write enabled)."""
        if not MCP_WRITE_ENABLED:
            return [TextContent(type="text", text="Write access disabled. Set THERMAL_MCP_WRITE=true to enable.")]

        content = args.get("content", "")
        temperature = args.get("temperature", 60.0)
        sacred = args.get("sacred", False)
        metadata = args.get("metadata", {})

        if not content:
            return [TextContent(type="text", text="Error: content is required")]

        import hashlib
        memory_hash = hashlib.sha256(content.encode()).hexdigest()

        async with self.pool.acquire() as conn:
            result = await conn.fetchval("""
                INSERT INTO thermal_memory_archive (
                    memory_hash, original_content, temperature_score,
                    sacred_pattern, metadata, created_at, current_stage,
                    access_count, compression_ratio, phase_coherence,
                    phase_angle, freshness_score, context_version,
                    chunk_index, chunk_total, is_chunk, is_observed,
                    temporal_state, is_canonical
                ) VALUES (
                    $1, $2, $3, $4, $5, NOW(), 'FRESH',
                    0, 1.0, 0.5, 0.0, 1.0, 1,
                    0, 1, false, false, 'current', false
                ) RETURNING id
            """, memory_hash, content, temperature, sacred,
                json.dumps(metadata))

        logger.info(f"Stored memory #{result} (temp={temperature}, sacred={sacred})")

        return [TextContent(
            type="text",
            text=json.dumps({"stored": True, "id": result, "temperature": temperature, "sacred": sacred})
        )]

    async def run_stdio(self):
        """Run as stdio MCP server."""
        logger.info("Starting Longhouse Thermal MCP (stdio mode)")
        logger.info(f"Write enabled: {MCP_WRITE_ENABLED}")
        logger.info(f"Max results: {MCP_MAX_RESULTS}")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())

    async def run_http(self):
        """Run as HTTP MCP server."""
        try:
            from mcp.server.sse import SseServerTransport
            from starlette.applications import Starlette
            from starlette.routing import Route
            import uvicorn

            sse = SseServerTransport("/messages")

            async def handle_sse(request):
                async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                    await self.server.run(streams[0], streams[1], self.server.create_initialization_options())

            app = Starlette(routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=sse.handle_post_message, methods=["POST"]),
            ])

            logger.info(f"Starting Longhouse Thermal MCP (HTTP mode, port {MCP_PORT})")
            config = uvicorn.Config(app, host="0.0.0.0", port=MCP_PORT)
            server = uvicorn.Server(config)
            await server.serve()
        except ImportError:
            logger.error("HTTP mode requires: pip install starlette uvicorn mcp[sse]")
            logger.info("Falling back to stdio mode")
            await self.run_stdio()


# Also provide a simple REST API for non-MCP clients (snap-on #2)
def create_rest_app():
    """Create a FastAPI REST interface — another snap-on."""
    try:
        from fastapi import FastAPI, Query
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError:
        return None

    app = FastAPI(
        title="Longhouse Thermal Memory",
        description="REST snap-on for thermal memory archive",
        version="0.1.0"
    )
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    import psycopg2
    from psycopg2.extras import RealDictCursor

    def get_conn():
        return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)

    @app.get("/api/v1/memory/search")
    def search(q: str, limit: int = Query(10, le=MCP_MAX_RESULTS), min_temp: float = 0):
        conn = get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, LEFT(original_content, 500) as content,
                   temperature_score, sacred_pattern, created_at
            FROM thermal_memory_archive
            WHERE original_content ILIKE %s AND temperature_score >= %s
            ORDER BY temperature_score DESC, created_at DESC LIMIT %s
        """, (f"%{q}%", min_temp, limit))
        results = cur.fetchall()
        conn.close()
        return {"query": q, "count": len(results), "results": results}

    @app.get("/api/v1/memory/recent")
    def recent(limit: int = Query(10, le=MCP_MAX_RESULTS), hours: float = 24):
        conn = get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, LEFT(original_content, 500) as content,
                   temperature_score, sacred_pattern, created_at
            FROM thermal_memory_archive
            WHERE created_at > NOW() - INTERVAL '1 hour' * %s
            ORDER BY created_at DESC LIMIT %s
        """, (hours, limit))
        results = cur.fetchall()
        conn.close()
        return {"hours": hours, "count": len(results), "results": results}

    @app.get("/api/v1/memory/stats")
    def stats():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE sacred_pattern = true), AVG(temperature_score) FROM thermal_memory_archive")
        total, sacred, avg_temp = cur.fetchone()
        conn.close()
        return {
            "total": total, "sacred": sacred,
            "avg_temperature": round(float(avg_temp), 2) if avg_temp else 0,
            "write_enabled": MCP_WRITE_ENABLED,
        }

    @app.get("/health")
    def health():
        return {"status": "alive", "service": "longhouse-thermal-mcp"}

    return app


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Longhouse Thermal Memory MCP Server")
    parser.add_argument("--mode", choices=["stdio", "http", "rest"], default="stdio",
                        help="Server mode: stdio (MCP), http (MCP over SSE), rest (FastAPI)")
    parser.add_argument("--port", type=int, default=MCP_PORT, help="Port for HTTP/REST mode")
    args = parser.parse_args()

    if args.mode == "rest":
        app = create_rest_app()
        if app:
            import uvicorn
            uvicorn.run(app, host="0.0.0.0", port=args.port)
        else:
            print("REST mode requires: pip install fastapi uvicorn")
    elif args.mode == "http":
        server = ThermalMCPServer()
        asyncio.run(server.run_http())
    else:
        if not MCP_AVAILABLE:
            print("MCP mode requires: pip install mcp")
            print("Try --mode rest for FastAPI interface instead")
            sys.exit(1)
        server = ThermalMCPServer()
        asyncio.run(server.run_stdio())
