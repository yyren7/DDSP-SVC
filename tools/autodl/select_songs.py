"""
The training songs of a speaker drawn from downloads/ that already hold one song per file (a song-stream
compilation downloaded part by part, an album of stream cuts), the way hanamaru_hareru's 190 were chosen
on 2026-10-22, without songsplit.

    python tools/autodl/select_songs.py <speaker dir> [--n 190] [--min-sec 120] [--max-sec 480] [--seed <name>] [--apply]

- Files are "<upload date> <video title> pNN <part title> [<id>_pN].<ext>" as the download job names them;
  a part title is the song (its trailing stream date, "26.10.10", is dropped). A file without parts is
  taken whole.
- Out: duets and group songs (another name joined with ×, &, feat., 合唱), medleys (串烧, メドレー), talk
  and intros, and songs shorter than --min-sec or longer than --max-sec.
- One take per song: titles compare without punctuation, spaces, case, 翻唱 / Take2 marks and a few
  traditional-simplified pairs; a title of 4 or more characters that is the start of another and at least
  60 % of it (a cut-off title), or 90 % similar, is the same song.
  The longest take stays.
- Of what is left, --n songs are drawn at random with a fixed seed (the speaker's name), so the choice can
  be made again.
Writes <speaker>/_selection.tsv (every file with its fate) and, with --apply, hard-links the chosen files
into raw_songs/ as "<upload date> NN <song>.<ext>" (NN the part number), like songsplit's names.
"""
import argparse
import difflib
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

NAME = re.compile(r'^(\d{8}) (.*?)(?: p(\d+) (.*?))? \[([A-Za-z0-9_]+)\]\.(\w+)$')
DATE_TAIL = re.compile(r'\s*\d{2}(?:\.\d{1,3}){1,2}\s*$')  # "26.10.10", also mistyped ones like "24.1.124"
OUT = re.compile(r'咩栗|MeUmy|×|&|feat\.?|ft\.|合唱|串烧|メドレー|medley|自我介绍|开场|结束|闲聊|杂谈|聊天|talk', re.I)
MARKS = re.compile(r'翻唱|take\s*\d|\(?\d+\)?$|【.*?】|（.*?）|\(.*?\)', re.I)
PUNCT = re.compile(r'[\s\W_]+', re.U)
TRAD = str.maketrans('樂種電戀愛麗時間說話讓這來為後國學會長發開關東車門們亞風雲龍鳥島夢歲與於淚聲應',
                     '乐种电恋爱丽时间说话让这来为后国学会长发开关东车门们亚风云龙鸟岛梦岁与于泪声应')
SIMILAR = 0.9
AUDIO = {'.m4a', '.mp3', '.opus', '.webm', '.ogg', '.flac', '.wav'}  # downloads/ also holds the .info.json files


def duration(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    try:
        return float(json.loads(out)['format']['duration'])
    except (ValueError, KeyError):
        return 0.0


def norm(title):
    t = DATE_TAIL.sub('', title)
    t = MARKS.sub('', t)
    return PUNCT.sub('', t).lower().translate(TRAD)


def same(a, b):
    """A cut title is the longer one's prefix and most of it (玫瑰 is not 玫瑰窃贼, 想见你 not 想见你想见你想见你)."""
    short, long_ = sorted((a, b), key=len)
    return a == b or (len(short) >= 4 and long_.startswith(short) and len(short) >= 0.6 * len(long_)) \
        or difflib.SequenceMatcher(None, a, b).ratio() >= SIMILAR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('speaker')
    ap.add_argument('--n', type=int, default=190)
    ap.add_argument('--min-sec', type=float, default=120)
    ap.add_argument('--max-sec', type=float, default=480)
    ap.add_argument('--seed')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    spk = Path(a.speaker)
    files = sorted(f for f in (spk / 'downloads').iterdir()
                   if f.is_file() and not f.name.startswith('_') and f.suffix.lower() in AUDIO)
    rows = []
    for f in files:
        m = NAME.match(f.name)
        if not m:
            rows.append(dict(file=f.name, fate='unparsed')); continue
        date, vtitle, part, ptitle, vid, ext = m.groups()
        title = DATE_TAIL.sub('', ptitle if ptitle else vtitle).strip()
        rows.append(dict(file=f.name, date=date, part=int(part or 1), title=title, key=norm(title), ext=ext,
                         sec=duration(f), fate=''))
    songs = [r for r in rows if r['fate'] != 'unparsed']
    for r in songs:
        if OUT.search(r['title']):
            r['fate'] = 'out: ' + OUT.search(r['title']).group(0)
        elif r['sec'] < a.min_sec:
            r['fate'] = f'short: {r["sec"]:.0f} s'
        elif r['sec'] > a.max_sec:
            r['fate'] = f'long: {r["sec"]:.0f} s'
    # one take per song: group by key, longest first, so the first of each group is the one kept
    groups = []
    for r in sorted((r for r in songs if not r['fate']), key=lambda r: -r['sec']):
        for g in groups:
            if same(g[0]['key'], r['key']):
                g.append(r); r['fate'] = 'repeat of ' + g[0]['title']; break
        else:
            groups.append([r])
    pool = [g[0] for g in groups]
    chosen = sorted(random.Random(a.seed or spk.name).sample(pool, min(a.n, len(pool))), key=lambda r: r['file'])
    for r in pool:
        r['fate'] = 'chosen' if r in chosen else 'not drawn'
    hours = sum(r['sec'] for r in chosen) / 3600
    print(f'{spk.name}: {len(files)} files, {len(songs)} songs; '
          f'{sum(r["fate"].startswith("out") for r in songs)} out, '
          f'{sum(r["fate"].startswith(("short", "long")) for r in songs)} off length, '
          f'{sum(r["fate"].startswith("repeat") for r in songs)} repeats; {len(pool)} distinct songs, '
          f'{len(chosen)} chosen, {hours:.1f} h', flush=True)
    with open(spk / '_selection.tsv', 'w', encoding='utf-8') as out:
        out.write('fate\tdate\tpart\tsec\ttitle\tfile\n')
        for r in rows:
            out.write('\t'.join(str(r.get(k, '')) for k in ('fate', 'date', 'part', 'sec', 'title', 'file')) + '\n')
    if not a.apply:
        return
    raw = spk / 'raw_songs'
    raw.mkdir(exist_ok=True)
    for r in chosen:
        d = r['date']
        dst = raw / f'{d[:4]}-{d[4:6]}-{d[6:]} {r["part"]:02d} {r["title"].replace("/", "_")}.{r["ext"]}'
        if not dst.exists():
            os.link(spk / 'downloads' / r['file'], dst)
    print(f'{len(chosen)} songs linked into {raw}', flush=True)


if __name__ == '__main__':
    main()
