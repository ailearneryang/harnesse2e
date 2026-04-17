package com.harness.geomag;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class PreprocessorTest {
    @Test
    public void normalizeProducesUnitVector() {
        double[] v = new double[]{3.0, 0.0, 4.0};
        double[] p = Preprocessor.preprocess(v);
        double norm = Math.sqrt(p[0]*p[0]+p[1]*p[1]+p[2]*p[2]);
        assertTrue(Math.abs(norm - 1.0) < 1e-9);
    }

    @Test
    public void preprocessRejectsZeroVector() {
        IllegalArgumentException error = assertThrows(IllegalArgumentException.class,
                () -> Preprocessor.preprocess(new double[]{0.0, 0.0, 0.0}));
        assertTrue(error.getMessage().contains("zero vector"));
    }

    @Test
    public void preprocessRejectsNonFiniteInput() {
        IllegalArgumentException error = assertThrows(IllegalArgumentException.class,
                () -> Preprocessor.preprocess(new double[]{1.0, Double.NaN, 0.0}));
        assertTrue(error.getMessage().contains("non-finite"));
    }
}
