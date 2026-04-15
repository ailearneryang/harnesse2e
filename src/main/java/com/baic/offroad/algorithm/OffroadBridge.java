package com.baic.offroad.algorithm;

import android.util.Log;

import com.baic.offroad.model.CalibrationData;
import com.baic.offroad.model.InstallationConfig;
import com.baic.offroad.util.OffroadLog;

/**
 * JNI 桥接层 — Java ↔ C++ 数据传递通道。
 *
 * Java 侧使用 float[] 数组传递传感器原始数据，避免频繁对象创建。
 * C++ 侧返回固定长度 float[] 结果数组，由 Java 侧解包为 OffroadDataBundle。
 * JNI 调用在 AlgorithmScheduler 的专用计算线程上执行。
 *
 * 需求追溯: architecture.md §6.2 桥接契约
 */
public class OffroadBridge {

    private static final String LIB_NAME = "offroad";
    private static boolean nativeLoaded = false;

    /** JNI 结果数组长度: 12个输出字段 */
    public static final int RESULT_ARRAY_SIZE = 12;

    /**
     * 加载 native 库 (liboffroad.so)。
     * 需求追溯: architecture.md §11.1 步骤7
     */
    public static synchronized boolean loadLibrary() {
        if (nativeLoaded) return true;
        try {
            System.loadLibrary(LIB_NAME);
            nativeLoaded = true;
            Log.i(OffroadLog.TAG_ALGORITHM, "liboffroad.so loaded successfully");
            return true;
        } catch (UnsatisfiedLinkError e) {
            Log.e(OffroadLog.TAG_ALGORITHM, "Failed to load liboffroad.so", e);
            // 降级: 使用 Java 侧 fallback 实现
            nativeLoaded = false;
            return false;
        }
    }

    public static boolean isNativeLoaded() {
        return nativeLoaded;
    }

    // ---- Native 方法声明 ----

    /**
     * 初始化 C++ 算法引擎。
     * @param iccMatrix ICC安装姿态矩阵 float[9]
     * @param imuMatrix IMU布置姿态矩阵 float[9]
     * @param filterWindow 大气压力滤波窗口大小
     * @return 0=成功, 负值=错误码
     */
    public static native int nativeInit(float[] iccMatrix, float[] imuMatrix, int filterWindow);

    /**
     * 执行一次算法计算。
     * @param sensorInput 传感器输入 float[16] (SensorInputFrame.toFloatArray())
     * @param result 输出结果 float[12] (由调用方分配，避免每帧创建)
     * @return 0=成功, 负值=错误码
     */
    public static native int nativeCompute(float[] sensorInput, float[] result);

    /**
     * 执行清零标定。
     * @param tiltOffset 当前倾斜角(用于计算补偿值)
     * @param pitchOffset 当前俯仰角(用于计算补偿值)
     * @return 0=成功, 负值=错误码
     */
    public static native int nativeCalibrate(float tiltOffset, float pitchOffset);

    /**
     * 应用清零补偿值。
     * @param tiltOffset 倾斜角补偿值
     * @param pitchOffset 俯仰角补偿值
     * @return 0=成功
     */
    public static native int nativeApplyCalibration(float tiltOffset, float pitchOffset);

    /**
     * 释放 C++ 算法引擎资源。
     */
    public static native void nativeDestroy();

    // ---- Java Fallback 实现 (native 库未加载时使用) ----

    /**
     * Java fallback 初始化。
     * 当 liboffroad.so 加载失败时提供基本功能。
     */
    public static int fallbackInit(InstallationConfig config) {
        Log.w(OffroadLog.TAG_ALGORITHM, "Using Java fallback algorithm (native lib not loaded)");
        return 0;
    }

    /**
     * Java fallback 计算。
     * 提供基础的传感器数据直通(无高级算法)。
     */
    public static int fallbackCompute(float[] sensorInput, float[] result) {
        if (sensorInput == null || result == null || result.length < RESULT_ARRAY_SIZE) {
            return -1;
        }

        // 简单的加速度→角度转换 (用于 native 库加载失败的降级场景)
        float accelX = sensorInput[0];
        float accelY = sensorInput[1];
        float accelZ = sensorInput[2];

        // 倾斜角: atan2(accelY, accelZ) (简化计算，无安装姿态补偿)
        float tiltRad = (float) Math.atan2(accelY, accelZ);
        float tiltDeg = (float) Math.toDegrees(tiltRad);

        // 俯仰角: atan2(-accelX, sqrt(accelY^2 + accelZ^2))
        float pitchRad = (float) Math.atan2(-accelX,
                Math.sqrt(accelY * accelY + accelZ * accelZ));
        float pitchDeg = (float) Math.toDegrees(pitchRad);

        boolean tiltValid = Math.abs(tiltDeg) <= 40.0f;
        boolean pitchValid = Math.abs(pitchDeg) <= 60.0f;

        // 大气压力直通
        float rawPressure = sensorInput[10];
        boolean pressureInputValid = sensorInput[11] > 0.5f;
        boolean pressureValid = pressureInputValid
                && rawPressure >= 300.0f && rawPressure <= 1100.0f;

        // 海拔: 基于标准大气压公式 (简化版)
        // h = 44330 * (1 - (P/P0)^(1/5.255))  P0=1013.25hPa
        float altitude = 0.0f;
        boolean altitudeValid = false;
        if (pressureValid) {
            altitude = 44330.0f * (1.0f - (float) Math.pow(rawPressure / 1013.25, 1.0 / 5.255));
            altitudeValid = altitude >= -500.0f && altitude <= 9000.0f;
        }

        // 指南针: 使用 GPS 航向
        float gpsBearing = sensorInput[7];
        boolean gpsValid = sensorInput[9] > 0.5f;
        int direction = -1;
        float compassAngle = 0.0f;
        boolean compassValid = gpsValid;
        if (gpsValid) {
            compassAngle = ((gpsBearing % 360.0f) + 360.0f) % 360.0f;
            direction = angleToDirection(compassAngle);
        }

        // 填充结果数组
        result[0] = tiltDeg;
        result[1] = tiltValid ? 1.0f : 0.0f;
        result[2] = pitchDeg;
        result[3] = pitchValid ? 1.0f : 0.0f;
        result[4] = rawPressure;
        result[5] = pressureValid ? 1.0f : 0.0f;
        result[6] = altitude;
        result[7] = altitudeValid ? 1.0f : 0.0f;
        result[8] = direction;
        result[9] = compassValid ? 1.0f : 0.0f;
        result[10] = compassAngle;
        result[11] = compassValid ? 1.0f : 0.0f;

        return 0;
    }

    /**
     * 角度转8方位编码。
     * 需求追溯: data_model.md §2.1 方向枚举定义
     */
    static int angleToDirection(float angle) {
        angle = ((angle % 360.0f) + 360.0f) % 360.0f;
        if (angle >= 337.5f || angle < 22.5f) return 0;  // N
        if (angle < 67.5f) return 1;   // NE
        if (angle < 112.5f) return 2;  // E
        if (angle < 157.5f) return 3;  // SE
        if (angle < 202.5f) return 4;  // S
        if (angle < 247.5f) return 5;  // SW
        if (angle < 292.5f) return 6;  // W
        return 7; // NW
    }
}
