"""
Cut song-stream recordings (歌回) into one file per song, leaving out the talk between songs.

For every second of a recording, PANNs (Cnn14_DecisionLevelMax, trained on AudioSet) gives the
probability of singing, music and speech. A song is a stretch where singing dominates, widened to
the intro and outro its backing track plays while nobody talks. Fan-posted song timestamps (道标)
from the comments in yt-dlp's info json, when there are any, name the songs and separate songs
sung back to back.

The per-second probabilities are cached, so re-running with other thresholds only redoes the
cheap part. Songs are cut without re-encoding.

    python tools/split_songs.py -i recordings/ -o songs/ --model-dir pretrain/panns
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

AUDIO_EXTS = {'.m4a', '.mp3', '.aac', '.flac', '.wav', '.ogg', '.opus', '.webm', '.mp4', '.mkv'}
SR = 32000  # PANNs sample rate
WIN = 10    # seconds per model window, the clip length PANNs was trained on

SING = ['Singing', 'Female singing', 'Male singing', 'Child singing', 'Choir', 'Vocal music', 'A capella']
SPEECH = ['Speech', 'Female speech, woman speaking', 'Male speech, man speaking', 'Conversation',
          'Narration, monologue']
MUSIC = ['Music']


# ---------------------------------------------------------------- per-second class probabilities

def cpu_quota():
    """CPUs this container may use (AutoDL's no-GPU mode allows half of one, nproc says 256)."""
    try:
        quota, period = open('/sys/fs/cgroup/cpu.max').read().split()
        if quota != 'max':
            return max(1, int(quota) // int(period))
    except (OSError, ValueError):
        pass
    return os.cpu_count() or 1


def load_model(model_dir, device):
    labels_csv = Path(model_dir) / 'class_labels_indices.csv'
    # panns_inference reads its label list from ~/panns_data when imported and would otherwise try
    # to wget it from Google storage, which is unreachable from AutoDL
    home_csv = Path.home() / 'panns_data' / 'class_labels_indices.csv'
    if not home_csv.exists():
        home_csv.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(labels_csv, home_csv)
    import torch
    from panns_inference.models import Cnn14_DecisionLevelMax
    model = Cnn14_DecisionLevelMax(sample_rate=SR, window_size=1024, hop_size=320, mel_bins=64,
                                   fmin=50, fmax=14000, classes_num=527)
    ckpt = torch.load(Path(model_dir) / 'Cnn14_DecisionLevelMax.pth', map_location='cpu', weights_only=False)
    model.load_state_dict(ckpt['model'])
    model.eval().to(device)
    labels = [line.split(',', 2)[2].strip().strip('"')
              for line in labels_csv.read_text(encoding='utf-8').splitlines()[1:] if line.strip()]
    return model, labels


def decode(path, seconds, limit=None):
    """Mono float32 audio at SR from ffmpeg, in chunks of `seconds`."""
    cmd = ['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', str(path)]
    if limit:
        cmd += ['-t', str(limit)]
    proc = subprocess.Popen(cmd + ['-vn', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], stdout=subprocess.PIPE)
    with proc.stdout:
        while True:
            buf = proc.stdout.read(SR * seconds * 4)
            if not buf:
                break
            yield np.frombuffer(buf, np.float32)
    if proc.wait() != 0:
        raise RuntimeError(f'ffmpeg could not decode {path}')


def analyze(path, model, device, batch, total, limit=None):
    """(seconds, classes) float16: the framewise probabilities averaged over each second."""
    import torch
    out, done, t0, shown = [], 0, time.time(), time.time()
    for chunk in decode(path, WIN * batch, limit):
        secs = -(-len(chunk) // SR)
        nwin = -(-secs // WIN)
        x = np.zeros(nwin * WIN * SR, np.float32)
        x[:len(chunk)] = chunk
        with torch.no_grad():
            fw = model(torch.from_numpy(x.reshape(nwin, WIN * SR)).to(device))['framewise_output']
        # 100 frames per second -> one row per second
        fw = fw[:, :WIN * 100].reshape(nwin, WIN, 100, -1).mean(2).reshape(nwin * WIN, -1)[:secs]
        out.append(fw.float().cpu().numpy().astype(np.float16))
        done += secs
        if time.time() - shown > 60:
            shown = time.time()
            print(f'   {done / 60:.0f}/{total / 60:.0f} min, {done / (shown - t0):.1f}x realtime', flush=True)
    return np.concatenate(out)


# ---------------------------------------------------------------- song timestamps (道标)

TS = re.compile(r'(?<![\d:：])(?:(\d{1,2})[:：](\d{2})[:：](\d{2})|(\d{1,3})[:：](\d{2}))(?![\d:：])')
NUM = re.compile(r'^\s*[#＃]?\s*\d{1,3}\s*[.、．)）]\s*')
NOTE = re.compile(r'[（(【\[][^（()）【】\[\]]*[）)】\]]')


def to_seconds(m):
    if m.group(1):
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return h * 3600 + mi * 60 + s if mi < 60 and s < 60 else None
    mi, s = int(m.group(4)), int(m.group(5))
    return mi * 60 + s if s < 60 else None


def parse_markers(text):
    """Timestamped lines of a comment -> [(seconds, name, numbered)] in the order written.
    "4.アイのシナリオ 50:30 (二度口胡后是51:20)" -> (3030, 'アイのシナリオ', True)"""
    found = []
    for line in text.splitlines():
        bare = NOTE.sub(' ', line)
        stamps = [t for t in map(to_seconds, TS.finditer(bare)) if t is not None]
        if not stamps:
            continue
        name = TS.sub(' ', NUM.sub('', bare, count=1))
        name = re.sub(r'\s+', ' ', name).strip(' -—–~～·・:：|｜,，.。、')
        found.append((stamps[0], name, bool(NUM.match(line))))
    return found


def best_markers(info):
    """The song list from the description or the comment with the most timestamped songs.
    When a list numbers its songs, unnumbered lines are remarks ("94:00 悄悄探头") and are dropped."""
    texts = [(info.get('description') or '', 0)]
    texts += [(c.get('text') or '', c.get('like_count') or 0) for c in info.get('comments') or []]
    best, best_key = [], (0, 0)
    for text, likes in texts:
        found = parse_markers(text)
        numbered = [m for m in found if m[2]]
        use = numbered if len(numbered) >= 3 else found
        if len(use) >= 3 and (len(use), likes) > best_key:
            best, best_key = use, (len(use), likes)
    return [(t, name) for t, name, _ in best]


def name_segments(segs, markers, lead=60, tail=30):
    """Index into markers (or None) for every song."""
    names, used = [None] * len(segs), set()
    # by time: the unused entry nearest to the song's start that lies within the song
    for i, (a, b) in enumerate(segs):
        cands = [(abs(t - a), j) for j, (t, _) in enumerate(markers) if j not in used and a - lead <= t <= b - tail]
        if cands:
            names[i] = min(cands)[1]
            used.add(names[i])
    # by order: fans list the songs in the order sung, so a run of unnamed songs between two named
    # ones takes the unused entries listed between those two when the counts agree (this covers
    # mistyped timestamps)
    i = 0
    while i < len(segs):
        if names[i] is not None:
            i += 1
            continue
        k = i
        while k < len(segs) and names[k] is None:
            k += 1
        lo = names[i - 1] if i > 0 else -1
        hi = names[k] if k < len(segs) else len(markers)
        free = [j for j in range(lo + 1, hi) if j not in used]
        if len(free) == k - i:
            for s, j in zip(range(i, k), free):
                names[s] = j
                used.add(j)
        i = k
    return names


# ---------------------------------------------------------------- songs from probabilities

def smooth(x, k):
    if k <= 1:
        return x
    return np.convolve(np.pad(x, (k // 2, k - 1 - k // 2), mode='edge'), np.ones(k) / k, mode='valid')


def runs(mask):
    """(start, end) of every run of True, end exclusive."""
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def curves(probs, labels, k):
    idx = {name: i for i, name in enumerate(labels)}
    pick = lambda names: probs[:, [idx[n] for n in names if n in idx]].max(1)
    return smooth(pick(SING), k), smooth(pick(SPEECH), k), smooth(pick(MUSIC), k)


def find_songs(probs, labels, markers, a):
    sing, speech, music = curves(probs, labels, a.smooth)
    talk = curves(probs, labels, 1)[1] > a.speech  # seconds in which someone talks
    n = len(sing)
    # 1) singing, joined across short gaps (interludes, a shout during a song) unless there is
    #    real talk in the gap. Over a backing track PANNs scores singing at only a few percent but
    #    speech near zero, while talk scores speech in the tens of percent; the music score cannot
    #    tell them apart because streams keep background music on during the talk too.
    segs = []
    for s, e in runs((sing > a.sing) & (speech < a.speech)):
        if segs and s - segs[-1][1] <= a.gap and talk[segs[-1][1]:s].sum() < a.talk:
            segs[-1][1] = e
        else:
            segs.append([s, e])
    # 2) songs sung back to back: split where the song list starts a new song and the music dips
    split = []
    for s, e in segs:
        cuts, level = [], np.median(sing[s:e] + music[s:e])
        for t in sorted(t for t, _ in markers):
            if s + a.min_song <= t <= e - a.min_song:
                lo, hi = max(s, t - 20), min(e, t + 20)
                d = lo + int(np.argmin(sing[lo:hi] + music[lo:hi]))
                if sing[d] + music[d] < a.dip * level and d - (cuts[-1] if cuts else s) >= a.min_song:
                    cuts.append(d)
        bounds = [s] + cuts + [e]
        split += [[x, y] for x, y in zip(bounds, bounds[1:])]
    # 3) widen to intro and outro (backing track on, nobody talking), never into a neighbour
    bg = (music > a.music) & (speech < a.speech)
    for k, seg in enumerate(split):
        floor = split[k - 1][1] if k else 0
        ceil = split[k + 1][0] if k + 1 < len(split) else n
        s0, e0 = seg
        while seg[0] > floor and s0 - seg[0] < a.extend and bg[seg[0] - 1]:
            seg[0] -= 1
        while seg[1] < ceil and seg[1] - e0 < a.extend and bg[seg[1]]:
            seg[1] += 1
        seg[0], seg[1] = max(floor, seg[0] - a.pad), min(ceil, seg[1] + a.pad)
    return [(int(s), int(e)) for s, e in split]  # keep_songs drops the short ones


def keep_songs(found, a):
    """Drop songs shorter than --min-song from every recording's segments. Bilibili splits a long recording
    into parts (分P, ids "BV..._p1", "BV..._p2"), which can cut a song in two: when the singing runs to the
    last second of one part and from the first second of the next, the two pieces count as one song."""
    parts = {}
    for i, r in enumerate(found):
        m = re.fullmatch(r'(.+)_p(\d+)', r['info'].get('id') or '')
        if m:
            parts[m[1], int(m[2])] = i
    other = [[0] * len(r['segs']) for r in found]  # seconds of the same song in the neighbouring part
    for (video, part), i in parts.items():
        j = parts.get((video, part + 1))
        if j is None or not found[i]['segs'] or not found[j]['segs']:
            continue
        (s1, e1), (s2, e2) = found[i]['segs'][-1], found[j]['segs'][0]
        if e1 == found[i]['n'] and s2 == 0:
            other[i][-1] += e2 - s2
            other[j][0] += e1 - s1
    for r, extra in zip(found, other):
        r['segs'] = [(s, e) for (s, e), x in zip(r['segs'], extra) if e - s + x >= a.min_song]


# ---------------------------------------------------------------- files

def stream_date(path, info):
    dates = re.findall(r'(\d{4})-(\d{2})-(\d{2})', info.get('title') or '')  # live date, end of the title
    if dates:
        return '-'.join(dates[-1])
    d = info.get('upload_date') or ''
    return f'{d[:4]}-{d[4:6]}-{d[6:]}' if len(d) == 8 else path.stem[:20]


def title_name(title):
    """Song name from the title of a single-song video: the part in 『』 when there is one, otherwise
    the title without its 【tags】 ("只要是爱就会褪色，是吗？『偏爱』【佐仓旬夏】" -> "偏爱")."""
    m = re.search(r'『([^』]+)』', title)
    if m:
        return m.group(1).strip()
    return re.sub(r'\s+', ' ', re.sub(r'【[^】]*】|\[[^\]]*\]', ' ', title)).strip(' -~～')


def safe(name):
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', name).strip(' .')[:80]


def cut(src, start, end, dst):
    tmp = dst.with_name(dst.stem + '.part' + dst.suffix)
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-ss', str(start), '-i', str(src),
                    '-t', str(end - start), '-map', '0:a:0', '-c', 'copy', str(tmp)], check=True)
    tmp.replace(dst)


def moved_songs(old, new):
    """{file: new file} for a recording cut again: song numbers shift when songs are added or dropped, so each
    old song goes to the new song that overlaps it most, or to None when nothing overlaps it any more."""
    def overlap(x, y):
        return min(x['end'], y['end']) - max(x['start'], y['start'])
    moved = {}
    for x in old:
        best = max(new, key=lambda y: overlap(x, y), default=None)
        moved[x['file']] = best['file'] if best and overlap(x, best) > 0 else None
    return moved


def write_check_list(tsv, entries, moved):
    """The hand-made spot-check list (_check.tsv, "file<TAB>reason") as it was when the run started, with its
    songs renamed by this run's cuts so far. Mapping from the start keeps a name that a recording cut earlier in
    the run has just taken from a later one from being moved twice."""
    lines, seen = [], set()
    for file, tab, reason in entries:
        file = moved.get(file, file)
        if file and file not in seen:  # two entries on songs that are now one keep the first reason
            seen.add(file)
            lines.append(file + tab + reason)
    tmp = tsv.with_name('_check.tsv.tmp')
    tmp.write_text(''.join(x + '\n' for x in lines), encoding='utf-8')
    tmp.replace(tsv)


def mmss(s):
    return f'{int(s) // 60}:{int(s) % 60:02d}'


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('-i', '--input', required=True, help='folder with the recordings (and their .info.json)')
    p.add_argument('-o', '--output', required=True, help='folder for the songs')
    p.add_argument('--model-dir', default='pretrain/panns', help='Cnn14_DecisionLevelMax.pth and class_labels_indices.csv')
    p.add_argument('--cache', default=None, help='per-second probabilities (default: <output>/_probs)')
    p.add_argument('--device', default=None, help='cuda or cpu (default: cuda when available)')
    p.add_argument('--batch', type=int, default=None, help='10 s windows per model call (default 16 on GPU, 1 on CPU)')
    p.add_argument('--only', default=None,
                   help='only recordings whose file name contains this (a song cut in two where the parts '
                        'of a recording meet is only kept whole when both parts are in the run)')
    p.add_argument('--limit', type=int, default=None, help='only the first LIMIT seconds of each recording (tests)')
    p.add_argument('--dry-run', action='store_true', help='print the songs, cut nothing')
    p.add_argument('--smooth', type=int, default=5, help='moving average over this many seconds')
    p.add_argument('--sing', type=float, default=0.02, help='singing probability that counts as singing')
    p.add_argument('--speech', type=float, default=0.1, help='speech probability that counts as talking')
    p.add_argument('--music', type=float, default=0.25, help='music probability that counts as a backing track')
    p.add_argument('--gap', type=int, default=45, help='join singing across gaps up to this many seconds')
    p.add_argument('--talk', type=int, default=15, help='...unless someone talks for this many seconds in the gap')
    p.add_argument('--dip', type=float, default=0.6, help='split back-to-back songs where the level drops below this share')
    p.add_argument('--extend', type=int, default=30, help='widen songs by up to this many seconds of intro / outro')
    p.add_argument('--pad', type=int, default=1, help='seconds added on both ends')
    p.add_argument('--min-song', type=int, default=60, help='drop songs shorter than this (s)')
    p.add_argument('--single-max', type=int, default=900,
                   help='recordings up to this long (s) are single songs or clips, named after the video title')
    a = p.parse_args()

    out = Path(a.output)
    cache = Path(a.cache) if a.cache else out / '_probs'
    out.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in Path(a.input).iterdir()
                   if f.suffix.lower() in AUDIO_EXTS and not f.name.startswith('_') and '.part' not in f.suffixes)
    if a.only:
        files = [f for f in files if a.only in f.name]
    print(f'{len(files)} recordings', flush=True)

    # 1) find the songs in every recording, analysing the ones not seen before; whether a short piece at the
    #    start or end of a part stays depends on the neighbouring part
    model, found = None, []
    for f in files:
        info_path = f.with_name(f.stem + '.info.json')
        info = json.loads(info_path.read_text(encoding='utf-8')) if info_path.exists() else {}
        npz = cache / (f.stem + (f'.{a.limit}s' if a.limit else '') + '.npz')
        if not npz.exists():
            print(f'== analysing {f.name}', flush=True)
            if model is None:
                import torch
                device = a.device or ('cuda' if torch.cuda.is_available() else 'cpu')
                if device == 'cpu':
                    torch.set_num_threads(cpu_quota())
                batch = a.batch or (16 if device == 'cuda' else 1)
                model, labels = load_model(a.model_dir, device)
                print(f'PANNs on {device}, batch {batch}, {torch.get_num_threads()} CPU threads', flush=True)
            total = a.limit or info.get('duration') or 0
            probs = analyze(f, model, device, batch, total, a.limit)
            np.savez_compressed(npz, probs=probs, labels=np.array(labels))
        data = np.load(npz)
        probs, labels = data['probs'].astype(np.float32), [str(x) for x in data['labels']]
        markers = best_markers(info)
        found.append({'file': f, 'info': info, 'n': len(probs), 'markers': markers,
                      'segs': find_songs(probs, labels, markers, a)})
    keep_songs(found, a)

    # 2) name and cut them
    taken, made = set(), set()
    check_tsv = out / '_check.tsv'
    check = [line.partition('\t') for line in check_tsv.read_text(encoding='utf-8').splitlines()] \
        if check_tsv.exists() else None
    moved = {}  # songs renamed or dropped by this run: old file -> new file or None
    for r in found:
        f, info, markers, segs = r['file'], r['info'], r['markers'], r['segs']
        print(f'== {f.name}', flush=True)
        names = name_segments(segs, markers)
        single = not markers and r['n'] <= a.single_max and info.get('title')
        date = stream_date(f, info)
        songs = []
        for k, ((s, e), j) in enumerate(zip(segs, names), 1):
            name = markers[j][1] if j is not None else title_name(info['title']) if single else ''
            file = f'{date} {k:02d} {safe(name) or "未知"}'
            if file in taken:  # e.g. two clips uploaded the same day
                file += f' [{info.get("id") or f.stem[-12:]}]'
            taken.add(file)
            songs.append({'file': file + f.suffix,
                          'start': s, 'end': e, 'name': name, 'marker': markers[j][0] if j is not None else None})
        sung = sum(x['end'] - x['start'] for x in songs)
        print(f'   {len(songs)} songs, {sung / 60:.0f} of {r["n"] / 60:.0f} min, '
              f'{sum(x["marker"] is not None for x in songs)} named from {len(markers)} timestamps', flush=True)
        for x in songs:
            mark = f'  (道标 {mmss(x["marker"])})' if x['marker'] is not None else ''
            print(f'   {mmss(x["start"]):>7} - {mmss(x["end"]):>7}  {x["file"]}{mark}', flush=True)
        if a.dry_run or a.limit:
            continue

        # replace what an earlier run cut from this recording; a file a recording before it has just been
        # cut to (same day, numbers shifted) stays
        record = cache / (f.stem + '.songs.json')
        old = json.loads(record.read_text(encoding='utf-8'))['songs'] if record.exists() else []
        for x in old:
            if x['file'] not in made:
                (out / x['file']).unlink(missing_ok=True)
        for x in songs:
            cut(f, x['start'], x['end'], out / x['file'])
            made.add(x['file'])
        record.write_text(json.dumps({'source': f.name, 'songs': songs}, ensure_ascii=False, indent=1), encoding='utf-8')
        if check is not None and old:
            moved.update(moved_songs(old, songs))
            write_check_list(out / '_check.tsv', check, moved)

    if not a.dry_run and not a.limit:
        rows = ['file\tsource\tstart\tend\tname']
        for record in sorted(cache.glob('*.songs.json')):
            r = json.loads(record.read_text(encoding='utf-8'))
            rows += [f'{x["file"]}\t{r["source"]}\t{mmss(x["start"])}\t{mmss(x["end"])}\t{x["name"]}' for x in r['songs']]
        (out / '_songs.tsv').write_text('\n'.join(rows) + '\n', encoding='utf-8')
        print(f'{len(rows) - 1} songs in {out}', flush=True)


if __name__ == '__main__':
    main()
