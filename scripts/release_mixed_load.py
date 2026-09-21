"""Bounded, tenant-isolated pre-release mixed-load probe.

Creates disposable organizations and records through public APIs, then measures a
mixed read/write/WebSocket workload. It never targets pre-existing business rows.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import uuid
from collections import Counter
from typing import Any

import httpx
import psutil
import websockets


async def checked(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    return response.json()["data"]


async def provision(client: httpx.AsyncClient, api: str, index: int) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:12]
    password = f"Load{suffix}!Aa9"
    session = await checked(
        await client.post(
            f"{api}/auth/register",
            json={
                "organization_name": f"Load Gate {index} {suffix}",
                "organization_slug": f"load-gate-{index}-{suffix}",
                "workspace_name": "Load Gate",
                "email": f"admin.{suffix}@load-gate.example",
                "username": f"load.admin.{suffix}",
                "first_name": "Load",
                "last_name": f"User{index}",
                "password": password,
            },
        )
    )
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    workspace = (await checked(await client.get(f"{api}/workspaces", headers=headers)))[0]
    conversation = await checked(
        await client.post(
            f"{api}/conversations",
            headers=headers,
            json={
                "workspace_id": workspace["id"],
                "type": "workspace",
                "name": f"Load gate {suffix}",
            },
        )
    )
    return {
        "token": session["access_token"],
        "user_id": session["user"]["id"],
        "conversation_id": conversation["id"],
        "suffix": suffix,
    }


async def websocket_activity(api: str, identity: dict[str, str], duration: float) -> int:
    url = (
        api.replace("http://", "ws://").replace("https://", "wss://")
        + f"/chat/ws/{identity['conversation_id']}?token={identity['token']}"
    )
    messages = 0
    async with websockets.connect(url, open_timeout=10) as socket:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            await socket.send(json.dumps({"type": "typing", "is_typing": True}))
            messages += 1
            await asyncio.sleep(1)
    return messages


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8001/api/v1")
    parser.add_argument("--users", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--duration", type=int, default=30)
    args = parser.parse_args()
    started = time.monotonic()
    latencies: list[float] = []
    statuses: Counter[str] = Counter()
    process = psutil.Process()
    cpu_before = psutil.cpu_percent(interval=0.2)
    memory_before = process.memory_info().rss
    limits = httpx.Limits(max_connections=args.concurrency * 2)
    async with httpx.AsyncClient(timeout=20, limits=limits) as client:
        identities = await asyncio.gather(
            *(provision(client, args.api, index) for index in range(args.users))
        )
        operations = [
            ("dashboard", "GET", "/dashboard"),
            ("tasks_page", "GET", "/tasks?page=1&page_size=25"),
            ("projects_page", "GET", "/projects?page=1&page_size=25"),
            ("reports", "GET", "/reports?page=1&page_size=25"),
            ("finance", "GET", "/finance/accounts"),
            ("vouchers", "GET", "/vouchers?page=1&page_size=25"),
        ]
        deadline = time.monotonic() + args.duration
        sequence = 0
        lock = asyncio.Lock()

        async def worker(worker_id: int) -> None:
            nonlocal sequence
            identity = identities[worker_id % len(identities)]
            headers = {"Authorization": f"Bearer {identity['token']}"}
            while time.monotonic() < deadline:
                async with lock:
                    sequence += 1
                    current = sequence
                if current % 10 == 0:
                    name, method, path = "task_write", "POST", "/tasks"
                    body: dict[str, Any] | None = {
                        "title": f"Load task {identity['suffix']} {current}",
                        "priority": "normal",
                    }
                elif current % 17 == 0:
                    name, method, path = "project_write", "POST", "/projects"
                    today = time.strftime("%Y-%m-%d")
                    body = {
                        "name": f"Load project {identity['suffix']} {current}",
                        "project_manager_id": identity["user_id"],
                        "member_ids": [],
                        "start_date": today,
                        "target_end_date": today,
                    }
                else:
                    name, method, path = operations[current % len(operations)]
                    body = None
                before = time.perf_counter()
                response = await client.request(
                    method, f"{args.api}{path}", headers=headers, json=body
                )
                latencies.append((time.perf_counter() - before) * 1000)
                statuses[f"{name}:{response.status_code}"] += 1

        websocket_tasks = [
            websocket_activity(args.api, identity, float(args.duration))
            for identity in identities[: min(4, len(identities))]
        ]
        results = await asyncio.gather(
            *(worker(index) for index in range(args.concurrency)), *websocket_tasks
        )
    elapsed = time.monotonic() - started
    ordered = sorted(latencies)

    def percentile(value: float) -> float:
        if not ordered:
            return 0.0
        return ordered[min(len(ordered) - 1, int(len(ordered) * value))]

    failures = sum(
        count for key, count in statuses.items() if not key.rsplit(":", 1)[1].startswith("2")
    )
    output = {
        "environment": "isolated local PostgreSQL/Redis/API; disposable load-gate tenants",
        "users": args.users,
        "concurrency": args.concurrency,
        "duration_seconds": args.duration,
        "elapsed_seconds": round(elapsed, 3),
        "requests": len(latencies),
        "failures": failures,
        "error_rate_percent": round((failures / max(1, len(latencies))) * 100, 3),
        "latency_ms": {
            "p50": round(percentile(0.50), 2),
            "p95": round(percentile(0.95), 2),
            "p99": round(percentile(0.99), 2),
            "max": round(max(ordered, default=0.0), 2),
            "mean": round(statistics.fmean(ordered), 2) if ordered else 0.0,
        },
        "websocket_connections": len(websocket_tasks),
        "websocket_messages": sum(value for value in results[-len(websocket_tasks) :]),
        "status_counts": dict(sorted(statuses.items())),
        "resource": {
            "client_cpu_percent_before": cpu_before,
            "client_cpu_percent_after": psutil.cpu_percent(interval=0.2),
            "client_rss_before_bytes": memory_before,
            "client_rss_after_bytes": process.memory_info().rss,
        },
    }
    sys.stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
