package com.harness.geomag;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class GeomagAlgorithmTest {
    @Test
    public void fuseReturnsNormalizedVector() {
        double[] mag = MagnetometerReader.fromRaw(30.0, -5.0, 12.0);
        double[] acc = new double[]{0.0, 0.0, 9.81};
        double[] gyro = new double[]{0.0, 0.0, 0.0};
        double[] out = GeomagAlgorithm.fuse(mag, acc, gyro);
        assertNotNull(out);
        assertEquals(3, out.length);
        assertTrue(out[0] > 0.0);
        assertEquals(1.0, Math.sqrt(out[0] * out[0] + out[1] * out[1] + out[2] * out[2]), 1e-9);
    }

    @Test
    public void fuseRejectsMissingMagnetometer() {
        IllegalArgumentException error = assertThrows(IllegalArgumentException.class,
                () -> GeomagAlgorithm.fuse(null, null, null));
        assertTrue(error.getMessage().contains("raw"));
    }
}
