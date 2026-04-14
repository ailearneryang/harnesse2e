package com.harness.geomag;

public class FilterFusion {
    /**
     * Default simple fusion: returns magnetometer vector after basic preprocessing/calibration.
     * In prod this would be an AHRS/extended Kalman / complementary filter.
     */
    public static double[] defaultFusion(double[] mag, double[] acc, double[] gyro) {
        double[] m = Calibration.calibrate(mag == null ? new double[]{0,0,0} : mag);
        double[] p = Preprocessor.preprocess(m);
        return p;
    }
}
