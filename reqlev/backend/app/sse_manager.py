"""ReqLev – SSE Connection Manager

Manages Server-Sent Events connections grouped by project_id.
When any change occurs on a project, broadcast() pushes an event to all
active viewers of that project — delivering instant live updates without
WebSocket complexity.

Architecture
------------
* Each SSE connection owns a private asyncio.Queue.
* The generator reads from the queue and yields SSE-formatted strings.
* Any write operation (router or service) calls broadcast() to fan-out
  the event to every active queue for the target project.
* A 30-second heartbeat keeps proxies and firewalls from closing idle
  connections.
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import AsyncGenerator, Dict, List

logger = logging.getLogger(__name__)

# Maximum seconds to wait before sending a heartbeat comment.
HEARTBEAT_INTERVAL = 30


class SSEManager:
    def __init__(self) -> None:
        # project_id → list of asyncio.Queue instances (one per active connection)
        self._queues: Dict[int, List[asyncio.Queue]] = defaultdict(list)

    # ── Connection lifecycle ──────────────────────────────────────────────

    def connect(self, project_id: int) -> asyncio.Queue:
        """Register a new SSE connection for a project. Returns its queue."""
        q: asyncio.Queue = asyncio.Queue()
        self._queues[project_id].append(q)
        logger.debug("SSE connect: project=%d  active=%d",
                     project_id, len(self._queues[project_id]))
        return q

    def disconnect(self, project_id: int, queue: asyncio.Queue) -> None:
        """Remove a disconnected queue. Cleans up empty project entries."""
        try:
            self._queues[project_id].remove(queue)
        except ValueError:
            pass  # already removed
        if not self._queues[project_id]:
            del self._queues[project_id]
        logger.debug("SSE disconnect: project=%d", project_id)

    # ── Broadcasting ──────────────────────────────────────────────────────

    async def broadcast(
        self, project_id: int, event_type: str, data: dict
    ) -> None:
        """Fan-out an event to every SSE listener on *project_id*."""
        payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        queues = list(self._queues.get(project_id, []))
        for q in queues:
            await q.put(payload)
        if queues:
            logger.debug("SSE broadcast: project=%d  event=%s  listeners=%d",
                         project_id, event_type, len(queues))

    # ── Streaming generator ───────────────────────────────────────────────

    async def stream(
        self, project_id: int, queue: asyncio.Queue
    ) -> AsyncGenerator[str, None]:
        """Async generator that yields SSE-formatted strings.

        Usage inside a FastAPI route::

            async def event_source(request: Request, ...):
                q = sse_manager.connect(project_id)
                return StreamingResponse(
                    sse_manager.stream(project_id, q),
                    media_type="text/event-stream"
                )
        """
        try:
            # Send an initial "connected" event so the client knows it's live.
            yield (
                f"event: connected\n"
                f"data: {json.dumps({'project_id': project_id})}\n\n"
            )

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                    yield event
                except asyncio.TimeoutError:
                    # Heartbeat: SSE comment keeps the connection alive.
                    yield ": heartbeat\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            self.disconnect(project_id, queue)


# Singleton shared across the entire FastAPI process.
sse_manager = SSEManager()
