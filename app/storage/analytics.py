"""Bounded session charts and paginated, session-local observation history."""
import math
from datetime import datetime,timezone

OFFSET="MAX(0,COALESCE(e.session_offset_s,e.source_offset_s,(julianday(e.occurred_at)-julianday(s.started_at))*86400))"

def bucket_seconds(duration):
    base=5 if duration<=120 else 15 if duration<=600 else 30 if duration<=1800 else 60
    return max(base,math.ceil(duration/90/base)*base)

def person_summaries(db,session_id,track_id=None):
    condition=' AND track_id=?' if track_id is not None else ''
    args=(session_id,track_id) if track_id is not None else (session_id,)
    people={r['track_id']:dict(r) for r in db.execute(
        "SELECT t.track_id,t.first_seen_s,t.last_seen_s,COALESCE(r.role,'UNKNOWN') AS role "
        "FROM session_tracks t LEFT JOIN session_person_roles r "
        "ON r.session_id=t.session_id AND r.person_id=t.track_id "
        'WHERE t.session_id=?'+condition,args)}
    for row in db.execute('SELECT track_id,event_type,COUNT(*) AS count FROM events WHERE session_id=?'+condition+' GROUP BY track_id,event_type',args):
        p=people.setdefault(row['track_id'],{'track_id':row['track_id'],'first_seen_s':None,'last_seen_s':None,'role':'UNKNOWN'})
        p.setdefault('event_counts',{})[row['event_type']]=row['count']
    for p in people.values():
        p.setdefault('event_counts',{});p['event_count']=sum(p['event_counts'].values())
        p['observed_span_s']=None if p['first_seen_s'] is None or p['last_seen_s'] is None else round(p['last_seen_s']-p['first_seen_s'],3)
    return sorted(people.values(),key=lambda p:p['track_id'])

def event_page(db,session_id,track_id=None,event_type=None,offset=0,limit=100):
    where='e.session_id=?';args=[session_id]
    if track_id is not None:where+=' AND e.track_id=?';args.append(track_id)
    if event_type:where+=' AND e.event_type=?';args.append(event_type)
    total=db.execute('SELECT COUNT(*) FROM events e WHERE '+where,args).fetchone()[0]
    rows=[dict(row) for row in db.execute(f'''SELECT e.id,e.session_id,e.track_id,e.event_type,e.confidence,
        e.occurred_at,e.source_offset_s,e.duration_s,e.review_priority,e.reason,e.evidence_start_s,e.evidence_end_s,ROUND({OFFSET},3) AS offset_s
        FROM events e JOIN sessions s ON s.id=e.session_id WHERE {where}
        ORDER BY offset_s,e.id LIMIT ? OFFSET ?''',[*args,limit,offset])]
    return {'items':rows,'total':total,'offset':offset,'limit':limit,
        'next_offset':offset+len(rows) if offset+len(rows)<total else None}

def session_analytics(db,session):
    sid=session['id']
    last=db.execute(f'SELECT MAX({OFFSET}) FROM events e JOIN sessions s ON s.id=e.session_id WHERE e.session_id=?',(sid,)).fetchone()[0]
    visible_last=db.execute('SELECT MAX(offset_s) FROM visibility_samples WHERE session_id=?',(sid,)).fetchone()[0]
    span_last=db.execute('SELECT MAX(last_seen_s) FROM session_tracks WHERE session_id=?',(sid,)).fetchone()[0]
    duration=max(last or 0,visible_last or 0,span_last or 0)
    if session['source_type']!='VIDEO':
        end=datetime.fromisoformat(session['ended_at']) if session['ended_at'] else datetime.now(timezone.utc)
        duration=max(duration,(end-datetime.fromisoformat(session['started_at'])).total_seconds())
    duration=max(0,duration);step=bucket_seconds(duration)
    counts={r['bucket']:r['count'] for r in db.execute(f'''SELECT CAST(({OFFSET})/? AS INTEGER) AS bucket,
        COUNT(*) AS count FROM events e JOIN sessions s ON s.id=e.session_id WHERE e.session_id=? GROUP BY bucket''',(step,sid))}
    visible={r['bucket']:dict(r) for r in db.execute('''SELECT CAST(offset_s/? AS INTEGER) AS bucket,
        AVG(people_count) AS people_count,COUNT(*) AS samples FROM visibility_samples WHERE session_id=? GROUP BY bucket''',(step,sid))}
    slots=min(100,int(duration//step)+1)
    people=person_summaries(db,sid)
    distribution={}
    for p in people:
        for kind,count in p['event_counts'].items():distribution[kind]=distribution.get(kind,0)+count
    avg=db.execute('SELECT AVG(people_count) FROM visibility_samples WHERE session_id=?',(sid,)).fetchone()[0]
    page=event_page(db,sid)
    role_counts={"STUDENT":0,"TEACHER":0,"UNKNOWN":0}
    role_events={"STUDENT":[],"TEACHER":[],"UNKNOWN":[]}
    for person in people:
        role=person.get('role','UNKNOWN') if person.get('role','UNKNOWN') in role_counts else 'UNKNOWN'
        role_counts[role]+=person['event_count']
        role_events[role].append(person)
    student_people=role_events['STUDENT']
    unknown_people=role_events['UNKNOWN']
    def role_summary(selected):
        counts={}
        for person in selected:
            for event_type,count in person['event_counts'].items(): counts[event_type]=counts.get(event_type,0)+count
        ids=tuple(person['track_id'] for person in selected)
        if ids:
            marks=','.join('?' for _ in ids)
            review_rows=db.execute(f"SELECT COUNT(*) AS total,SUM(CASE WHEN review_priority='HIGH_REVIEW' THEN 1 ELSE 0 END) AS high FROM events WHERE session_id=? AND track_id IN ({marks}) AND review_priority IN ('REVIEW','HIGH_REVIEW')",(sid,*ids)).fetchone()
            review=int(review_rows['total'] or 0); high=int(review_rows['high'] or 0)
        else: review=high=0
        return {'people':[dict(person) for person in selected],
                'person_ids':list(ids),'event_count':sum(counts.values()),
                'event_distribution':[{'event_type':k,'count':v} for k,v in sorted(counts.items(),key=lambda x:-x[1])],
                'review_moments':review,'high_review_moments':high}
    return {'session':session,'duration_s':round(duration,3),'bucket_seconds':step,
        'people_observed':max(session['track_count'],len(people)),
        'average_visible_people':round(avg,2) if avg is not None else None,
        'event_distribution':[{'event_type':k,'count':v} for k,v in sorted(distribution.items(),key=lambda x:-x[1])],
        'events_over_time':[{'offset_s':i*step,'count':counts.get(i,0)} for i in range(slots)],
        'people_over_time':[{'offset_s':i*step,'people_count':round(visible[i]['people_count'],2) if i in visible else None,
            'samples':visible[i]['samples'] if i in visible else 0} for i in range(slots)] if visible else [],
        'people':people,'track_ids':[p['track_id'] for p in people],
        'event_timeline':page['items'],'event_page':{k:v for k,v in page.items() if k!='items'},
        'confirmed_durations':None,'duration_note':'Event occurrences do not record state end times.',
        'timelapse_seek_available':False,
        'role_counts':role_counts,
        'student_exam':role_summary(student_people),
        'unknown_exam':role_summary(unknown_people),
        'teacher_exam':role_summary(role_events['TEACHER']),
        'role_policy':'Historical events are retained; current session role assignments determine student and unknown Exam aggregates.'}
