# Reproducibility

## Guarantees

Same **seed + configuration + schema version** yields:

```text
same initial population -> same mutations -> same design contents
-> same design IDs -> same evaluator results -> same Omega results
-> same archive -> same history -> same CLI output
```

This is enforced by:

1. `random.Random(seed)` — deterministic search RNG.
2. `design_id()` — SHA-256 content-addressed identity (128-bit) over serialized design contents with the
   design's own `id` excluded, keys sorted, `sort_keys=True`.
   - `parent_ids` participate, so lineage is embedded in child identity.
   - `architecture_schema_version` and `provenance` participate, so identity is bound to generator config.
3. Evaluator RNG seeded from `sha256(design.model_dump_json())` — deterministic once IDs are deterministic
   and archive succession is deterministic.
4. Deterministic selection (stable sort on Ω keys), deterministic archive ordering (Ω-sorted).
5. No Python built-in `hash()` for persistent identity (it is randomized per process).
6. No random UUIDs anywhere in the deterministic path.

## Verified by tests

`tests/test_reproducibility.py` and `tests/test_specification.py`:

| Test | Verifies |
| --- | --- |
| `test_same_seed_identical_populations` | two `SearchEngine(42)` -> identical IDs + identical content |
| `test_different_seed_different_populations` | seed 42 vs 43 -> different content/IDs, all IDs unique |
| `test_schema_version_and_provenance_deterministic` | every generated design carries schema v1 + stable provenance |
| `test_provenance_participates_in_design_id` | changing provenance changes the design ID |
| `test_evolution_reproducibility` | two independent seed-42 evolves -> identical child IDs/content |
| `test_cross_process_reproducibility` | two separate `python -c` subprocesses -> identical ID lists |
| `test_specification_is_deterministic` | same design -> byte-identical specification + hash |
| `test_cross_process_specification_hash_stable` | spec hash identical across subprocesses |
| plus archive/hash/writer tests | `tests/test_engine.py`, `tests/test_objective.py`, remaining spec tests |

## Configuration identity

`rnd_engine.reproducibility.configuration_fingerprint(search_config, objective_config, schema_version)`
is a stable SHA-256 fingerprint. It is stamped into every design's provenance
(`Design.provenance["configuration_fingerprint"]`) and thus into the design ID and specification hash.
Two runs can only collide on design IDs if the fingerprint AND the deterministic RNG sequence match.

## Reproducing a run

```powershell
# identical inputs across machines/processes:
rnd-engine --population 32 --generations 10 --seed 42
```

Run the CLI twice from a clean artifact state; the archive, history, and stdout are byte-for-byte identical.

## Cross-process / cross-version stability

- Serialize all JSON via `json.dumps(..., sort_keys=True, separators=(",", ":"))` — independent of dict ordering.
- All digests use SHA-256; no reliance on `hash()`/`id()`/str-of-tuple ordering.
- If the Design schema or generator changes, `ARCHITECTURE_SCHEMA_VERSION` / `SPECIFICATION_SCHEMA_VERSION` /
  `GENERATOR_VERSION` must be bumped so old identities are never silently reused.

## Boundary

- Determinism is guaranteed for the surrogate evaluation and the deterministic generation path.
- Hardware stages do not yet exist; when they arrive they will record their own tool/config/PDK versions and
  content hashes per artifact (Phase F/G/H/I). Determinism never licenses fabricated evidence.