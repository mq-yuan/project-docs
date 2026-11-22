# Fusion Contract

## Coordinate frames

- World and camera frames are right-handed with OpenCV camera axes (`+X` right, `+Y` down,
  `+Z` forward), in meters.
- The surface is the zero crossing of the TSDF; distances are positive in free space.

## Voxel hashing

- The volume is split into `8x8x8` voxel bricks indexed by signed `int32` brick coordinates.
- Hash keys and probing use integer arithmetic only; FP16 is allowed only for per-voxel payloads.
- Hash table occupancy stays at or below `0.70`
  ([voxel hashing load factor](../findings/voxel-hashing.md)).
