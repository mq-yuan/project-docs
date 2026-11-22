# Voxel Hashing Load Factor

Robin Hood open addressing stays at 1.3 mean probes per lookup up to 0.70 table occupancy. At
0.80 occupancy, probe chains grow past warp width and frame time doubles from 8 ms to 16 ms.
2-choice Cuckoo hashing is not usable at 0.70: 18% of insertions trigger eviction cascades.

Scope: `8x8x8` bricks at 2 cm voxels, up to 1.2M active bricks.

Evidence:

- [Exp-009: Robin Hood vs. Cuckoo hashing](../records/exp-009-robin-hood-vs-cuckoo.md)
- [Exp-012: Street-scale occupancy ceiling](../records/exp-012-street-scale-occupancy.md)
- Kernel: [hash_grid.cu](../../src/fusion/hash_grid.cu)
