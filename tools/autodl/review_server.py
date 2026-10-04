"""
Review page for listening to every pipeline stage in the browser (audio streams, nothing is stored locally)
and leaving feedback. Feedback goes to .autodl/feedback.jsonl, which runner.sh publishes to GitHub.

Standard library only. Started by runner.sh; open it through AutoDL's "custom service" link.
"""
import argparse
import html
import json
import os
import re
import time
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
STATE = REPO / '.autodl'
AUDIO_EXTS = {'.wav', '.flac', '.mp3', '.m4a', '.ogg', '.opus'}
MIME = {'.wav': 'audio/wav', '.flac': 'audio/flac', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4',
        '.ogg': 'audio/ogg', '.opus': 'audio/ogg'}
PAGE_SIZE = 40

# Stages shown on the page, in pipeline order.
STAGES = [
    ('raw', '原始歌曲', 'raw_songs'),
    ('vocals', '1 分离人声', 'preprocess_work/1_vocals'),
    ('karaoke', '2 去和声', 'preprocess_work/2_karaoke'),
    ('dereverb', '3 去混响', 'preprocess_work/3_dereverb'),
    ('denoise', '4 去噪', 'preprocess_work/4_denoise'),
    ('slices', '5 切片', 'preprocess_work/5_slices'),
    ('train', '训练集', 'data/train/audio'),
    ('val', '验证集', 'data/val/audio'),
    ('test', '测试歌曲', 'test_songs'),
    ('test_dry', '测试歌曲干声', 'preprocess_work_test/4_denoise'),
    ('infer', '转换结果', 'infer_out'),
]
SONG_STAGES = ['raw', 'vocals', 'karaoke', 'dereverb', 'denoise']
STAGE_DIR = {k: REPO / d for k, _, d in STAGES}
STAGE_NAME = {k: n for k, n, _ in STAGES}

CSS = """
body{font:15px/1.5 -apple-system,'PingFang SC','Microsoft YaHei',sans-serif;margin:0 auto;max-width:960px;
padding:16px;background:#fafafa;color:#222}
a{color:#0b62c4;text-decoration:none} h1{font-size:20px} h2{font-size:17px;margin-top:28px}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px 12px;margin:8px 0}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center} .name{font-weight:600;word-break:break-all}
audio{width:100%;max-width:520px;height:36px} .muted{color:#777;font-size:13px}
textarea{width:100%;box-sizing:border-box;min-height:44px;font:inherit}
button{padding:4px 12px;font:inherit;cursor:pointer} pre{white-space:pre-wrap;font-size:12px;background:#f0f0f0;
padding:8px;border-radius:6px;max-height:360px;overflow:auto} .ok{color:#18794e}
"""

JS = """
async function fb(id, target){
  const box=document.getElementById(id); const t=box.value.trim(); if(!t) return;
  const r=await fetch('feedback',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({target:target,text:t})});
  if(r.ok){box.value='';document.getElementById(id+'_ok').textContent='已提交 ✓';}
}
"""


def audio_files(folder, recursive=False):
    if not folder.is_dir():
        return []
    it = folder.rglob('*') if recursive else folder.iterdir()
    return sorted(f for f in it if f.is_file() and f.suffix.lower() in AUDIO_EXTS)


def esc(s):
    return html.escape(str(s), quote=True)


