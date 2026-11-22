# Exp-009: Robin Hood vs. Cuckoo Hashing

Conclusion: at 0.70 occupancy, Robin Hood hashing needs 1.3 mean probes with no failed
insertions; 2-choice Cuckoo hashing triggers eviction cascades on 18% of insertions.

Setup: ScanNet scenes `0000`, `0050`, `0084`; `8x8x8` bricks at 2 cm voxels;
kernel [hash_grid.cu](../../src/fusion/hash_grid.cu).

| Scheme at 0.70 occupancy | Mean probes | Insertions with evictions | Frame time |
| --- | --- | --- | --- |
| Robin Hood | 1.3 | 0% | 8 ms |
| 2-choice Cuckoo | 1.2 | 18% | 15 ms |
