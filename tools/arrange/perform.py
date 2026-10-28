"""
The performance of a score: the MIDI events a part sends, in seconds, for a General MIDI player or for the
sound library_map/ gives the part.

    events(song, part, for_sound=True)  -> [(seconds, bytes)]     what render.py feeds the plugin
    write_midi(song, path, for_sound)   -> one track per part      build/<song>/<song>.mid and render/<part>.mid

For a sound, each note's articulation (the note's own, else the part's art:, else the sound's default:) is
looked up in the sound's articulations: and, if missing, along score.ARTICULATIONS' fallback chain. What it maps
to is sent just before the note, and only when it changes: keyswitch: <pitch> (a short note KS_LEAD before),
cc: [<n>, <value>], program: <n>. leg notes are stretched by the sound's legato_overlap: (seconds) into the
next note, so legato patches hear the overlap they detect. The part's humanize: {time: ms, vel: n, seed: n} in
song.yaml moves every onset and velocity by a seeded random amount, the same on every build; chords move
together. The General MIDI version leaves keyswitches out and uses the part's program:.
"""
import random

import mido

from score import ARTICULATIONS, ScoreError, pitch_to_midi

KS_LEAD = 0.020      # seconds a keyswitch comes before its note
KS_LEN = 0.010       # seconds a keyswitch note is held
TICKS = 960          # MIDI file resolution, per beat
CC_STEP = 0.5        # steps between ramp points of a controller curve


def resolve_art(art, available):
    """The articulation a sound plays for art: art itself, else the first of its fallbacks it has."""
    if art in available:
        return art
    for alt in ARTICULATIONS.get(art, []):
        if alt in available:
            return alt
    return None


def note_events(song, part, for_sound=True):
    """[(on_s, off_s, midi, vel, art_played)] of a part, humanized, before keyswitches."""
    spec = song.parts[part]
    sound = song.sound(part) if for_sound else {}
    arts = sound.get('articulations', {})
    default = spec.get('art') or sound.get('default')
    hum = spec.get('humanize') or {}
    rng = random.Random(hum.get('seed', 0))
    jitter_t, jitter_v = hum.get('time', 0) / 1000.0, hum.get('vel', 0)
    overlap = sound.get('legato_overlap', 0.0)
    out, last_onset, shift = [], None, 0.0
    evs = song.events(part)
    for i, (step, n, sec) in enumerate(evs):
        if n.art and n.art not in ARTICULATIONS:
            raise ScoreError(f'{n.src}: unknown articulation {n.art!r} (score.ARTICULATIONS)')
        art = n.art or default
        played = resolve_art(art, arts) if arts else art
        if step != last_onset:  # notes struck together move together
            shift = rng.gauss(0, jitter_t / 2) if jitter_t else 0.0
            shift = max(-jitter_t, min(jitter_t, shift))
            last_onset = step
        vel = n.vel + (rng.randint(-jitter_v, jitter_v) if jitter_v else 0)
        on = max(0.0, song.seconds(step) + shift)
        off = song.seconds(step + n.dur) + shift
        if art == 'leg' and overlap and i + 1 < len(evs) and evs[i + 1][0] <= step + n.dur:
            off += overlap
        out.append((on, max(off, on + 0.005), n.midi, max(1, min(127, vel)), played))
    return out


def cc_curve(song, part):
    """[(seconds, cc, value)]: each controller's points, ramped linearly from one to the next."""
    out = []
    pts = song.cc_events(part)
    for i, (step, c, sec) in enumerate(pts):
        out.append((song.seconds(step), c.cc, c.value))
        if i + 1 < len(pts) and pts[i + 1][1].cc == c.cc:
            nstep, nxt = pts[i + 1][0], pts[i + 1][1]
            s, last = step + CC_STEP, c.value
            while s < nstep:
                v = round(c.value + (nxt.value - c.value) * float((s - step) / (nstep - step)))
                if v != last:
                    out.append((song.seconds(s), c.cc, v))
                    last = v
                s += CC_STEP
    return out


def events(song, part, for_sound=True, channel=0):
    """[(seconds, bytes)] of a part, sorted, with keyswitches and controllers."""
    sound = song.sound(part) if for_sound else {}
    arts = sound.get('articulations', {})
    msgs = []
    if not for_sound and 'program' in song.parts[part]:
        msgs.append((0.0, 0, mido.Message('program_change', channel=channel, program=song.parts[part]['program'])))
    current = None
    for on, off, midi, vel, art in note_events(song, part, for_sound):
        if for_sound and art != current and art in arts:
            how = arts[art] or {}
            t = max(0.0, on - KS_LEAD)
            if 'keyswitch' in how:
                ks = pitch_to_midi(how['keyswitch'])
                msgs.append((t, 1, mido.Message('note_on', channel=channel, note=ks, velocity=100)))
                msgs.append((t + KS_LEN, 0, mido.Message('note_off', channel=channel, note=ks)))
            if 'cc' in how:
                msgs.append((t, 1, mido.Message('control_change', channel=channel, control=how['cc'][0],
                                                value=how['cc'][1])))
            if 'program' in how:
                msgs.append((t, 1, mido.Message('program_change', channel=channel, program=how['program'])))
            current = art
        msgs.append((on, 2, mido.Message('note_on', channel=channel, note=midi, velocity=vel)))
        msgs.append((off, 0, mido.Message('note_off', channel=channel, note=midi)))
    for t, cc, v in cc_curve(song, part):
        msgs.append((t, 1, mido.Message('control_change', channel=channel, control=cc, value=v)))
    # at the same instant: note-offs, then controllers and keyswitches, then note-ons
    msgs.sort(key=lambda m: (m[0], m[1]))
    return [(t, m.bytes()) for t, _, m in msgs]


def _track(song, name, evs):
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage('track_name', name=name, time=0))
    sec_per_tick = 60.0 / song.tempo / TICKS
    last = 0
    for t, data in evs:
        tick = round(t / sec_per_tick)
        msg = mido.Message.from_bytes(data)
        msg.time = tick - last
        last = tick
        tr.append(msg)
    return tr


def write_midi(song, path, parts=None, for_sound=False):
    """A type 1 MIDI file: a tempo track, then one track per part on its own channel (drums on 10 in GM)."""
    mf = mido.MidiFile(type=1, ticks_per_beat=TICKS)
    head = mido.MidiTrack()
    head.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(song.tempo), time=0))
    head.append(mido.MetaMessage('time_signature', numerator=song.beats_per_bar, denominator=song.beat_unit, time=0))
    mf.tracks.append(head)
    ch = 0
    for part in parts or song.parts:
        drums = song.parts[part].get('drums', False)
        channel = 9 if drums and not for_sound else (0 if for_sound else ch)
        if not drums and not for_sound:
            ch += 1 + (ch == 8)  # skip channel 10
        mf.tracks.append(_track(song, song.parts[part].get('name', part), events(song, part, for_sound, channel)))
    path.parent.mkdir(parents=True, exist_ok=True)
    mf.save(path)
    return path
