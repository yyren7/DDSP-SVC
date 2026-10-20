"""
Calibrate the line scores against the listener: the keep / exclude marks of the calibration page
(review_server.py, calib) train a logistic regression over the signal measurements of eval_lines.py and the
learned scores of score_lines.py, pooled over the speakers given.

    python tools/autodl/fit_lines.py <speaker dir>...

Prints how well each score alone agrees with the marks (AUC) and how well the fitted model does in
cross-validation, then writes the model to <speaker>/eval/line_model.json for each speaker. build_clips.py
(dataset clean) keeps the lines the model keeps. The marked lines were drawn more often from low score
bands (CALIB_BANDS); each mark is weighted by how common its band is, so the agreement and the hours
kept are those of all lines, not of the sample.
"""
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

REPO = Path(__file__).resolve().parent.parent.parent
FEEDBACK = REPO / '.autodl' / 'feedback.jsonl'
SIGNAL = ['score', 'kar_drop', 'kar_cut', 'dr_drop', 'vleak_low', 'vleak_mid', 'hvr_mid', 'hvr_low', 'unpitched',
          'tail', 'level', 'voiced', 'dur']
LEARNED = ['singmos', 'dns_ovrl', 'dns_sig', 'dns_bak', 'aes_pq', 'aes_ce', 'aes_cu', 'spk_cos',
           'f0_agree', 'f0_vdis', 'f0_jump', 'f0_octave', 'f0_high', 'rmvpe_voiced']
BANDS = [(0, 50), (50, 75), (75, 90), (90, 101)]  # the score bands of the calibration sample


def load_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()] if path.exists() else []


def table(spk):
    """{(song, k): merged measurements} of one speaker."""
    rows = {(m['song'], m['k']): dict(m) for m in load_jsonl(spk / 'eval' / 'lines.jsonl')}
    for r in load_jsonl(spk / 'eval' / 'lines_learned.jsonl'):
        if (r['song'], r['k']) in rows:
            rows[(r['song'], r['k'])].update(r)
    return rows


def marks(spk):
    """{(song, k): 1 keep / 0 exclude}, the latest mark per line; 拿不准 leaves a line out."""
    out = {}
    for e in load_jsonl(FEEDBACK):
        t = e.get('target', '')
        if e.get('speaker') != spk.name or not t.startswith('line:') or '#' not in t:
            continue
        song, k = t[5:].rsplit('#', 1)
        if e.get('text') in ('保留', '排除'):
            out[(song, int(k))] = 1 if e['text'] == '保留' else 0
        elif e.get('text') == '拿不准':
            out.pop((song, int(k)), None)
    return out


def band(score):
    return next(i for i, (lo, hi) in enumerate(BANDS) if lo <= score < hi)


def matrix(rows, feats, fill=None):
    X = np.array([[np.nan if r.get(f) is None else float(r[f]) for f in feats] for r in rows], dtype=np.float64)
    fill = np.nanmedian(X, axis=0) if fill is None else np.asarray(fill)
    X = np.where(np.isnan(X), fill, X)
    return X, fill


def keep_set(spk, threshold=None):
    """{(song, k)} of the lines the fitted model keeps (build_clips.py, dataset clean)."""
    model = json.loads((spk / 'eval' / 'line_model.json').read_text(encoding='utf-8'))
    rows = list(table(spk).values())
    X, _ = matrix(rows, model['features'], model['fill'])
    z = (X - model['mean']) / model['std']
    p = 1 / (1 + np.exp(-(z @ np.array(model['coef']) + model['intercept'])))
    t = model['threshold'] if threshold is None else threshold
    return {(r['song'], r['k']) for r, pi in zip(rows, p) if pi >= t}


