package com.harness.geomag;

public class FilterFusion {
    /**
     * Default simple fusion: returns magnetometer vector after basic preprocessing/calibration.
     * In prod this would be an AHRS/extended Kalman / complementary filter.
     * The placeholder accelerometer / gyro channels stay optional until protocol details freeze,
     * but if callers provide them they must already be valid 3-axis vectors.
     */
    public static double[] defaultFusion(double[] mag, double[] acc, double[] gyro) {
        VectorValidator.requireOptionalVector("acc", acc);
        VectorValidator.requireOptionalVector("gyro", gyro);
        double[] calibratedMag = Calibration.calibrate(mag);
        return Preprocessor.preprocess(calibratedMag);
    }
}
