package com.harness.geomag;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class FilterFusionTest {
    @Test
    public void defaultFusionIsStable() {
        double[] mag = new double[]{10.0, 0.0, 0.0};
        double[] out = FilterFusion.defaultFusion(mag, null, null);
        assertNotNull(out);
        assertEquals(3, out.length);
        assertArrayEquals(new double[]{1.0, 0.0, 0.0}, out, 1e-9);
    }

    @Test
    public void defaultFusionRejectsInvalidPlaceholderAccVector() {
        IllegalArgumentException error = assertThrows(IllegalArgumentException.class,
                () -> FilterFusion.defaultFusion(new double[]{10.0, 0.0, 0.0}, new double[]{1.0}, null));
        assertTrue(error.getMessage().contains("acc"));
    }
}
