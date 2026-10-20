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
import os
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
    ('vocals', '1 分离人声', 'work/1_vocals'),
    ('dereverb', '2 去混响', 'work/2_dereverb'),
    ('karaoke', '3 去和声', 'work/3_karaoke'),
    ('slices', '4 切片', 'work/4_slices'),
    ('train', '训练集', 'data/train/audio'),
    ('val', '验证集', 'data/val/audio'),
    ('test', '测试歌曲', 'test_songs'),
    ('test_dry', '测试歌曲干声', 'work_test/3_karaoke'),
    ('infer', '转换结果', 'infer_out'),
]
SONG_STAGES = ['raw', 'vocals', 'dereverb', 'karaoke']
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
"""

JS = """
async function fb(id, target){
  const box=document.getElementById(id); const t=box.value.trim(); if(!t) return;
  const r=await fetch('feedback',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({target:target,text:t})});
  if(r.ok){box.value='';document.getElementById(id+'_ok').textContent='已提交 ✓';}
}
async function mark(btn){  // keep / exclude button: data-t is the file, its text the decision
  const r=await fetch('feedback',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({target:btn.dataset.t,text:btn.textContent})});
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


DECISIONS = ('排除', '保留')


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
        if not self.authorized({}):
            return self.send_html('forbidden', 403)
        length = int(self.headers.get('Content-Length', 0))
        try:
            data = json.loads(self.rfile.read(min(length, 100000)))
            entry = {'time': time.strftime('%F %T'), 'speaker': self.pick_speaker({}),
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
        sets = compare_sets(spk)
        if sets:
            parts.append(f'<h2>模型对比（{len(sets)} 段）</h2><div class="card row"><a class="name" href="compare">'
                         '逐段试听</a><span class="muted">同一段歌用不同的模型和步骤去伴奏，选出最好的做法</span></div>')
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
        folder = stage_dir(self.spk, 'karaoke')
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
                '100 分表示没测到问题，最终以耳朵为准。播放的是最终干声（3 去和声）；“对比各阶段”能听原曲和每一步。'
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


def opus_copy(src, background=False):
    """Opus version of an audio file, made once and kept in .autodl/opus (None if ffmpeg fails).
    A 4-minute WAV takes about 3 s on the 0.5 CPU core of no-GPU mode; background runs ffmpeg at the
    lowest CPU priority."""
    st = src.stat()
    key = hashlib.sha1(f'{src}|{st.st_size}|{st.st_mtime_ns}|{OPUS_BITRATE}'.encode()).hexdigest()
    dst = STATE / 'opus' / f'{key}.ogg'
    with _transcode_locks.setdefault(key, threading.Lock()):  # range requests arrive in parallel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix('.part.ogg')
            cmd = ['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-i', str(src), '-vn',
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
    every speaker, then the dereverb and vocals stages, each in the ranking page's worst-first order with
    the speakers taking turns. Logs only at the start and the end: the runner takes a review log written
    in the last 2 minutes for someone listening."""
    t0, made = time.time(), 0
    for key in ('karaoke', 'dereverb', 'vocals'):
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
