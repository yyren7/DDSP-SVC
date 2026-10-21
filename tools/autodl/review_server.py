"""
Review page for listening to every pipeline stage in the browser (audio streams, nothing is stored locally)
and leaving feedback. Feedback goes to .autodl/feedback.jsonl, which runner.sh publishes to GitHub.
Each speaker's folders (speakers/<name>/) have their own page; it opens on SPEAKER from plan.txt and
?spk=<name> switches to another one. Songs cut from song-stream recordings (songsplit job, songs/)
are listed per recording.

Standard library only (plus ffmpeg for the Opus fallback). Started by runner.sh; open it through
AutoDL's "custom service" link, or where that is not offered, an ssh tunnel to the port.
"""
import argparse
import hashlib
import html
import json
import math
import os
import random
import re
import subprocess
import threading
import time
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import rank_songs  # next to this file, which runner.sh starts as a script

REPO = Path(__file__).resolve().parent.parent.parent
ROOT = REPO.parent  # the data disk: the repo, and the speaker folders kept outside it
SPEAKERS = ROOT / 'speakers'
STATE = REPO / '.autodl'
PLAN = REPO / 'tools' / 'autodl' / 'plan.txt'
AUDIO_EXTS = {'.wav', '.flac', '.mp3', '.m4a', '.ogg', '.opus'}
MIME = {'.wav': 'audio/wav', '.flac': 'audio/flac', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4',
        '.ogg': 'audio/ogg', '.opus': 'audio/ogg'}
PAGE_SIZE = 40

# Stages shown on the page, in pipeline order, as folders inside speakers/<name>/ (see config.sh).
STAGES = [
    ('raw', '原始歌曲', 'raw_songs'),
    ('vocals', '1 分离人声', 'work/1_vocals'),  # the stage folders of stages.py, in its order
    ('karaoke', '2 去和声', 'work/2_karaoke'),
    ('dereverb', '3 去混响（最终干声）', 'work/3_dereverb'),
    ('slices', '4 切片', 'work/4_slices'),
    ('train', '训练集', 'data/train/audio'),
    ('val', '验证集', 'data/val/audio'),
    ('test', '测试歌曲', 'test_songs'),
    ('test_dry', '测试歌曲干声', 'work_test/3_dereverb'),
    ('infer', '转换结果', 'infer_out'),
]
SONG_STAGES = ['raw', 'vocals', 'karaoke', 'dereverb']
DRY_STAGE = 'dereverb'  # the final dry vocals (stages.DRY)
STAGE_NAME = {k: n for k, n, _ in STAGES}
SPEAKER_RE = re.compile(r'[A-Za-z0-9_-]+')

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
td,th{padding:3px 8px;border-bottom:1px solid #eee;text-align:right} td:first-child{text-align:left}
"""

JS = """
// The access key rides along in the URL where the page got it there: VS Code's browser shows pages in a
// frame, which does not send the SameSite=Lax key cookie with the page's own requests.
const KEYQ = (location.search.match(/[?&](key=[^&]*)/) || [])[1];
const FEEDBACK = 'feedback' + (KEYQ ? '?' + KEYQ : '');
async function fb(id, target){
  const box=document.getElementById(id); const t=box.value.trim(); if(!t) return;
  const r=await fetch(FEEDBACK,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({target:target,text:t})});
  if(r.ok){box.value='';document.getElementById(id+'_ok').textContent='已提交 ✓';}
}
async function note(btn){  // free text about one item: data-t the target, data-box the textarea, data-spk the speaker
  const box=document.getElementById(btn.dataset.box); const t=box.value.trim(); if(!t) return;
  const r=await fetch(FEEDBACK,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({target:btn.dataset.t,text:t,speaker:btn.dataset.spk||''})});
  if(r.ok) document.getElementById(btn.dataset.box+'_ok').textContent='已提交 ✓';
}
async function mark(btn){  // keep / exclude button: data-t is the file, its text the decision
  const r=await fetch(FEEDBACK,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({target:btn.dataset.t,text:btn.textContent,speaker:btn.dataset.spk||''})});
  if(r.ok) document.getElementById(btn.dataset.s).textContent='已标记：'+btn.textContent;
}
// A player that cannot play its source switches once to data-alt (see audio_tag). Nothing here touches a
// source before it is played: changing it on page load made the browser fetch every song on the page.
document.addEventListener('DOMContentLoaded', () => {
  for (const a of document.querySelectorAll('audio[data-alt]')) {
    a.addEventListener('error', () => {
      if (!a.dataset.alt) return;
      a.src = a.dataset.alt; a.dataset.alt = '';
      a.play().catch(() => {});
    });
  }
});
"""
OPUS_FROM = {'.m4a', '.mp4', '.aac', '.wav', '.flac'}
OPUS_BITRATE = '128k'
_transcode_locks = {}
_foreground = threading.BoundedSemaphore(2)  # transcodes for listeners at a time, on 0.5 CPU core


def audio_tag(rel):
    """Player for a file (path relative to ROOT), fetched only when played. WAV (1.4 Mbit/s) stalls in
    AutoDL's port forwarding, so it plays as an Opus copy and falls back to the WAV where Opus does not
    play (Safari); AAC plays as it is and falls back to Opus where there is no AAC decoder (VS Code's
    built-in browser)."""
    src = f'file?p={urllib.parse.quote(rel)}'
    if Path(rel).suffix.lower() in ('.wav', '.flac'):
        src, alt = src + '&fmt=ogg', src
    elif Path(rel).suffix.lower() in OPUS_FROM:
        alt = src + '&fmt=ogg'
    else:
        return f'<audio controls preload="none" src="{src}"></audio>'
    return f'<audio controls preload="none" src="{src}" data-alt="{alt}"></audio>'


def audio_files(folder, recursive=False):
    if not folder.is_dir():
        return []
    it = folder.rglob('*') if recursive else folder.iterdir()
    return sorted(f for f in it if f.is_file() and f.suffix.lower() in AUDIO_EXTS)


def esc(s):
    return html.escape(str(s), quote=True)


def plan_value(key):
    """KEY=VALUE from plan.txt, read the way runner.sh reads it."""
    try:
        lines = PLAN.read_text(encoding='utf-8').splitlines()
    except OSError:
        return ''
    values = [line.split('=', 1)[1] for line in lines if line.startswith(key + '=')]
    return re.sub(r'\s*#.*$', '', values[-1]).strip('"') if values else ''


def speakers():
    return sorted(d.name for d in SPEAKERS.iterdir() if d.is_dir()) if SPEAKERS.is_dir() else []


def stage_dir(spk, key):
    return SPEAKERS / spk / dict((k, d) for k, _, d in STAGES)[key]


def songs_dir(spk):
    return SPEAKERS / spk / 'songs'


def compare_dir(spk):
    return SPEAKERS / spk / 'compare'


def compare_sets(spk):
    """{excerpt: [(file, version)]} from compare/<version>/<excerpt>.wav, versions in folder order."""
    out = {}
    root = compare_dir(spk)
    if root.is_dir():
        for version in sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith('_')):
            for f in audio_files(version):
                out.setdefault(f.stem, []).append((f, version.name))
    return dict(sorted(out.items()))


def song_meta(folder):
    """{file: [file, source, start, end, name]} from the songs folder's _songs.tsv."""
    meta = {}
    tsv = folder / '_songs.tsv'
    if tsv.exists():
        for line in tsv.read_text(encoding='utf-8').splitlines()[1:]:
            cols = line.split('\t')
            if len(cols) >= 4:
                meta[cols[0]] = cols
    return meta


