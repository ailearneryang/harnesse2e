package com.harness.geomag;

public class Preprocessor {
    public static double[] preprocess(double[] vec) {
        double[] normalized = VectorValidator.requireVector("vec", vec);
        double norm = Math.sqrt(
                normalized[0] * normalized[0]
                        + normalized[1] * normalized[1]
                        + normalized[2] * normalized[2]);
        if (norm == 0.0d) {
            throw new IllegalArgumentException("vec must not be a zero vector");
        }
        return new double[]{
                normalized[0] / norm,
                normalized[1] / norm,
                normalized[2] / norm
        };
    }
}
