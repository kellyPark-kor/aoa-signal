import tempfile, time
from storage import Store

def test_dedup_key():
    p=tempfile.mktemp(suffix='.sqlite3'); s=Store(p)
    assert not s.was_sent('BTCUSDT',123,'LONG')
    s.mark_sent('BTCUSDT',123,'LONG',time.time(),False)
    assert s.was_sent('BTCUSDT',123,'LONG')
    s.mark_sent('BTCUSDT',123,'LONG',time.time(),False)
    row=s.con.execute('SELECT COUNT(*) FROM sent_notifications').fetchone()[0]
    assert row==1
    s.close()
