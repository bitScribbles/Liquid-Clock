"""Browser checks for Liquid Clock: behaviour, timed events, accessibility (axe), offline.

Run from the repo root after `cd checks && npm install`:
    python3 checks/check.py
Needs Python Playwright with Chromium. Screenshots go to checks/out/.
"""
import http.server, os, socketserver, threading, functools
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "checks", "out"); os.makedirs(S, exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=ROOT)); PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://localhost:{PORT}/"
axe = open(os.path.join(ROOT, "checks", "node_modules", "axe-core", "axe.min.js")).read()
INIT = "window.__wake=0;Object.defineProperty(navigator,'wakeLock',{value:{request:async()=>{window.__wake++;return new EventTarget();}}});"
SEEN = "try{localStorage.setItem('lc.welcomed','1')}catch(e){}"   # past the welcome, for checks about the clock itself
SAFARI27 = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/27.2 Mobile/15E148 Safari/604.1'
SAFARI26 = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1'
fails = []
def ok(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)
def audit(pg, tag, el='pn'):
    pg.evaluate(axe)
    r = pg.evaluate("axe.run(document.getElementById('"+el+"'),{runOnly:['wcag2a','wcag2aa','wcag21aa','wcag22aa','best-practice']}).then(r=>r.violations.map(v=>v.id+' ('+v.nodes.length+'): '+v.nodes.slice(0,3).map(n=>n.target.join(' ')).join(' | ')))")
    ok(not r, f'{tag} axe: {r or "none"}')
def now_at(pg, base_js, x):       # set the time and read the state in one step (bursts make frames slow here)
    return pg.evaluate(f"x=>{{off=({base_js})+x-Date.now();return state()}}", int(x*1000))
def at(pg, base_js, x):           # move the clock to x seconds from an event and let it settle
    pg.evaluate(f"x=>{{window.__B={base_js};off=window.__B+x-Date.now()}}", int(x*1000)); pg.wait_for_timeout(500)
    pg.evaluate("x=>{off=window.__B+x-Date.now()}", int(x*1000)); pg.wait_for_timeout(50)
    return pg.evaluate("state()")

