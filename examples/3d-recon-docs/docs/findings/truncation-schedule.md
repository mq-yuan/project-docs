# Truncation Schedule

Annealing the truncation band linearly from 12 cm to 4 cm over the first 30% of frames raises
ScanNet validation F-score from 0.81 (fixed 4 cm) to 0.87, at the same 8 ms frame time.

Scope: indoor RGB-D scans at 2 cm voxels; outdoor scenes are untested.

Evidence:

- [Exp-016: Coarse-to-fine truncation](../records/exp-016-coarse-to-fine-truncation.md)
- Schedule: [losses.py](../../src/fusion/losses.py)
