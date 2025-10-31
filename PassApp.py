#!/usr/bin/env python3
"""
finalpass2.py
Flask app with terminal-style UI, emblem, encode/decode, persistent SQLite, AJAX verification popup.

Run:
  python3 -m venv venv
  source venv/bin/activate
  pip install flask
  python finalpass2.py

Open: http://127.0.0.1:5000

Place emblem image at ./static/emblem.png
Password to save entries: KMSMGDWIZFILMS
"""
from flask import Flask, request, render_template_string, g, jsonify, url_for, redirect
import os, sqlite3, re
from datetime import datetime

# ---------- Config ----------
APP_SECRET = "change_this_for_local_use"
DB_FILE = os.path.join(os.path.dirname(__file__), "jumbles.db")
SAVE_PASSWORD = "KMSMGDWIZFILMS"

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = APP_SECRET

# ---------- Encoding/Decoding logic (same as before) ----------
def char_to_num(c):
    if 'A' <= c <= 'Z':
        return f"{ord(c) - ord('A') + 1:02}"
    elif 'a' <= c <= 'z':
        return f"{ord(c) - ord('a') + 27:02}"
    elif '0' <= c <= '9':
        return f"{ord(c) - ord('0') + 53:02}"
    else:
        return "63"

def num_to_char(nstr):
    n = int(nstr)
    if 1 <= n <= 26:
        return chr(n + ord('A') - 1)
    elif 27 <= n <= 52:
        return chr(n - 27 + ord('a'))
    elif 53 <= n <= 62:
        return chr(n - 53 + ord('0'))
    else:
        return '?'

qwerty_order = ['Q','W','E','R','T','Y','U','I','O','P','A','S','D','F','G','H','J','K','L','Z','X','C','V','B','N','M']
qwerty_map = {c: i for i, c in enumerate(qwerty_order)}
rev_qwerty_map = {i: c for c, i in qwerty_map.items()}

def qchar_to_num(ch):
    chu = ch.upper()
    if chu in qwerty_map:
        return f"{qwerty_map[chu]:02}"
    else:
        raise ValueError(f"Character '{ch}' not allowed in 6-char code (must be QWERTY letters).")

def num_to_qchar(nstr):
    n = int(nstr)
    return rev_qwerty_map.get(n, '?')

# canonical block list & synonyms
canonical_list = [
    "white_wool", "white_terracotta", "redstone_dust", "cobblestone", "iron_block",
    "oak_planks", "oak_log", "oak_sapling", "oak_boat", "stone", "dirt",
    "sand", "glass", "glass_pane", "spruce_planks", "birch_planks",
    "jungle_planks", "acacia_planks", "dark_oak_planks", "stone_bricks",
    "gold_block", "diamond_block", "emerald_block", "coal_block", "gravel"
]
canonical_to_id = {name: f"{i+1:02}" for i, name in enumerate(canonical_list)}
id_to_canonical = {v: k for k, v in canonical_to_id.items()}

synonyms = {
    "white": "white_wool", "white_wool": "white_wool", "wool": "white_wool",
    "white_terracotta": "white_terracotta", "terracotta": "white_terracotta",
    "redstone": "redstone_dust", "redstone_dust": "redstone_dust", "dust": "redstone_dust",
    "cobblestone": "cobblestone", "cobble": "cobblestone", "stone": "stone",
    "iron": "iron_block", "iron_block": "iron_block", "oak": "oak_planks",
    "oak_planks": "oak_planks", "planks": "oak_planks", "oak_log": "oak_log", "log": "oak_log",
    "sapling": "oak_sapling","boat": "oak_boat","dirt":"dirt","sand":"sand",
    "glass":"glass","glass_pane":"glass_pane","stone_bricks":"stone_bricks",
    "gold":"gold_block","diamond":"diamond_block","emerald":"emerald_block",
    "coal":"coal_block","gravel":"gravel","cobble_stone":"cobblestone",
    "white_concrete":"white_terracotta","white concrete":"white_terracotta"
}

