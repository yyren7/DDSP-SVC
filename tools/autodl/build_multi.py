"""
A training set of several speakers for one model: the members' own datasets (build_clips.py) side by side
in the layout DDSP-SVC's preprocess.py reads speaker ids from, train/audio/<n>/ and val/audio/<n>/.

    python tools/autodl/build_multi.py <mix dir> <dataset> <speaker dir>...

<mix dir> is a speaker folder of its own (speakers/<mix>/, e.g. umi_pheebie): the set goes to its
data_<dataset>/, and features/train with configs/speakers/<mix>.yaml (n_spk = the number of members) make
its model in exp_<dataset>/. Speaker n is the n-th folder given, so the id stays the same for inference
(-id n, or a mix of them with --spk_mix_dict). The clips are hard links to the members' data_<dataset>/
(no second copy on the disk; the members are not touched), so build each member's set first.
"""
import os
import sys
from pathlib import Path


def main():
    mix, dataset, members = Path(sys.argv[1]), sys.argv[2], [Path(p) for p in sys.argv[3:]]
    if not members:
        sys.exit('give the speaker folders, in the order of their ids')
    out = mix / f'data_{dataset}'
    if out.exists() and any(out.rglob('*.wav')):
        sys.exit(f'{out} holds clips already; move it away to build it again')
    for n, spk in enumerate(members, 1):
        src = spk / f'data_{dataset}'
        for part in ('train', 'val'):
            clips = sorted((src / part / 'audio').glob('*.wav'))
            if not clips:
                sys.exit(f'{src / part / "audio"}: no clips; run clips@{spk.name}:{dataset} first')
            folder = out / part / 'audio' / str(n)
            folder.mkdir(parents=True, exist_ok=True)
            for f in clips:
                os.link(f, folder / f.name)
            print(f'{mix.name} {dataset}: speaker {n} = {spk.name}, {len(clips)} {part} clips', flush=True)


if __name__ == '__main__':
    main()
