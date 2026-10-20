"""
The stage folders that tools/prepare_dataset.py writes in speakers/<name>/work/, in pipeline order, for
the scripts that read them. Standard library only, so the review server can use it too; keep it in step
with UVR_STEPS in prepare_dataset.py.

Since 2026-10-20 the backing vocals come off before the reverb: 1_vocals -> 2_karaoke -> 3_dereverb.
"""
MIX = '0_input'
CHAIN = [('voc', '1_vocals'), ('kar', '2_karaoke'), ('derev', '3_dereverb')]  # (key, folder), in order
DIRS = {'mix': MIX, **dict(CHAIN)}
DRY_KEY = CHAIN[-1][0]  # the final dry vocals
DRY = DIRS[DRY_KEY]
STEPS = [(CHAIN[i][0], CHAIN[i + 1][0]) for i in range(len(CHAIN) - 1)]  # (input key, output key) per step
INPUT = {out: inp for inp, out in STEPS}  # step output key -> its input key
TAG = {'kar': 'kar', 'derev': 'dr'}  # a step's short name in measurement names (kar_drop, holes_dr_pm, ...)
CHAIN_ID = '>'.join(k for k, _ in CHAIN)  # stamped into results, so that results of another order are redone
