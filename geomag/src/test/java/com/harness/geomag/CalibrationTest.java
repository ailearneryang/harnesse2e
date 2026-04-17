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

    @Test
    public void calibrationReturnsDefensiveCopy() {
        double[] raw = new double[]{1.0, 2.0, 3.0};
        double[] calibrated = Calibration.calibrate(raw);
        raw[0] = 99.0;
        assertArrayEquals(new double[]{1.0, 2.0, 3.0}, calibrated);
    }

    @Test
    public void calibrationRejectsShortVector() {
        IllegalArgumentException error = assertThrows(IllegalArgumentException.class,
                () -> Calibration.calibrate(new double[]{1.0, 2.0}));
        assertTrue(error.getMessage().contains("exactly 3 elements"));
    }
}