def check_list(spk):
    """[(file, label)] picked for a spot check: _check.tsv in the songs folder, "file<TAB>reason" per line."""
    folder = songs_dir(spk)
    tsv = folder / '_check.tsv'
    if not tsv.exists():
        return []
    meta, out = song_meta(folder), []
    for line in tsv.read_text(encoding='utf-8').splitlines():
        cols = line.split('\t')
        f = folder / cols[0]
        if f.is_file():
            where = f'　原录像 {meta[f.name][2]}–{meta[f.name][3]}' if f.name in meta else ''
            out.append((f, f'{f.stem}{where}　（{cols[1] if len(cols) > 1 else "抽查"}）'))
    return out


DECISIONS = ('排除', '保留', '拿不准')


def decisions(spk):
    """{file path relative to ROOT: latest of DECISIONS} from the feedback of this speaker."""
    out = {}
    try:
        lines = (STATE / 'feedback.jsonl').read_text(encoding='utf-8').splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('speaker') == spk and e.get('text') in DECISIONS:
            out[e.get('target')] = e['text']
    return out


CALIB_BANDS = [(0, 50, 12), (50, 75, 18), (75, 90, 18), (90, 101, 12)]  # line score band, lines drawn from it


def calib_sample(spk):
    """[{song, k, start, end}] drawn once from eval/lines.jsonl (eval_lines.py) to calibrate the line
    scores against the listener: a fixed number of lines from each score band, in random order. Kept in
    eval/calib.json so that every visit shows the same lines."""
    path = SPEAKERS / spk / 'eval' / 'calib.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    src = SPEAKERS / spk / 'eval' / 'lines.jsonl'
    if not src.exists():
        return []
    lines = [json.loads(x) for x in src.read_text(encoding='utf-8').splitlines() if x.strip()]
    rnd = random.Random(spk)
    out = []
    for lo, hi, n in CALIB_BANDS:
        band = [m for m in lines if lo <= m['score'] < hi]
        out += rnd.sample(band, min(n, len(band)))
    rnd.shuffle(out)
    out = [{'song': m['song'], 'k': m['k'], 'start': m['start'], 'end': m['end']} for m in out]
    tmp = path.with_suffix('.part')
    tmp.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)
    return out


CLIP_STAGES = {'mix': 'mix', 'voc': 'vocals', 'kar': 'karaoke', 'derev': 'dereverb', 'dry': DRY_STAGE}  # clip?from=
ORIGINAL_DIR = '0 原曲'  # compare_lines.py: the input song, cut like the versions
BLIND_NAMES = '甲乙丙丁戊己庚辛'


def blind_order(root, spk, n):
    """[(neutral name, version folder)] of compare/_lines/ for line n, in an order fixed by speaker and n."""
    versions = sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith(('_', '0 ')))
    random.Random(f'{spk}|{n}').shuffle(versions)
    return list(zip(BLIND_NAMES, versions))


AB_CHOICES = ('甲更好', '乙更好', '差不多')
AB_FIRST = 8  # cards of each speaker shown first: half her own clips, half the other speakers'


def ab_manifest(spk):
    """abtest/manifest.json of tools/autodl/abtest.py, or None."""
    path = SPEAKERS / spk / 'abtest' / 'manifest.json'
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def ab_items(spk, man):
    """The clips of the manifest with their own ones and the other speakers' taking turns."""
    own = [it for it in man['items'] if it['src_spk'] == spk]
    other = [it for it in man['items'] if it['src_spk'] != spk]
    out = []
    for k in range(max(len(own), len(other))):
        out += own[k:k + 1] + other[k:k + 1]
    return out


def ab_order(spk, name, datasets):
    """[(甲, dataset), (乙, dataset)] for one clip, shuffled by speaker and clip, the same on every visit."""
    ds = list(datasets)
    random.Random(f'ab|{spk}|{name}').shuffle(ds)
    return list(zip(BLIND_NAMES, ds))


def ab_audio(spk, name, v):
    """Player of one clip of the A/B page by its neutral name (v: 原声 or a name of ab_order), so that its
    address does not tell the model either (abclip resolves it)."""
    src = f'abclip?sp={urllib.parse.quote(spk)}&n={urllib.parse.quote(name)}&v={urllib.parse.quote(v)}'
    return f'<audio controls preload="none" src="{src}&fmt=ogg" data-alt="{src}"></audio>'


def ab_choices(spk):
    """{clip name: latest of AB_CHOICES} from the feedback on the A/B page of this speaker."""
    out = {}
    try:
        lines = (STATE / 'feedback.jsonl').read_text(encoding='utf-8').splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        t = str(e.get('target', ''))
        if e.get('speaker') == spk and t.startswith(f'ab:{spk}:') and e.get('text') in AB_CHOICES:
            out[t[len(f'ab:{spk}:'):]] = e['text']
    return out


