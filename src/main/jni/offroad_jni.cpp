/**
 * B60VS-F03 越野信息算法 — JNI 桥接层 C++ 实现
 *
 * 此文件实现 OffroadBridge.java 中声明的 native 方法。
 * 算法核心由各 Engine 模块实现，此文件仅负责 JNI 数据转换。
 *
 * 需求追溯: architecture.md §6.2 桥接契约
 * 内存纪律: 禁止动态分配(new/malloc)，全部使用栈/静态分配 [NFR-002]
 */

#include <jni.h>
#include <android/log.h>
#include <cmath>
#include <cstring>
#include <mutex>

#define LOG_TAG "OffRoad.JNI"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// ---- 全局状态(静态分配, 无动态内存) ----

// [H3 fix] 全局互斥锁保护所有共享状态
static std::mutex g_mutex;

// ICC 安装姿态矩阵 3x3
static float g_icc_matrix[9] = {1,0,0, 0,1,0, 0,0,1};
// IMU 布置姿态矩阵 3x3
static float g_imu_matrix[9] = {1,0,0, 0,1,0, 0,0,1};
// 合并变换矩阵 3x3 (icc * imu)
static float g_transform[9] = {1,0,0, 0,1,0, 0,0,1};

// 清零补偿值 — 仅由 native 层存储，实际补偿由 Java 层统一应用 [H4 fix]
static float g_tilt_offset = 0.0f;
static float g_pitch_offset = 0.0f;

// 大气压力滤波窗口
static int g_filter_window = 10;
static float g_pressure_buffer[64] = {0}; // 固定大小滤波缓冲区
static int g_pressure_idx = 0;
static int g_pressure_count = 0;

// 是否已初始化
static bool g_initialized = false;

// ---- 矩阵运算工具(栈分配) ----

static void mat3x3_multiply(const float* a, const float* b, float* out) {
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            out[i*3+j] = 0.0f;
            for (int k = 0; k < 3; k++) {
                out[i*3+j] += a[i*3+k] * b[k*3+j];
            }
        }
    }
}

static void mat3x3_vec3_multiply(const float* m, const float* v, float* out) {
    for (int i = 0; i < 3; i++) {
        out[i] = m[i*3+0]*v[0] + m[i*3+1]*v[1] + m[i*3+2]*v[2];
    }
}

// ---- 角度计算 ----

/**
 * 从加速度计算倾斜角(roll)和俯仰角(pitch)。
 * 使用坐标变换后的加速度数据。
 * 需求追溯: [FUN-001~008], AttitudeEngine
 *
 * [H4 fix] 清零补偿不在此处应用，由 Java 层 AlgorithmScheduler.applyCalibrationOffset()
 * 统一应用，避免双重补偿。
 */
static void compute_attitude(const float* accel, float* tilt, float* pitch) {
    // 坐标变换: 应用安装姿态补偿
    float transformed[3];
    mat3x3_vec3_multiply(g_transform, accel, transformed);

    float ax = transformed[0];
    float ay = transformed[1];
    float az = transformed[2];

    // 倾斜角(roll): atan2(ay, az) [FUN-001]
    *tilt = atan2f(ay, az) * 180.0f / (float)M_PI;

    // 俯仰角(pitch): atan2(-ax, sqrt(ay^2 + az^2)) [FUN-005]
    *pitch = atan2f(-ax, sqrtf(ay*ay + az*az)) * 180.0f / (float)M_PI;

    // [H4 fix] 移除 C++ 层补偿，仅保留 Java 层统一补偿
    // 原代码: *tilt -= g_tilt_offset; *pitch -= g_pitch_offset;
}

/**
 * 大气压力滑动平均滤波。
 * 需求追溯: [FUN-014], PressureFilter
 */
static float filter_pressure(float raw_pressure) {
    if (g_filter_window <= 0 || g_filter_window > 64) g_filter_window = 10;

    g_pressure_buffer[g_pressure_idx] = raw_pressure;
    g_pressure_idx = (g_pressure_idx + 1) % g_filter_window;
    if (g_pressure_count < g_filter_window) g_pressure_count++;

    float sum = 0.0f;
    for (int i = 0; i < g_pressure_count; i++) {
        sum += g_pressure_buffer[i];
    }
    return sum / (float)g_pressure_count;
}

