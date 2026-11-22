# Exp-012: Street-Scale Occupancy Ceiling

Conclusion: on street sequences with up to 1.2M active bricks, Robin Hood hashing holds 1.3
mean probes at 0.70 occupancy; at 0.80, probe chains exceed warp width and frame time doubles.

Setup: urban RGB-D sequence at 2 cm voxels; kernel [hash_grid.cu](../../src/fusion/hash_grid.cu).

| Peak occupancy | Mean probes | Frame time |
| --- | --- | --- |
| 0.70 | 1.3 | 8 ms |
| 0.80 | 2.1 | 16 ms |
