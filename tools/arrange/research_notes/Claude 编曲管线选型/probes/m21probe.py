import music21
from music21 import stream, key, scale, note, roman, chord, interval, analysis
print("music21", music21.__version__)
S = stream.Stream
for m in ["augmentOrDiminish","transpose","makeMeasures","makeNotation","chordify","analyze","quantize","scaleOffsets","scaleDurations"]:
    print("Stream."+m, hasattr(S, m))
print("retro/invert on Stream:", [m for m in dir(S) if any(k in m.lower() for k in ("retro","invert","reverse","mirror"))])
print("scale classes:", [c for c in dir(scale) if c.endswith("Scale")][:40])
k = key.Key("D", "dorian"); print("Key D dorian:", k, k.mode, [str(p) for p in k.pitches])
print("RomanNumeral V7 in C:", [str(p) for p in roman.RomanNumeral("V7", key.Key("C")).pitches])
print("romanNumeralFromChord:", roman.romanNumeralFromChord(chord.Chord(["G3","B3","D4","F4"]), key.Key("C")).figure)
print("harmony.ChordSymbol Cm7:", [str(p) for p in music21.harmony.ChordSymbol("Cm7").pitches])
s = stream.Stream([note.Note("C4"), note.Note("E4"), note.Note("G4")])
print("analyze key:", s.analyze("key"))
print("transpose by interval M2 ok:", [str(n.pitch) for n in s.transpose("M2").notes])
print("augment x2 durations:", [n.quarterLength for n in s.augmentOrDiminish(2).notes])
import music21.serial as ser
print("serial ToneRow transforms:", [m for m in dir(ser.ToneRow) if "Transformation" in m])
print("pitch.Pitch.transpose exists:", hasattr(music21.pitch.Pitch, "transpose"))
print("scale.getPitches DorianScale:", [str(p) for p in scale.DorianScale("D").getPitches("D4","D5")])
print("modules features/voiceLeading:", hasattr(music21, "voiceLeading"), hasattr(music21, "features"))
