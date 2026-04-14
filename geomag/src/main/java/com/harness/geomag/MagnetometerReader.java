package com.harness.geomag;

public class MagnetometerReader {
    // Stub: in real system this reads sensor streams; here provide helper to validate input
    public static double[] fromRaw(double x, double y, double z) {
        return new double[]{x, y, z};
    }
}