def normalize_block_input(txt):
    if not txt:
        return None
    t = txt.strip().lower()
    t = re.sub(r"[\s\-]+", "_", t)
    t = re.sub(r"[^\w_]", "", t)
    if t in synonyms:
        return synonyms[t]
    if t in canonical_to_id:
        return t
    if "terracotta" in t:
        return "white_terracotta"
    if "wool" in t:
        return "white_wool"
    if "plank" in t:
        return "oak_planks"
    if "log" in t:
        return "oak_log"
    if "stone" in t and "brick" in t:
        return "stone_bricks"
    if "sand" in t:
        return "sand"
    if "dirt" in t or "grass" in t:
        return "dirt"
    if "cobble" in t:
        return "cobblestone"
    return None

def encode(username, code6, block_input):
    uname_len = len(username)
    if uname_len > 99:
        raise ValueError("Username too long (max 99).")
    length_prefix = f"{uname_len:02}"
    uname_num = ''.join(char_to_num(c) for c in username)
    if len(code6) != 6:
        raise ValueError("Code must be 6 chars.")
    code_nums = ''.join(qchar_to_num(ch) for ch in code6)
    canon = normalize_block_input(block_input)
    if canon is None:
        canon = "white_wool"
    block_id = canonical_to_id.get(canon, canonical_to_id["white_wool"])
    jumble = length_prefix + uname_num + code_nums + block_id
    return jumble, canon

def decode(jumble):
    if not re.fullmatch(r"\d+", jumble):
        raise ValueError("Jumble must be digits only.")
    if len(jumble) < 2 + 12 + 2:
        raise ValueError("Jumble too short.")
    prefix = jumble[:2]
    uname_len = int(prefix)
    uname_digits = uname_len * 2
    expected_len = 2 + uname_digits + 12 + 2
    if len(jumble) != expected_len:
        raise ValueError(f"Jumble length mismatch. Expected {expected_len} digits for username length {uname_len}.")
    uname_part = jumble[2:2+uname_digits]
    code_part = jumble[2+uname_digits:2+uname_digits+12]
    block_part = jumble[-2:]
    username = "".join(num_to_char(uname_part[i:i+2]) for i in range(0, len(uname_part), 2))
    code6 = "".join(num_to_qchar(code_part[i:i+2]) for i in range(0, len(code_part), 2))
    blockname = id_to_canonical.get(block_part, "unknown_block")
    return username, code6, blockname

