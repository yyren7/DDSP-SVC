"""
The re-singing test of the bake-off (README.md): SoulX-Singer (SVS) sings a Chinese song in hanamaru_hareru's voice
from the lyrics and melody of the original singer's dry lead, as SoulX-Singer's own preprocessing transcribes them
(Paraformer lyrics with word times, ROSVOT notes, RMVPE F0), prompted with a stretch of her own Chinese singing.
Nothing of the original singer's sound goes in, unlike a conversion.

    /root/autodl-tmp/conda_envs/bk/bin/python tools/bakeoff/svs.py prompt <her dry vocal>
    /root/autodl-tmp/conda_envs/bk/bin/python tools/bakeoff/svs.py sing <song>...

prompt: her dry vocal through the preprocessing (segments of up to PROMPT_MAX s); the segment of PROMPT_MIN to
        PROMPT_MAX s with the most sung characters becomes the prompt (svs/prompt.json, svs/prompt.wav).
sing:   the dry lead of each song of set/manifest.json (by its name, e.g. liangrenfen) through the preprocessing,
        then the whole song sung twice, following the original's F0 (melody) and its transcribed notes (score), into
        out/soulx_svs_melody/ and out/soulx_svs_score/ as song__<song>.wav, matched in loudness to the input.
The transcriptions are kept in svs/<song>/metadata.json; the authors advise correcting them by hand with their MIDI
editor for the best result, which this test does not do.
"""
import copy
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert  # noqa: E402  (soundfile in place of torchaudio's loader)
from make_set import match_level  # noqa: E402

B = convert.B
S = B / 'svs'
PROMPT_MIN, PROMPT_MAX = 8.0, 20.0  # seconds
HAN = re.compile(r'[一-鿿]')


def pipeline(audio, out, max_merge_s, again=False):
    """SoulX-Singer's metadata of a dry vocal (segments with words, notes and F0), kept in out/metadata.json and
    taken from there when it is already made, unless again."""
    from preprocess.pipeline import PreprocessPipeline
    if (out / 'metadata.json').exists() and not again:
        return json.loads((out / 'metadata.json').read_text(encoding='utf-8'))
    if out.exists():
        shutil.rmtree(out)
    PreprocessPipeline(device='cuda', language='Mandarin', save_dir=str(out), vocal_sep=False,
                       max_merge_duration=int(max_merge_s * 1000), midi_transcribe=True).run(
        audio_path=str(audio), language='Mandarin')
    return json.loads((out / 'metadata.json').read_text(encoding='utf-8'))


def prompt(path):
    path = Path(path).resolve()
    convert.enter('SoulX-Singer')
    segs = pipeline(path, S / f'prompt_{path.stem}', PROMPT_MAX)
    for s in segs:  # what the recogniser heard, to judge the prompt by (she sings some Chinese songs in Japanese)
        print(f'  {s["index"]} {(s["time"][1] - s["time"][0]) / 1000:.1f} s: {"".join(HAN.findall(s["text"]))}')

    def sung(seg):
        return len(HAN.findall(seg['text']))
    fits = [s for s in segs if PROMPT_MIN <= (s['time'][1] - s['time'][0]) / 1000 <= PROMPT_MAX]
    best = max(fits or segs, key=sung)
    x, sr = sf.read(str(path), dtype='float32', always_2d=True)
    a, b = (int(t / 1000 * sr) for t in best['time'])
    sf.write(str(S / 'prompt.wav'), x[a:b].mean(1), sr, subtype='PCM_16')
    (S / 'prompt.json').write_text(json.dumps([{**best, 'time': [0, best['time'][1] - best['time'][0]]}],
                                              ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'prompt: segment {best["index"]}, {(b - a) / sr:.1f} s, {sung(best)} characters: '
          f'{"".join(HAN.findall(best["text"]))}')


def sing(songs):
    convert.enter('SoulX-Singer')
    from cli.inference import build_model
    from soulxsinger.utils.data_processor import DataProcessor
    from soulxsinger.utils.file_utils import load_config
    man = {it['src_spk']: it for it in json.loads((B / 'set' / 'manifest.json').read_text(encoding='utf-8'))['items']
           if it['kind'] == 'song'}
    config = load_config('soulxsinger/config/soulxsinger.yaml')
    sr = config.audio.sample_rate
    targets = {s: pipeline(Path(man[s]['input']).resolve(), S / s, 60) for s in songs}
    model = build_model('pretrained_models/SoulX-Singer/model.pt', config, 'cuda', use_fp16=True)
    dp = DataProcessor(hop_size=config.audio.hop_size, sample_rate=sr,
                       phoneset_path='soulxsinger/utils/phoneme/phone_set.json', device='cuda')
    prompt_data = dp.process(json.loads((S / 'prompt.json').read_text(encoding='utf-8'))[0], str(S / 'prompt.wav'))
    for song, segs in targets.items():
        for control in ('melody', 'score'):
            y = np.zeros(int(segs[-1]['time'][1] / 1000 * sr), np.float32)
            for seg in segs:  # as cli/inference.py: each segment generated and put back at its time
                target = dp.process(copy.deepcopy(seg), None)  # process() rewrites the segment it is given
                with torch.no_grad():
                    g = model.infer({'prompt': prompt_data, 'target': target}, auto_shift=False, pitch_shift=0,
                                    n_steps=config.infer.n_steps, cfg=config.infer.cfg, control=control,
                                    use_fp16=True)
                g = g.squeeze().float().cpu().numpy()
                a = int(seg['time'][0] / 1000 * sr)
                n = min(len(g), len(y) - a)
                y[a:a + n] = g[:n]
            out = B / 'out' / f'soulx_svs_{control}'
            out.mkdir(parents=True, exist_ok=True)
            name = man[song]['name']
            sf.write(str(out / f'{name}.wav'), match_level(y, sr, man[song]['input']), sr, subtype='PCM_16')
            print(f'{song} {control}: {len(segs)} segments, {len(y) / sr:.0f} s', flush=True)


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ('prompt', 'sing'):
        sys.exit(__doc__)
    S.mkdir(parents=True, exist_ok=True)
    prompt(sys.argv[2]) if sys.argv[1] == 'prompt' else sing(sys.argv[2:])


if __name__ == '__main__':
    main()
