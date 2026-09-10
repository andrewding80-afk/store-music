"""Prove the damping. A flapping speaker must say nothing; a real fault must speak."""
import importlib.util, time

spec = importlib.util.spec_from_file_location('cs', 'check_status.py')
cs = importlib.util.module_from_spec(spec); spec.loader.exec_module(cs)

now = int(time.time())
def st(ok, result='x', age_h=0, unreachable=None):
    return {'ok': ok, 'result': result, 'written_at': 'now',
            'written_at_epoch': now - age_h * 3600,
            'stores_switched_on_but_unreachable': unreachable or [], 'run_url': 'u'}

def run(latest, history):
    cs.latest_status = lambda: latest
    cs.published_verdicts = lambda limit=12: history
    return cs.decide()

cases = [
    ("healthy",                     st(True, 'all as expected'), [st(True)], 'OK'),
    ("one bad run only",            st(False), [st(False), st(True), st(True)], 'OK'),
    ("two bad runs",                st(False), [st(False), st(False), st(True)], 'OK'),
    ("three bad in a row",          st(False, 'SOMETHING NEEDS ATTENTION'),
                                    [st(False), st(False), st(False), st(True)], 'FAULT'),
    ("flapping, bad then good",     st(True), [st(True), st(False), st(True), st(False)], 'OK'),
    ("stale, job stopped",          st(True, 'was fine', age_h=40), [st(True)], 'STALE'),
    ("stale beats healthy",         st(True, 'looked fine', age_h=72), [st(True)], 'STALE'),
    ("unreadable status",           None, [], 'FAULT'),
]
bad = 0
for label, latest, hist, expect in cases:
    state, msg = run(latest, hist)
    ok = state == expect
    bad += (not ok)
    print(("  PASS  " if ok else "  FAIL  ") + ("%-6s" % state) + " | " + label)
print()
print("all cases correct" if not bad else str(bad) + " FAILING")
raise SystemExit(1 if bad else 0)
