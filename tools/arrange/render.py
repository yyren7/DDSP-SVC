"""
Renders a song through its sounds' plugins, one stem per part, and mixes the stems; or captures the state of a
plugin once its patch is loaded by hand.

    python render.py <song> [--parts flute,harp] [--sr 48000] [--block 512] [--force]
    python render.py --capture <library>/<sound>
    python render.py --repro <song> <part>

A part is rendered by a fresh instance of the library's plugin (library_map/<library>.yaml plugin:), restored to
the sound's saved state (state:, under library_map/), fed perform.events() offline with Pedalboard. The stem goes
to build/<song>/stems/<part>.wav beside <part>.key, the sha256 of everything the stem depends on (the events,
the plugin binary's size and time, the state, sample rate, block size, length): a part whose key is unchanged is
not rendered again, so a one-note edit renders one stem. A stem whose peak is under SILENT is an error: plugins
that fail to load their samples render silence without saying so.

The mix (build/<song>/<song>.wav) sums the stems with song.yaml mix: gain (dB) and pan (-1 left to 1 right,
constant power), then one gain to a peak of PEAK.

--capture opens the plugin's editor (restored to the saved state, if there is one); load the patch, close the
window, and the state is saved to the sound's state: file. --repro renders a part twice, each time from a fresh
instance, and compares: equal hashes, else the level of the difference (a plugin with its own randomness, such
as a round-robin counter, can only pass a null test).
"""
import argparse
import hashlib
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

import perform
from score import BUILD, LIBRARY_MAP, ScoreError, Song

SILENT = 10 ** (-80 / 20)  # peak below -80 dBFS: nothing came out
PEAK = 10 ** (-1 / 20)     # peak of the mix
TAIL = 3.0                 # seconds rendered after the last bar, for releases and reverb


def plugin_spec(song, part):
    lib, snd = song.parts[part]['sound'].split('/', 1)
    meta = song.library(lib)
    sound = meta['sounds'][snd]
    return Path(meta['plugin']), LIBRARY_MAP / sound['state'] if sound.get('state') else None, sound


def binary_id(path):
    """Size and modification time of the plugin's binary, so a plugin update renders again."""
    files = [path] if path.is_file() else sorted(path.rglob('*.vst3')) + sorted(path.rglob('*.dll'))
    files = [f for f in files if f.is_file()] or [path]
    return ';'.join(f'{f.name}:{f.stat().st_size}:{int(f.stat().st_mtime)}' for f in files if f.exists())


def load(plugin_path, state_path):
    from pedalboard import load_plugin
    if not plugin_path.exists():
        raise ScoreError(f'plugin not installed: {plugin_path}')
    p = load_plugin(str(plugin_path), initialization_timeout=30.0)
    if state_path is not None:
        if not state_path.exists():
            raise ScoreError(f'no saved state {state_path}: run render.py --capture first')
        p.raw_state = state_path.read_bytes()
    return p


def render_part(song, part, sr, block):
    plugin_path, state_path, sound = plugin_spec(song, part)
    evs = perform.events(song, part, for_sound=True)
    length = song.seconds(song.length_steps) + sound.get('tail', TAIL)
    p = load(plugin_path, state_path)
    t0 = time.perf_counter()
    audio = p(evs, duration=length, sample_rate=sr, num_channels=2, buffer_size=block, reset=True)
    return np.asarray(audio, dtype=np.float32), time.perf_counter() - t0


def stem_key(song, part, sr, block):
    plugin_path, state_path, sound = plugin_spec(song, part)
    h = hashlib.sha256()
    for t, data in perform.events(song, part, for_sound=True):
        h.update(f'{t:.9f}:'.encode() + bytes(data))
    h.update(binary_id(plugin_path).encode())
    if state_path is not None and state_path.exists():
        h.update(state_path.read_bytes())
    h.update(f'{sr}:{block}:{song.seconds(song.length_steps) + sound.get("tail", TAIL):.6f}'.encode())
    return h.hexdigest()


def db(x):
    return 20 * np.log10(max(float(x), 1e-12))


