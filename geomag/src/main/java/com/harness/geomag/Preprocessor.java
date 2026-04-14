package com.harness.geomag;

public class Preprocessor {
    public static double[] preprocess(double[] vec) {
        if (vec == null || vec.length < 3) return new double[]{0.0,0.0,0.0};
        // simple normalization placeholder
        double norm = Math.sqrt(vec[0]*vec[0] + vec[1]*vec[1] + vec[2]*vec[2]);
        if (norm == 0) return new double[]{0.0,0.0,0.0};
        return new double[]{vec[0]/norm, vec[1]/norm, vec[2]/norm};
    }
}
