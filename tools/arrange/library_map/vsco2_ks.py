"""
Writes keyswitched .sfz files into the VSCO 2 CE folder for the instruments it ships as one file per articulation,
so that a part can change articulation note by note like the -KS files that come with it:

    python library_map/vsco2_ks.py

Each Claude-<instrument>-KS.sfz holds the articulation files one after another, as the -KS files do: every
<global> becomes a <master> with sw_last=<its key>, and a first <global> sets the keyswitch range (from C1 up,
below every instrument's lowest note) and the default. Run it again after reinstalling VSCO 2 CE; vsco2.yaml
names the files and their keys.
"""
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
NAMES = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
FIRST_KS = 24  # C1

# instrument: [articulation file, ...] in keyswitch order from C1
KS = {
    'Oboe': ['OboeSusNV', 'OboeSusVib', 'OboeStac'],
    'Bassoon': ['BassoonSus', 'BassoonVib', 'BassoonStac'],
    'Piccolo': ['PiccoloSus', 'PiccoloStac'],
    'Trumpet': ['TrumpetSus', 'TrumpetSusVib', 'TrumpetStac'],
    'Trombone': ['TromboneSus', 'TromboneVib', 'TromboneStac'],
    'FHorn': ['FHornSus', 'FHornStac'],
    'Timpani': ['Timpani', 'TimpaniRolls'],
}


def key_name(n):
    return f'{NAMES[n % 12]}{n // 12 - 1}'


def build(root, files):
    out = [f'// Written by tools/arrange/library_map/vsco2_ks.py from {", ".join(files)}.\n',
           f'<global>\nsw_lokey={key_name(FIRST_KS)}\nsw_hikey={key_name(FIRST_KS + len(files) - 1)}\n'
           f'sw_default={key_name(FIRST_KS)}\n']
    for i, f in enumerate(files):
        text = (root / f'{f}.sfz').read_text(encoding='utf-8', errors='replace')
        if text.count('<global>') != 1:
            raise SystemExit(f'{f}.sfz: expected one <global>')
        sw = f'<master>\nsw_last={key_name(FIRST_KS + i)}\nsw_label={key_name(FIRST_KS + i).upper()} {f}\n'
        out.append(f'\n// ---- {f} ----\n' + re.sub(r'<global>', lambda m: sw, text))
    return ''.join(out)


def main():
    meta = yaml.safe_load((HERE / 'vsco2.yaml').read_text(encoding='utf-8'))
    root = Path(meta['root'])
    if not root.exists():
        sys.exit(f'VSCO 2 CE not found at {root}')
    for name, files in KS.items():
        path = root / f'Claude-{name}-KS.sfz'
        path.write_text(build(root, files), encoding='utf-8')
        print(f'{path.name}: ' + ', '.join(f'{key_name(FIRST_KS + i).upper()} {f}' for i, f in enumerate(files)))


if __name__ == '__main__':
    main()
