package com.harness.geomag;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class CalibrationTest {
    @Test
    public void identityCalibration() {
        double[] raw = new double[]{1.0,2.0,3.0};
        double[] c = Calibration.calibrate(raw);
        assertArrayEquals(raw, c);
    }
}