def main():
    spks = [Path(d) for d in sys.argv[1:]]
    rows, y, w, who = [], [], [], []
    for spk in spks:
        tab, mk = table(spk), marks(spk)
        pop = np.bincount([band(r['score']) for r in tab.values()], minlength=len(BANDS)) / len(tab)
        got = [(tab[key], v) for key, v in mk.items() if key in tab]
        if not got:
            continue
        smp = np.bincount([band(r['score']) for r, _ in got], minlength=len(BANDS)) / len(got)
        for r, v in got:
            rows.append(r)
            y.append(v)
            w.append(pop[band(r['score'])] / smp[band(r['score'])])
            who.append(spk.name)
        print(f'{spk.name}: {len(got)} marked lines, {sum(v for _, v in got)} keep', flush=True)
    y, w = np.array(y), np.array(w)
    if len(y) < 20 or y.min() == y.max():
        sys.exit('too few marks (need at least 20, with both keep and exclude)')
    feats = [f for f in SIGNAL + LEARNED if any(r.get(f) is not None for r in rows)]
    X, fill = matrix(rows, feats)

    print('\nhow each score alone agrees with the marks (weighted AUC; 0.5 = chance, 1 = perfect):')
    for j, f in sorted(enumerate(feats), key=lambda t: -abs(roc_auc_score(y, X[:, t[0]], sample_weight=w) - .5)):
        a = roc_auc_score(y, X[:, j], sample_weight=w)
        print(f'  {f:13s} {max(a, 1 - a):.3f}  ({"higher" if a >= .5 else "lower"} = keep)')

    mean, std = X.mean(0), X.std(0) + 1e-9
    Z = (X - mean) / std
    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    best = None
    for C in (0.03, 0.1, 0.3, 1.0):
        p = np.zeros(len(y))
        for tr, te in cv.split(Z, y):
            m = LogisticRegression(C=C, max_iter=2000).fit(Z[tr], y[tr], sample_weight=w[tr])
            p[te] = m.predict_proba(Z[te])[:, 1]
        auc = roc_auc_score(y, p, sample_weight=w)
        if not best or auc > best[0]:
            best = (auc, C, p)
    auc, C, p = best
    # threshold: the best balanced accuracy of the cross-validated predictions
    def bacc(t):
        keep = p >= t
        return 0.5 * (np.average(keep[y == 1], weights=w[y == 1]) + np.average(~keep[y == 0], weights=w[y == 0]))
    t = max(np.arange(0.2, 0.81, 0.02), key=bacc)
    sig_auc = roc_auc_score(y, X[:, feats.index('score')], sample_weight=w)
    sig_acc = 0.5 * (np.average(X[y == 1, feats.index('score')] >= 75, weights=w[y == 1])
                     + np.average(X[y == 0, feats.index('score')] < 75, weights=w[y == 0]))
    print(f'\nsignal score alone: AUC {sig_auc:.3f}, balanced accuracy at 75 points {sig_acc:.3f}')
    print(f'fitted model (C={C}, 5-fold cross-validation): AUC {auc:.3f}, balanced accuracy {bacc(t):.3f} '
          f'at p >= {t:.2f}')
    m = LogisticRegression(C=C, max_iter=2000).fit(Z, y, sample_weight=w)
    print('weights (standardized features, + = keep):',
          ', '.join(f'{f} {c:+.2f}' for f, c in sorted(zip(feats, m.coef_[0]), key=lambda t: -abs(t[1]))[:12]))
    model = {'features': feats, 'fill': fill.tolist(), 'mean': mean.tolist(), 'std': std.tolist(),
             'coef': m.coef_[0].tolist(), 'intercept': float(m.intercept_[0]), 'threshold': float(t),
             'cv_auc': auc, 'cv_balanced_accuracy': bacc(t), 'marks': int(len(y))}
    for spk in spks:
        (spk / 'eval' / 'line_model.json').write_text(json.dumps(model, indent=1), encoding='utf-8')
        tab = table(spk)
        keep = keep_set(spk)
        hours = sum(r['end'] - r['start'] for key, r in tab.items() if key in keep) / 3600
        print(f'{spk.name}: model keeps {len(keep)} of {len(tab)} lines, {hours:.2f} h')


if __name__ == '__main__':
    main()
