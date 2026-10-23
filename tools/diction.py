"""
Diction repair of a converted lead vocal: the phrases the listener hears sung wrong are taken from another
conversion of the same dry lead, chosen by ear, and spliced in at the breaths around them, so that no phrase has
a seam inside.

    python tools/diction.py clips --cand cand/x --fixes x/diction_fixes.tsv -o review/x
    python tools/diction.py apply --cand cand/x --fixes x/diction_fixes.tsv -o fixed.wav
    python tools/diction.py cand --cand cand/x --model exp/model_40000.pt --seed 3 4 5

--cand is a folder of conversions of one dry lead (other random draws, other checkpoints), all on its timeline,
with the dry lead itself as dry.wav; the first by name is the one being fixed (--base names another). The fix
list is a TSV, one line per place the listener reports, under a line of column names (COLUMNS; a list without
it has those columns in that order):

  time        where it is heard in the mix, which has the timeline of the dry lead: 83, 1:23, 1:23.5, or a
              range 1:20-1:26 for a place longer than a phrase
  heard, want what it sounds like and what it should be: free text, for the record and the review page
  start, end  the seconds spliced, written by clips: the phrases the time falls in (the nearest one when it falls
              between two), from the middle of the breath before them to the middle of the breath after, at most
              EDGE beyond them; kept once written (edit them by hand to move a span), so that the same list
              splices the same again
  take        the candidate chosen, its file name without .wav; none when no candidate is right; the base when
              it was right after all; empty until chosen
  note        free text

clips writes each line's span, cut from dry.wav and from every conversion, into <out>/01/, <out>/02/, ... with
<out>/clips.json, which the review page plays (tools/autodl/review_server.py, 咬字修补) and whose buttons write the
listener's choice into the take column. When the candidates are not the ones of the last clips, the lines that
had none right wait for a choice again. apply splices every chosen take into the base, crossfaded over FADE at
the edges of its span; lines whose spans overlap must have chosen the same take. cand converts dry.wav once more
with each checkpoint and seed (torch.manual_seed before main_reflow.py), as <n>_<k>k_s<seed>.wav, for when no
candidate is right. clips and apply need numpy and soundfile only, cand the ddsp env (and the GPU).

auto (deprecated 2026-10-23, never used on a song): Qwen3-ASR picks the phrases and the takes, see auto().
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ASR_SR = 16000
MIN_GAP = 0.25     # seconds of quiet that end a phrase
MIN_PHRASE = 0.3   # seconds: shorter bursts join the nearest phrase
MAX_PHRASE = 20.0  # seconds: longer phrases are cut at their quietest frame
QUIET_DB = 35.0    # a frame is quiet this far under the loud end of the dry lead
FADE = 0.02        # seconds of crossfade at a splice
EDGE = 0.5         # seconds: the most of a breath a span of the fix list takes beyond its phrases
REF_FLOOR = 0.5    # a phrase whose original misses more than this share of its lyrics is judged against the original
COLUMNS = ('time', 'heard', 'want', 'start', 'end', 'take', 'note')  # of the fix list
NONE = 'none'      # the take of a line that no candidate is right for
DRY = 'dry.wav'    # the dry lead in a --cand folder
CAND_RUN = ("import sys, runpy, torch; torch.manual_seed(int(sys.argv[1])); sys.argv = ['main_reflow.py'] + "
            "sys.argv[2:]; runpy.run_path('main_reflow.py', run_name='__main__')")
CREDIT = re.compile(r'^\s*(作词|作詞|作曲|编曲|編曲|制作|製作|词|曲|演唱|歌|lyrics?|composer|arranger|producer)\s*[:：]', re.I)
SMALL_KANA = set('ゃゅょぁぃぅぇぉゎ')


def load_mono(path, sr=None):
    x, r = sf.read(str(path), dtype='float32', always_2d=True)
    return mono(x, r, sr)


def mono(x, r, sr=None):
    """Channels averaged, resampled to sr if given: (signal, rate)."""
    x = x.mean(axis=1)
    if sr and r != sr:
        import librosa
        x, r = librosa.resample(x, orig_sr=r, target_sr=sr), sr
    return x, r


def phrases(x, sr):
    """[(start, end)] in seconds of the sung phrases of a dry vocal, split at quiet stretches of MIN_GAP or more."""
    hop = int(0.01 * sr)
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    loud = db > np.percentile(db, 99) - QUIET_DB
    segs, i = [], 0
    while i < n:
        if not loud[i]:
            i += 1
            continue
        j = i
        while j < n and loud[j]:
            j += 1
        segs.append([i, j])
        i = j
    merged = []
    for s in segs:  # close the short gaps
        if merged and (s[0] - merged[-1][1]) * 0.01 < MIN_GAP:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    out = []
    for s in merged:  # bursts too short to be a phrase join the closer neighbour
        if (s[1] - s[0]) * 0.01 < MIN_PHRASE and out:
            out[-1][1] = s[1]
        else:
            out.append(s)
    final = []
    for a, b in out:
        while (b - a) * 0.01 > MAX_PHRASE:
            lo, hi = a + int(MAX_PHRASE * 50), a + int(MAX_PHRASE * 100)
            cut = lo + int(np.argmin(db[lo:hi]))
            final.append((a, cut))
            a = cut
        final.append((a, b))
    return [(a * 0.01, b * 0.01) for a, b in final]


def units(text, lang):
    """The sung units of a text: toneless pinyin syllables (Chinese), morae in hiragana (Japanese), lowercased
    words for Latin script; punctuation dropped."""
    out = []
    for tok in re.findall(r"[A-Za-z']+|[^\sA-Za-z']", text):
        if re.match(r"[A-Za-z']", tok):
            out.append(tok.lower().strip("'"))
        elif lang == 'Chinese':
            if '一' <= tok <= '鿿':
                from pypinyin import lazy_pinyin
                out += lazy_pinyin(tok)
        else:
            out += kana(tok)
    return [u for u in out if u]


_kks = None


def kana(text):
    """Morae of a Japanese text in hiragana (kanji read by pykakasi): small ゃゅょ and the like join the kana
    before them; っ and ー count as morae of their own."""
    global _kks
    if _kks is None:
        import pykakasi
        _kks = pykakasi.kakasi()
    hira = ''.join(p['hira'] for p in _kks.convert(text))
    out = []
    for ch in hira:
        if not ('ぁ' <= ch <= 'ゟ' or ch == 'ー'):
            continue
        if ch in SMALL_KANA and out:
            out[-1] += ch
        else:
            out.append(ch)
    return out


def align(ref, hyp):
    """Levenshtein alignment: [(ref unit or None, hyp unit or None)], equal units matched first."""
    n, m = len(ref), len(hyp)
    d = np.zeros((n + 1, m + 1), dtype=np.int32)
    d[:, 0], d[0, :] = np.arange(n + 1), np.arange(m + 1)
    for i in range(1, n + 1):
        r = ref[i - 1]
        for j in range(1, m + 1):
            d[i, j] = min(d[i - 1, j - 1] + (r != hyp[j - 1]), d[i - 1, j] + 1, d[i, j - 1] + 1)
    ops, i, j = [], n, m
    while i or j:
        if i and j and d[i, j] == d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            ops.append((ref[i - 1], hyp[j - 1]))
            i, j = i - 1, j - 1
        elif i and d[i, j] == d[i - 1, j] + 1:
            ops.append((ref[i - 1], None))
            i -= 1
        else:
            ops.append((None, hyp[j - 1]))
            j -= 1
    return ops[::-1]


def errors(ops):
    return sum(r != h for r, h in ops)


def lyric_text(path):
    lines = []
    for line in open(path, encoding='utf-8'):
        line = re.sub(r'\[[^\]]*\]', '', line).strip()
        if line and not CREDIT.match(line):
            lines.append(line)
    return ' '.join(lines)


def references(lyr, heard):
    """Each phrase's share of the lyrics: the lyrics' units from the first to the last that the global alignment
    matches to what is heard of the original singer in that phrase (None where none is)."""
    flat = [(p, u) for p, us in enumerate(heard) for u in us]
    ops = align(lyr, [u for _, u in flat])
    span = [[None, None] for _ in heard]
    li = hi = 0
    for r, h in ops:
        if r is not None and h is not None:
            p = flat[hi][0]
            span[p][0] = li if span[p][0] is None else span[p][0]
            span[p][1] = li
        li += r is not None
        hi += h is not None
    return [lyr[a:b + 1] if a is not None else None for a, b in span]


class Recogniser:
    """Qwen3-ASR, or a model fine-tuned from it with the same interface (VocalParse, whose lyrics come before
    <|file_sep|> and a score of pitch, note and tempo tokens)."""

    def __init__(self, model, lang):
        import torch
        from qwen_asr import Qwen3ASRModel
        self.lang = lang
        self.model = Qwen3ASRModel.from_pretrained(model, dtype=torch.bfloat16, device_map='cuda:0',
                                                   max_inference_batch_size=32, max_new_tokens=512)

    def __call__(self, clips):
        res = self.model.transcribe(audio=[(c, ASR_SR) for c in clips], language=[self.lang] * len(clips))
        return [re.sub(r'<(P|NOTE|BPM)_[^>]*>', '', r.text.split('<|file_sep|>')[0]) for r in res]


def cut(x, sr, span, pad=0.1):
    a, b = max(0, int((span[0] - pad) * sr)), min(len(x), int((span[1] + pad) * sr))
    return x[a:b]


def splice(base, other, sr, start, end):
    """`base` with [start, end) seconds taken from `other`, crossfaded over FADE at both edges (equal power)."""
    f = max(1, int(FADE * sr))
    a, b = max(0, int(start * sr)), min(len(base), int(end * sr))
    w = np.ones(b - a)
    k = min(f, (b - a) // 2)
    ramp = np.sin(np.linspace(0, np.pi / 2, k)) ** 2
    w[:k], w[len(w) - k:] = ramp, ramp[::-1]
    w = w.reshape(-1, *([1] * (base.ndim - 1)))
    out = base.copy()
    out[a:b] = np.sqrt(1 - w) * base[a:b] + np.sqrt(w) * other[a:b]
    return out


def seconds(text):
    """Seconds of 83, 83.5, 1:23 or 1:23.5 (a full-width colon too)."""
    s = 0.0
    for part in text.replace('：', ':').split(':'):
        s = s * 60 + float(part)
    return s


def when(text):
    """(from, to) seconds of a reported time: one moment, or a range like 1:20-1:26."""
    t = [seconds(p) for p in re.split(r'\s*[-–~～]\s*', text.strip())]
    return min(t), max(t)


def mmss(t):
    return f'{int(t // 60)}:{t % 60:04.1f}'


def slot(spans, t0, t1, total):
    """(start, end) seconds to splice for a report at t0..t1 among the phrases `spans` of a song `total` seconds
    long: the phrases it touches, or the nearest one when it falls between two, from the middle of the breath
    before them to the middle of the breath after, at most EDGE beyond them."""
    hit = [p for p, (a, b) in enumerate(spans) if a <= t1 and b >= t0]
    if not hit:
        mid = (t0 + t1) / 2
        hit = [min(range(len(spans)), key=lambda p: max(spans[p][0] - mid, mid - spans[p][1]))]
    p, q = hit[0], hit[-1]
    lo = spans[p - 1][1] if p else 0.0
    hi = spans[q + 1][0] if q + 1 < len(spans) else total
    return max((lo + spans[p][0]) / 2, spans[p][0] - EDGE), min((spans[q][1] + hi) / 2, spans[q][1] + EDGE)


def read_fixes(path):
    """(columns, lines) of a fix list, each line a dict over the columns, which gain those of COLUMNS they lack;
    blank lines are skipped, so the lines are numbered as the review page numbers them."""
    text = [line for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    head = text[0].split('\t') if text and text[0].split('\t')[0].strip() == 'time' else []
    head = [c.strip() for c in head]
    cols = head + [c for c in COLUMNS if c not in head]
    rows = [dict(zip(cols, [c.strip() for c in line.split('\t')] + [''] * len(cols))) for line in text[bool(head):]]
    return cols, rows


def write_fixes(path, cols, rows):
    path = Path(path)
    tmp = path.with_name(path.name + '.part')
    tmp.write_text(''.join('\t'.join(line) + '\n' for line in [cols] + [[r[c] for c in cols] for r in rows]),
                   encoding='utf-8')
    tmp.replace(path)


def candidates(folder):
    """{name: path} of the conversions in a --cand folder, in the order of their names (DRY is not one)."""
    return {f.stem: f for f in sorted(Path(folder).glob('*.wav')) if f.name != DRY and f.is_file()}


def base_of(conv, name):
    """The conversion being fixed: `name`, else the first by name."""
    if not conv:
        raise SystemExit('no conversions in --cand')
    if name and name not in conv:
        raise SystemExit(f'--base {name}: not one of {", ".join(conv)}')
    return name or next(iter(conv))


def excerpt(path, start, end):
    """[start, end) seconds of an audio file, reading only those from disk: (signal, rate)."""
    sr = sf.info(str(path)).samplerate
    x, _ = sf.read(str(path), start=int(start * sr), stop=int(end * sr), dtype='float32', always_2d=True)
    return x, sr


def clips(args):
    """The span of each line of the fix list that has none written into it, and every line's span cut from the
    dry lead and from every conversion into <out>/<line>/, with <out>/clips.json for the review page."""
    conv = candidates(args.cand)
    base = base_of(conv, args.base)
    takes = [k for k in conv if k != base]
    cols, rows = read_fixes(args.fixes)
    dry_path = Path(args.cand) / DRY
    dry, sr = load_mono(dry_path)
    spans, total = phrases(dry, sr), len(dry) / sr
    for n, r in enumerate(rows, 1):
        if not (r['start'] and r['end']):
            try:
                a, b = slot(spans, *when(r['time']), total)
            except ValueError:
                raise SystemExit(f'{args.fixes} line {n}: time {r["time"]!r} is none of 83, 1:23, 1:20-1:26')
            r['start'], r['end'] = f'{a:.2f}', f'{b:.2f}'
    out = Path(args.out)
    try:
        before = json.loads((out / 'clips.json').read_text(encoding='utf-8'))['takes']
    except (OSError, ValueError, KeyError):
        before = None
    if before is not None and set(before) != set(takes):  # new candidates: those that had none right get to choose
        for r in rows:
            r['take'] = '' if r['take'] == NONE else r['take']
    write_fixes(args.fixes, cols, rows)

    out.mkdir(parents=True, exist_ok=True)
    for old in out.iterdir():
        if old.is_dir() and old.name.isdigit():
            shutil.rmtree(old)
    sources = [('dry', dry_path)] + [(k, conv[k]) for k in [base] + takes]
    for n, r in enumerate(rows, 1):
        d = out / f'{n:02d}'
        d.mkdir()
        for name, path in sources:
            x, rate = excerpt(path, float(r['start']), float(r['end']))
            sf.write(str(d / f'{name}.flac'), np.clip(x, -1, 1), rate, subtype='PCM_24')
        print(f'{n:2d}. {r["time"]:>9}  {r["heard"]} -> {r["want"]}: {mmss(float(r["start"]))}-{mmss(float(r["end"]))}'
              f'{"  take " + r["take"] if r["take"] else ""}')
    man = {'fixes': str(Path(args.fixes).resolve()), 'base': base, 'takes': takes,
           'rows': [{'n': n, **{c: r[c] for c in ('time', 'heard', 'want', 'start', 'end')}}
                    for n, r in enumerate(rows, 1)]}
    tmp = out / 'clips.json.part'
    tmp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(out / 'clips.json')
    print(f'{out}: {len(rows)} lines, each cut from {DRY}, {base} and {len(takes)} candidates')


def apply(args):
    """The base with the take chosen for each line of the fix list spliced in over the line's span."""
    conv = candidates(args.cand)
    base = base_of(conv, args.base)
    _, rows = read_fixes(args.fixes)
    chosen, waiting = [], []
    for n, r in enumerate(rows, 1):
        if r['take'] in ('', NONE):
            waiting.append(n)
        elif r['take'] != base:
            if r['take'] not in conv:
                raise SystemExit(f'{args.fixes} line {n}: take {r["take"]!r} is not in {args.cand}')
            if not (r['start'] and r['end']):
                raise SystemExit(f'{args.fixes} line {n}: no span yet, run clips first')
            chosen.append((float(r['start']), float(r['end']), r['take'], n))
    groups = []  # [start, end, take, lines] of the spans to splice, those that overlap merged
    for a, b, take, n in sorted(chosen):
        if groups and a < groups[-1][1]:
            g = groups[-1]
            if take != g[2]:
                raise SystemExit(f'{args.fixes}: lines {g[3][0]} and {n} overlap, but chose {g[2]} and {take}')
            g[1] = max(g[1], b)
            g[3].append(n)
        else:
            groups.append([a, b, take, [n]])

    out, sr = sf.read(str(conv[base]), dtype='float32', always_2d=True)
    loaded = {}
    for a, b, take, lines in groups:
        if take not in loaded:
            x, r = sf.read(str(conv[take]), dtype='float32', always_2d=True)
            if r != sr or x.shape[1] != out.shape[1]:
                raise SystemExit(f'{conv[take]}: {r} Hz, {x.shape[1]} channels; {base} has {sr} Hz, {out.shape[1]}')
            loaded[take] = np.pad(x[:len(out)], ((0, max(0, len(out) - len(x))), (0, 0)))
        out = splice(out, loaded[take], sr, a, b)
        print(f'{mmss(a)}-{mmss(b)} from {take} (line {", ".join(map(str, lines))})')
    sf.write(args.out, out, sr, subtype='FLOAT')
    print(f'{args.out}: {len(groups)} spans of other takes in {base}'
          + (f'; lines {", ".join(map(str, waiting))} still wait for a take' if waiting else ''))


