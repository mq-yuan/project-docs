# Evaluation

Run fusion and mesh metrics on the ScanNet validation split:

```bash
uv run python src/fusion/losses.py --split val
```

The truncation schedule is implemented in [losses.py](../../src/fusion/losses.py). Check the
[fusion contract](../contracts/fusion-spec.md) before changing brick indexing.
