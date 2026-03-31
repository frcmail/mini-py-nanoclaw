from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ASSISTANT_NAME, DATA_DIR, STORE_DIR
from .group_folder import is_valid_group_folder
from .types import (
    AdditionalMount,
    ContainerConfig,
    NewMessage,
    RegisteredGroup,
    ScheduledTask,
    TaskRunLog,
)

_TASK_UPDATE_COLUMNS = frozenset({
    "group_folder", "chat_jid", "prompt", "schedule_type", "schedule_value",
    "context_mode", "next_run", "last_run", "last_result", "status", "created_at",
})


class NanoClawDB:
    def __init__(self, db_path: Path | None = None) -> None:
        path = db_path or (STORE_DIR / "messages.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._create_schema()

    @classmethod
    def in_memory(cls) -> NanoClawDB:
        obj = cls.__new__(cls)
        obj._conn = sqlite3.connect(":memory:")
        obj._conn.row_factory = sqlite3.Row
        obj._create_schema()
        return obj

    def close(self) -> None:
        self._conn.close()

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chats (
              jid TEXT PRIMARY KEY,
              name TEXT,
              last_message_time TEXT,
              channel TEXT,
              is_group INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS messages (
              id TEXT,
              chat_jid TEXT,
              sender TEXT,
              sender_name TEXT,
              content TEXT,
              timestamp TEXT,
              is_from_me INTEGER,
              is_bot_message INTEGER DEFAULT 0,
              PRIMARY KEY (id, chat_jid)
            );
            CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp);

            CREATE TABLE IF NOT EXISTS scheduled_tasks (
              id TEXT PRIMARY KEY,
              group_folder TEXT NOT NULL,
              chat_jid TEXT NOT NULL,
              prompt TEXT NOT NULL,
              schedule_type TEXT NOT NULL,
              schedule_value TEXT NOT NULL,
              context_mode TEXT DEFAULT 'isolated',
              next_run TEXT,
              last_run TEXT,
              last_result TEXT,
              status TEXT DEFAULT 'active',
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_next_run ON scheduled_tasks(next_run);
            CREATE INDEX IF NOT EXISTS idx_status ON scheduled_tasks(status);

            CREATE TABLE IF NOT EXISTS task_run_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              task_id TEXT NOT NULL,
              run_at TEXT NOT NULL,
              duration_ms INTEGER NOT NULL,
              status TEXT NOT NULL,
              result TEXT,
              error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_task_run_logs ON task_run_logs(task_id, run_at);

            CREATE TABLE IF NOT EXISTS router_state (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
              group_folder TEXT PRIMARY KEY,
              session_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS registered_groups (
              jid TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              folder TEXT NOT NULL UNIQUE,
              trigger_pattern TEXT NOT NULL,
              added_at TEXT NOT NULL,
              container_config TEXT,
              requires_trigger INTEGER DEFAULT 1,
              is_main INTEGER DEFAULT 0
            );
            """
        )
        self._conn.commit()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def store_chat_metadata(
        self,
        chat_jid: str,
        timestamp: str,
        name: str | None = None,
        channel: str | None = None,
        is_group: bool | None = None,
    ) -> None:
        group = None if is_group is None else int(is_group)
        visible_name = name or chat_jid
        self._conn.execute(
            """
            INSERT INTO chats (jid, name, last_message_time, channel, is_group)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(jid) DO UPDATE SET
              name = COALESCE(excluded.name, chats.name),
              last_message_time = MAX(chats.last_message_time, excluded.last_message_time),
              channel = COALESCE(excluded.channel, chats.channel),
              is_group = COALESCE(excluded.is_group, chats.is_group)
            """,
            (chat_jid, visible_name, timestamp, channel, group),
        )
        self._conn.commit()

    def get_all_chats(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT jid, name, last_message_time, channel, is_group FROM chats ORDER BY last_message_time DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def set_last_group_sync(self) -> None:
        self.store_chat_metadata("__group_sync__", self._now_iso(), "__group_sync__")

    def get_last_group_sync(self) -> str | None:
        row = self._conn.execute(
            "SELECT last_message_time FROM chats WHERE jid = '__group_sync__'"
        ).fetchone()
        return None if row is None else str(row["last_message_time"])

    def store_message(self, msg: NewMessage) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO messages
            (id, chat_jid, sender, sender_name, content, timestamp, is_from_me, is_bot_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg.id,
                msg.chat_jid,
                msg.sender,
                msg.sender_name,
                msg.content,
                msg.timestamp,
                int(msg.is_from_me),
                int(msg.is_bot_message),
            ),
        )
        self._conn.commit()

    def get_messages_since(
        self, chat_jid: str, since_timestamp: str, bot_prefix: str, limit: int = 200
    ) -> list[NewMessage]:
        rows = self._conn.execute(
            """
            SELECT * FROM (
              SELECT id, chat_jid, sender, sender_name, content, timestamp, is_from_me, is_bot_message
              FROM messages
              WHERE chat_jid = ? AND timestamp > ?
                AND is_bot_message = 0 AND content NOT LIKE ?
                AND content != '' AND content IS NOT NULL
              ORDER BY timestamp DESC
              LIMIT ?
            ) ORDER BY timestamp
            """,
            (chat_jid, since_timestamp, f"{bot_prefix}:%", limit),
        ).fetchall()
        return [
            NewMessage(
                id=str(row["id"]),
                chat_jid=str(row["chat_jid"]),
                sender=str(row["sender"]),
                sender_name=str(row["sender_name"]),
                content=str(row["content"]),
                timestamp=str(row["timestamp"]),
                is_from_me=bool(row["is_from_me"]),
                is_bot_message=bool(row["is_bot_message"]),
            )
            for row in rows
        ]

    def has_messages_since(self, chat_jid: str, since_timestamp: str, bot_prefix: str) -> bool:
        row = self._conn.execute(
            """
            SELECT 1
            FROM messages
            WHERE chat_jid = ? AND timestamp > ?
              AND is_bot_message = 0 AND content NOT LIKE ?
              AND content != '' AND content IS NOT NULL
            LIMIT 1
            """,
            (chat_jid, since_timestamp, f"{bot_prefix}:%"),
        ).fetchone()
        return row is not None

    def get_new_messages(
        self, jids: list[str], last_timestamp: str, bot_prefix: str, limit: int = 200
    ) -> tuple[list[NewMessage], str]:
        if not jids:
            return [], last_timestamp
        placeholders = ",".join(["?"] * len(jids))
        rows = self._conn.execute(
            f"""
            SELECT * FROM (
              SELECT id, chat_jid, sender, sender_name, content, timestamp, is_from_me, is_bot_message
              FROM messages
              WHERE timestamp > ? AND chat_jid IN ({placeholders})
                AND is_bot_message = 0 AND content NOT LIKE ?
                AND content != '' AND content IS NOT NULL
              ORDER BY timestamp DESC
              LIMIT ?
            ) ORDER BY timestamp
            """,
            (last_timestamp, *jids, f"{bot_prefix}:%", limit),
        ).fetchall()
        messages = [
            NewMessage(
                id=str(row["id"]),
                chat_jid=str(row["chat_jid"]),
                sender=str(row["sender"]),
                sender_name=str(row["sender_name"]),
                content=str(row["content"]),
                timestamp=str(row["timestamp"]),
                is_from_me=bool(row["is_from_me"]),
                is_bot_message=bool(row["is_bot_message"]),
            )
            for row in rows
        ]
        new_ts = last_timestamp
        for msg in messages:
            if msg.timestamp > new_ts:
                new_ts = msg.timestamp
        return messages, new_ts

    def create_task(self, task: ScheduledTask) -> None:
        self._conn.execute(
            """
            INSERT INTO scheduled_tasks
            (id, group_folder, chat_jid, prompt, schedule_type, schedule_value, context_mode, next_run, last_run, last_result, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.group_folder,
                task.chat_jid,
                task.prompt,
                task.schedule_type,
                task.schedule_value,
                task.context_mode,
                task.next_run,
                task.last_run,
                task.last_result,
                task.status,
                task.created_at,
            ),
        )
        self._conn.commit()

    def get_task_by_id(self, task_id: str) -> ScheduledTask | None:
        row = self._conn.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()
        return None if row is None else self._row_to_task(row)

    def get_all_tasks(self) -> list[ScheduledTask]:
        rows = self._conn.execute("SELECT * FROM scheduled_tasks ORDER BY created_at DESC").fetchall()
        return [self._row_to_task(row) for row in rows]

    def get_due_tasks(self) -> list[ScheduledTask]:
        now = self._now_iso()
        rows = self._conn.execute(
            """
            SELECT * FROM scheduled_tasks
            WHERE status = 'active' AND next_run IS NOT NULL AND next_run <= ?
            ORDER BY next_run
            """,
            (now,),
        ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def update_task(self, task_id: str, **updates: Any) -> None:
        if not updates:
            return
        invalid_cols = set(updates.keys()) - _TASK_UPDATE_COLUMNS
        if invalid_cols:
            raise ValueError(f"Invalid column(s) for task update: {invalid_cols}")
        assignments = []
        values: list[Any] = []
        for key, value in updates.items():
            assignments.append(f"{key} = ?")
            values.append(value)
        values.append(task_id)
        self._conn.execute(
            f"UPDATE scheduled_tasks SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
        self._conn.commit()

    def update_task_after_run(self, task_id: str, next_run: str | None, last_result: str) -> None:
        now = self._now_iso()
        self._conn.execute(
            """
            UPDATE scheduled_tasks
            SET next_run = ?, last_run = ?, last_result = ?,
                status = CASE WHEN ? IS NULL THEN 'completed' ELSE status END
            WHERE id = ?
            """,
            (next_run, now, last_result, next_run, task_id),
        )
        self._conn.commit()

    def delete_task(self, task_id: str) -> None:
        self._conn.execute("DELETE FROM task_run_logs WHERE task_id = ?", (task_id,))
        self._conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
        self._conn.commit()

    def log_task_run(self, log: TaskRunLog) -> None:
        self._conn.execute(
            """
            INSERT INTO task_run_logs (task_id, run_at, duration_ms, status, result, error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (log.task_id, log.run_at, log.duration_ms, log.status, log.result, log.error),
        )
        self._conn.commit()

    def get_router_state(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM router_state WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def set_router_state(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO router_state (key, value) VALUES (?, ?)", (key, value)
        )
        self._conn.commit()

    def get_session(self, group_folder: str) -> str | None:
        row = self._conn.execute(
            "SELECT session_id FROM sessions WHERE group_folder = ?", (group_folder,)
        ).fetchone()
        return None if row is None else str(row["session_id"])

    def set_session(self, group_folder: str, session_id: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO sessions (group_folder, session_id) VALUES (?, ?)",
            (group_folder, session_id),
        )
        self._conn.commit()

    def get_all_sessions(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT group_folder, session_id FROM sessions").fetchall()
        return {str(row["group_folder"]): str(row["session_id"]) for row in rows}

    def get_registered_group(self, jid: str) -> RegisteredGroup | None:
        row = self._conn.execute("SELECT * FROM registered_groups WHERE jid = ?", (jid,)).fetchone()
        if row is None:
            return None
        folder = str(row["folder"])
        if not is_valid_group_folder(folder):
            return None
        return self._row_to_registered_group(row)

    def set_registered_group(self, jid: str, group: RegisteredGroup) -> None:
        if not is_valid_group_folder(group.folder):
            raise ValueError(f'Invalid group folder "{group.folder}" for JID {jid}')

        config_json = None
        if group.container_config is not None:
            config_json = json.dumps(asdict(group.container_config))

        self._conn.execute(
            """
            INSERT OR REPLACE INTO registered_groups
            (jid, name, folder, trigger_pattern, added_at, container_config, requires_trigger, is_main)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                jid,
                group.name,
                group.folder,
                group.trigger,
                group.added_at,
                config_json,
                1 if group.requires_trigger is not False else 0,
                1 if group.is_main else 0,
            ),
        )
        self._conn.commit()

    def get_all_registered_groups(self) -> dict[str, RegisteredGroup]:
        rows = self._conn.execute("SELECT * FROM registered_groups").fetchall()
        result: dict[str, RegisteredGroup] = {}
        for row in rows:
            folder = str(row["folder"])
            if not is_valid_group_folder(folder):
                continue
            result[str(row["jid"])] = self._row_to_registered_group(row)
        return result

    def migrate_json_state(self) -> None:
        def migrate_file(filename: str) -> Any | None:
            file_path = DATA_DIR / filename
            if not file_path.exists():
                return None
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
            file_path.rename(file_path.with_suffix(file_path.suffix + ".migrated"))
            return data

        router_state = migrate_file("router_state.json")
        if isinstance(router_state, dict):
            if isinstance(router_state.get("last_timestamp"), str):
                self.set_router_state("last_timestamp", router_state["last_timestamp"])
            if isinstance(router_state.get("last_agent_timestamp"), dict):
                self.set_router_state(
                    "last_agent_timestamp", json.dumps(router_state["last_agent_timestamp"])
                )

        sessions = migrate_file("sessions.json")
        if isinstance(sessions, dict):
            for folder, session_id in sessions.items():
                if isinstance(folder, str) and isinstance(session_id, str):
                    self.set_session(folder, session_id)

        groups = migrate_file("registered_groups.json")
        if isinstance(groups, dict):
            for jid, raw in groups.items():
                if not isinstance(jid, str) or not isinstance(raw, dict):
                    continue
                folder = raw.get("folder")
                if not isinstance(folder, str) or not is_valid_group_folder(folder):
                    continue
                group = RegisteredGroup(
                    name=str(raw.get("name", jid)),
                    folder=folder,
                    trigger=str(raw.get("trigger", f"@{ASSISTANT_NAME}")),
                    added_at=str(raw.get("added_at", self._now_iso())),
                    requires_trigger=raw.get("requires_trigger"),
                    is_main=raw.get("is_main"),
                )
                self.set_registered_group(jid, group)

    def _row_to_task(self, row: sqlite3.Row) -> ScheduledTask:
        return ScheduledTask(
            id=str(row["id"]),
            group_folder=str(row["group_folder"]),
            chat_jid=str(row["chat_jid"]),
            prompt=str(row["prompt"]),
            schedule_type=str(row["schedule_type"]),
            schedule_value=str(row["schedule_value"]),
            context_mode=str(row["context_mode"]),
            next_run=None if row["next_run"] is None else str(row["next_run"]),
            last_run=None if row["last_run"] is None else str(row["last_run"]),
            last_result=None if row["last_result"] is None else str(row["last_result"]),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
        )

    def _row_to_registered_group(self, row: sqlite3.Row) -> RegisteredGroup:
        config = None
        raw_cfg = row["container_config"]
        if raw_cfg:
            try:
                cfg = json.loads(str(raw_cfg))
                raw_mounts = cfg.get("additionalMounts") or cfg.get("additional_mounts") or []
                mounts: list[AdditionalMount] = []
                if isinstance(raw_mounts, list):
                    for mount in raw_mounts:
                        if not isinstance(mount, dict):
                            continue
                        host_path = mount.get("hostPath") or mount.get("host_path")
                        if not isinstance(host_path, str):
                            continue
                        mounts.append(
                            AdditionalMount(
                                host_path=host_path,
                                container_path=mount.get("containerPath") or mount.get("container_path"),
                                readonly=bool(mount.get("readonly", True)),
                            )
                        )
                config = ContainerConfig(
                    timeout=cfg.get("timeout"),
                    additional_mounts=mounts or None,
                )
            except json.JSONDecodeError:
                config = None

        return RegisteredGroup(
            name=str(row["name"]),
            folder=str(row["folder"]),
            trigger=str(row["trigger_pattern"]),
            added_at=str(row["added_at"]),
            container_config=config,
            requires_trigger=None if row["requires_trigger"] is None else bool(row["requires_trigger"]),
            is_main=bool(row["is_main"]),
        )
