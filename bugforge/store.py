"""Session-local SQLite ticket database and action audit log."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher
from .models import BugReport


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def similarity(a: str, b: str) -> float:
    a, b = a.casefold().strip(), b.casefold().strip()
    seq = SequenceMatcher(None, a, b).ratio()
    sa = set(a.split())
    sb = set(b.split())
    overlap = len(sa & sb) / len(sa | sb) if sa | sb else 0
    return max(seq, overlap)


class TicketStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / 'tickets.sqlite3'
        self.reports = self.root / 'reports'
        self.reports.mkdir(exist_ok=True)
        self._init()

    def _connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self):
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS tickets (
                  id TEXT PRIMARY KEY,
                  title TEXT NOT NULL,
                  severity TEXT NOT NULL,
                  category TEXT NOT NULL,
                  project TEXT NOT NULL,
                  report_json TEXT NOT NULL,
                  report_file TEXT,
                  github_url TEXT,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT NOT NULL,
                  action TEXT NOT NULL,
                  status TEXT NOT NULL,
                  detail TEXT NOT NULL
                );
            ''')

    def log(self, action: str, status: str, detail: str):
        with self._connect() as conn:
            conn.execute('INSERT INTO audit(created_at, action, status, detail) VALUES (?, ?, ?, ?)',
                         (utc_now(), action[:80], status[:25], detail[:1500]))

    def create_ticket(self, report: BugReport, project: str, report_file: str | None = None) -> str:
        identifier = uuid.uuid4().hex[:10].upper()
        with self._connect() as conn:
            conn.execute('''INSERT INTO tickets(id, title, severity, category, project, report_json,
                          report_file, created_at) VALUES (?,?,?,?,?,?,?,?)''',
                         (identifier, report.title, report.severity, report.category, project,
                          report.model_dump_json(), report_file, utc_now()))
        return identifier

    def update_ticket(self, ticket_id: str, **fields):
        allowed = {'report_file', 'github_url'}
        if not fields or not set(fields).issubset(allowed):
            raise ValueError('Invalid fields to update.')
        changes = ', '.join(f'{key} = ?' for key in fields)
        with self._connect() as conn:
            conn.execute(f'UPDATE tickets SET {changes} WHERE id = ?', (*fields.values(), ticket_id))

    def list_tickets(self):
        with self._connect() as conn:
            return [dict(row) for row in conn.execute('SELECT * FROM tickets ORDER BY created_at DESC, rowid DESC')]

    def list_audit(self, limit: int = 100):
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(
                'SELECT * FROM audit ORDER BY id DESC LIMIT ?', (limit,))]

    def find_similar(self, title: str, threshold: float = 0.63):
        hits = []
        for row in self.list_tickets():
            score = similarity(title, row['title'])
            if score >= threshold:
                hits.append({'title': row['title'], 'score': score, 'source': 'Local ticket',
                             'url': row['github_url'] or '', 'id': row['id']})
        return sorted(hits, key=lambda x: x['score'], reverse=True)[:5]

    def save_markdown(self, contents: str) -> str:
        # File names are generated internally, never from AI output.
        name = f'bug-report-{uuid.uuid4().hex[:12]}.md'
        candidate = (self.reports / name).resolve()
        if not candidate.is_relative_to(self.reports.resolve()):
            raise ValueError('Invalid report path.')
        candidate.write_text(contents, encoding='utf-8')
        return name