# ---------- SQLite helpers ----------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        exists = os.path.exists(DB_FILE)
        db = g._database = sqlite3.connect(DB_FILE)
        db.row_factory = sqlite3.Row
        if not exists:
            # ensure table created
            cur = db.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS jumbles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                code6 TEXT NOT NULL,
                block TEXT NOT NULL,
                jumble TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """)
            db.commit()
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# ---------- HTML (terminal style) ----------
PAGE = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>MC Jumble — Terminal Verifier</title>
<style>
:root{
  --bg:#000;
  --text:#0f0;
  --muted:#6f6;
  --panel:#071006;
  --accent:#0bde74;
}
html,body{height:100%;margin:0;background:var(--bg);color:var(--text);font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", monospace;}
.container{max-width:1000px;margin:18px auto;padding:18px;}
.header{display:flex;align-items:center;justify-content:center;gap:18px;margin-bottom:8px;}
.logo img{height:120px;width:auto;filter:drop-shadow(0 6px 8px rgba(0,0,0,0.6));}
.title{font-size:20px;color:var(--muted);text-align:center;}
.panel{background:linear-gradient(180deg,#031003 0%, #071006 100%);padding:14px;border-radius:8px;border:1px solid rgba(0,255,0,0.06);box-shadow:0 6px 24px rgba(0,0,0,0.6);}
.field{margin:8px 0;}
.label{color:#5f5;font-size:12px;margin-bottom:6px;}
.input{width:100%;padding:10px;border-radius:6px;background:#001100;border:1px solid rgba(0,255,0,0.08);color:var(--text);outline:none;font-family:inherit;}
.input:focus{box-shadow:0 0 12px rgba(11,222,116,0.08);border-color:var(--accent);}
.row{display:flex;gap:8px;}
.btn{background:#0bde74;color:#001100;padding:8px 12px;border-radius:8px;border:0;cursor:pointer;font-weight:700;}
.btn.secondary{background:#444;color:var(--text);}
.small{font-size:12px;color:#6f6;}
.table{width:100%;border-collapse:collapse;margin-top:12px;color:var(--muted);}
.table th, .table td{padding:6px 8px;border-bottom:1px dashed rgba(0,255,0,0.04);font-size:13px;}
.footer{color:#464;font-size:12px;margin-top:10px;}
.hint{color:#4f4;font-size:12px;margin-top:8px;}

/* notification popup */
.toast {
  position:fixed;
  right:18px;
  bottom:18px;
  min-width:320px;
  max-width:420px;
  background:linear-gradient(180deg,#08130a,#071007);
  border:1px solid rgba(255,255,255,0.03);
  padding:12px 14px;
  border-radius:10px;
  box-shadow:0 10px 40px rgba(0,0,0,0.6);
  display:flex;
  gap:12px;
  align-items:center;
  z-index:9999;
  transform-origin:100% 100%;
  animation:pop .12s ease-out;
}
@keyframes pop { from { transform: scale(0.96) translateY(6px); opacity:0 } to { transform: scale(1) translateY(0); opacity:1 } }
.status-dot{width:18px;height:18px;border-radius:50%;flex:0 0 18px;border:2px solid rgba(0,0,0,0.5);box-shadow:0 2px 6px rgba(0,0,0,0.6);}
.toast .content{flex:1;}
.toast .title{font-weight:800;color:var(--text);margin-bottom:4px;}
.toast .msg{color:#bfb;font-size:13px;}

/* coloured states */
.dot-green{background:#16c60c;}
.dot-red{background:#e23a3a;}
.dot-yellow{background:#e2c93a;}

/* terminal look: fake cursor in inputs */
.input::placeholder{color:#1b6f1b;opacity:0.7;}
.cursor { display:inline-block; width:10px; background:var(--text); margin-left:6px; animation:blink 1s steps(2) infinite; height:18px; vertical-align:middle; border-radius:2px;}
@keyframes blink { 0%,40% { opacity:1 } 50% { opacity:0 } 100% { opacity:1 } }

/* responsive */
@media (max-width:720px){
  .row{flex-direction:column;}
  .header{flex-direction:column;}
}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo"><img src="{{ emblem_url }}" alt="emblem" /></div>
      <div class="title">
        <div style="font-size:18px">MC Jumble — Terminal Verifier</div>
        <div style="margin-top:6px" class="small">Type carefully. Save requires password. Matches persist in jumbles.db</div>
      </div>
    </div>

    <!-- Encode panel -->
    <div class="panel" id="encodePanel">
      <div style="font-weight:800; color:#0f0; margin-bottom:8px;">> encode — create a numeric jumble</div>
      <div class="field">
        <div class="label">Username (case-sensitive)</div>
        <input id="username" class="input" placeholder="IvanSveshnikov">
      </div>
      <div class="field">
        <div class="label">6-character code (QWERTY letters only)</div>
        <input id="code6" class="input" placeholder="QQQQQW" maxlength="6">
      </div>
      <div class="field">
        <div class="label">Placeable item (approximate allowed)</div>
        <input id="block" class="input" placeholder="white terracotta, cobblestone, oak boat">
      </div>
      <div style="margin-top:8px;">
        <label style="color:#6f6;"><input type="checkbox" id="saveToggle"> Save entry to list (requires password)</label>
      </div>
      <div id="pwdBox" style="display:none;margin-top:8px;">
        <div class="label">Save password</div>
        <input id="savePwd" class="input" type="password" placeholder="Password">
      </div>
      <div style="margin-top:10px;" class="row">
        <button class="btn" id="btnEncode">ENCODE</button>
        <button class="btn secondary" id="btnClear">CLEAR</button>
        <div style="flex:1"></div>
        <div class="small">Output jumble: <span id="outputJumble" style="color:#bfb; font-weight:700;">—</span></div>
      </div>
    </div>

    <!-- Decode panel -->
    <div style="margin-top:12px;" class="panel">
      <div style="font-weight:800; color:#0f0; margin-bottom:8px;">> decode — enter numeric jumble</div>
      <div class="field">
        <input id="jumbleIn" class="input" placeholder="Paste numeric jumble here">
      </div>
      <div class="row" style="margin-top:8px;">
        <button class="btn" id="btnDecode">DECODE</button>
        <button class="btn secondary" id="btnVerifyNum">VERIFY (numeric)</button>
        <div style="flex:1"></div>
        <div class="small">Decoded: <span id="decodedOut" style="color:#bfb">—</span></div>
      </div>
    </div>

    <!-- Verify verbal panel -->
    <div style="margin-top:12px;" class="panel">
      <div style="font-weight:800; color:#0f0; margin-bottom:8px;">> verify — verbal combo (username:code:block)</div>
      <div class="field">
        <input id="verbalIn" class="input" placeholder="e.g. IvanSveshnikov:QQQQQW:white terracotta">
      </div>
      <div class="row" style="margin-top:8px;">
        <button class="btn" id="btnVerifyVerbal">VERIFY (verbal)</button>
      </div>
    </div>

    <!-- Saved entries (read-only) -->
    <div style="margin-top:12px;" class="panel">
      <div style="font-weight:800;color:#0f0;margin-bottom:8px;">> saved list (recent)</div>
      <table class="table">
        <thead><tr><th>ID</th><th>USER</th><th>CODE</th><th>BLOCK</th><th>JUMBLE</th><th>CREATED</th></tr></thead>
        <tbody id="entriesTbody">
          <!-- populated by JS -->
        </tbody>
      </table>
    </div>

    <div class="footer">Tip: to save an encoded entry tick "Save" and enter the password. The password is required to prevent abuse.</div>
  </div>

  <!-- notification toast (hidden when none) -->
  <div id="toastContainer"></div>

<script>
// helper display toast
function showToast(state, title, message) {
  const dotClass = state === "legal" ? "dot-green" : state === "illegal" ? "dot-red" : "dot-yellow";
  const html = `<div class="toast" role="status" aria-live="polite">
    <div class="status-dot ${dotClass}"></div>
    <div class="content">
      <div class="title">${title}</div>
      <div class="msg">${message}</div>
    </div>
  </div>`;
  const container = document.getElementById("toastContainer");
  container.innerHTML = html;
  // hide after 8 seconds
  setTimeout(()=> { container.innerHTML = ""; }, 8000);
}

// page interactions
document.getElementById('saveToggle').addEventListener('change', e=>{
  document.getElementById('pwdBox').style.display = e.target.checked ? 'block':'none';
});

document.getElementById('btnClear').addEventListener('click', ()=>{
  ['username','code6','block','savePwd','outputJumble','jumbleIn','decodedOut','verbalIn'].forEach(id=>{
    const el=document.getElementById(id); if(el) { if(el.tagName==='INPUT') el.value=''; else el.textContent='—'; }
  });
});

// async helper for API calls
async function postJson(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body)
  });
  return r.json();
}

// fetch saved entries (read)
async function refreshEntries(){
  const res = await fetch('/api/list');
  const data = await res.json();
  const tbody = document.getElementById('entriesTbody');
  tbody.innerHTML = '';
  data.entries.forEach(e=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${e.id}</td><td>${e.username}</td><td>${e.code6}</td><td>${e.block}</td><td><code>${e.jumble}</code></td><td>${e.created_at.split('T')[0]}</td>`;
    tbody.appendChild(tr);
  });
}
refreshEntries();

// encode button
document.getElementById('btnEncode').addEventListener('click', async ()=>{
  const username = document.getElementById('username').value.trim();
  const code6 = document.getElementById('code6').value.trim();
  const block = document.getElementById('block').value.trim();
  const save = document.getElementById('saveToggle').checked;
  const pwd = document.getElementById('savePwd').value || '';
  if(!username){ showToast('illegal','Encode failed','Username required'); return; }
  if(code6.length !== 6){ showToast('illegal','Encode failed','6-character code required'); return; }
  const payload = { username, code6, block, save, pwd };
  const resp = await postJson('/api/encode', payload);
  if(!resp.ok){ showToast('illegal','Encode error', resp.error || 'Unknown'); return; }
  document.getElementById('outputJumble').textContent = resp.jumble;
  if(resp.saved){
    showToast('legal','Encoded & saved','Jumble: '+resp.jumble+' — block: '+resp.block);
    refreshEntries();
  } else {
    showToast('yellow','Encoded','Jumble: '+resp.jumble+' — block: '+resp.block);
  }
});

// decode button
document.getElementById('btnDecode').addEventListener('click', async ()=>{
  const jumble = document.getElementById('jumbleIn').value.trim();
  if(!jumble){ showToast('illegal','Decode failed','No jumble provided'); return; }
  const resp = await postJson('/api/decode', { jumble });
  if(!resp.ok){ showToast('illegal','Decode error', resp.error || 'Unknown'); return; }
  const s = `User=${resp.username} | Code=${resp.code6} | Block=${resp.block}`;
  document.getElementById('decodedOut').textContent = s;
  showToast('yellow','Decoded', s);
});

// verify numeric
document.getElementById('btnVerifyNum').addEventListener('click', async ()=>{
  const jumble = document.getElementById('jumbleIn').value.trim();
  if(!jumble){ showToast('illegal','Verify failed','No jumble provided'); return; }
  const resp = await postJson('/api/verify', { jumble });
  if(!resp.ok){ showToast('illegal','Verify error', resp.error || 'Unknown'); return; }
  // resp: {status: "legal"|"illegal"|"bug", message, details}
  const map = { legal:'legal','bug':'yellow','illegal':'illegal' };
  const cls = resp.status === 'legal' ? 'legal' : resp.status === 'illegal' ? 'illegal' : 'bug';
  const title = resp.status === 'legal' ? 'VERIFIED — legal migrant' :
                resp.status === 'illegal' ? 'ILLEGAL — invalid' : 'POTENTIAL BUG — verify yourself';
  showToast(resp.status === 'legal' ? 'legal' : resp.status === 'illegal' ? 'illegal' : 'yellow', title, resp.message);
});

// verify verbal
document.getElementById('btnVerifyVerbal').addEventListener('click', async ()=>{
  const verbal = document.getElementById('verbalIn').value.trim();
  if(!verbal){ showToast('illegal','Verify failed','No verbal input'); return; }
  const resp = await postJson('/api/verify', { verbal });
  if(!resp.ok){ showToast('illegal','Verify error', resp.error || 'Unknown'); return; }
  const title = resp.status === 'legal' ? 'VERIFIED — legal migrant' :
                resp.status === 'illegal' ? 'ILLEGAL — invalid' : 'POTENTIAL BUG — verify yourself';
  showToast(resp.status === 'legal' ? 'legal' : resp.status === 'illegal' ? 'illegal' : 'yellow', title, resp.message);
  if(resp.status==='legal') refreshEntries();
});
</script>
</body>
</html>
"""

