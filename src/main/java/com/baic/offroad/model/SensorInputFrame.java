package com.baic.offroad.model;

/**
 * 传感器输入帧 — 单帧传感器采集数据。
 * 由 Java 层聚合后通过 JNI 传递给 C++ 算法。
 * 不持久化，每帧覆盖。
 *
 * 需求追溯: data_model.md §2.5
 */
public class SensorInputFrame {

    // ---- IMU 加速度 (Sensor API TYPE_ACCELEROMETER) [IF-002] ----
    public float accelX;
    public float accelY;
    public float accelZ;

    // ---- IMU 角速度 (Sensor API TYPE_GYROSCOPE) [IF-002] ----
    public float gyroX;
    public float gyroY;
    public float gyroZ;

    // ---- GPS 数据 (Location API) [IF-001] ----
    public double latitude;
    public double longitude;
    public float gpsAltitude;
    public float gpsBearing;
    public float gpsSpeed;
    public boolean gpsValid;

    // ---- CAN 数据 [IF-004] ----
    /** 大气压力原始值 (EMS_0x131) */
    public float rawPressure;
    /** 压力信号是否有效 */
    public boolean pressureValid;

    // ---- 车速 [IF-003] ----
    /** 车速(km/h) */
    public float vehicleSpeed;

    // ---- 时间戳 ----
    public long timestamp;

    /** JNI 传输数组长度 */
    public static final int FLOAT_ARRAY_SIZE = 16;

    /**
     * 打包为 float[16] 数组，用于 JNI 高效传递。
     * boolean 用 0.0/1.0 编码，通过 GetPrimitiveArrayCritical 传递。
     * 需求追溯: data_model.md §2.5 "JNI 传输优化"
     *
     * 布局:
     * [0] accelX, [1] accelY, [2] accelZ,
     * [3] gyroX,  [4] gyroY,  [5] gyroZ,
     * [6] gpsAltitude, [7] gpsBearing, [8] gpsSpeed, [9] gpsValid(0/1),
     * [10] rawPressure, [11] pressureValid(0/1),
     * [12] vehicleSpeed,
     * [13-15] reserved
     */
    public float[] toFloatArray() {
        float[] arr = new float[FLOAT_ARRAY_SIZE];
        arr[0] = accelX;
        arr[1] = accelY;
        arr[2] = accelZ;
        arr[3] = gyroX;
        arr[4] = gyroY;
        arr[5] = gyroZ;
        arr[6] = gpsAltitude;
        arr[7] = gpsBearing;
        arr[8] = gpsSpeed;
        arr[9] = gpsValid ? 1.0f : 0.0f;
        arr[10] = rawPressure;
        arr[11] = pressureValid ? 1.0f : 0.0f;
        arr[12] = vehicleSpeed;
        arr[13] = 0.0f; // reserved
        arr[14] = 0.0f; // reserved
        arr[15] = 0.0f; // reserved
        return arr;
    }

    @Override
    public String toString() {
        return "SensorInputFrame{" +
                "accel=(" + accelX + "," + accelY + "," + accelZ + ")" +
                ", gyro=(" + gyroX + "," + gyroY + "," + gyroZ + ")" +
                ", gps=" + gpsValid +
                ", pressure=" + rawPressure + "(v=" + pressureValid + ")" +
                ", speed=" + vehicleSpeed +
                "}";
    }
}
