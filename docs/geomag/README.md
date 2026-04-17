Geomag module

This module provides a minimal geomagnetic algorithm scaffold used for development and testing.

Files:
- geomag/src/main/java/com/harness/geomag/* : core classes
- geomag/src/test/java/... : JUnit 5 tests

Notes:
- `mag` is the required 3-axis input for the current placeholder algorithm.
- `acc` and `gyro` remain optional placeholder channels until protocol details are frozen; if supplied, they must also be valid 3-axis vectors.
- Invalid, non-finite, or zero vectors fail fast with `IllegalArgumentException` instead of silently degrading to zero output.

Acceptance: tests run with Gradle (java plugin) and default fusion returns a normalized 3-element vector.
