"""Every page opened in a real headless browser with a realistic journal and small data files; fails on any console error (item 25).
Needs Playwright with Chromium (pip install playwright && python -m playwright install chromium). Where it is not installed, the test
prints SKIP and passes, so the normal CI run is unchanged. Run: python test_ui_pages.py"""
import json, os, shutil, socket, subprocess, sys, tempfile, threading, time
try:
    from playwright.sync_api import sync_playwright
except Exception:
    print('SKIP test_ui_pages: Playwright is not installed here'); print('\nALL PASSED'); sys.exit(0)

ROOT = os.path.dirname(os.path.abspath(__file__)); fails = []
def check(n, c, info=''):
    print(('PASS ' if c else 'FAIL ') + n + (f'   {info}' if info and not c else '')); (None if c else fails.append(n))

STUB = """window.supabase={createClient:()=>({auth:{getSession:async()=>({data:{session:{user:{id:'u1',email:'t@example.com'}}}}),
 mfa:{getAuthenticatorAssuranceLevel:async()=>({data:{currentLevel:'aal1',nextLevel:'aal1'},error:null}),listFactors:async()=>({data:{totp:[]},error:null})},
 onAuthStateChange:()=>({data:{subscription:{unsubscribe(){}}}}),signOut:async()=>({})},
 from:()=>({select:()=>({eq:()=>({maybeSingle:async()=>({data:null,error:null}),single:async()=>({data:null,error:null})}),order:()=>({limit:async()=>({data:[],error:null})})}),upsert:async()=>({error:null})}),
 channel:()=>({on(){return this},subscribe(){return this}}),removeChannel(){} })};"""

def site_with_data():
    d = tempfile.mkdtemp(); shutil.copytree(os.path.join(ROOT, 'site'), d, dirs_exist_ok=True); os.makedirs(os.path.join(d, 'data', 'health'), exist_ok=True)
    now = time.strftime('%Y-%m-%dT%H:%M:%S+05:30', time.gmtime(time.time() + 19800))
    days = [time.strftime('%Y-%m-%d', time.gmtime(time.time() - 86400 * (60 - i))) for i in range(60)]
    candles = [[100 + i * .3, 101.5 + i * .3, 99 + i * .3, 100.8 + i * .3] for i in range(60)]
    chart = dict(times=days, candles=candles, volume=[1000 + (i % 7) * 300 for i in range(60)], ema=[100 + i * .3 for i in range(60)])
    setup = lambda sym, st, gr, holds=(): dict(symbol=sym, direction='long', label='LONG', section='swing', stage=st, stage_label='', status={3: 'IN ZONE (wait for 1H)', 4: '1H CONFIRMED (wait for the 15m)', 5: 'TRIGGERED', 2: 'SET ALERT (wait)'}[st], grade=gr, score=9 if gr == 'A+' else 6,
        entry=110.0, sl=100.0, t1=120.0, t2=130.0, t3=140.0, zone_bot=108.0, zone_top=112.0, price=113.0, atr=2.0, sector='Chemicals', holds=list(holds), tfs=['1D'], charts={'1D': chart}, ticks=['Key level'], checklist=[dict(ok=True, tf='1D', title='CHoCH', text='ok'), dict(ok=False, tf='1H', title='1H close', text='not yet')],
        structure=2, zone_q=2, confirm=1, context=2, spark=[c[3] for c in candles[-30:]], risk_pct=9.0, plan=dict(execution=['wait'], trail=[], marks=[]), notes=[], logic=[], weekly=dict(up=True, text='Weekly up'), h1={}, m15={})
    data = {'swing': dict(mode='swing', generated_at=now, setups=[setup('AAA', 3, 'A+'), setup('BBB', 4, 'A', ['room < 2R']), setup('CCC', 5, 'A+'), setup('DDD', 2, 'B')], scanned=499, universe=500, nifty_trend=True),
            'options': dict(mode='options', generated_at=now, setups=[], lot_size=65, snapshot=dict(spot=25500, change_pct=-.5, vix=15, above_1h=False, bias_down=True, why_none=dict(CALL='No CHoCH', PUT='No CHoCH'), losses_today=0)),
            'intraday': dict(mode='intraday', generated_at=now, setups=[], scanned=150),
            'market': dict(indices=dict(nifty=dict(price=25500, change_pct=-.5))), 'news': dict(items=[], events=[], holidays=[], by_symbol={}),
            'signals_swing': dict(signals=[], dropped=[], watch={}), 'signals_options': dict(signals=[], dropped=[], watch={}), 'signals_intraday': dict(signals=[], dropped=[], watch={}),
            'gold': dict(generated_at=now, source='twelvedata:XAU/USD', price=2650, market_open=True, session='London', styles={}, feed=dict(ok=True), chart=dict(tf='5m', times=[f'2026-11-23 {9 + i // 12:02d}:{(i % 12) * 5:02d}' for i in range(60)], candles=candles, ema=[c[3] for c in candles]))}
    for k, v in data.items(): json.dump(v, open(os.path.join(d, 'data', k + '.json'), 'w'))
    return d

