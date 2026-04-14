package com.harness.geomag;

public class Evaluator {
    public static double rmse(double[] a, double[] b) {
        if (a == null || b == null) return Double.POSITIVE_INFINITY;
        int n = Math.min(a.length, b.length);
        double s = 0.0;
        for (int i=0;i<n;i++) {
            double d = a[i]-b[i]; s += d*d;
        }
        return Math.sqrt(s / Math.max(n,1));
    }
}
