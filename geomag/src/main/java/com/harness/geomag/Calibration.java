package com.harness.geomag;

public class Calibration {
    public static double[] calibrate(double[] raw) {
        // identity calibration for default
        return VectorValidator.requireVector("raw", raw);
    }
}
