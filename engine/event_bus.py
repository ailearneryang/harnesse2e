"""Runtime event bus for realtime UI and durable event history."""

from __future__ import annotations

import json
import os
import threading
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List, Optional


class EventBus:
    """Append-only event store with in-memory replay for SSE clients."""

    def __init__(self, data_dir: str, max_events: int = 1000):
        self.data_dir = data_dir
        self.event_file = os.path.join(data_dir, "runtime_events.jsonl")
        self.max_events = max_events
        self._lock = threading.Lock()
        self._seq = 0
        self._events: Deque[Dict] = deque(maxlen=max_events)

        os.makedirs(data_dir, exist_ok=True)
        self._load_existing_events()

    def _load_existing_events(self) -> None:
        if not os.path.exists(self.event_file):
            return

        with open(self.event_file, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._seq = max(self._seq, int(event.get("seq", 0)))
                self._events.append(event)

    def publish(
        self,
        event_type: str,
        message: str,
        source: str = "system",
        data: Optional[Dict] = None,
        task_id: Optional[str] = None,
        stage: Optional[str] = None,
        level: str = "info",
    ) -> Dict:
        with self._lock:
            self._seq += 1
            event = {
                "seq": self._seq,
                "timestamp": datetime.now().isoformat(),
                "type": event_type,
                "source": source,
                "message": message,
                "task_id": task_id,
                "stage": stage,
                "level": level,
                "data": data or {},
            }
            self._events.append(event)
            with open(self.event_file, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            return event

    def latest(self, limit: int = 200) -> List[Dict]:
        with self._lock:
            return list(self._events)[-limit:]

    def since(self, seq: int) -> List[Dict]:
        with self._lock:
            return [event for event in self._events if int(event.get("seq", 0)) > seq]

    @property
    def current_seq(self) -> int:
        with self._lock:
            return self._seq