# haru / yuusha: the lyrics against what Qwen3-ASR hears of the original, phrase by phrase, with the units that differ
import sys
sys.path.insert(0, '/root/autodl-tmp/DDSP-SVC/tools')
import diction as dc
C = '/root/autodl-tmp/covers'
asr = dc.Recogniser('Qwen/Qwen3-ASR-1.7B', 'Japanese')
for s in sys.argv[1:]:
    dry, _ = dc.load_mono(f'{C}/cand/{s}/dry.wav', dc.ASR_SR)
    spans = dc.phrases(dry, dc.ASR_SR)
    texts = asr([dc.cut(dry, dc.ASR_SR, sp) for sp in spans])
    heard = [dc.units(t, 'Japanese') for t in texts]
    lyr_text = dc.lyric_text(f'{C}/{s}/lyrics.lrc')
    refs = dc.references(dc.units(lyr_text, 'Japanese'), heard)
    print(f'##### {s}')
    for sp, t, h, r in list(zip(spans, texts, heard, refs))[:14]:
        if r is None:
            print(f'{sp[0]:6.1f} no lyrics | {t}'); continue
        ops = dc.align(r, h)
        print(f'{sp[0]:6.1f}-{sp[1]:5.1f} err {dc.errors(ops):2d}/{len(r):2d} | {t[:60]}')
        print('        ' + ' '.join(f'{a or "_"}>{b or "_"}' for a, b in ops if a != b)[:150])
