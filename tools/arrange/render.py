"""
Renders a song through its sounds' plugins, one stem per part, and mixes the stems; or captures the state of a
plugin once its patch is loaded by hand.

    python render.py <song> [--parts flute,harp] [--sr 48000] [--block 512] [--force]
    python render.py --capture <library>/<sound>
    python render.py --repro <song> <part>
    python render.py --smoke <library>[/<sound>]

A part is rendered by a fresh instance of the library's plugin (library_map/<library>.yaml plugin:, and
plugin_name: when the file holds several), fed perform.events() offline with Pedalboard, after its state is set:
for a library with state_from: sfz the state is made here from the sound's patch: (an .sfz file under root:), so
there is nothing to capture; otherwise it is the sound's saved state: file under library_map/. init_timeout: is
how long Pedalboard feeds the plugin silence after loading it and again before each render, for plugins that load
their samples in the background (Kontakt); it costs that long per stem, so it is 0 unless needed (sfizz loads in
setState).

The stem goes to build/<song>/stems/<part>.wav beside <part>.key, the sha256 of everything the stem depends on
(the events, the plugin binary's size and time, the state or the .sfz file, sample rate, block size, length): a
part whose key is unchanged is not rendered again, so a one-note edit renders one stem. A stem whose peak is under
SILENT is an error: plugins that fail to load their samples render silence without saying so.

The mix (build/<song>/<song>.wav) sums the stems with song.yaml mix: gain (dB) and pan (-1 left to 1 right,
constant power), then one gain to a peak of PEAK.

--capture opens the plugin's editor (restored to the saved state, if there is one) while a thread renders a note
in the middle of the sound's range every CAPTURE_EVERY seconds, as a DAW would be playing: Spitfire's Kontakt
patches only initialise while audio is being processed, and a patch saved uninitialised renders silence ever
after. Load the patch (Kontakt: from its menu's Load), wait until it sounds (printed), close the window, and the
state is saved to the sound's state: file. --repro renders a part twice, each time from a fresh
instance, and compares: equal hashes, else the level of the difference (a plugin with its own randomness, such
as a round-robin counter, can only pass a null test). --smoke plays one note in the middle of each sound's range
in each of its articulations, SMOKE_GAP apart, into build/smoke/<library>_<sound>.wav to listen to, and prints
each one's level: short articulations should have died away at 0.4 s, long ones not.
"""
import argparse
import hashlib
import re
import struct
import sys
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

import perform
from score import BUILD, LIBRARY_MAP, ScoreError, Song, midi_to_pitch, pitch_to_midi

SILENT = 10 ** (-80 / 20)  # peak below -80 dBFS: nothing came out
PEAK = 10 ** (-1 / 20)     # peak of the mix
TAIL = 3.0                 # seconds rendered after the last bar, for releases and reverb
CAPTURE_EVERY = 2.0        # seconds between the notes played while --capture's window is open
SMOKE_GAP = 2.5            # seconds between the notes of --smoke, each 1.5 s long
JUCE_B64 = '.ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+'


def juce_b64decode(s):
    """JUCE MemoryBlock::fromBase64Encoding: '<size>.' then 6 bits a character, little-endian, its own alphabet."""
    size, chars = s.split('.', 1)
    n = sum(JUCE_B64.index(c) << (6 * i) for i, c in enumerate(chars))
    return n.to_bytes(int(size) + 1, 'little')[:int(size)]