with sync_playwright() as p:
    b = p.chromium.launch(args=['--use-gl=swiftshader','--enable-webgl','--ignore-gpu-blocklist'])
    ctx = b.new_context(viewport={"width": 844, "height": 390}, device_scale_factor=2, has_touch=True, is_mobile=True)
    ctx.add_init_script(INIT); ctx.add_init_script(SEEN)
    def page(**kw):
        c = b.new_context(**kw); c.add_init_script(SEEN); return c.new_page()
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(1500)
    ok(pg.evaluate("gl.getProgramParameter(pr,gl.LINK_STATUS)"), 'shader compiles and links')
    ok(pg.evaluate("document.fonts.check('500 20px \"Space Grotesk\"')"), 'Space Grotesk loaded for the face numerals')
    pg.screenshot(path=S + "/clock.png")

    # the settings panel: only the centre opens it; closed, it can't be reached by keyboard
    open_ = lambda: pg.evaluate("document.getElementById('pn').classList.contains('open')")
    pg.touchscreen.tap(780, 40); pg.wait_for_timeout(300); ok(not open_(), 'a tap away from the centre does nothing')
    ok(pg.evaluate("window.__wake") >= 1, 'the first touch asks for the screen to stay on')
    pg.keyboard.press('Tab'); pg.keyboard.press('Tab')
    ok(pg.evaluate("!document.getElementById('pn').contains(document.activeElement)"), 'closed panel is out of the keyboard order')
    pg.touchscreen.tap(422, 195); pg.wait_for_timeout(600); ok(open_(), 'a tap at the centre opens the panel')
    audit(pg, 'Colours')
    pg.click('.pc[data-id=custom]'); pg.wait_for_timeout(300); audit(pg, 'Custom colours')
    # the phone standard (brand guide, 12 November 2026): 44px targets, text that grows, nothing sideways
    small = pg.evaluate("""[...document.querySelectorAll('#pn button,#pn select,#pn .links a,#cu label')].filter(e=>e.offsetParent)
       .map(e=>{const r=e.getBoundingClientRect();return [e.id||e.textContent.trim().slice(0,20)||e.dataset.k,Math.round(r.width),Math.round(r.height)]})
       .filter(([n,w,h])=>h<44||(w<44&&!/^#/.test(n)))""")
    ok(not small, f'Settings: every control at least 44px to tap {small or ""}')
    # the selected palette's ring (outline 2px, offset 3px) fits inside the scrolling body, in every column
    clip = pg.evaluate("""(()=>{const b=document.getElementById('pbody').getBoundingClientRect(),out=[];
      for(const id of Object.keys(PRESETS)){palId=id;applyPalette();const r=document.querySelector('.pc.on i').getBoundingClientRect();
        if(r.left-5<b.left-.5||r.right+5>b.right+.5)out.push(id)}palId='marquis';applyPalette();return out})()""")
    ok(not clip, f'Settings: the selected ring is never clipped {clip or ""}')
    ok(pg.evaluate("[...document.querySelectorAll('#st h3')].map(h=>h.textContent).join()") == 'Clock,Liquid,Moments' and pg.text_content('#tCol') == 'Settings',
       'Settings: grouped as Colours, Clock, Liquid, Moments')
    pg.click('#tAbout'); pg.wait_for_timeout(300); audit(pg, 'About')
    ok('final duel' in pg.inner_text('#vAbout') and 'final act' not in pg.inner_text('#vAbout'), 'About tells the origin right')
    ok(pg.inner_text('#ver') == pg.evaluate("VERSION"), 'About shows the version')
    ok(pg.evaluate("[...document.querySelectorAll('#vAbout a')].some(a=>a.href==='https://github.com/amandaghassaei/gpu-io')")
       and 'Amanda Ghassaei' in pg.inner_text('#vAbout') and pg.evaluate("[...document.querySelectorAll('#vAbout a')].some(a=>a.getAttribute('href')==='lib/gpu-io-LICENSE.txt')")
       and 'no other outside code' not in pg.inner_text('#vAbout'), 'About credits gpu-io by Amanda Ghassaei, with its licence')
    ok(pg.evaluate("[...document.querySelectorAll('#vAbout a')].some(a=>a.href==='https://bitscribbles.com/takepart.html'&&a.textContent==='Contribute')")
       and 'coffee' not in pg.inner_text('#vAbout').lower() and '™' not in pg.inner_text('#vAbout'), 'About links Contribute to Take part, no coffee link')
    pg.keyboard.press('Escape'); pg.wait_for_timeout(500); ok(not open_(), 'Escape closes the panel')

    # style choices persist
    pg.evaluate("palId='seine';applyPalette();STYLE.hands='fine';STYLE.face='marks';STYLE.secs='on';STYLE.para='off';STYLE.deep='on';applyStyle()")
    pg.reload(); pg.wait_for_timeout(1200)
    ok(pg.evaluate("palId==='seine'&&STYLE.hands==='fine'&&STYLE.face==='marks'&&STYLE.secs==='on'&&STYLE.para==='off'&&STYLE.deep==='on'"), 'palette and style (Second hand, Parallax and Deep too) survive a reload')
    ok(pg.evaluate("(()=>{off=new Date(2026,0,1,10,8,45).getTime()-Date.now();const s=state();return Math.abs(s.sa-1.5*Math.PI)<.01&&gl.getUniform(pr,uSec)===1})()"), 'Seconds: the second hand points at 9 at 45 s')
    pg.click('#hub', force=True); pg.wait_for_timeout(500)
    seg = lambda k: pg.evaluate(f"[...document.querySelectorAll('.seg[data-k={k}] button')].map(b=>b.textContent+':'+b.getAttribute('aria-pressed')).join()")
    ok(seg('secs') == 'Off:false,On:true' and seg('para') == 'Off:true,On:false' and seg('deep') == 'Off:false,On:true',
       'Settings offer Second hand, Parallax and Deep, each Off or On')
    ok(pg.evaluate("gl.getUniform(pr,uPara)===0&&gl.getUniform(pr,uLit)===1"), 'Deep works without Parallax')
    ok(pg.evaluate("!document.querySelector('.seg[data-k=ink],.seg[data-k=depth]')") and seg('hours') == 'Spin:true,Off:false',
       'Settings: no Edges (Ink), no single Depth, On the hour is Spin or Off')
    audit(pg, 'Settings with Deep')
    pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
    pg.screenshot(path=S + "/seine-styled.png")

    # depth: tilt moves the hands and the liquid; with no sensor it drifts on its own; Off holds everything still
    # (software rendering here is slow, so step the tilt directly rather than waiting on frames)
    ok(pg.evaluate("tiltAim=[1,-1];tiltAt=performance.now();for(let i=0;i<20;i++)tiltStep(.1);tilt[0]>.9&&tilt[1]<-.9"), 'tilt: the picture follows the tilt')
    a = pg.evaluate("tiltAt=-1e9;mouseAt=-1e9;for(let i=0;i<20;i++)tiltStep(.1);tilt.slice()"); pg.wait_for_timeout(4000)   # the drift is slow, and can sit at a turning point
    ok(pg.evaluate("t=>{for(let i=0;i<20;i++)tiltStep(.1);return Math.hypot(tilt[0]-t[0],tilt[1]-t[1])}", a) > .05, 'tilt: with no tilt sensor it drifts on its own')
    pg.screenshot(path=S + "/seine-deep.png")
    pg.evaluate("STYLE.para='on';STYLE.deep='off';applyStyle()")
    ok(pg.evaluate("gl.getUniform(pr,uPara)===1&&gl.getUniform(pr,uLit)===0"), 'Parallax works without Deep')
    pg.evaluate("STYLE.para='off';STYLE.deep='off';applyStyle()"); pg.wait_for_timeout(200)
    ok(pg.evaluate("gl.getUniform(pr,uPara)===0&&gl.getUniform(pr,uLit)===0"), 'Parallax and Deep Off turn the shader effects off')
    dm = page(viewport={"width": 1280, "height": 800})
    dm.goto(URL); dm.wait_for_timeout(600); dm.evaluate("STYLE.para='on';applyStyle()")
    dm.mouse.move(1270, 10); dm.wait_for_timeout(300)
    ok(dm.evaluate("for(let i=0;i<20;i++)tiltStep(.1);tilt[0]>.8&&tilt[1]>.8"), 'tilt: on a computer the mouse stands in for tilt')
    dm.context.close()
    # saved settings from 1.14 and before carry over: Depth Deep → Parallax and Deep on; Ink and Drop are gone
    oc = b.new_context(viewport={"width": 844, "height": 390}); oc.add_init_script(SEEN)
    oc.add_init_script("""try{localStorage.setItem('lc.style','{"ink":"1","depth":"deep","hours":"drop"}')}catch(e){}""")
    op = oc.new_page(); op.goto(URL); op.wait_for_timeout(800)
    ok(op.evaluate("STYLE.para==='on'&&STYLE.deep==='on'&&STYLE.hours==='spin'&&!('ink' in STYLE)&&!('depth' in STYLE)"),
       'old settings carry over: Depth Deep becomes Parallax and Deep, Drop becomes Spin, Ink is dropped')
    oc.close()

    # midnight: the colours gather into a knot, stop dead at 12:00, then spin back out in the new day's mix
    M = "(()=>{const d=new Date();d.setHours(24,0,0,0);return d.getTime()})()"
    s = at(pg, M, -300); ok(s['gth'][0] == 0 and 'mid' not in s, 'midnight: nothing building through the minutes before')
    ok(pg.evaluate("!document.querySelector('#void,#flash,#glow,#hint')"), 'no black, white or orange screens (or the old hint) left')
    g = [now_at(pg, M, x)['gth'][0] for x in (-61, -45, -20, -5, -.1)]
    ok(g[0] == 0 and 0 < g[1] < g[2] < g[3] < g[4] <= pg.evaluate("1/KF")+1e-6, 'midnight: the colours gather into an ever tighter knot through the last minute')
    s = now_at(pg, M, -20); ok(s['frz'] == 0 and s['gth'][1] > 0, 'midnight: spiralling in')
    ok(pg.evaluate("(()=>{off=("+M+")-20e3-Date.now();return fluidDrive(state()).om>0})()"), 'midnight: the fluid turns it counterclockwise as it gathers')
    ok([now_at(pg, M, x)['frz'] for x in (-.2, .1, 3.9, 4.1)] == [0, 1, 1, 0], 'midnight: everything stops dead from 12:00:00 for 4 s')
    s = at(pg, M, 2); ok(s['frz'] == 1 and pg.evaluate("getComputedStyle(ck).opacity") == '1', 'midnight: held still, the hands still showing')
    g = [now_at(pg, M, x)['gth'][0] for x in (5, 15, 30, 60)]
    ok(g[0] > g[1] > g[2] > 0 and 1 / g[2] > 1.6 and g[3] == 0, 'midnight: the knot lets go, the colours fill the screen by about +30 s, gone by a minute past')
    s = at(pg, M, 65); ok(s['gth'][0] == 0 and s['frz'] == 0, 'midnight: clock back after a minute')
    mx = [now_at(pg, M, x)['dsd'] for x in (-3000, -1, 1, 3000)]
    ok(mx[0] == mx[1] and mx[2] == mx[3] and mx[1] != mx[2], "midnight: a new mix for the new day, kept all day")
    # on the hour, Spin (the default): the liquid turns through the minute before and the minute after each hour, not at midnight
    Hr = "(()=>{const d=new Date();d.setHours(d.getHours()+1,0,0,0);if(d.getHours()===0)d.setHours(1);return d.getTime()})()"
    ok(pg.evaluate("STYLE.hours") == 'spin', 'on the hour: Spin by default')
    sp = [now_at(pg, Hr, x) for x in (-70, -30, 30, 70)]
    ok([round(s['spw']) for s in sp] == [0, 1, 1, 0] and sp[1]['hsp'] == -30 and sp[2]['hsp'] == 30,
       'on the hour: turns through the minute before and the minute after')
    ok(now_at(pg, Hr, -5)['pu'] < .15, 'on the hour: the minute surge is gentler while it turns')
    ok(now_at(pg, M, -30)['spw'] == 0 and now_at(pg, M, 30)['spw'] == 0, 'on the hour: not at midnight, which has its own build')
    om = lambda x: pg.evaluate("(x=>{off=("+Hr+")+x-Date.now();const d=fluidDrive(state());return d?d.om:0})", int(x*1000))
    ok(om(-30) > 0 and om(30) < 0 and om(-70) == 0, 'on the hour: the fluid turns counterclockwise before, clockwise after')
    # On the hour: Spin or Off; New Year plays as an ordinary midnight for now; drops and Paris dawn are gone
    pg.evaluate("STYLE.hours='off'"); t = now_at(pg, Hr, -30)
    fd = pg.evaluate("(x=>{off=("+Hr+")+x-Date.now();return fluidDrive(state())})", -30000); pg.evaluate("STYLE.hours='spin'")
    ok(t['spw'] == 0 and fd is None, 'on the hour: Off means no spin')
    NY = "new Date(new Date().getFullYear()+1,0,1).getTime()"
    s = now_at(pg, NY, 2); ok(s['frz'] == 1 and s['gth'][0] > 0, 'New Year: an ordinary midnight for now (gathered and held)')
    ok(pg.evaluate("['bursts','burst','dawnState','parisSunrise','newYear'].every(n=>typeof window[n]==='undefined')"), 'no drops, Paris dawn or New Year special left in the code')

    # battery: 30 fps while calm, every frame through midnight and after a touch
    gap = lambda base_js, x: pg.evaluate(f"x=>{{const B={base_js};off=B+x-Date.now();return frameGap(state(),1e9)}}", int(x*1000))  # set and read in one go
    calm = gap("Date.now()-(new Date().getSeconds()-25)*1000", 0)
    ok(30 <= calm <= 34, f'battery: calm clock draws at 30 fps (gap {calm:.0f} ms)')
    ok(gap(M, -30) == 0, 'battery: midnight gathering at full speed')
    ok(gap(M, 30) == 0, 'battery: full speed while the colours spin back out')
    ok(gap(M, 2) == 0, 'battery: full speed through the hold (the hands keep moving)')
    ok(pg.evaluate("frameGap({gth:[0,0,1]},200)") == 0, 'battery: full speed just after a touch')

    # Stir: a drag stirs the liquid (not from the panel); after 15 s untouched the fluid rests
    ok(pg.evaluate("!!FL && gl.getProgramParameter(pr,gl.LINK_STATUS)"), 'stir: the fluid starts, sharing the clock\'s WebGL')
    pg.evaluate("off=new Date(2026,0,5,10,10,20).getTime()-Date.now();if(pn.classList.contains('open'))closePanel();FL.reset();FL.on=false;FL.at=-1e9"); pg.wait_for_timeout(300)   # a calm moment, nothing driving the fluid
    pg.mouse.move(150, 100); pg.mouse.down(); pg.mouse.move(320, 130, steps=6); pg.mouse.up(); pg.wait_for_timeout(100)
    ok(pg.evaluate("FL.on && FL.at>0"), 'stir: a drag across the liquid stirs it')
    ok(pg.evaluate("FL.at=performance.now()-16e3;FL.drive(null);FL.step(.016);!FL.on"), 'stir: after 15 s untouched the fluid rests')
    pg.evaluate("FL.at=-1e9"); pg.click('#hub', force=True); pg.wait_for_timeout(500)
    bb = pg.query_selector('#pn').bounding_box(); pg.mouse.move(bb['x']+20, bb['y']+bb['height']/2); pg.mouse.down()
    pg.mouse.move(bb['x']+120, bb['y']+bb['height']/2+20, steps=6); pg.mouse.up()
    ok(pg.evaluate("FL.at===-1e9"), 'stir: a drag on the settings panel does not stir')
    pg.evaluate("if(pn.classList.contains('open'))closePanel()"); pg.wait_for_timeout(300)

    # the panel's tabs and Done stay on screen on a short, sideways phone, even after scrolling to Custom
    ls = page(viewport={"width": 844, "height": 350}, has_touch=True, is_mobile=True)
    ls.goto(URL); ls.wait_for_timeout(800); ls.touchscreen.tap(422, 175); ls.wait_for_timeout(600)
    ls.evaluate("document.querySelector('.pc[data-id=custom]').scrollIntoView({block:'center'})"); ls.wait_for_timeout(200)
    bb = ls.query_selector('.pc[data-id=custom]').bounding_box(); ls.touchscreen.tap(bb['x']+bb['width']/2, bb['y']+bb['height']/2); ls.wait_for_timeout(400)
    ls.evaluate("document.getElementById('pbody').scrollTop=9999"); ls.wait_for_timeout(200)
    d = ls.evaluate("(()=>{const r=document.getElementById('pd').getBoundingClientRect();return [r.top,r.bottom,innerHeight]})()")
    ok(d[0] >= 0 and d[1] <= d[2], f'panel: Done stays on screen sideways after scrolling to Custom (top {d[0]:.0f})')

    # reduce motion: a calmer clock
    rm = page(viewport={"width": 844, "height": 390}, reduced_motion='reduce')
    rm.goto(URL + "?t=23:59:50"); rm.wait_for_timeout(800)
    ok(rm.evaluate("state().gth[1]") < 2.6, 'reduce motion: midnight spirals half as much')
    rm.evaluate("STYLE.para='on';STYLE.deep='on';applyStyle();tiltAim=[1,1];tiltAt=performance.now();for(let i=0;i<20;i++)tiltStep(.1)")
    ok(rm.evaluate("Math.hypot(tilt[0],tilt[1])<.01") and 'reduce motion' in rm.text_content('#dnote'), 'reduce motion: Parallax and Deep hold still, and say why')
    rm.context.close()

    # offline: the service worker serves the clock with no connection
    pg.goto(URL); pg.wait_for_timeout(1500)
    pg.evaluate("navigator.serviceWorker.ready"); pg.reload(); pg.wait_for_timeout(1000)
    ctx.set_offline(True); pg.reload(); pg.wait_for_timeout(1500)
    ok(pg.evaluate("typeof VERSION!=='undefined' && document.fonts.check('500 20px \"Space Grotesk\"')"), 'opens offline, fonts included')
    ok(pg.evaluate("!!window.GPUIO && !!FL"), 'offline: the fluid (gpu-io) is there too')
    ctx.set_offline(False)
    pg.evaluate("fetch('clips/install-iphone-safari.jpg').then(r=>r.blob())"); pg.wait_for_timeout(400)
    ok(pg.evaluate("caches.keys().then(ks=>Promise.all(ks.map(k=>caches.open(k).then(c=>c.keys())))).then(a=>a.flat().every(r=>!r.url.includes('/clips/')))"),
       'the install clips are never kept offline')

    # larger text: at twice the usual size (as iPhone's largest standard Larger Text setting), nothing runs sideways
    for w_, h_ in [(390, 844), (320, 568)]:
        lt = page(viewport={"width": w_, "height": h_}, is_mobile=True, has_touch=True)
        lt.goto(URL); lt.wait_for_timeout(800); lt.evaluate("document.documentElement.style.setProperty('--t','2px');palId='custom';custom={...PRESETS.marquis,name:'Custom'};applyPalette();openPanel()"); lt.wait_for_timeout(500)
        wide = lt.evaluate("""[...document.querySelectorAll('#pn *')].filter(e=>e.offsetParent&&e.getBoundingClientRect().right>innerWidth+1).map(e=>e.id||e.className||e.tagName).slice(0,5)""")
        lt.click('#tAbout'); lt.wait_for_timeout(200)
        wide += lt.evaluate("""[...document.querySelectorAll('#vAbout *')].filter(e=>e.offsetParent&&e.getBoundingClientRect().right>innerWidth+1).map(e=>e.id||e.className||e.tagName).slice(0,5)""")
        ok(not wide, f'larger text (200%) at {w_}px: nothing runs off the side {wide or ""}')
        lt.context.close()

    # welcome: first visit only; what it is and where the settings are; then install steps for the device
    def iphone(ua=SAFARI27, init=None, **kw):
        c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True, user_agent=ua, **kw)
        if init: c.add_init_script(init)
        w = c.new_page(); w.on("pageerror", lambda e: errs.append(str(e))); w.goto(URL); w.wait_for_timeout(1400); return w
    shown = lambda w: w.evaluate("document.getElementById('ob').classList.contains('open')")
    w = iphone()
    ok(shown(w) and w.is_visible('#ob1') and not w.is_visible('#ob2'), 'welcome: opens on the first visit, at screen 1')
    ok(w.evaluate("document.activeElement.id") == 'obT1' and 'Touch the centre' in w.inner_text('#ob1'), 'welcome: focus on its title; says to touch the centre for settings')
    w.screenshot(path=S + "/welcome-1.png"); audit(w, 'Welcome 1', 'ob')
    w.click('#obNext'); w.wait_for_timeout(300)
    steps = w.inner_text('#obSteps')
    ok(w.is_visible('#ob2') and '≡' in steps and 'View More' in steps and 'Open as Web App' in steps and 'an iPhone, in Safari' in w.inner_text('#obDev'),
       'welcome: Safari 27 on iPhone gets ≡ → Share → View More → Add')
    ok(w.is_visible('#obPlay') and '26 s' in w.inner_text('#obPlay') and not w.is_visible('#obVid'), 'welcome: Safari clip offered, closed until tapped')
    w.click('#obPlay'); w.wait_for_timeout(1200)
    ok(w.evaluate("obVid.src.startsWith('blob:')&&obVid.muted&&obVid.loop&&obVid.playsInline&&obVid.getAttribute('aria-label').includes('Add to Home Screen')"),
       'welcome: the clip plays muted, looping, inline, from memory, with the steps as its label')
    w.screenshot(path=S + "/welcome-2.png"); audit(w, 'Welcome 2 with clip', 'ob')
    w.click('#obChange'); w.select_option('#obOs', 'android'); w.select_option('#obBr', 'chrome'); w.wait_for_timeout(200)
    ok('Install app' in w.inner_text('#obSteps') and not w.is_visible('#obClip') and w.evaluate("JSON.parse(localStorage.getItem('lc.device')).os") == 'android',
       'welcome: Not right? Change switches the steps, hides the clip, and is remembered')
    w.select_option('#obOs', 'iphone'); w.select_option('#obBr', 'safari'); w.wait_for_timeout(200)
    ok(w.evaluate("localStorage.getItem('lc.device')") is None, 'welcome: choosing the detected device again goes back to detecting')
    w.click('#obDone'); w.wait_for_timeout(300)
    ok(not shown(w) and w.evaluate("localStorage.getItem('lc.welcomed')") == '1' and w.evaluate("document.activeElement.id") == 'hub',
       'welcome: Start the clock closes it, remembers, and leaves focus on the centre')
    w.reload(); w.wait_for_timeout(1400); ok(not shown(w), 'welcome: not shown again')
    w.click('#hub', force=True); w.wait_for_timeout(500); w.click('#tAbout'); w.wait_for_timeout(200); w.click('#howTo'); w.wait_for_timeout(400)
    ok(shown(w) and w.is_visible('#ob2') and not w.evaluate("document.getElementById('pn').classList.contains('open')"), 'welcome: About → How to install opens the install screen')
    w.keyboard.press('Escape'); w.wait_for_timeout(200); ok(not shown(w), 'welcome: Escape closes it')
    w.context.close()
    w = iphone(SAFARI26); w.click('#obNext'); w.wait_for_timeout(200)
    ok('⋯' in w.inner_text('#obSteps') and not w.is_visible('#obClip'), 'welcome: Safari 26 gets ⋯ and no clip')
    w.context.close()
    w = iphone(init="localStorage.setItem('lc.hinted','1')")
    ok(not shown(w), 'welcome: not shown to people who were already here')
    w.context.close()
    w = iphone(init="Object.defineProperty(navigator,'standalone',{value:true})")
    ok(shown(w) and w.inner_text('#obNext') == 'Start the clock' and not w.is_visible('#howWrap'), 'welcome: installed, just screen 1, and no How to install')
    w.click('#obNext'); w.wait_for_timeout(200); ok(not shown(w), 'welcome: installed, Start the clock closes it')
    w.context.close()

    ok(not errs, f'no page errors {errs or ""}')
    b.close()
print('\n' + ('All checks passed.' if not fails else f'{len(fails)} failed.'))
