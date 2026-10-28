import json, os, copy, subprocess, sys
from music21 import stream, note, chord, meter, key, tempo, instrument, dynamics, articulations, converter
out = sys.argv[1]
def build(change=False):
    sc = stream.Score()
    mel = stream.Part(); mel.insert(0, instrument.Flute()); mel.partName="Lead"
    mel.append(tempo.MetronomeMark(number=120)); mel.append(key.Key("D","dorian")); mel.append(meter.TimeSignature("4/4"))
    m = "D5 E5 F5 A5 | G5 F5 E5 C5 | D5 A4 B4 C5 | D5 . . ."
    for bar in m.split("|"):
        for tok in bar.split():
            if tok == ".": mel[-1].quarterLength += 1 if isinstance(mel[-1], note.Note) else 0; continue
            n = note.Note(tok, quarterLength=1); mel.append(n)
    ns = list(mel.recurse().notes)
    ns[0].articulations.append(articulations.Accent()); mel.insert(0, dynamics.Dynamic("mf"))
    if change: ns[5].pitch.nameWithOctave = "G5"; ns[5].articulations.append(articulations.Staccato())
    pad = stream.Part(); pad.insert(0, instrument.Piano()); pad.partName="Pad"
    for c in [["D4","F4","A4","C5"],["C4","E4","G4"],["G3","B3","D4","F4"],["D4","F4","A4"]]:
        pad.append(chord.Chord(c, quarterLength=4))
    bass = stream.Part(); bass.insert(0, instrument.ElectricBass()); bass.partName="Bass"
    for p in ["D2","C2","G2","D2"]:
        bass.append(note.Note(p, quarterLength=2)); bass.append(note.Note(p, quarterLength=2))
    for p in (mel, pad, bass): sc.insert(0, p)
    return sc
a, b = build(False), build(True)
fa = a.write("musicxml", fp=os.path.join(out,"v1.musicxml")); fb = b.write("musicxml", fp=os.path.join(out,"v2.musicxml"))
fm = a.write("midi", fp=os.path.join(out,"v1.mid"))
print("musicxml chars:", len(open(fa, encoding="utf-8").read()), " midi bytes:", os.path.getsize(fm))
# compact JSON note list
evs=[]
for p in a.parts:
    for n in p.recurse().notes:
        ps = [x.nameWithOctave for x in (n.pitches)]
        evs.append([p.partName, float(n.getOffsetInHierarchy(a)), float(n.quarterLength), ps])
js = json.dumps(evs, separators=(",",":")); print("compact json chars:", len(js))
abc = """X:1
T:probe
M:4/4
L:1/4
Q:1/4=120
K:Ddor
V:1 name="Lead"
!mf!!accent!d e f a|g f e c|d A B c|d4|]
V:2 name="Pad"
[DFAc]4|[CEG]4|[G,B,DF]4|[DFA]4|]
V:3 name="Bass" clef=bass
D,,2D,,2|C,,2C,,2|G,,2G,,2|D,,2D,,2|]
"""
print("hand ABC chars:", len(abc))
ly = r"""\version "2.24.0"
\score { << \new Staff \with {instrumentName="Lead"} { \tempo 4=120 \key d \dorian \time 4/4 d''4\mf-> e'' f'' a'' | g'' f'' e'' c'' | d'' a' b' c'' | d''1 \bar "|." }
\new Staff \with {instrumentName="Pad"} { <d' f' a' c''>1 | <c' e' g'>1 | <g b d' f'>1 | <d' f' a'>1 }
\new Staff \with {instrumentName="Bass"} { \clef bass d,2 d, | c, c, | g, g, | d, d, } >> \layout {} \midi {} }"""
print("hand LilyPond chars:", len(ly))
import pretty_midi
pm = pretty_midi.PrettyMIDI(fm)
print("pretty_midi version:", pretty_midi.__version__ if hasattr(pretty_midi,"__version__") else "?", "instruments:", [(i.name, i.program, len(i.notes)) for i in pm.instruments])
inst = pm.instruments[0]
print("Instrument attrs:", [x for x in ("notes","pitch_bends","control_changes","program","is_drum") if hasattr(inst,x)])
print("PrettyMIDI methods:", [m for m in ("get_piano_roll","get_tempo_changes","key_signature_changes","time_signature_changes","lyrics","adjust_times","synthesize","fluidsynth","get_chroma","estimate_tempo","get_downbeats","get_beats") if hasattr(pm,m)])