def juce_b64encode(b):
    n = int.from_bytes(b, 'little')
    return f'{len(b)}.' + ''.join(JUCE_B64[(n >> (6 * i)) & 63] for i in range((len(b) * 8 + 5) // 6))


def sfizz_state(default, sfz):
    """A fresh sfizz instance's raw_state with the .sfz file put in. Pedalboard's raw_state is JUCE's
    copyXmlToBinary ('VC2!', the string's length, XML, NUL) of <VST3PluginState><IComponent>base64</IComponent>;
    sfizz's component state (SfizzVstState, version 5 in sfizz 1.2.3) begins with a uint64 version and the sfz path
    as an int32 length (counting the NUL) and the string."""
    if default[:4] != b'VC2!':
        raise ScoreError('sfizz state: not the JUCE XML format sfizz_state knows')
    xml = default[8:8 + struct.unpack('<I', default[4:8])[0]].decode()
    m = re.search(r'<IComponent>([^<]*)</IComponent>', xml)
    comp = juce_b64decode(m.group(1))
    version, n = struct.unpack('<Qi', comp[:12])
    if version != 5:
        raise ScoreError(f'sfizz state version {version}: sfizz_state knows version 5 (sfizz 1.2.3)')
    path = Path(sfz).as_posix().encode() + b'\0'
    comp = comp[:8] + struct.pack('<i', len(path)) + path + comp[12 + n:]
    data = (xml[:m.start(1)] + juce_b64encode(comp) + xml[m.end(1):]).encode()
    return b'VC2!' + struct.pack('<I', len(data)) + data + b'\0'


def plugin_spec(song, part):
    """The library entry and the sound entry of a part's sound."""
    lib, snd = song.parts[part]['sound'].split('/', 1)
    meta = song.library(lib)
    return meta, meta['sounds'][snd]


def binary_id(path):
    """Size and modification time of the plugin's binary, so a plugin update renders again."""
    files = [path] if path.is_file() else sorted(path.rglob('*.vst3')) + sorted(path.rglob('*.dll'))
    files = [f for f in files if f.is_file()] or [path]
    return ';'.join(f'{f.name}:{f.stat().st_size}:{int(f.stat().st_mtime)}' for f in files if f.exists())


def state_id(meta, sound):
    """What the state set on the plugin depends on: the .sfz file (path and text), or the saved state."""
    if meta.get('state_from') == 'sfz':
        sfz = Path(meta['root']) / sound['patch']
        return sfz.as_posix().encode() + (sfz.read_bytes() if sfz.exists() else b'')
    st = LIBRARY_MAP / sound['state'] if sound.get('state') else None
    return st.read_bytes() if st is not None and st.exists() else b''


def load(meta, sound, state=True):
    """A fresh instance of the library's plugin, with the sound's state unless state is False."""
    from pedalboard import load_plugin
    path = Path(meta['plugin'])
    if not path.exists():
        raise ScoreError(f'plugin not installed: {path}')
    kw = {'plugin_name': meta['plugin_name']} if meta.get('plugin_name') else {}
    p = load_plugin(str(path), initialization_timeout=float(meta.get('init_timeout', 0)), **kw)
    if not state:
        return p
    if meta.get('state_from') == 'sfz':
        sfz = Path(meta['root']) / sound['patch']
        if not sfz.exists():
            raise ScoreError(f'no such sfz file: {sfz}')
        p.raw_state = sfizz_state(p.raw_state, sfz)
    elif sound.get('state'):
        st = LIBRARY_MAP / sound['state']
        if not st.exists():
            raise ScoreError(f'no saved state {st}: run render.py --capture first')
        p.raw_state = st.read_bytes()
    return p


def render_part(song, part, sr, block):
    meta, sound = plugin_spec(song, part)
    evs = [(bytes(data), t) for t, data in perform.events(song, part, for_sound=True)]  # Pedalboard: (bytes, s)
    length = song.seconds(song.length_steps) + sound.get('tail', TAIL)
    p = load(meta, sound)
    t0 = time.perf_counter()
    audio = p(evs, duration=length, sample_rate=sr, num_channels=2, buffer_size=block, reset=True)
    return np.asarray(audio, dtype=np.float32), time.perf_counter() - t0


def stem_key(song, part, sr, block):
    meta, sound = plugin_spec(song, part)
    h = hashlib.sha256()
    for t, data in perform.events(song, part, for_sound=True):
        h.update(f'{t:.9f}:'.encode() + bytes(data))
    h.update(binary_id(Path(meta['plugin'])).encode())
    h.update(state_id(meta, sound))
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


def leave(code):
    """sfizz hangs the process when its DLL is unloaded at exit, so on Windows the process is ended without
    unloading anything (every file is written and closed by now)."""
    sys.stdout.flush()
    sys.stderr.flush()
    if sys.platform == 'win32':
        import ctypes
        k = ctypes.windll.kernel32
        k.TerminateProcess(k.GetCurrentProcess(), code)
    sys.exit(code)


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
    ap.add_argument('--smoke', metavar='LIBRARY[/SOUND]')
    a = ap.parse_args()
    code = 0
    try:
        if a.capture:
            capture(a.capture, a.sr, a.block)
        elif a.smoke:
            smoke(a.smoke, a.sr, a.block)
        elif a.repro:
            repro(Song(a.song), a.part, a.sr, a.block)
        else:
            render(Song(a.song), a)
    except ScoreError as e:
        print(f'error: {e}')
        code = 1
    except BaseException:
        import traceback
        traceback.print_exc()
        code = 1
    leave(code)


def capture(ref, sr, block):
    lib, snd = ref.split('/', 1)
    meta = yaml.safe_load((LIBRARY_MAP / f'{lib}.yaml').read_text(encoding='utf-8'))
    sound = meta['sounds'][snd]
    if meta.get('state_from') == 'sfz':
        print(f'{lib}: the state is made from the patch ({sound["patch"]}); there is nothing to capture')
        return
    state = LIBRARY_MAP / sound['state']
    p = load(meta, sound, state=state.exists())
    lo, hi = (pitch_to_midi(x) for x in sound['range'])
    note = (lo + hi) // 2
    stop, heard = threading.Event(), threading.Event()

    def play():
        while not stop.is_set():
            audio = np.asarray(p([(bytes([0x90, note, 90]), 0.05), (bytes([0x80, note, 0]), 1.0)],
                                 duration=CAPTURE_EVERY, sample_rate=sr, num_channels=2, buffer_size=block,
                                 reset=False))
            if not heard.is_set() and np.abs(audio).max() >= SILENT:
                heard.set()
                print(f'it sounds ({midi_to_pitch(note)}, {db(np.abs(audio).max()):.0f} dBFS): close the window',
                      flush=True)
            stop.wait(CAPTURE_EVERY * 0.9)

    player = threading.Thread(target=play, daemon=True)
    player.start()
    print(f'{p.name}: load {sound.get("patch", "the patch")} in the window, then close it once it sounds',
          flush=True)
    p.show_editor()
    stop.set()
    player.join()
    if not heard.is_set():
        print('warning: it never sounded while the window was open; the saved state may render silence')
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_bytes(p.raw_state)
    print(f'saved {len(p.raw_state)} bytes -> {state}')


def smoke(ref, sr, block):
    lib, _, only = ref.partition('/')
    meta = yaml.safe_load((LIBRARY_MAP / f'{lib}.yaml').read_text(encoding='utf-8'))
    out = BUILD / 'smoke'
    out.mkdir(parents=True, exist_ok=True)
    for name, sound in meta['sounds'].items():
        if only and name != only:
            continue
        lo, hi = (pitch_to_midi(x) for x in sound['range'])
        note, arts = (lo + hi) // 2, list(sound['articulations'])
        evs = []
        for i, art in enumerate(arts):
            t = 0.1 + i * SMOKE_GAP
            how = sound['articulations'][art] or {}
            if 'keyswitch' in how:
                ks = pitch_to_midi(how['keyswitch'])
                evs += [(bytes([0x90, ks, 100]), t - perform.KS_LEAD),
                        (bytes([0x80, ks, 0]), t - perform.KS_LEAD + perform.KS_LEN)]
            if 'cc' in how:
                evs.append((bytes([0xB0, *how['cc']]), t - perform.KS_LEAD))
            if 'program' in how:
                evs.append((bytes([0xC0, how['program']]), t - perform.KS_LEAD))
            evs += [(bytes([0x90, note, 90]), t), (bytes([0x80, note, 0]), t + 1.5)]
        p = load(meta, sound)
        audio = np.asarray(p(evs, duration=0.1 + len(arts) * SMOKE_GAP, sample_rate=sr, num_channels=2,
                             buffer_size=block, reset=True), dtype=np.float32)
        sf.write(out / f'{lib}_{name}.wav', audio.T, sr, subtype='FLOAT')
        env = np.abs(audio).max(0)
        cells = []
        for i, art in enumerate(arts):
            s = env[int((0.1 + i * SMOKE_GAP) * sr):][:2 * sr]
            if s.max() < SILENT:
                cells.append(f'{art} SILENT')
                continue
            at = lambda t: db(s[int(t * sr):int((t + 0.05) * sr)].max() / s.max())
            cells.append(f'{art} {db(s.max()):.0f} dBFS ({at(0.4):.0f} dB at 0.4 s, {at(1.6):.0f} at 1.6 s)')
        print(f'{name} at {midi_to_pitch(note)}: ' + '; '.join(cells))
    print(f'-> {out}')


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
