# Exp-016: Coarse-to-Fine Truncation

Conclusion: annealing truncation from 12 cm to 4 cm over the first 30% of frames raises
F-score from 0.81 to 0.87 at the same frame time.

Setup: ScanNet validation subset of 20 scenes at 2 cm voxels; schedule in
[losses.py](../../src/fusion/losses.py).

| Truncation | F-score | Frame time |
| --- | --- | --- |
| Fixed 4 cm | 0.81 | 8 ms |
| 12 cm to 4 cm over 30% of frames | 0.87 | 8 ms |