class Handler(BaseHTTPRequestHandler):
    server_version = 'review/1.0'

    def log_message(self, fmt, *args):
        print('%s %s' % (time.strftime('%F %T'), fmt % args), flush=True)

    # ---------- auth ----------
    def authorized(self, query):
        key = os.environ.get('REVIEW_KEY')
        if not key:
            return True
        if query.get('key', [''])[0] == key:
            self.set_cookie = f'review_key={key}; Path=/; Max-Age=2592000; SameSite=Lax'
            return True
        c = cookies.SimpleCookie(self.headers.get('Cookie', ''))
        return 'review_key' in c and c['review_key'].value == key

    # ---------- helpers ----------
    def send_html(self, body, status=200):
        data = ('<!doctype html><html lang="zh"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>DDSP-SVC 试听</title><style>{CSS}</style><script>{JS}</script></head>'
                f'<body>{body}</body></html>').encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        if getattr(self, 'set_cookie', None):
            self.send_header('Set-Cookie', self.set_cookie)
        self.end_headers()
        self.wfile.write(data)

    def player(self, f, label=None):
        rel = f.relative_to(REPO).as_posix()
        fid = 'fb' + str(abs(hash(rel)))
        return (f'<div class="card"><div class="name">{esc(label or f.name)}</div>'
                f'<audio controls preload="none" src="file?p={urllib.parse.quote(rel)}"></audio>'
                f'<textarea id="{fid}" placeholder="这一段的反馈（可选）"></textarea>'
                f'<div class="row"><button onclick="fb(\'{fid}\',\'{esc(rel)}\')">提交</button>'
                f'<span id="{fid}_ok" class="ok"></span></div></div>')

    # ---------- routes ----------
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        if not self.authorized(q):
            return self.send_html('<h1>需要访问密钥</h1><p>在网址后面加上 <code>?key=密钥</code>，'
                                  '密钥在 runner 的输出里。</p>', 403)
        route = url.path.rstrip('/').split('/')[-1]
        if route == 'file':
            return self.serve_file(q.get('p', [''])[0])
        if route == 'stage':
            return self.page_stage(q.get('s', [''])[0], int(q.get('page', ['1'])[0] or 1))
        if route == 'song':
            return self.page_song(q.get('n', [''])[0])
        return self.page_index()

    def do_POST(self):
        if not self.authorized({}):
            return self.send_html('forbidden', 403)
        length = int(self.headers.get('Content-Length', 0))
        try:
            data = json.loads(self.rfile.read(min(length, 100000)))
            entry = {'time': time.strftime('%F %T'), 'target': str(data.get('target', ''))[:300],
                     'text': str(data.get('text', ''))[:5000]}
        except (ValueError, AttributeError):
            return self.send_html('bad request', 400)
        STATE.mkdir(exist_ok=True)
        with open(STATE / 'feedback.jsonl', 'a', encoding='utf-8') as fp:
            fp.write(json.dumps(entry, ensure_ascii=False) + '\n')
        self.send_response(204)
        self.end_headers()

    def page_index(self):
        status = (STATE / 'publish' / 'status.txt')
        parts = ['<h1>DDSP-SVC 试听与反馈</h1>',
                 '<div class="card"><b>总体反馈</b>（会同步给 Claude）'
                 '<textarea id="fbgen" placeholder="例如：去混响太狠，声音发闷；第 3 首切片有伴奏残留"></textarea>'
                 '<div class="row"><button onclick="fb(\'fbgen\',\'general\')">提交</button>'
                 '<span id="fbgen_ok" class="ok"></span></div></div>']
        songs = audio_files(STAGE_DIR['vocals'])
        if songs:
            parts.append('<h2>按歌曲对比各阶段</h2><div class="card">')
            parts.append(' · '.join(f'<a href="song?n={urllib.parse.quote(f.stem)}">{esc(f.stem)}</a>'
                                    for f in songs))
            parts.append('</div>')
        parts.append('<h2>按阶段浏览</h2>')
        for key, name, _ in STAGES:
            n = len(audio_files(STAGE_DIR[key], recursive=True))
            if n:
                parts.append(f'<div class="card row"><a class="name" href="stage?s={key}">{esc(name)}</a>'
                             f'<span class="muted">{n} 个文件</span></div>')
        if status.exists():
            parts.append(f'<h2>运行状态</h2><pre>{esc(status.read_text(errors="replace"))}</pre>')
        self.send_html(''.join(parts))

    def page_stage(self, key, page):
        if key not in STAGE_DIR:
            return self.send_html('unknown stage', 404)
        files = audio_files(STAGE_DIR[key], recursive=True)
        pages = max(1, (len(files) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(max(1, page), pages)
        chunk = files[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
        nav = ' '.join(f'<b>{p}</b>' if p == page else f'<a href="stage?s={key}&page={p}">{p}</a>'
                       for p in range(1, pages + 1))
        body = [f'<p><a href="./">← 返回</a></p><h1>{esc(STAGE_NAME[key])}</h1>',
                f'<p class="muted">{len(files)} 个文件，第 {page}/{pages} 页　{nav}</p>']
        body += [self.player(f, f.relative_to(STAGE_DIR[key]).as_posix()) for f in chunk]
        body.append(f'<p>{nav}</p>')
        self.send_html(''.join(body))

    def page_song(self, stem):
        body = [f'<p><a href="./">← 返回</a></p><h1>{esc(stem)}</h1>']
        for key in SONG_STAGES:
            match = [f for f in audio_files(STAGE_DIR[key]) if f.stem == stem or
                     re.sub(r'\s+', '_', f.stem) == stem]
            if match:
                body.append(f'<h2>{esc(STAGE_NAME[key])}</h2>' + self.player(match[0]))
        slices = [f for f in audio_files(STAGE_DIR['slices']) if f.stem.rsplit('_', 1)[0] == stem]
        if slices:
            body.append(f'<h2>{esc(STAGE_NAME["slices"])}（{len(slices)} 段）</h2>')
            body += [self.player(f) for f in slices[:PAGE_SIZE]]
        self.send_html(''.join(body))

    def serve_file(self, rel):
        path = (REPO / rel).resolve()
        allowed = any(os.path.commonpath([path, d.resolve()]) == str(d.resolve()) for d in STAGE_DIR.values())
        if not allowed or not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
            return self.send_html('not found', 404)
        size = path.stat().st_size
        start, end = 0, size - 1
        m = re.match(r'bytes=(\d*)-(\d*)', self.headers.get('Range', ''))
        if m:
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else end
            elif m.group(2):  # suffix range: last N bytes
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.end_headers()
                return
        self.send_response(206 if m else 200)
        self.send_header('Content-Type', MIME.get(path.suffix.lower(), 'application/octet-stream'))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if m:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        with open(path, 'rb') as fp:
            fp.seek(start)
            remaining = end - start + 1
            try:
                while remaining > 0:
                    buf = fp.read(min(1 << 16, remaining))
                    if not buf:
                        break
                    self.wfile.write(buf)
                    remaining -= len(buf)
            except (BrokenPipeError, ConnectionResetError):
                pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=6008)
    args = p.parse_args()
    print(f'review server on :{args.port}', flush=True)
    ThreadingHTTPServer(('0.0.0.0', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
