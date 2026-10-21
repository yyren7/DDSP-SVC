"""
More lines for the calibration page (review_server.py, calib), drawn where the keep rule fitted so far
(fit_lines.py, eval/line_model.json) is least sure: for most of them its keep probability lies between 0.4
and 0.8, where marks move the rule's threshold most; a few from each end keep the fit honest. Lines of the
earlier sample are left out (by time span: the lines were cut again since).

    python tools/autodl/calib_add.py <speaker dir>...

Appends the lines of STRATA to <speaker>/eval/calib.json (a copy of the file before is kept next to it).
Each added entry carries q, its chance of being drawn (lines drawn over lines in its probability band),
from which fit_lines.py weights its mark. The page lists them after the earlier lines; calib?todo=1 shows
the unmarked ones alone.
"""
import json
import random
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fit_lines  # noqa: E402
from stages import CHAIN_ID  # noqa: E402

STRATA = [(0.0, 0.4, 4), (0.4, 0.6, 7), (0.6, 0.8, 9), (0.8, 1.01, 5)]  # keep probability band, lines drawn


def overlaps(m, spans):
    """Whether line m shares at least half its span (IoU) with an earlier calibration line of its song."""
    return any(min(m['end'], e) - max(m['start'], s) >= 0.5 * (max(m['end'], e) - min(m['start'], s))
               for s, e in spans.get(m['song'], []))


def main():
    for d in sys.argv[1:]:
        spk = Path(d)
        path = spk / 'eval' / 'calib.json'
        old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
        spans, taken = {}, {(c['song'], c['k']) for c in old}
        for c in old:
            spans.setdefault(c['song'], []).append((c['start'], c['end']))
        tab = fit_lines.table(spk)
        p = fit_lines.probabilities(spk)
        rnd = random.Random(f'{spk.name}|calib|{len(old)}')
        new = []
        for lo, hi, n in STRATA:
            pool = [m for key, m in tab.items() if lo <= p[key] < hi]
            fresh = [m for m in pool if (m['song'], m['k']) not in taken and not overlaps(m, spans)]
            draw = rnd.sample(fresh, min(n, len(fresh)))
            new += [{'song': m['song'], 'k': m['k'], 'start': m['start'], 'end': m['end'],
                     'p': round(p[(m['song'], m['k'])], 3), 'q': len(draw) / len(pool), 'chain': CHAIN_ID} for m in draw]
            print(f'{spk.name}: keep probability {lo:.1f}-{min(hi, 1):.1f}: {len(pool)} lines, {len(draw)} drawn', flush=True)
        rnd.shuffle(new)
        if old:  # a copy, not a move: the review page draws a fresh sample when the file is missing
            shutil.copy(path, path.with_name(f'calib.json.{time.strftime("%Y%m%d-%H%M%S")}'))
        tmp = path.with_suffix('.part')
        tmp.write_text(json.dumps(old + new, ensure_ascii=False), encoding='utf-8')
        tmp.replace(path)
        print(f'{spk.name}: {len(new)} lines added, {len(old) + len(new)} in all', flush=True)


if __name__ == '__main__':
    main()