def mix(song, stems, sr, out):
    total = max(len(a) for a in stems.values())
    bus = np.zeros((total, 2), dtype=np.float64)
    settings = song.meta.get('mix') or {}
    for part, a in stems.items():
        m = settings.get(part, {})
        g = 10 ** (m.get('gain', 0) / 20)
        pan = float(m.get('pan', 0))
        theta = (pan + 1) * np.pi / 4
        lr = np.array([np.cos(theta), np.sin(theta)]) * np.sqrt(2)  # constant power, unity in the middle
        bus[:len(a)] += a * g * lr  # stems are (frames, 2)
    peak = np.abs(bus).max()
    bus *= PEAK / peak if peak > 0 else 1
    sf.write(out, bus.astype(np.float32), sr, subtype='FLOAT')
    return db(peak)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('song', nargs='?')
    ap.add_argument('part', nargs='?')
    ap.add_argument('--parts')
    ap.add_argument('--sr', type=int, default=48000)
    ap.add_argument('--block', type=int, default=512)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--capture', metavar='LIBRARY/SOUND')
    ap.add_argument('--repro', action='store_true')
    a = ap.parse_args()
    try:
        if a.capture:
            return capture(a.capture)
        song = Song(a.song)
        if a.repro:
            return repro(song, a.part, a.sr, a.block)
        render(song, a)
    except ScoreError as e:
        print(f'error: {e}')
        sys.exit(1)


def capture(ref):
    import yaml
    lib, snd = ref.split('/', 1)
    meta = yaml.safe_load((LIBRARY_MAP / f'{lib}.yaml').read_text(encoding='utf-8'))
    sound = meta['sounds'][snd]
    state = LIBRARY_MAP / sound['state']
    p = load(Path(meta['plugin']), state if state.exists() else None)
    print(f'{p.name}: load {sound.get("patch", "the patch")} in the window, then close it')
    p.show_editor()
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_bytes(p.raw_state)
    print(f'saved {len(p.raw_state)} bytes -> {state}')


def repro(song, part, sr, block):
    a, t1 = render_part(song, part, sr, block)
    b, t2 = render_part(song, part, sr, block)
    ha, hb = hashlib.sha256(a.tobytes()).hexdigest(), hashlib.sha256(b.tobytes()).hexdigest()
    print(f'{part}: {t1:.2f} s and {t2:.2f} s to render {a.shape[-1] / sr:.1f} s; peak {db(np.abs(a).max()):.1f} dBFS')
    if ha == hb:
        print('identical (sha256 ' + ha[:16] + ')')
    else:
        n = min(a.shape[-1], b.shape[-1])
        resid = db(np.abs(a[..., :n] - b[..., :n]).max())
        print(f'not identical; the difference peaks at {resid:.1f} dBFS' + (' (passes a -90 dBFS null test)'
                                                                         if resid < -90 else ''))


def render(song, a):
    import psutil
    out = BUILD / song.name / 'stems'
    out.mkdir(parents=True, exist_ok=True)
    parts = a.parts.split(',') if a.parts else [p for p in song.parts if song.parts[p].get('sound')]
    stems = {}
    proc = psutil.Process()
    for part in parts:
        if not song.events(part):
            continue
        wav, keyf = out / f'{part}.wav', out / f'{part}.key'
        key = stem_key(song, part, a.sr, a.block)
        if not a.force and wav.exists() and keyf.exists() and keyf.read_text() == key:
            stems[part] = sf.read(wav, dtype='float32', always_2d=True)[0]
            print(f'{part}: unchanged')
            continue
        audio, secs = render_part(song, part, a.sr, a.block)
        peak = np.abs(audio).max()
        if peak < SILENT:
            raise ScoreError(f'{part}: the plugin rendered silence (peak {db(peak):.0f} dBFS); is the patch loaded '
                             f'in its saved state, and can it find its samples?')
        sf.write(wav, audio.T, a.sr, subtype='FLOAT')
        keyf.write_text(key)
        stems[part] = audio.T
        rss = proc.memory_info().rss / 2 ** 20
        print(f'{part}: rendered in {secs:.2f} s, peak {db(peak):.1f} dBFS, process {rss:.0f} MB')
    if stems:
        peak = mix(song, stems, a.sr, BUILD / song.name / f'{song.name}.wav')
        print(f'mix: {len(stems)} stems, summed peak {peak:.1f} dBFS, brought to {db(PEAK):.0f} dBFS '
              f'-> {BUILD / song.name / (song.name + ".wav")}')


if __name__ == '__main__':
    main()
