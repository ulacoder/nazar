import json
import sqlite3
from contextlib import closing
from pathlib import Path

class Store:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self._initialize()

    def connect(self):
        connection=sqlite3.connect(self.path,timeout=10)
        connection.row_factory=sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self):
        with closing(self.connect()) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT NOT NULL CHECK(mode IN ('LESSON','EXAM')),
                    started_at TEXT NOT NULL, ended_at TEXT,
                    track_count INTEGER NOT NULL DEFAULT 0,
                    source_type TEXT NOT NULL DEFAULT 'CAMERA', source_name TEXT,
                    summary_json TEXT NOT NULL DEFAULT '{}',
                    teacher TEXT, class_name TEXT, subject TEXT, notes TEXT,
                    timelapse_interval_s REAL, timelapse_fps REAL);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL REFERENCES sessions(id),
                    occurred_at TEXT NOT NULL, track_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL, confidence REAL, source_offset_s REAL,
                    duration_s REAL, review_priority TEXT, reason TEXT, evidence_start_s REAL, evidence_end_s REAL);
                CREATE INDEX IF NOT EXISTS events_session_idx ON events(session_id,id);
                CREATE INDEX IF NOT EXISTS events_type_idx ON events(event_type,occurred_at);
                CREATE TABLE IF NOT EXISTS timelapses (
                    session_id INTEGER PRIMARY KEY REFERENCES sessions(id),
                    path TEXT, frame_count INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT, ended_at TEXT,
                    file_size INTEGER NOT NULL DEFAULT 0,
                    available INTEGER NOT NULL DEFAULT 0, error TEXT);
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS visibility_samples (
                    session_id INTEGER NOT NULL REFERENCES sessions(id),
                    offset_s REAL NOT NULL, people_count INTEGER NOT NULL,
                    PRIMARY KEY(session_id,offset_s));
                CREATE TABLE IF NOT EXISTS session_tracks (
                    session_id INTEGER NOT NULL REFERENCES sessions(id),track_id INTEGER NOT NULL,
                    PRIMARY KEY(session_id,track_id));
                CREATE TABLE IF NOT EXISTS session_person_roles (
                    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    person_id INTEGER NOT NULL,
                    role TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK(role IN ('STUDENT','TEACHER','UNKNOWN')),
                    PRIMARY KEY(session_id,person_id));
            """)
            session_columns={row[1] for row in db.execute("PRAGMA table_info(sessions)")}
            event_columns={row[1] for row in db.execute("PRAGMA table_info(events)")}
            if "source_type" not in session_columns: db.execute("ALTER TABLE sessions ADD COLUMN source_type TEXT NOT NULL DEFAULT 'CAMERA'")
            if "source_name" not in session_columns: db.execute("ALTER TABLE sessions ADD COLUMN source_name TEXT")
            if "source_offset_s" not in event_columns: db.execute("ALTER TABLE events ADD COLUMN source_offset_s REAL")
            for column,kind in (("teacher","TEXT"),("class_name","TEXT"),("subject","TEXT"),("notes","TEXT"),
                ("timelapse_interval_s","REAL"),("timelapse_fps","REAL")):
                if column not in session_columns: db.execute(f"ALTER TABLE sessions ADD COLUMN {column} {kind}")
            if 'session_offset_s' not in event_columns:db.execute('ALTER TABLE events ADD COLUMN session_offset_s REAL')
            if 'source_video_path' not in session_columns:db.execute('ALTER TABLE sessions ADD COLUMN source_video_path TEXT')
            for column,kind in (("duration_s","REAL"),("review_priority","TEXT"),("reason","TEXT"),("evidence_start_s","REAL"),("evidence_end_s","REAL")):
                if column not in event_columns: db.execute(f'ALTER TABLE events ADD COLUMN {column} {kind}')
            track_columns={row[1] for row in db.execute('PRAGMA table_info(session_tracks)')}
            for name in ('first_seen_s','last_seen_s'):
                if name not in track_columns:db.execute(f'ALTER TABLE session_tracks ADD COLUMN {name} REAL')
            db.execute("PRAGMA user_version=4")
            db.commit()

    def set_person_role(self,session_id,person_id,role):
        if role not in {"STUDENT","TEACHER","UNKNOWN"}: raise ValueError("role must be STUDENT, TEACHER, or UNKNOWN")
        if not isinstance(person_id,int) or person_id < 1: raise ValueError("person_id must be positive")
        with closing(self.connect()) as db:
            if not db.execute("SELECT 1 FROM sessions WHERE id=?",(session_id,)).fetchone(): return None
            db.execute("INSERT INTO session_person_roles(session_id,person_id,role) VALUES (?,?,?) ON CONFLICT(session_id,person_id) DO UPDATE SET role=excluded.role",(session_id,person_id,role));db.commit()
        return {"session_id":session_id,"person_id":person_id,"role":role}

    def person_roles(self,session_id):
        with closing(self.connect()) as db:
            return {row["person_id"]:row["role"] for row in db.execute("SELECT person_id,role FROM session_person_roles WHERE session_id=?",(session_id,))}

    def start_session(self,mode,started_at,source_type="CAMERA",source_name=None,metadata=None,timelapse_interval_s=None,timelapse_fps=None):
        metadata=metadata or {}
        with closing(self.connect()) as db:
            cursor=db.execute("""INSERT INTO sessions(mode,started_at,source_type,source_name,teacher,class_name,subject,notes,
                timelapse_interval_s,timelapse_fps) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (mode,started_at,source_type,source_name,metadata.get("teacher"),metadata.get("class_name"),
                metadata.get("subject"),metadata.get("notes"),timelapse_interval_s,timelapse_fps))
            db.commit();return cursor.lastrowid

    def stop_session(self,session_id,ended_at,track_count,summary):
        with closing(self.connect()) as db:
            db.execute("UPDATE sessions SET ended_at=?,track_count=?,summary_json=? WHERE id=?",(ended_at,track_count,json.dumps(summary),session_id))
            db.commit()

    def add_events(self,session_id,events):
        if not events: return
        with closing(self.connect()) as db:
            self._insert_events(db,session_id,events)
            db.commit()

    def set_source_video(self,session_id,path):
        with closing(self.connect()) as db:
            db.execute('UPDATE sessions SET source_video_path=? WHERE id=?',(str(path),session_id));db.commit()

    @staticmethod
    def _insert_events(db,session_id,events):
        db.executemany('INSERT INTO events(session_id,occurred_at,track_id,event_type,confidence,source_offset_s,session_offset_s,duration_s,review_priority,reason,evidence_start_s,evidence_end_s) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            [(session_id,e['occurred_at'],e['track_id'],e['event_type'],e.get('confidence'),e.get('source_offset_s'),e.get('session_offset_s'),e.get('duration_s'),e.get('review_priority'),e.get('reason'),e.get('evidence_start_s'),e.get('evidence_end_s')) for e in events])

    def write_observation(self,session_id,events,spans,sample):
        with closing(self.connect()) as db:
            self._insert_events(db,session_id,events)
            db.executemany('''INSERT INTO session_tracks(session_id,track_id,first_seen_s,last_seen_s) VALUES (?,?,?,?)
                ON CONFLICT(session_id,track_id) DO UPDATE SET
                first_seen_s=CASE WHEN first_seen_s IS NULL THEN excluded.first_seen_s ELSE MIN(first_seen_s,excluded.first_seen_s) END,
                last_seen_s=CASE WHEN last_seen_s IS NULL THEN excluded.last_seen_s ELSE MAX(last_seen_s,excluded.last_seen_s) END''',
                [(session_id,tid,*span) for tid,span in spans.items()])
            if sample is not None:
                db.execute('INSERT OR REPLACE INTO visibility_samples VALUES (?,?,?)',(session_id,*sample))
            db.commit()

    def add_visibility_sample(self,session_id,offset_s,track_ids):
        with closing(self.connect()) as db:
            db.execute("INSERT OR REPLACE INTO visibility_samples(session_id,offset_s,people_count) VALUES (?,?,?)",
                (session_id,round(offset_s,2),len(track_ids)))
            db.executemany("INSERT OR IGNORE INTO session_tracks(session_id,track_id) VALUES (?,?)",
                [(session_id,track_id) for track_id in track_ids]);db.commit()

    def save_timelapse(self,session_id,record):
        with closing(self.connect()) as db:
            db.execute("INSERT OR REPLACE INTO timelapses(session_id,path,frame_count,started_at,ended_at,file_size,available,error) VALUES (?,?,?,?,?,?,?,?)",
                (session_id,record.get("path"),record.get("frame_count",0),record.get("started_at"),record.get("ended_at"),record.get("file_size",0),int(record.get("available",False)),record.get("error")))
            db.commit()

    def sessions(self):
        with closing(self.connect()) as db:
            rows=db.execute("""SELECT s.id,s.mode,s.started_at,s.ended_at,s.track_count,s.source_type,s.source_name,
                s.teacher,s.class_name,s.subject,s.notes,
                (SELECT COUNT(*) FROM events e WHERE e.session_id=s.id) AS event_count,
                COALESCE(t.available,0) AS timelapse_available
                FROM sessions s LEFT JOIN timelapses t ON t.session_id=s.id ORDER BY s.id DESC""")
            return [dict(row) for row in rows]

    def session(self,session_id):
        with closing(self.connect()) as db:
            row=db.execute("""SELECT s.*,(SELECT COUNT(*) FROM events e WHERE e.session_id=s.id) AS event_count,
                t.path AS timelapse_path,t.frame_count AS timelapse_frames,t.file_size AS timelapse_size,
                COALESCE(t.available,0) AS timelapse_available,t.error AS timelapse_error
                FROM sessions s LEFT JOIN timelapses t ON t.session_id=s.id WHERE s.id=?""",(session_id,)).fetchone()
            if not row: return None
            item=dict(row);item["summary"]=json.loads(item.pop("summary_json"));return item

    def events(self,session_id=None,mode=None,event_type=None,date=None,limit=500):
        query="SELECT e.*,s.mode,s.subject,s.class_name FROM events e JOIN sessions s ON s.id=e.session_id WHERE 1=1"
        params=[]
        for condition,value in (("e.session_id=?",session_id),("s.mode=?",mode),("e.event_type=?",event_type),("substr(e.occurred_at,1,10)=?",date)):
            if value is not None: query+=" AND "+condition;params.append(value)
        query+=" ORDER BY e.id DESC"
        if limit is not None: query+=" LIMIT ?";params.append(limit)
        with closing(self.connect()) as db: return [dict(row) for row in db.execute(query,params)]

    def session_analytics(self,session_id):
        from .analytics import session_analytics
        session=self.session(session_id)
        if not session:return None
        with closing(self.connect()) as db:return session_analytics(db,session)

    def event_page(self,session_id,track_id=None,event_type=None,offset=0,limit=100):
        from .analytics import event_page
        with closing(self.connect()) as db:return event_page(db,session_id,track_id,event_type,offset,limit)

    def person_detail(self,session_id,track_id):
        from .analytics import person_summaries,event_page
        with closing(self.connect()) as db:
            people=person_summaries(db,session_id,track_id)
            if not people:return None
            return {**people[0],'session_id':session_id,'events':event_page(db,session_id,track_id)}

    def delete_session(self,session_id):
        with closing(self.connect()) as db:
            row=db.execute('SELECT * FROM sessions WHERE id=?',(session_id,)).fetchone()
            if not row:return None
            item=dict(row)
            db.execute('DELETE FROM events WHERE session_id=?',(session_id,))
            db.execute('DELETE FROM visibility_samples WHERE session_id=?',(session_id,))
            db.execute('DELETE FROM session_tracks WHERE session_id=?',(session_id,))
            db.execute('DELETE FROM timelapses WHERE session_id=?',(session_id,))
            db.execute('DELETE FROM sessions WHERE id=?',(session_id,));db.commit()
            return item

    def save_settings(self,values):
        with closing(self.connect()) as db:
            db.executemany("INSERT OR REPLACE INTO app_settings(key,value_json) VALUES (?,?)",[(k,json.dumps(v)) for k,v in values.items()]);db.commit()

    def load_settings(self):
        with closing(self.connect()) as db:
            return {r["key"]:json.loads(r["value_json"]) for r in db.execute("SELECT key,value_json FROM app_settings")}
