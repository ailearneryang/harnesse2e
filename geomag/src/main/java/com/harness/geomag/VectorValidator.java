package com.harness.geomag;

final class VectorValidator {
    static final int VECTOR_SIZE = 3;

    private VectorValidator() {
    }

    static double[] requireVector(String name, double[] vector) {
        if (vector == null) {
            throw new IllegalArgumentException(name + " must not be null");
        }
        if (vector.length != VECTOR_SIZE) {
            throw new IllegalArgumentException(name + " must contain exactly 3 elements");
        }
        double[] copy = new double[VECTOR_SIZE];
        for (int i = 0; i < VECTOR_SIZE; i++) {
            double value = vector[i];
            if (!Double.isFinite(value)) {
                throw new IllegalArgumentException(name + " contains non-finite value at index " + i);
            }
            copy[i] = value;
        }
        return copy;
    }

    static void requireOptionalVector(String name, double[] vector) {
        if (vector != null) {
            requireVector(name, vector);
        }
    }

    static double[] requireComponents(String name, double x, double y, double z) {
        return requireVector(name, new double[]{x, y, z});
    }
}