/**
 * 海拔高度计算(基于大气压力 + GPS 辅助)。
 * h = 44330 * (1 - (P/P0)^(1/5.255)), P0=1013.25hPa
 * 需求追溯: [FUN-009~012], AltitudeEngine
 */
static float compute_altitude(float pressure_hpa) {
    if (pressure_hpa < 300.0f || pressure_hpa > 1100.0f) return 0.0f;
    return 44330.0f * (1.0f - powf(pressure_hpa / 1013.25f, 1.0f / 5.255f));
}

/**
 * 指南针方向计算(角度→8方位)。
 * 需求追溯: [FUN-017], CompassEngine
 */
static int angle_to_direction(float angle) {
    // 归一化到 [0, 360)
    angle = fmodf(fmodf(angle, 360.0f) + 360.0f, 360.0f);

    if (angle >= 337.5f || angle < 22.5f) return 0;  // N
    if (angle < 67.5f) return 1;   // NE
    if (angle < 112.5f) return 2;  // E
    if (angle < 157.5f) return 3;  // SE
    if (angle < 202.5f) return 4;  // S
    if (angle < 247.5f) return 5;  // SW
    if (angle < 292.5f) return 6;  // W
    return 7; // NW
}

// ---- JNI 方法实现 ----

extern "C" {

JNIEXPORT jint JNICALL
Java_com_baic_offroad_algorithm_OffroadBridge_nativeInit(
        JNIEnv* env, jclass clazz,
        jfloatArray iccMatrix, jfloatArray imuMatrix, jint filterWindow) {

    std::lock_guard<std::mutex> lock(g_mutex);  // [H3 fix]

    LOGI("nativeInit: filterWindow=%d", filterWindow);

    // 使用 GetPrimitiveArrayCritical 避免拷贝 [architecture.md §11.2]
    jfloat* icc = (jfloat*)env->GetPrimitiveArrayCritical(iccMatrix, nullptr);
    if (icc) {
        memcpy(g_icc_matrix, icc, 9 * sizeof(float));
        env->ReleasePrimitiveArrayCritical(iccMatrix, icc, JNI_ABORT);
    }

    jfloat* imu = (jfloat*)env->GetPrimitiveArrayCritical(imuMatrix, nullptr);
    if (imu) {
        memcpy(g_imu_matrix, imu, 9 * sizeof(float));
        env->ReleasePrimitiveArrayCritical(imuMatrix, imu, JNI_ABORT);
    }

    // 计算合并变换矩阵
    mat3x3_multiply(g_icc_matrix, g_imu_matrix, g_transform);

    g_filter_window = (filterWindow > 0 && filterWindow <= 64) ? filterWindow : 10;
    g_pressure_idx = 0;
    g_pressure_count = 0;
    memset(g_pressure_buffer, 0, sizeof(g_pressure_buffer));

    g_tilt_offset = 0.0f;
    g_pitch_offset = 0.0f;
    g_initialized = true;

    LOGI("nativeInit: OK, transform matrix computed");
    return 0;
}

JNIEXPORT jint JNICALL
Java_com_baic_offroad_algorithm_OffroadBridge_nativeCompute(
        JNIEnv* env, jclass clazz,
        jfloatArray sensorInput, jfloatArray result) {

    std::lock_guard<std::mutex> lock(g_mutex);  // [H3 fix]

    if (!g_initialized) return -1;

    // 使用 GetPrimitiveArrayCritical 零拷贝访问 [architecture.md §6.2]
    jfloat* input = (jfloat*)env->GetPrimitiveArrayCritical(sensorInput, nullptr);
    if (!input) return -2;

    // 解包输入 (布局见 SensorInputFrame.toFloatArray())
    float accel[3] = {input[0], input[1], input[2]};
    float gyro[3] = {input[3], input[4], input[5]};
    float gps_altitude = input[6];
    float gps_bearing = input[7];
    float gps_speed = input[8];
    bool gps_valid = input[9] > 0.5f;
    float raw_pressure = input[10];
    bool pressure_input_valid = input[11] > 0.5f;
    float vehicle_speed = input[12];

    env->ReleasePrimitiveArrayCritical(sensorInput, input, JNI_ABORT);

    // ---- 计算 ----

    // 1. 姿态解算 (倾斜角 + 俯仰角) [FUN-001~008]
    float tilt = 0.0f, pitch = 0.0f;
    compute_attitude(accel, &tilt, &pitch);
    bool tilt_valid = (fabsf(tilt) <= 40.0f);
    bool pitch_valid = (fabsf(pitch) <= 60.0f);

    // 2. 大气压力滤波 [FUN-013~016]
    float pressure = 0.0f;
    bool pressure_valid = false;
    if (pressure_input_valid && raw_pressure >= 300.0f && raw_pressure <= 1100.0f) {
        pressure = filter_pressure(raw_pressure);
        pressure_valid = (pressure >= 300.0f && pressure <= 1100.0f);
    }

    // 3. 海拔计算 [FUN-009~012]
    float altitude = 0.0f;
    bool altitude_valid = false;
    if (pressure_valid) {
        altitude = compute_altitude(pressure);
        altitude_valid = (altitude >= -500.0f && altitude <= 9000.0f);
    }

    // 4. 指南针 [FUN-017~022]
    float compass_angle = 0.0f;
    int compass_dir = -1;
    bool compass_valid = false;
    if (gps_valid) {
        compass_angle = fmodf(fmodf(gps_bearing, 360.0f) + 360.0f, 360.0f);
        compass_dir = angle_to_direction(compass_angle);
        compass_valid = true;
    }

    // ---- 填充结果 ----
    jfloat* out = (jfloat*)env->GetPrimitiveArrayCritical(result, nullptr);
    if (!out) return -3;

    out[0] = tilt;
    out[1] = tilt_valid ? 1.0f : 0.0f;
    out[2] = pitch;
    out[3] = pitch_valid ? 1.0f : 0.0f;
    out[4] = pressure;
    out[5] = pressure_valid ? 1.0f : 0.0f;
    out[6] = altitude;
    out[7] = altitude_valid ? 1.0f : 0.0f;
    out[8] = (float)compass_dir;
    out[9] = compass_valid ? 1.0f : 0.0f;
    out[10] = compass_angle;
    out[11] = compass_valid ? 1.0f : 0.0f;

    env->ReleasePrimitiveArrayCritical(result, out, 0);
    return 0;
}

JNIEXPORT jint JNICALL
Java_com_baic_offroad_algorithm_OffroadBridge_nativeCalibrate(
        JNIEnv* env, jclass clazz,
        jfloat tiltOffset, jfloat pitchOffset) {

    std::lock_guard<std::mutex> lock(g_mutex);  // [H3 fix]

    LOGI("nativeCalibrate: tilt=%.2f pitch=%.2f", tiltOffset, pitchOffset);
    g_tilt_offset = tiltOffset;
    g_pitch_offset = pitchOffset;
    return 0;
}

JNIEXPORT jint JNICALL
Java_com_baic_offroad_algorithm_OffroadBridge_nativeApplyCalibration(
        JNIEnv* env, jclass clazz,
        jfloat tiltOffset, jfloat pitchOffset) {

    std::lock_guard<std::mutex> lock(g_mutex);  // [H3 fix]

    LOGI("nativeApplyCalibration: tilt=%.2f pitch=%.2f", tiltOffset, pitchOffset);
    g_tilt_offset = tiltOffset;
    g_pitch_offset = pitchOffset;
    return 0;
}

JNIEXPORT void JNICALL
Java_com_baic_offroad_algorithm_OffroadBridge_nativeDestroy(
        JNIEnv* env, jclass clazz) {

    std::lock_guard<std::mutex> lock(g_mutex);  // [H3 fix]

    LOGI("nativeDestroy");
    g_initialized = false;
    g_pressure_idx = 0;
    g_pressure_count = 0;
    memset(g_pressure_buffer, 0, sizeof(g_pressure_buffer));
}

} // extern "C"