def sign_test(wins, losses):
    """Two-sided sign test p-value of wins against losses (ties left out)."""
    n, k = wins + losses, max(wins, losses)
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n)


def line_card(spk, n, m, marks, buttons=True, note_open=False):
    """One line of eval/lines.jsonl ({song, k, start, end}) numbered n: the dry vocals of the line, the
    same place in the input song and after each step, keep / exclude / unsure buttons, and a box for why."""
    target = f'line:{m["song"]}#{m["k"]}'
    sid = 'mk' + hashlib.sha1(f'{spk}|{target}'.encode()).hexdigest()[:10]
    state = f'已标记：{marks[target]}' if target in marks else ('还没标记' if not buttons else '')
    span = (f'sp={urllib.parse.quote(spk)}&song={urllib.parse.quote(m["song"])}'
            f'&s={max(0, m["start"] - 0.1):.2f}&e={m["end"] + 0.1:.2f}')
    attrs = f'data-t="{esc(target)}" data-spk="{esc(spk)}"'
    marks_html = ''.join(f'<button {attrs} data-s="{sid}" onclick="mark(this)">{d}</button>'
                         for d in ('保留', '排除', '拿不准')) if buttons else ''
    note = (f'<textarea id="{sid}n" placeholder="为什么这样标（可选）"></textarea>'
            f'<div class="row"><button {attrs} data-box="{sid}n" onclick="note(this)">提交原因</button>'
            f'<span id="{sid}n_ok" class="ok"></span></div>')
    note = note if note_open else f'<details><summary class="muted">写原因</summary>{note}</details>'
    return (f'<div class="card"><div class="name">{n}. <span class="muted">{esc(m["song"])}　'
            f'{m["start"]:.1f}–{m["end"]:.1f} 秒</span></div>'
            f'<audio controls preload="none" src="clip?{span}&from=dry"></audio>'
            f'<details><summary class="muted">原曲和每一步的同一句</summary>'
            + ''.join(f'<div class="muted">{label}</div><audio controls preload="none" src="clip?{span}&from={key}"></audio>'
                      for key, label in (('mix', '原曲'), ('voc', '1 分离人声'), ('kar', '2 去和声'),
                                         ('derev', '3 去混响（最终干声）'))) +
            '</details>'
            f'<div class="row">{marks_html}<span id="{sid}" class="ok">{esc(state)}</span></div>{note}</div>')


def song_groups(spk):
    """{recording title: [(file, label)]} for the songs folder, using its _songs.tsv when present."""
    folder = songs_dir(spk)
    meta = song_meta(folder)
    groups = {}
    for f in audio_files(folder):
        cols = meta.get(f.name)
        if cols:  # source "20201206 【...】「歌回」冬季恋曲「2020-12-05」 [BV...].m4a" -> the title alone
            title = re.sub(r'^\d{8} |\s*\[[^\]]*\]$', '', Path(cols[1]).stem)
            groups.setdefault(title, []).append((f, f'{f.stem}　原录像 {cols[2]}–{cols[3]}'))
        else:
            groups.setdefault(f.name[:10], []).append((f, f.stem))
    return dict(sorted(groups.items(), key=lambda g: g[1][0][0].name))


