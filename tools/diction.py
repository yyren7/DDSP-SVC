"""
Diction check and repair of a converted lead vocal. The dry lead is cut into phrases at its breaths; Qwen3-ASR
transcribes each phrase of the original singer and of every candidate conversion, and the transcriptions are
compared with the lyrics as sung units: a Chinese syllable (toneless pinyin, the melody sets the tone), a
Japanese mora (in hiragana, so that 君 and きみ are one), an English word. A phrase that the first conversion
gets wrong in more units than the original singer does (the recogniser's own floor) is taken from the candidate
that gets the most of it right, spliced in at the breaths around it, so that no phrase has a seam inside.

    python tools/diction.py --dry 3_dereverb/x.wav --lyrics x.lrc --lang Japanese \
        --conv default.wav other.wav ... -o fixed.wav [--report fixed.json]

--conv are conversions of --dry (other random draws, other checkpoints), all as long as it, the first being the
one to keep where nothing does better: list them in the order to prefer. The lyrics (LRC or plain text, credit
lines dropped) are matched to what the recogniser hears of the original singer over the whole song, so a
version with repeats or cuts against the published lyrics still lines up; a phrase whose original is far from
its lyrics (an ad-lib, a line the lyrics do not have) is judged against the original singer's transcription.
The lyrics are never given to the recogniser: as context they would make it hear them in a wrong conversion.
Runs in the asr env (tools/autodl/setup_asr.sh).
"""
import argparse
import json
import re

import numpy as np
import soundfile as sf

ASR_SR = 16000
MIN_GAP = 0.25     # seconds of quiet that end a phrase
MIN_PHRASE = 0.3   # seconds: shorter bursts join the nearest phrase
MAX_PHRASE = 20.0  # seconds: longer phrases are cut at their quietest frame
QUIET_DB = 35.0    # a frame is quiet this far under the loud end of the dry lead
FADE = 0.02        # seconds of crossfade at a splice
REF_FLOOR = 0.5    # a phrase whose original misses more than this share of its lyrics is judged against the original
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry', required=True, help="the original singer's dry lead that was converted")
    ap.add_argument('--lyrics', required=True, help='LRC or plain text')
    ap.add_argument('--lang', required=True, choices=('Chinese', 'Japanese'))
    ap.add_argument('--conv', required=True, nargs='+', help='conversions of --dry, the one to keep first')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--report', help='JSON of every phrase: lyrics, what is heard in each file, the choice')
    ap.add_argument('--model', default='Qwen/Qwen3-ASR-1.7B')
    args = ap.parse_args()

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


if __name__ == '__main__':
    main()