# ---------- API endpoints ----------
@app.route('/')
def index():
    emblem_url = url_for('static', filename='emblem.png')
    return render_template_string(PAGE, emblem_url=emblem_url)

@app.route('/api/list', methods=['GET'])
def api_list():
    db = get_db()
    cur = db.execute("SELECT id, username, code6, block, jumble, created_at FROM jumbles ORDER BY id DESC LIMIT 200")
    rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"entries": rows})

@app.route('/api/encode', methods=['POST'])
def api_encode():
    data = request.get_json() or {}
    username = data.get('username','').strip()
    code6 = data.get('code6','').strip()
    block = data.get('block','').strip()
    save = bool(data.get('save'))
    pwd = data.get('pwd','')
    # validate
    if not username:
        return jsonify({"ok":False, "error":"Username required"}), 400
    if len(code6) != 6:
        return jsonify({"ok":False, "error":"6-character code required"}), 400
    for ch in code6:
        if ch.upper() not in qwerty_map:
            return jsonify({"ok":False, "error":"Code contains invalid character"}), 400
    try:
        jumble, canon = encode(username, code6, block)
    except Exception as e:
        return jsonify({"ok":False, "error": str(e)}), 400

    saved = False
    if save:
        # check password
        if pwd != SAVE_PASSWORD:
            return jsonify({"ok":False, "error":"Bad save password"}), 403
        db = get_db()
        cur = db.cursor()
        try:
            cur.execute("INSERT INTO jumbles (username, code6, block, jumble, created_at) VALUES (?, ?, ?, ?, ?)",
                        (username, code6.upper(), canon, jumble, datetime.utcnow().isoformat()))
            db.commit()
            saved = True
        except sqlite3.IntegrityError:
            saved = True  # already exists: treat as saved
        except Exception as e:
            return jsonify({"ok":False, "error":"DB error: "+str(e)}), 500

    return jsonify({"ok":True, "jumble":jumble, "block":canon, "saved": saved})

