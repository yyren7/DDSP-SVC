# For each song: search karaoke-ish uploads and print those with 2+ parts or on/off words, with their part list.
import sys, re, json, time, urllib.request
sys.argv = [sys.argv[0], 'x']; exec(open('/root/autodl-tmp/covers/bsearch.py').read().split('kw = sys.argv[1]')[0])
SONGS = json.load(open('/root/autodl-tmp/covers/songs.json'))
WORD = re.compile(r'off ?vocal|on ?vocal|伴奏|双音轨|雙音軌|カラオケ|ニコカラ|卡拉|KTV|instrumental|消音', re.I)
for name, queries in SONGS.items():
    print(f'##### {name}')
    seen = set()
    for q in queries:
        try: r = search(q)
        except Exception as e: print('  search error', e); continue
        for v in (r.get('data') or {}).get('result') or []:
            if v['bvid'] in seen: continue
            seen.add(v['bvid']); t = re.sub('<[^>]+>', '', v['title'])
            if not WORD.search(t): continue
            try: pl = get('https://api.bilibili.com/x/player/pagelist?bvid=' + v['bvid'])['data']
            except Exception: pl = []
            parts = ' | '.join(f"P{p['page']} {p['duration']}s {p['part'][:40]}" for p in pl[:4])
            print(f"  {v['bvid']} {v['duration']:>6} play={v['play']:<7} {t[:70]}\n      {parts}")
        time.sleep(0.6)
