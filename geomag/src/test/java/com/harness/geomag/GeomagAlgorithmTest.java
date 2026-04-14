package com.harness.geomag;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class GeomagAlgorithmTest {
    @Test
    public void fuseReturnsVector() {
        double[] mag = MagnetometerReader.fromRaw(30.0, -5.0, 12.0);
        double[] acc = new double[]{0.0, 0.0, 9.81};
        double[] gyro = new double[]{0.0, 0.0, 0.0};
        double[] out = GeomagAlgorithm.fuse(mag, acc, gyro);
        assertNotNull(out);
        assertEquals(3, out.length);
    }
}