class Handler(BaseHTTPRequestHandler):
    server_version = 'review/1.0'

    def log_message(self, fmt, *args):
        # the access key arrives as ?key=...; keep it out of this log, which runner.sh publishes
        print('%s %s' % (time.strftime('%F %T'), re.sub(r'key=[^&\s"]*', 'key=***', fmt % args)), flush=True)

    # ---------- auth ----------
    def authorized(self, query):
        key = os.environ.get('REVIEW_KEY')
        if not key:
            return True
        if query.get('key', [''])[0] == key:
            self.cookies_out.append(f'review_key={key}; Path=/; Max-Age=2592000; SameSite=Lax')
            self.url_key = key  # send_html puts it into the page's links and players too
            return True
        c = cookies.SimpleCookie(self.headers.get('Cookie', ''))
        return 'review_key' in c and c['review_key'].value == key

    def pick_speaker(self, query):
        """?spk=<name> (remembered in a cookie), else the remembered one, else SPEAKER from plan.txt."""
        known = speakers()
        want = query.get('spk', [''])[0]
        if want in known:
            self.cookies_out.append(f'review_spk={want}; Path=/; Max-Age=2592000; SameSite=Lax')
            return want
        c = cookies.SimpleCookie(self.headers.get('Cookie', ''))
        if 'review_spk' in c and c['review_spk'].value in known:
            return c['review_spk'].value
        plan = plan_value('SPEAKER')
        return plan if SPEAKER_RE.fullmatch(plan or '') else (known[0] if known else '')

    # ---------- helpers ----------
    def send_html(self, body, status=200):
        if getattr(self, 'url_key', None):  # opened with ?key=: keep it in every relative link and source
            def add_key(m):
                url = m.group(2)
                return f'{m.group(1)}="{url}{"&" if "?" in url else "?"}key={self.url_key}"'
            body = re.sub(r'\b(src|href|data-alt)="(?!https?:|#|javascript:|data:)([^"]*)"', add_key, body)
        data = ('<!doctype html><html lang="zh"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>DDSP-SVC 试听</title><style>{CSS}</style><script>{JS}</script></head>'
                f'<body>{body}</body></html>').encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        for c in self.cookies_out:
            self.send_header('Set-Cookie', c)
        self.end_headers()
        self.wfile.write(data)

    def player(self, f, label=None):
        rel = f.relative_to(ROOT).as_posix()
        fid = 'fb' + str(abs(hash(rel)))
        wav = (f' <a class="muted" href="file?p={urllib.parse.quote(rel)}" download="{esc(f.name)}">下载 WAV 原文件</a>'
               if f.suffix.lower() in ('.wav', '.flac') else '')
        return (f'<div class="card"><div class="name">{esc(label or f.name)}{wav}</div>'
                + audio_tag(rel) +
                f'<textarea id="{fid}" placeholder="这一段的反馈（可选）"></textarea>'
                f'<div class="row"><button onclick="fb(\'{fid}\',\'{esc(rel)}\')">提交</button>'
                f'<span id="{fid}_ok" class="ok"></span></div></div>')

    # ---------- routes ----------
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        self.cookies_out = []
        if not self.authorized(q):
            return self.send_html('<h1>需要访问密钥</h1><p>在网址后面加上 <code>?key=密钥</code>，'
                                  '密钥在 runner 的输出里。</p>', 403)
        route = url.path.rstrip('/').split('/')[-1]
        self.spk = self.pick_speaker(q)
        if route == 'file':
            return self.serve_file(q.get('p', [''])[0], q.get('fmt', [''])[0])
        if route == 'clip':
            return self.serve_clip(q)
        if route == 'calib':
            return self.page_calib(q.get('todo', [''])[0] == '1')
        if route == 'notes':
            return self.page_notes(q.get('sel', [''])[0])
        if route == 'lcmp':
            return self.page_lcmp(q.get('sel', [''])[0])
        if route == 'ab':
            return self.page_ab()
        if route == 'abclip':
            return self.serve_abclip(q)
        if route == 'abres':
            return self.page_abres()
        if route == 'stage':
            return self.page_stage(q.get('s', [''])[0], int(q.get('page', ['1'])[0] or 1))
        if route == 'song':
            return self.page_song(q.get('n', [''])[0])
        if route == 'songs':
            return self.page_songs(q.get('g', [''])[0])
        if route == 'check':
            return self.page_check()
        if route == 'compare':
            return self.page_compare()
        if route == 'rank':
            return self.page_rank(q.get('order', [''])[0] == 'worst')
        return self.page_index()

    def do_POST(self):
        self.cookies_out = []
        if not self.authorized(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)):
            return self.send_html('forbidden', 403)
        length = int(self.headers.get('Content-Length', 0))
        try:
            data = json.loads(self.rfile.read(min(length, 100000)))
            spk = data.get('speaker') if data.get('speaker') in speakers() else self.pick_speaker({})
            entry = {'time': time.strftime('%F %T'), 'speaker': spk,
                     'target': str(data.get('target', ''))[:300], 'text': str(data.get('text', ''))[:5000]}
        except (ValueError, AttributeError):
            return self.send_html('bad request', 400)
        STATE.mkdir(exist_ok=True)
        with open(STATE / 'feedback.jsonl', 'a', encoding='utf-8') as fp:
            fp.write(json.dumps(entry, ensure_ascii=False) + '\n')
        self.send_response(204)
        self.end_headers()

    def page_index(self):
        status = (STATE / 'publish' / 'status.txt')
        spk, plan = self.spk, plan_value('SPEAKER')
        switch = ' · '.join((f'<b>{esc(s)}</b>' if s == spk else f'<a href="./?spk={urllib.parse.quote(s)}">{esc(s)}</a>')
                            + (' <span class="muted">（plan.txt 当前）</span>' if s == plan else '')
                            for s in speakers())
        parts = [f'<h1>DDSP-SVC 试听与反馈：{esc(spk or "（还没有说话人）")}</h1>',
                 f'<div class="card row"><span class="muted">说话人</span> {switch or "无"}</div>',
                 '<div class="card"><b>总体反馈</b>（会同步给 Claude）'
                 '<textarea id="fbgen" placeholder="例如：去混响太狠，声音发闷；第 3 首切片有伴奏残留"></textarea>'
                 '<div class="row"><button onclick="fb(\'fbgen\',\'general\')">提交</button>'
                 '<span id="fbgen_ok" class="ok"></span></div></div>']
        if not spk:
            return self.send_html(''.join(parts))
        ab = [(s, m) for s in speakers() if (m := ab_manifest(s))]
        if ab:
            done = sum(len(ab_choices(s)) for s, _ in ab)
            parts.append(f'<h2>A/B 盲听（已听 {done} 句）</h2><div class="card row"><a class="name" href="ab">'
                         '两个模型比一比</a><span class="muted">'
                         + '；'.join(f'{esc(s)}：{" 和 ".join(map(esc, m["datasets"]))}，{m["step"]} 步' for s, m in ab)
                         + '</span></div>')
        sets = compare_sets(spk)
        if sets:
            parts.append(f'<h2>模型对比（{len(sets)} 段）</h2><div class="card row"><a class="name" href="compare">'
                         '逐段试听</a><span class="muted">同一段歌用不同的模型和步骤去伴奏，选出最好的做法</span></div>')
        sample = calib_sample(spk)
        if sample:
            marks = decisions(spk)
            done = sum(f'line:{m["song"]}#{m["k"]}' in marks for m in sample)
            parts.append(f'<h2>逐句校准（已标 {done}/{len(sample)} 句）</h2><div class="card row">'
                         '<a class="name" href="calib?todo=1">只看没标的</a> · <a class="name" href="calib">全部</a>'
                         '<span class="muted">抽出来的句子，分数不显示；你的标记用来校准逐句评分</span></div>')
        ranked = rank_songs.rank(rank_songs.load(SPEAKERS / spk))
        if ranked:
            parts.append(f'<h2>干声按质量排序（{len(ranked)} 首）</h2><div class="card row"><a class="name" href="rank">'
                         '从好到坏</a> · <a class="name" href="rank?order=worst">从坏到好</a>'
                         '<span class="muted">按测出的问题打分，每首可以标记排除或保留</span></div>')
        check = check_list(spk)
        if check:
            parts.append(f'<h2>待抽查（{len(check)} 首）</h2><div class="card row"><a class="name" href="check">'
                         '逐首试听</a><span class="muted">切歌结果里需要人工确认的歌，每首写明了原因</span></div>')
        groups = song_groups(spk)
        if groups:
            parts.append(f'<h2>歌回切歌（{sum(map(len, groups.values()))} 首）</h2><div class="card">')
            parts.append('<br>'.join(f'<a href="songs?g={urllib.parse.quote(title)}">{esc(title)}</a> '
                                     f'<span class="muted">{len(songs)} 首</span>' for title, songs in groups.items()))
            parts.append('</div>')
        songs = audio_files(stage_dir(spk, 'vocals'))
        if songs:
            parts.append('<h2>按歌曲对比各阶段</h2><div class="card">')
            parts.append(' · '.join(f'<a href="song?n={urllib.parse.quote(f.stem)}">{esc(f.stem)}</a>'
                                    for f in songs))
            parts.append('</div>')
        parts.append('<h2>按阶段浏览</h2>')
        for key, name, _ in STAGES:
            n = len(audio_files(stage_dir(spk, key), recursive=True))
            if n:
                parts.append(f'<div class="card row"><a class="name" href="stage?s={key}">{esc(name)}</a>'
                             f'<span class="muted">{n} 个文件</span></div>')
        if status.exists():
            parts.append(f'<h2>运行状态</h2><pre>{esc(status.read_text(errors="replace"))}</pre>')
        self.send_html(''.join(parts))

    def page_stage(self, key, page):
        if key not in STAGE_NAME or not self.spk:
            return self.send_html('unknown stage', 404)
        folder = stage_dir(self.spk, key)
        files = audio_files(folder, recursive=True)
        pages = max(1, (len(files) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(max(1, page), pages)
        chunk = files[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
        nav = ' '.join(f'<b>{p}</b>' if p == page else f'<a href="stage?s={key}&page={p}">{p}</a>'
                       for p in range(1, pages + 1))
        body = [f'<p><a href="./">← 返回</a></p><h1>{esc(STAGE_NAME[key])}</h1>',
                f'<p class="muted">{len(files)} 个文件，第 {page}/{pages} 页　{nav}</p>']
        body += [self.player(f, f.relative_to(folder).as_posix()) for f in chunk]
        body.append(f'<p>{nav}</p>')
        self.send_html(''.join(body))

    def page_song(self, stem):
        if not self.spk:
            return self.send_html('not found', 404)
        body = [f'<p><a href="./">← 返回</a></p><h1>{esc(stem)}</h1>']
        for key in SONG_STAGES:
            match = [f for f in audio_files(stage_dir(self.spk, key)) if f.stem == stem or
                     re.sub(r'\s+', '_', f.stem) == stem]
            if match:
                body.append(f'<h2>{esc(STAGE_NAME[key])}</h2>' + self.player(match[0]))
        slices = [f for f in audio_files(stage_dir(self.spk, 'slices')) if f.stem.rsplit('_', 1)[0] == stem]
        if slices:
            body.append(f'<h2>{esc(STAGE_NAME["slices"])}（{len(slices)} 段）</h2>')
            body += [self.player(f) for f in slices[:PAGE_SIZE]]
        self.send_html(''.join(body))

    def page_songs(self, title):
        songs = song_groups(self.spk).get(title) if self.spk else None
        if not songs:
            return self.send_html('not found', 404)
        body = [f'<p><a href="./">← 返回</a></p><h1>{esc(title)}</h1>',
                f'<p class="muted">{len(songs)} 首，时间是这首歌在原录像里的位置</p>']
        body += [self.player(f, label) for f, label in songs]
        self.send_html(''.join(body))

    def page_rank(self, worst_first):
        if not self.spk:
            return self.send_html('not found', 404)
        ranked = rank_songs.rank(rank_songs.load(SPEAKERS / self.spk))
        marks = decisions(self.spk)
        folder = stage_dir(self.spk, DRY_STAGE)
        items = []
        for k, (score, name, labels, m) in enumerate(ranked, 1):
            f = folder / f'{name}.wav'
            if f.is_file():
                items.append((k, score, name, labels, m, f, f.relative_to(ROOT).as_posix()))
        if worst_first:
            items.reverse()
        excluded = [it for it in items if marks.get(it[6]) == '排除']
        sung = sum(it[4].get('voiced_sec') or 0 for it in items)
        left = sung - sum(it[4].get('voiced_sec') or 0 for it in excluded)
        bands = [(90, 101), (75, 90), (60, 75), (40, 60), (0, 40)]
        counts = '，'.join(f'{lo}–{min(hi, 100)} 分 {sum(lo <= it[1] < hi for it in items)} 首' for lo, hi in bands)
        body = ['<p><a href="./">← 返回</a></p>',
                f'<h1>干声按质量排序：{"从坏到好" if worst_first else "从好到坏"}</h1>',
                f'<p><a href="rank{"" if worst_first else "?order=worst"}">改成{"从好到坏" if worst_first else "从坏到好"}</a></p>',
                '<p class="muted">分数只反映测出来的问题（去和声断口、整段被去掉、伴奏残影、底噪、混响、嗓音杂音等），'
                '100 分表示没测到问题，最终以耳朵为准。播放的是最终干声（3 去混响）；“对比各阶段”能听原曲和每一步。'
                '标记会同步给 Claude。</p>',
                f'<div class="card">{counts}<br>已标记排除 {len(excluded)} 首；'
                f'有效歌声 {sung / 3600:.1f} 小时，排除后剩 {left / 3600:.1f} 小时</div>']
        for k, score, name, labels, m, f, rel in items:
            sid = 'mk' + hashlib.sha1(rel.encode()).hexdigest()[:10]
            state = f'已标记：{marks[rel]}' if rel in marks else ''
            problems = '；'.join(labels) if labels else '没测到问题'
            body.append(
                f'<div class="card"><div class="name">{k}. {score:.0f} 分　{esc(name)}</div>'
                f'<div class="muted">{esc(problems)}　有效歌声 {(m.get("voiced_sec") or 0) / 60:.1f} 分钟</div>'
                + audio_tag(rel) +
                f'<div class="row"><button data-t="{esc(rel)}" data-s="{sid}" onclick="mark(this)">排除</button>'
                f'<button data-t="{esc(rel)}" data-s="{sid}" onclick="mark(this)">保留</button>'
                f'<a href="song?n={urllib.parse.quote(name)}">对比各阶段</a>'
                f'<span id="{sid}" class="ok">{esc(state)}</span></div></div>')
        self.send_html(''.join(body))

    def page_calib(self, todo=False):
        """calib: the lines of eval/calib.json to mark, numbered as there; calib?todo=1: only those not marked
        yet (calib_add.py adds lines after the first marks). Lines of songs no longer there are left out."""
        sample = calib_sample(self.spk) if self.spk else []
        if not sample:
            return self.send_html('<p><a href="./">← 返回</a></p><p>这个说话人还没有逐句结果（eval_lines.py lines）。</p>', 404)
        marks = decisions(self.spk)
        dry = stage_dir(self.spk, DRY_STAGE)
        cards = [(i, m) for i, m in enumerate(sample, 1) if (dry / f'{m["song"]}.wav').is_file()
                 and not (todo and f'line:{m["song"]}#{m["k"]}' in marks)]
        done = sum(f'line:{m["song"]}#{m["k"]}' in marks for m in sample)
        view = f'calib{"?todo=1" if todo else ""}'
        others = ' · '.join(f'<a href="{view}{"&" if todo else "?"}spk={urllib.parse.quote(s)}">{esc(s)}</a>'
                            for s in speakers() if s != self.spk and (SPEAKERS / s / 'eval' / 'lines.jsonl').exists())
        body = ['<p><a href="./">← 返回</a></p>', f'<h1>逐句校准：{esc(self.spk)}</h1>',
                f'<p>其他说话人：{others}</p>' if others else '',
                f'<div class="card">已标 {done}/{len(sample)} 句'
                + (f'，这里只列还没标的 {len(cards)} 句（<a href="calib">看全部</a>）。' if todo
                   else '（<a href="calib?todo=1">只看没标的</a>）。')
                + '顺序打乱，分数不显示。'
                '<br>按“这一句能不能拿去训练”来判断：听得出伴奏或和声残留、混响拖尾重、杂音或电音、'
                '声音被切断或削弱、不是她的声音，就点<b>排除</b>；干净自然就点<b>保留</b>；拿不准就点<b>拿不准</b>。'
                '<br><span class="muted">播放的是最终干声的这一句（前后各多 0.1 秒）；“原曲和每一步的同一句”可以对照。'
                '标记会同步给 Claude，改主意再点一次就行，以最后一次为准。</span></div>']
        body += [line_card(self.spk, i, m, marks) for i, m in cards]
        self.send_html(''.join(body))

    def page_notes(self, sel):
        """notes?sel=<speaker>:<n>,<n>;<speaker>:<n>...: lines of the calibration pages, by their number
        there, each with a box for why it was marked the way it was."""
        body = ['<p><a href="./">← 返回</a></p><h1>写原因</h1>',
                '<p class="muted">每句写一下为什么这样标，例如：混了伴奏、在说话不是在唱、电音或机械感、发闷、跑调、'
                '不像她的声音。展开“原曲和每一步的同一句”能听出问题是哪一步出现的（例如对讲机感从“3 去混响”开始），'
                '也请写上。提交后会同步给 Claude；想改标记回校准页改。</p>']
        for part in sel.split(';'):
            spk, _, nums = part.partition(':')
            if spk not in speakers():
                continue
            sample, marks = calib_sample(spk), decisions(spk)
            body.append(f'<h2>{esc(spk)}</h2>')
            for n in nums.split(','):
                if n.strip().isdigit() and 1 <= int(n) <= len(sample):
                    body.append(line_card(spk, int(n), sample[int(n) - 1], marks, buttons=False, note_open=True))
        self.send_html(''.join(body))

    def page_lcmp(self, sel):
        """lcmp?sel=<speaker>:<n>,...: calibration lines n through the chains of compare_lines.py, blind: the
        versions of each line in a shuffled order (fixed by speaker and n, see blind_order) under neutral names."""
        body = ['<p><a href="./">← 返回</a></p><h1>同一句的几种做法（盲听）</h1>',
                '<p class="muted">每句先是原曲，然后是几种去伴奏做法的结果，顺序每句打乱，名字不代表做法。'
                '听完写一句：哪个最好、哪个有对讲机感或发虚、哪个混响没去干净，例如“丙最好，甲乙发虚”。'
                '提交后会同步给 Claude。</p>']
        for part in sel.split(';'):
            spk, _, nums = part.partition(':')
            root = compare_dir(spk) / '_lines' if spk in speakers() else None
            if not root or not root.is_dir():
                continue
            sample = calib_sample(spk)
            body.append(f'<h2>{esc(spk)}</h2>')
            for n in nums.split(','):
                if not (n.strip().isdigit() and 1 <= int(n) <= len(sample)):
                    continue
                m = sample[int(n) - 1]
                target = f'cmp:line:{m["song"]}#{m["k"]}'
                sid = 'cm' + hashlib.sha1(f'{spk}|{target}'.encode()).hexdigest()[:10]
                players = ''
                for name, version in [('原曲', ORIGINAL_DIR)] + blind_order(root, spk, int(n)):
                    f = root / version / f'{int(n)}.wav'
                    if f.is_file():
                        players += f'<div class="muted">{name}</div>' + audio_tag(f.relative_to(ROOT).as_posix())
                body.append(
                    f'<div class="card"><div class="name">{int(n)}. <span class="muted">{esc(m["song"])}　'
                    f'{m["start"]:.1f}–{m["end"]:.1f} 秒</span></div>{players}'
                    f'<textarea id="{sid}" placeholder="哪个最好、哪个发虚或有对讲机感"></textarea>'
                    f'<div class="row"><button data-t="{esc(target)}" data-spk="{esc(spk)}" data-box="{sid}" '
                    f'onclick="note(this)">提交</button><span id="{sid}_ok" class="ok"></span></div></div>')
        self.send_html(''.join(body))

    def page_ab(self):
        """ab: the conversions of tools/autodl/abtest.py, blind. Each card is one clip: the input, then the
        result of each model under a neutral name in an order fixed by speaker and clip (ab_order)."""
        body = ['<p><a href="./">← 返回</a></p><h1>A/B 盲听：两个模型哪个好</h1>',
                '<div class="card">每句先听<b>原声</b>（模型的输入），再听<b>甲</b>和<b>乙</b>：同一句由两个模型各转换一次，'
                '顺序每句随机，名字不代表模型。选更好的一个：更像她本人、更自然、没有电音、沙哑、发虚或对讲机感。'
                '分不出就点“差不多”。<br>每人前 8 句就够（4 句是她自己的歌重建，4 句是别人的歌转成她的声音），'
                '想多听再展开“更多”。响度已对齐。听完点最下面的“揭晓”。'
                '<span class="muted">改主意再点一次，以最后一次为准。</span></div>']
        for spk in speakers():
            man = ab_manifest(spk)
            if not man:
                continue
            root, choices = SPEAKERS / spk / 'abtest', ab_choices(spk)
            items = ab_items(spk, man)
            own = [it for it in items if it['src_spk'] == spk]
            body.append(f'<h2>{esc(spk)}</h2>')
            if own:
                body.append(f'<div class="card"><div class="muted">她本人的声音，用来对照像不像</div>'
                            + ab_audio(spk, own[0]['name'], '原声') + '</div>')
            cards = []
            for i, it in enumerate(items, 1):
                target = f'ab:{spk}:{it["name"]}'
                sid = 'ab' + hashlib.sha1(target.encode()).hexdigest()[:10]
                what = '她自己的歌，重建' if it['src_spk'] == spk else f'{esc(it["src_spk"])} 的歌，转成她的声音'
                players = '<div class="muted">原声</div>' + ab_audio(spk, it['name'], '原声')
                for name, _ in ab_order(spk, it['name'], man['datasets']):
                    players += f'<div class="muted">{name}</div>' + ab_audio(spk, it['name'], name)
                attrs = f'data-t="{esc(target)}" data-spk="{esc(spk)}"'
                state = f'已标记：{choices[it["name"]]}' if it['name'] in choices else ''
                cards.append(
                    f'<div class="card"><div class="name">{i}. <span class="muted">{what}　{it["dur"]:.0f} 秒</span></div>'
                    f'{players}<div class="row">'
                    + ''.join(f'<button {attrs} data-s="{sid}" onclick="mark(this)">{c}</button>' for c in AB_CHOICES)
                    + f'<span id="{sid}" class="ok">{esc(state)}</span></div>'
                    f'<details><summary class="muted">写原因（可选）</summary>'
                    f'<textarea id="{sid}n" placeholder="例如：乙有电音，甲更像她"></textarea>'
                    f'<div class="row"><button {attrs} data-box="{sid}n" onclick="note(this)">提交原因</button>'
                    f'<span id="{sid}n_ok" class="ok"></span></div></details></div>')
            body += cards[:AB_FIRST]
            if len(cards) > AB_FIRST:
                body.append(f'<details><summary>更多（{len(cards) - AB_FIRST} 句，可选）</summary>'
                            + ''.join(cards[AB_FIRST:]) + '</details>')
        body.append('<p><a href="abres">听完了，揭晓 →</a></p>')
        self.send_html(''.join(body))

    def page_abres(self):
        """abres: the listener's choices of the A/B page decoded into the models, and the learned scores
        of the results (abtest/scores.jsonl) next to those of the inputs."""
        body = ['<p><a href="ab">← 回到盲听</a></p><h1>A/B 结果</h1>',
                '<p class="muted">p 是符号检验（不算“差不多”）：小于 0.05 才算听感上真的分出了好坏。'
                '下表是机器打分的平均，“原声”一行是输入本身，作为参照。</p>']
        names = {'singmos': 'SingMOS 歌声自然度', 'aes_pq': '制作质量 PQ', 'aes_ce': '好听程度 CE',
                 'dns_ovrl': 'DNSMOS 总体', 'spk_cos': '像她（声纹相似度）', 'f0_rmse_cents': '音高误差（音分）'}
        for spk in speakers():
            man = ab_manifest(spk)
            if not man:
                continue
            ds, choices = man['datasets'], ab_choices(spk)
            body.append(f'<h2>{esc(spk)}：{" 对 ".join(map(esc, ds))}（{man["step"]} 步）</h2>')
            own_names = {it['name'] for it in man['items'] if it['src_spk'] == spk}
            rows = []
            for label, pick in (('全部', lambda n: True), ('她自己的歌', lambda n: n in own_names),
                                ('别人的歌', lambda n: n not in own_names)):
                wins, ties = {d: 0 for d in ds}, 0
                for n, c in choices.items():
                    if not pick(n):
                        continue
                    order = dict(ab_order(spk, n, ds))
                    if c == '差不多':
                        ties += 1
                    elif c[0] in order:
                        wins[order[c[0]]] += 1
                p = f'，p = {sign_test(*[wins[d] for d in ds[:2]]):.2f}' if len(ds) == 2 else ''
                rows.append(f'{label}：' + '，'.join(f'{esc(d)} 胜 {w}' for d, w in wins.items()) + f'，差不多 {ties}{p}')
            body.append(f'<div class="card">已听 {len(choices)}/{len(man["items"])} 句<br>' + '<br>'.join(rows) + '</div>')
            path = SPEAKERS / spk / 'abtest' / 'scores.jsonl'
            if not path.exists():
                body.append('<p class="muted">机器打分还没做完。</p>')
                continue
            scores = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
            for label, own in (('她自己的歌（重建）', True), ('别人的歌（转换）', False)):
                head = ''.join(f'<th>{esc(names[k])}</th>' for k in names)
                trs = []
                for d in ['_source'] + ds:
                    sel = [r for r in scores if r['dataset'] == d and r['self'] == own]
                    if not sel:
                        continue
                    cells = []
                    for k in names:
                        v = [r[k] for r in sel if r.get(k) is not None]
                        cells.append(f'<td>{sum(v) / len(v):.3f}</td>' if v else '<td>–</td>')
                    trs.append(f'<tr><td>{"原声" if d == "_source" else esc(d)}</td>{"".join(cells)}</tr>')
                n = sum((it['src_spk'] == spk) == own for it in man['items'])
                body.append(f'<div class="card"><b>{label}</b>，每格是 {n} 句的平均；音高误差越小越好，其余越大越好'
                            f'<div style="overflow-x:auto"><table style="border-collapse:collapse;font-size:13px">'
                            f'<tr><th></th>{head}</tr>{"".join(trs)}</table></div></div>')
        self.send_html(''.join(body))

    def page_check(self):
        check = check_list(self.spk) if self.spk else []
        body = ['<p><a href="./">← 返回</a></p><h1>待抽查</h1>',
                f'<p class="muted">{len(check)} 首。听完在每首下面写结论，例如“完整一首”“只有半首”“不是她在唱”。'
                '反馈会同步给 Claude。</p>']
        body += [self.player(f, label) for f, label in check]
        self.send_html(''.join(body))

    def page_compare(self):
        sets = compare_sets(self.spk) if self.spk else {}
        body = ['<p><a href="./">← 返回</a></p><h1>模型对比</h1>',
                '<p class="muted">每段歌都用几种做法去伴奏。听完在下面写哪个版本最好、哪个有问题'
                '（伴奏残留、和声没去干净、声音发闷、有杂音或电音），反馈会同步给 Claude。</p>']
        for name, items in sets.items():
            body.append(f'<h2>{esc(name)}</h2>')
            body += [self.player(f, version) for f, version in items]
        self.send_html(''.join(body))

    def serve_file(self, rel, fmt=''):
        path = (ROOT / rel).resolve()
        # any speaker's audio folders, so a page opened before switching speakers keeps playing
        dirs = [d for s in speakers() for d in [stage_dir(s, k) for k in STAGE_NAME] + [songs_dir(s), compare_dir(s)]]
        allowed = any(os.path.commonpath([path, d.resolve()]) == str(d.resolve()) for d in dirs)
        if not allowed or not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
            return self.send_html('not found', 404)
        if fmt == 'ogg' and path.suffix.lower() in OPUS_FROM:
            path = opus_copy(path)
            if not path:
                return self.send_html('transcoding failed', 500)
        self.send_path(path)

    def serve_abclip(self, q):
        """abclip?sp=<speaker>&n=<clip>&v=原声|甲|乙[&fmt=ogg]: one clip of the A/B page (ab_audio)."""
        spk, name, v = (q.get(k, [''])[0] for k in ('sp', 'n', 'v'))
        man = ab_manifest(spk) if spk in speakers() else None
        if not man or name not in {it['name'] for it in man['items']}:
            return self.send_html('not found', 404)
        folder = '_source' if v == '原声' else dict(ab_order(spk, name, man['datasets'])).get(v)
        path = SPEAKERS / spk / 'abtest' / folder / f'{name}.wav' if folder else None
        if not path or not path.is_file():
            return self.send_html('not found', 404)
        if q.get('fmt', [''])[0] == 'ogg':
            path = opus_copy(path)
            if not path:
                return self.send_html('transcoding failed', 500)
        self.send_path(path)

    def serve_clip(self, q):
        """clip?sp=<speaker>&song=<name>&s=<sec>&e=<sec>&from=mix|voc|derev|kar: one line as Opus, from
        the song as it went into the pipeline (0_input) or from a stage (CLIP_STAGES), the dry vocals by default."""
        spk, song = q.get('sp', [''])[0], q.get('song', [''])[0]
        try:
            s, e = float(q.get('s', [''])[0]), float(q.get('e', [''])[0])
        except ValueError:
            return self.send_html('bad span', 400)
        if spk not in speakers() or not 0 <= s < e <= s + 60:
            return self.send_html('not found', 404)
        stage = CLIP_STAGES.get(q.get('from', [''])[0], DRY_STAGE)
        if stage == 'mix':
            folder = SPEAKERS / spk / 'work' / '0_input'
            src = next((f for f in audio_files(folder) if f.stem == song), None)
        else:
            src = stage_dir(spk, stage) / f'{song}.wav'
            src = src if src.parent == stage_dir(spk, stage) and src.is_file() else None
        path = src and opus_copy(src, span=(s, e))
        if not path:
            return self.send_html('not found', 404)
        self.send_path(path)

    def send_path(self, path):
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


def opus_copy(src, background=False, span=None):
    """Opus version of an audio file, made once and kept in .autodl/opus (None if ffmpeg fails); with
    span=(start, end) in seconds, of that part only (in .autodl/opus/clips).
    A 4-minute WAV takes about 3 s on the 0.5 CPU core of no-GPU mode; background runs ffmpeg at the
    lowest CPU priority."""
    st = src.stat()
    cut = f'|{span[0]:.2f}-{span[1]:.2f}' if span else ''
    key = hashlib.sha1(f'{src}|{st.st_size}|{st.st_mtime_ns}|{OPUS_BITRATE}{cut}'.encode()).hexdigest()
    dst = STATE / 'opus' / ('clips' if span else '') / f'{key}.ogg'
    with _transcode_locks.setdefault(key, threading.Lock()):  # range requests arrive in parallel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix('.part.ogg')
            seek = ['-ss', f'{span[0]:.2f}', '-t', f'{span[1] - span[0]:.2f}'] if span else []
            cmd = ['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', *seek, '-i', str(src), '-vn',
                   '-c:a', 'libopus', '-b:a', OPUS_BITRATE, '-compression_level', '5', str(tmp)]
            if background:
                r = subprocess.run(['nice', '-n', '19'] + cmd, capture_output=True)
            else:
                with _foreground:
                    r = subprocess.run(cmd, capture_output=True)
            if r.returncode != 0:
                print('opus transcoding failed:', r.stderr.decode(errors='replace')[-300:], flush=True)
                tmp.unlink(missing_ok=True)
                return None
            tmp.replace(dst)
    return dst


def prewarm():
    """Opus copies made ahead of time, so a song plays without waiting for ffmpeg: the dry vocals of
    every speaker, then the karaoke and vocals stages, each in the ranking page's worst-first order with
    the speakers taking turns. Logs only at the start and the end: the runner takes a review log written
    in the last 2 minutes for someone listening."""
    t0, made = time.time(), 0
    for key in (DRY_STAGE, 'karaoke', 'vocals'):
        lists = []
        for spk in speakers():
            folder = stage_dir(spk, key)
            names = [name for _, name, _, _ in reversed(rank_songs.rank(rank_songs.load(SPEAKERS / spk)))]
            files = [folder / f'{n}.wav' for n in names]
            files = [f for f in files if f.is_file()] or audio_files(folder)
            lists.append(files)
        for k in range(max(map(len, lists), default=0)):
            for files in lists:
                if k < len(files):
                    made += opus_copy(files[k], background=True) is not None
    print(f'prewarm: {made} Opus copies ready after {time.time() - t0:.0f} s', flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=6008)
    args = p.parse_args()
    print(f'review server on :{args.port}', flush=True)
    threading.Thread(target=prewarm, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
