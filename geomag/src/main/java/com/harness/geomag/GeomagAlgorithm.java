package com.harness.geomag;

public class GeomagAlgorithm {
    /**
     * Default fusion entrypoint: combines magnetometer/accelerometer/gyro to produce corrected magnetic vector
     */
    public static double[] fuse(double[] mag, double[] acc, double[] gyro) {
        // Very small default implementation delegating to FilterFusion
        return FilterFusion.defaultFusion(mag, acc, gyro);
    }
}
