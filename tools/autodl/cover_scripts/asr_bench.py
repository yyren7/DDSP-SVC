# Which recogniser hears the original singers' dry leads closest to the lyrics: unit error over each whole song
# (global alignment of all phrases against all lyrics), Qwen3-ASR-1.7B and, for Chinese, VocalParse
import sys
import time
sys.path.insert(0, '/root/autodl-tmp/DDSP-SVC/tools')
import diction as dc
C = '/root/autodl-tmp/covers'
SONGS = [('aini', 'Chinese'), ('haohaode', 'Chinese'), ('liangrenfen', 'Chinese'),
         ('haru', 'Japanese'), ('yuusha', 'Japanese'), ('idol', 'Japanese')]
MODELS = {'qwen3-asr': 'Qwen/Qwen3-ASR-1.7B', 'vocalparse': 'pymaster/VocalParse'}
clips = {}
for s, lang in SONGS:
    dry, _ = dc.load_mono(f'{C}/cand/{s}/dry.wav', dc.ASR_SR)
    spans = dc.phrases(dry, dc.ASR_SR)
    clips[s] = [dc.cut(dry, dc.ASR_SR, sp) for sp in spans]
    print(f'{s}: {len(spans)} phrases, {sum(b - a for a, b in spans):.0f} s sung')
for name, path in MODELS.items():
    for lang in ('Chinese', 'Japanese'):
        songs = [s for s, l in SONGS if l == lang]
        if name == 'vocalparse' and lang == 'Japanese':
            continue
        asr = dc.Recogniser(path, lang)
        for s in songs:
            t = time.time()
            texts = asr(clips[s])
            hyp = [u for x in texts for u in dc.units(x, lang)]
            lyr = dc.units(dc.lyric_text(f'{C}/{s}/lyrics.lrc'), lang)
            ops = dc.align(lyr, hyp)
            sub = sum(r is not None and h is not None and r != h for r, h in ops)
            dl = sum(h is None for r, h in ops)
            ins = sum(r is None for r, h in ops)
            print(f'{name:10s} {s:12s} lyrics {len(lyr):4d} heard {len(hyp):4d} | sub {sub:3d} del {dl:3d} ins {ins:3d} '
                  f'| sub/heard {sub / max(len(hyp), 1) * 100:4.1f}% | {time.time() - t:.0f} s | e.g. {texts[3][:40]!r}')
        del asr
        import torch, gc
        gc.collect(); torch.cuda.empty_cache()