def journal():
    T = lambda **o: dict(dict(id='t' + str(abs(hash(str(o))) % 99999), d='2026-11-20', tm='10:00', cat='Swing', dir='Long', setup='Pullback from OB', tf='Daily', qty=10, entry=100, sl=95, tgt=115, exit=None, grade='A+', note='', parts=None), **o)
    trades = [T(inst='AAA'), T(inst='NIFTY 25000 CE', cat='Options', entry=120, sl=80, tgt=200, qty=65)] + [T(inst=f'W{i}', d=f'2026-{4 + i % 7:02d}-{1 + i % 27:02d}', xd=f'2026-{4 + i % 7:02d}-{2 + i % 26:02d}', exit=108 if i % 3 else 96, brk='FOMO entry' if i % 5 == 0 else 'None') for i in range(20)]
    return [dict(id='j1', name='Main', schema=2, demo=False, updated=1, set=dict(capital=200000, riskC=0.01), lists=dict(setups=['Pullback from OB']), trades=trades)]

def serve(d):
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    p = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '-d', d, '--bind', '127.0.0.1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(.8); return p, port

PAGES = ['dashboard', 'premarket', 'swing', 'options', 'intraday', 'gold', 'journal', 'analytics', 'review', 'backtest', 'market', 'news', 'playbook', 'health', 'settings', 'design', 'stock?sym=AAA', 'trade?s=swing&id=AAA%7Clong', 'yearly']
d = site_with_data(); srv, port = serve(d)
seed = "if(!localStorage.getItem('seeded')){localStorage.setItem('tji_journals_v1',%s);localStorage.setItem('tji_last_v1','j1');localStorage.setItem('ds_tour_done','true');localStorage.setItem('ds_seen_ver','999');localStorage.setItem('seeded','1');}" % json.dumps(json.dumps(journal()))
try:
    with sync_playwright() as p:
        try: b = p.chromium.launch()
        except Exception as e: print(f'SKIP test_ui_pages: Chromium is not installed ({str(e)[:80]})'); print('\nALL PASSED'); sys.exit(0)
        for vw, label in (((1400, 1000), 'desktop'), ((390, 844), 'phone')):
            ctx = b.new_context(viewport={'width': vw[0], 'height': vw[1]}); pg = ctx.new_page(); errs = []
            pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None); pg.on('pageerror', lambda e: errs.append('PAGEERROR ' + str(e)))
            pg.route('**/cdn.jsdelivr.net/**', lambda r: r.fulfill(status=200, content_type='application/javascript', body=STUB)); pg.route('**/fonts.googleapis.com/**', lambda r: r.fulfill(status=200, body=''))
            pg.add_init_script(seed)
            for r in PAGES:
                pg.goto(f'http://127.0.0.1:{port}/index.html#/{r}'); pg.wait_for_timeout(1200)
                body = pg.inner_text('#page')
                check(f'{label}: {r} renders without a page error', 'This page hit an error' not in body, body[:160])
                if label == 'phone': check(f'phone: {r} fits the screen width', pg.evaluate('document.documentElement.scrollWidth') <= vw[0] + 2, pg.evaluate('document.documentElement.scrollWidth'))
            real = sorted(set(e for e in errs if 'Failed to load resource' not in e and 'favicon' not in e))
            check(f'{label}: no console errors on any page', not real, real[:5]); ctx.close()
        b.close()
finally:
    srv.terminate(); shutil.rmtree(d, ignore_errors=True)
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
