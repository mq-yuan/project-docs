# neural-tsdf Documentation

Current work: [Status](status.md).

## Contracts

- [Fusion contract](contracts/fusion-spec.md) - coordinate frames, voxel brick layout and hash table limits.

## Guides

- [Evaluation](guides/benchmarking.md) - run fusion and mesh metrics on the ScanNet validation split.

## Findings

- [Voxel hashing load factor](findings/voxel-hashing.md) - Robin Hood hashing stays at 1.3 mean probes up to 0.70 occupancy; at 0.80 frame time doubles.
- [Truncation schedule](findings/truncation-schedule.md) - annealing truncation from 12 cm to 4 cm over the first 30% of frames raises ScanNet F-score from 0.81 to 0.87 at the same frame time.

## Records

- [Exp-009: Robin Hood vs. Cuckoo hashing](records/exp-009-robin-hood-vs-cuckoo.md)
- [Exp-012: Street-scale occupancy ceiling](records/exp-012-street-scale-occupancy.md)
- [Exp-016: Coarse-to-fine truncation](records/exp-016-coarse-to-fine-truncation.md)
