package com.harness.geomag;

public class Calibration {
    public static double[] calibrate(double[] raw) {
        if (raw == null) return new double[]{0.0,0.0,0.0};
        // identity calibration for default
        return new double[]{raw[0], raw[1], raw[2]};
    }
}
