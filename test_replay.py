import tempfile, time
from storage import Store

def simulate(states):
    p=tempfile.mktemp(suffix='.sqlite3'); s=Store(p); sent=[]; prev='WAIT'
    for i,state in enumerate(states):
        if prev=='WAIT' and state in ('LONG','SHORT') and not s.was_sent('BTCUSDT',i,state):
            s.mark_sent('BTCUSDT',i,state,time.time(),False); sent.append((i,state))
        s.mark_processed('BTCUSDT',i,state,time.time()); s.set_state('BTCUSDT',state,i,time.time()); prev=state
    # Simulate restart: same states replayed; sent keys prevent duplicates.
    for i,state in enumerate(states):
        if prev=='WAIT' and state in ('LONG','SHORT') and not s.was_sent('BTCUSDT',i,state):
            s.mark_sent('BTCUSDT',i,state,time.time(),True); sent.append((i,state))
        prev=state
    assert sent==[(1,'LONG'),(4,'SHORT'),(7,'LONG')]
    s.close()

def test_replay_exactly_once():
    simulate(['WAIT','LONG','LONG','WAIT','SHORT','SHORT','WAIT','LONG','WAIT'])