def cand(args):
    """dry.wav of the --cand folder converted once with each --model and --seed, as <n>_<k>k_s<seed>.wav numbered
    after the conversions there; one of the same checkpoint and seed already there is kept."""
    folder = Path(args.cand)
    have = candidates(folder)
    n = 1 + max((int(m.group(1)) for k in have if (m := re.match(r'(\d+)_', k))), default=-1)
    repo = Path(__file__).resolve().parent.parent
    for model in args.model:
        m = re.fullmatch(r'model_(\d+)', Path(model).stem)
        tag = f'{int(m.group(1)) / 1000:g}k' if m else Path(model).stem
        for seed in args.seed:
            name = f'{tag}_s{seed}'
            if any(k.split('_', 1)[-1] == name for k in have):
                print(f'{name}: there already')
                continue
            out = folder.resolve() / f'{n}_{name}.wav'
            subprocess.run([sys.executable, '-c', CAND_RUN, str(seed), '-i', str((folder / DRY).resolve()),
                            '-m', str(Path(model).resolve()), '-o', str(out), '-k', '0', '-id', str(args.spk_id)],
                           cwd=repo, check=True)
            print(out)
            n += 1


def auto(args):
    """Deprecated 2026-10-23, never used on a song: the listener finds the wrong phrases instead (clips), as the
    recogniser is not reliable enough: of the original singers themselves it gets 1-9% of the syllables wrong in
    the Chinese songs, 7-23% of the morae in the Japanese ones (tools/autodl/cover_scripts/asr_bench.py).

        python tools/diction.py auto --dry 3_dereverb/x.wav --lyrics x.lrc --lang Japanese \\
            --conv default.wav other.wav ... -o fixed.wav [--report fixed.json]

    The dry lead is cut into phrases at its breaths; Qwen3-ASR transcribes each phrase of the original singer and
    of every candidate conversion, and the transcriptions are compared with the lyrics as sung units: a Chinese
    syllable (toneless pinyin, the melody sets the tone), a Japanese mora (in hiragana, so that 君 and きみ are
    one), an English word. A phrase that the first conversion gets wrong in more units than the original singer
    does (the recogniser's own floor) is taken from the candidate that gets the most of it right, spliced in at
    the breaths around it.

    --conv are conversions of --dry (other random draws, other checkpoints), all as long as it, the first being
    the one to keep where nothing does better: list them in the order to prefer. The lyrics (LRC or plain text,
    credit lines dropped) are matched to what the recogniser hears of the original singer over the whole song, so
    a version with repeats or cuts against the published lyrics still lines up; a phrase whose original is far
    from its lyrics (an ad-lib, a line the lyrics do not have) is judged against the original singer's
    transcription. The lyrics are never given to the recogniser: as context they would make it hear them in a
    wrong conversion. Runs in the asr env (tools/autodl/setup_asr.sh)."""
    dry, _ = load_mono(args.dry, ASR_SR)
    spans = phrases(dry, ASR_SR)
    asr = Recogniser(args.model, args.lang)
    heard_orig = [units(t, args.lang) for t in asr([cut(dry, ASR_SR, s) for s in spans])]
    lyr = units(lyric_text(args.lyrics), args.lang)
    refs = references(lyr, heard_orig)

    convs = []
    for path in args.conv:
        x, sr = sf.read(path, dtype='float32', always_2d=True)
        convs.append((x, sr))
    sr = convs[0][1]
    heard = []
    for x, r in convs:
        m, _ = mono(x, r, ASR_SR)
        heard.append([units(t, args.lang) for t in asr([cut(m, ASR_SR, s) for s in spans])])

    out = convs[0][0]
    rows, fixed, left = [], 0, 0
    for p, span in enumerate(spans):
        ref, by = refs[p], 'lyrics'
        if not ref or errors(align(ref, heard_orig[p])) > REF_FLOOR * len(ref):
            ref, by = heard_orig[p], 'original'
        floor = errors(align(ref, heard_orig[p])) if by == 'lyrics' else 0
        errs = [errors(align(ref, h[p])) for h in heard]
        best = int(np.argmin(errs))  # the first of the best: the order of --conv is the preference
        if errs[best] < errs[0]:
            lo = spans[p - 1][1] if p else 0.0
            hi = spans[p + 1][0] if p + 1 < len(spans) else len(out) / sr
            out = splice(out, convs[best][0], sr, (lo + span[0]) / 2, (span[1] + hi) / 2)
            fixed += 1
        if errs[best] > floor:
            left += 1
        rows.append({'start': round(span[0], 2), 'end': round(span[1], 2), 'ref_by': by, 'ref': ' '.join(ref),
                     'original': ' '.join(heard_orig[p]), 'floor': floor,
                     'heard': [' '.join(h[p]) for h in heard], 'errors': errs, 'chosen': best,
                     'wrong': [[r, h] for r, h in align(ref, heard[best][p]) if r != h]})
    sf.write(args.out, out, sr, subtype='FLOAT')
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as fp:
            json.dump({'conv': args.conv, 'phrases': rows}, fp, ensure_ascii=False, indent=1)
    bad = sum(r['errors'][0] > r['floor'] for r in rows)
    print(f'{args.out}: {len(spans)} phrases, {bad} worse than the original singer in {args.conv[0]}, '
          f'{fixed} taken from another candidate, {left} still worse than the original')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    fixes = argparse.ArgumentParser(add_help=False)
    fixes.add_argument('--cand', required=True, help=f'folder of the conversions of a dry lead, which is {DRY} there')
    fixes.add_argument('--fixes', required=True, help='the fix list (TSV)')
    fixes.add_argument('--base', help='the conversion being fixed (default: the first by name)')

    p = sub.add_parser('clips', parents=[fixes], help="each line's span, cut from the dry lead and every conversion")
    p.add_argument('-o', '--out', required=True, help='folder of the clips and clips.json (the review page reads it)')
    p.set_defaults(run=clips)
    p = sub.add_parser('apply', parents=[fixes], help='the chosen takes spliced into the base')
    p.add_argument('-o', '--out', required=True, help='WAV')
    p.set_defaults(run=apply)
    p = sub.add_parser('cand', help='more conversions of the dry lead, with other checkpoints and seeds')
    p.add_argument('--cand', required=True, help=f'folder of the conversions, with the dry lead as {DRY}')
    p.add_argument('--model', required=True, nargs='+', help='checkpoints (model_<step>.pt)')
    p.add_argument('--seed', required=True, type=int, nargs='+')
    p.add_argument('--spk-id', default='1', help="the model's speaker id (main_reflow.py -id)")
    p.set_defaults(run=cand)
    p = sub.add_parser('auto', help='deprecated: Qwen3-ASR picks the phrases and the takes',
                       description=auto.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--dry', required=True, help="the original singer's dry lead that was converted")
    p.add_argument('--lyrics', required=True, help='LRC or plain text')
    p.add_argument('--lang', required=True, choices=('Chinese', 'Japanese'))
    p.add_argument('--conv', required=True, nargs='+', help='conversions of --dry, the one to keep first')
    p.add_argument('-o', '--out', required=True)
    p.add_argument('--report', help='JSON of every phrase: lyrics, what is heard in each file, the choice')
    p.add_argument('--model', default='Qwen/Qwen3-ASR-1.7B')
    p.set_defaults(run=auto)
    args = ap.parse_args()
    args.run(args)


if __name__ == '__main__':
    main()