@app.route('/api/decode', methods=['POST'])
def api_decode():
    data = request.get_json() or {}
    jumble = data.get('jumble','').strip()
    if not jumble:
        return jsonify({"ok":False, "error":"No jumble provided"}), 400
    try:
        username, code6, blockname = decode(jumble)
        return jsonify({"ok":True, "username":username, "code6":code6, "block":blockname})
    except Exception as e:
        return jsonify({"ok":False, "error": str(e)}), 400

@app.route('/api/verify', methods=['POST'])
def api_verify():
    data = request.get_json() or {}
    verbal = (data.get('verbal') or "").strip()
    jumble = (data.get('jumble') or "").strip()
    db = get_db()

    # helper for making result types:
    # 'legal' -> green (found in DB)
    # 'illegal' -> red (invalid)
    # 'bug' -> yellow (valid decode/encode but not found)
    if verbal:
        # parse verbal: username:code:block or whitespace variants
        parts = re.split(r"[:;,\\|]+", verbal)
        if len(parts) < 3:
            parts2 = verbal.split()
            if len(parts2) >= 3:
                username = parts2[0]
                code6 = parts2[1]
                block = " ".join(parts2[2:])
            else:
                return jsonify({"ok": False, "status": "illegal", "message": "Couldn't parse verbal input. Use username:code:block"}), 400
        else:
            username, code6, block = parts[0].strip(), parts[1].strip(), parts[2].strip()
        # try to encode and check DB
        try:
            jum, canon = encode(username, code6, block)
        except Exception as e:
            return jsonify({"ok": False, "status":"illegal", "message": f"Encoding failed: {e}"}), 400
        cur = db.execute("SELECT id FROM jumbles WHERE jumble = ?", (jum,))
        row = cur.fetchone()
        if row:
            return jsonify({"ok": True, "status":"legal", "message": f"Verbal combo matches saved entry ID {row['id']}. Jumble: {jum}", "details": {"id":row['id'], "jumble":jum}})
        else:
            return jsonify({"ok": True, "status":"bug", "message": f"Not found in saved list. Expected jumble would be: {jum} (interpreted block: {canon})", "details":{"jumble":jum}})

    elif jumble:
        # numeric verification
        try:
            username, code6, blockname = decode(jumble)
        except Exception as e:
            return jsonify({"ok": False, "status":"illegal", "message": f"Decode failed: {e}"}), 400
        cur = db.execute("SELECT id, username, code6, block FROM jumbles WHERE jumble = ?", (jumble,))
        row = cur.fetchone()
        if row:
            return jsonify({"ok": True, "status":"legal", "message": f"Jumble matches saved entry ID {row['id']} (username={row['username']}, code={row['code6']}, block={row['block']}).", "details": {"id":row['id']}})
        else:
            # decoded but not in DB -> potential bug or simply not-saved entry
            return jsonify({"ok": True, "status":"bug", "message": f"Jumble decodes to username={username}, code={code6}, block={blockname}, but it's not in saved list.", "details": {"username":username, "code6":code6, "block":blockname}})

    else:
        return jsonify({"ok": False, "status":"illegal", "message":"Provide verbal combo OR numeric jumble to verify."}), 400

# ---------- start server ----------
if __name__ == '__main__':
    # ensure DB created inside app context
    with app.app_context():
        get_db()
    # run
    app.run(host='0.0.0.0', port=5000, debug=True)
