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
    }
}
