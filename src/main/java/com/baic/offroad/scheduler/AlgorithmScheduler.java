package com.baic.offroad.scheduler;

import android.os.Handler;
import android.os.HandlerThread;
import android.os.SystemClock;
import android.util.Log;

import com.baic.offroad.algorithm.CanEncoder;
import com.baic.offroad.algorithm.OffroadBridge;
import com.baic.offroad.model.CalibrationData;
import com.baic.offroad.model.CompassMemory;
import com.baic.offroad.model.InstallationConfig;
import com.baic.offroad.model.OffroadDataBundle;
import com.baic.offroad.model.SensorInputFrame;
import com.baic.offroad.persistence.CalibrationStore;
import com.baic.offroad.persistence.CompassMemoryStore;
import com.baic.offroad.sensor.CanSignalAdapter;
import com.baic.offroad.sensor.LocationCollector;
import com.baic.offroad.sensor.SensorCollector;
import com.baic.offroad.util.OffroadLog;

/**
 * 算法调度核心 — 聚合传感器数据，按固定周期触发 JNI 算法计算，分发结果。
 *
 * 职责:
 * 1. 传感器数据聚合 (IMU + GPS + CAN)
 * 2. 定时触发算法计算 (~20Hz [TBD-010])
 * 3. 结果分发 (UI回调 + CAN 0x4F0)
 * 4. 指南针记忆值管理 (运动→静止检测)
 * 5. 清零标定处理
 *
 * 需求追溯: architecture.md §6.1 AlgorithmScheduler
 */
public class AlgorithmScheduler {

    /** 算法计算结果监听器 */
    public interface OnResultListener {
        void onOffroadDataComputed(OffroadDataBundle data);
    }

    private final SensorCollector sensorCollector;
    private final LocationCollector locationCollector;
    private final CanSignalAdapter canSignalAdapter;
    private final CompassMemoryStore compassMemoryStore;
    private final CalibrationStore calibrationStore;
    private final InstallationConfig config;

    private OnResultListener resultListener;

    // 专用计算线程 (architecture.md §4.4: JNI调用不占用主线程)
    private HandlerThread computeThread;
    private Handler computeHandler;

    // 复用数组: 避免每帧创建 (architecture.md §11.2 内存纪律)
    private final float[] sensorInputArray = new float[SensorInputFrame.FLOAT_ARRAY_SIZE];
    private final float[] resultArray = new float[OffroadBridge.RESULT_ARRAY_SIZE];

    // 车辆运动状态检测 (architecture.md §8.3)
    private boolean wasMoving = false;
    private volatile boolean running = false;

    // 当前帧数据缓存 (单帧缓存，原子性替换)
    private volatile OffroadDataBundle currentData = new OffroadDataBundle();

    // 计算周期统计
    private long totalComputeCount = 0;
    private long totalComputeTimeNs = 0;

    // 是否使用 native 库
    private boolean useNative = false;

    // 标定数据缓存
    private CalibrationData calibrationData;

    public AlgorithmScheduler(
            SensorCollector sensorCollector,
            LocationCollector locationCollector,
            CanSignalAdapter canSignalAdapter,
            CompassMemoryStore compassMemoryStore,
            CalibrationStore calibrationStore,
            InstallationConfig config) {
        this.sensorCollector = sensorCollector;
        this.locationCollector = locationCollector;
        this.canSignalAdapter = canSignalAdapter;
        this.compassMemoryStore = compassMemoryStore;
        this.calibrationStore = calibrationStore;
        this.config = config;
    }

    public void setResultListener(OnResultListener listener) {
        this.resultListener = listener;
    }

    /**
     * 初始化算法引擎并启动计算循环。
     * 需求追溯: architecture.md §11.1 步骤7~9
     */
    public void start() {
        if (running) {
            Log.w(OffroadLog.TAG_ALGORITHM, "AlgorithmScheduler already running");
            return;
        }

        // 加载标定数据 [NFR-008]
        calibrationData = calibrationStore.load();

        // 初始化 native 算法引擎
        useNative = OffroadBridge.isNativeLoaded();
        if (useNative) {
            int ret = OffroadBridge.nativeInit(
                    config.getIccAttitudeMatrix(),
                    config.getImuAttitudeMatrix(),
                    config.getPressureFilterWindow());
            if (ret != 0) {
                Log.e(OffroadLog.TAG_ALGORITHM, "nativeInit failed: " + ret + ", fallback to Java");
                useNative = false;
            } else {
                // 应用已有的清零补偿值
                if (calibrationData.isCalibrated() && calibrationData.isOffsetValid()) {
                    OffroadBridge.nativeApplyCalibration(
                            calibrationData.getTiltOffset(),
                            calibrationData.getPitchOffset());
                }
            }
        }

        if (!useNative) {
            OffroadBridge.fallbackInit(config);
        }

        // 启动计算线程
        computeThread = new HandlerThread("OffRoad.Compute");
        computeThread.start();
        computeHandler = new Handler(computeThread.getLooper());

        running = true;
        long periodMs = 1000 / config.getUpdateRateHz();
        scheduleNextCompute(periodMs);

        Log.i(OffroadLog.TAG_ALGORITHM, "AlgorithmScheduler started, period=" + periodMs
                + "ms, native=" + useNative);
    }

    /**
     * 停止计算循环。
     */
    public void stop() {
        running = false;
        if (computeHandler != null) {
            computeHandler.removeCallbacksAndMessages(null);
        }
        if (computeThread != null) {
            computeThread.quitSafely();
            computeThread = null;
        }
        if (useNative && OffroadBridge.isNativeLoaded()) {
            OffroadBridge.nativeDestroy();
        }
        Log.i(OffroadLog.TAG_ALGORITHM, "AlgorithmScheduler stopped, totalCompute=" + totalComputeCount);
    }

    /**
     * 调度下一次计算。
     */
    private void scheduleNextCompute(long periodMs) {
        if (!running || computeHandler == null) return;
        computeHandler.postDelayed(() -> {
            if (running) {
                doCompute();
                scheduleNextCompute(periodMs);
            }
        }, periodMs);
    }

    /**
     * 执行一次算法计算。
     * 在专用计算线程上执行。
     */
    private void doCompute() {
        long startNs = System.nanoTime();

        try {
            // 1. 聚合传感器数据
            assembleSensorInput();

            // 2. 执行算法计算
            int ret;
            if (useNative) {
                ret = OffroadBridge.nativeCompute(sensorInputArray, resultArray);
            } else {
                ret = OffroadBridge.fallbackCompute(sensorInputArray, resultArray);
            }

            if (ret != 0) {
                Log.e(OffroadLog.TAG_ALGORITHM, "Compute failed: " + ret);
                return;
            }

            // 3. 解包结果 → OffroadDataBundle
            OffroadDataBundle data = OffroadDataBundle.fromFloatArray(resultArray);

            // 4. 应用清零补偿 (每帧) [FUN-029]
            applyCalibrationOffset(data);

            // 5. 原子性替换当前帧缓存
            currentData = data;

            // 6. 检测运动→静止，存储指南针记忆值 [SCN-001]
            checkVehicleMotionState(data);

            // 7. 分发结果 → UI 回调
            if (resultListener != null) {
                resultListener.onOffroadDataComputed(data);
            }

            // 8. 编码并发送 CAN 0x4F0 [FUN-023]
            byte[] canFrame = CanEncoder.encode(data);
            canSignalAdapter.sendOffroadCanMessage(canFrame);

        } catch (Exception e) {
            // 算法故障隔离: 记录日志，不崩溃进程 (architecture.md §11.3)
            Log.e(OffroadLog.TAG_ALGORITHM, "Compute exception", e);
        }

        // 统计
        long elapsedNs = System.nanoTime() - startNs;
        totalComputeCount++;
        totalComputeTimeNs += elapsedNs;

        long elapsedMs = elapsedNs / 1_000_000;
        if (elapsedMs > OffroadLog.COMPUTE_CYCLE_WARNING_MS) {
            Log.w(OffroadLog.TAG_ALGORITHM, "Compute cycle too slow: " + elapsedMs + "ms");
        }
    }

    /**
     * 聚合传感器数据到 float 数组。
     */
    private void assembleSensorInput() {
        float[] accel = sensorCollector.getAccelData();
        float[] gyro = sensorCollector.getGyroData();

        sensorInputArray[0] = accel[0];
        sensorInputArray[1] = accel[1];
        sensorInputArray[2] = accel[2];
        sensorInputArray[3] = gyro[0];
        sensorInputArray[4] = gyro[1];
        sensorInputArray[5] = gyro[2];
        sensorInputArray[6] = locationCollector.getGpsAltitude();
        sensorInputArray[7] = locationCollector.getGpsBearing();
        sensorInputArray[8] = locationCollector.getGpsSpeed();
        sensorInputArray[9] = locationCollector.isGpsValid() ? 1.0f : 0.0f;
        sensorInputArray[10] = canSignalAdapter.getRawPressure();
        sensorInputArray[11] = canSignalAdapter.isPressureValid() ? 1.0f : 0.0f;
        sensorInputArray[12] = canSignalAdapter.getVehicleSpeed();
        sensorInputArray[13] = 0.0f;
        sensorInputArray[14] = 0.0f;
        sensorInputArray[15] = 0.0f;
    }

    /**
     * 应用清零补偿值。
     * 需求追溯: [FUN-029], data_model.md §2.3
     */
    private void applyCalibrationOffset(OffroadDataBundle data) {
        if (calibrationData == null || !calibrationData.isCalibrated()) return;
        if (!calibrationData.isOffsetValid()) return;

        data.setTiltAngle(data.getTiltAngle() - calibrationData.getTiltOffset());
        data.setPitchAngle(data.getPitchAngle() - calibrationData.getPitchOffset());
        data.validate(); // 重新校验范围
    }

    /**
     * 检测车辆运动状态变化，触发指南针记忆值存储。
     * 需求追溯: [FUN-019, SCN-001], architecture.md §8.3
     */
    private void checkVehicleMotionState(OffroadDataBundle data) {
        float speed = canSignalAdapter.getVehicleSpeed();
        boolean isMoving = speed > 0.0f;

        // 运动→静止: 存储指南针记忆值
        if (wasMoving && !isMoving) {
            if (data.isCompassDirectionValid() && data.isCompassAngleValid()) {
                CompassMemory memory = new CompassMemory(
                        data.getCompassDirection(),
                        data.getCompassAngle(),
                        System.currentTimeMillis(),
                        true);
                compassMemoryStore.save(memory);
                Log.i(OffroadLog.TAG_ALGORITHM, "Compass memory saved on MOVING→STOPPED: " + memory);
            }
        }

        wasMoving = isMoving;
    }

    /**
     * 执行清零标定操作。
     * 需求追溯: [FUN-026~029, SCN-009]
     *
     * @return true=清零成功, false=条件不满足或执行失败
     */
    public boolean executeCalibration() {
        // 前提条件: 车速=0 [FUN-027]
        float speed = canSignalAdapter.getVehicleSpeed();
        if (speed > 0.0f) {
            Log.w(OffroadLog.TAG_CALIB, "Calibration rejected: vehicle is moving, speed=" + speed);
            return false;
        }

        OffroadDataBundle snapshot = currentData;
        float currentTilt = snapshot.getTiltAngle();
        float currentPitch = snapshot.getPitchAngle();

        // 审计日志: 清零前角度值 (architecture.md §9.3)
        Log.w(OffroadLog.TAG_CALIB, "Calibration START: tilt=" + currentTilt + " pitch=" + currentPitch);

        // 执行清零
        CalibrationData newCalib = new CalibrationData(
                currentTilt,
                currentPitch,
                true,
                System.currentTimeMillis());

        // 校验补偿值范围
        if (!newCalib.isOffsetValid()) {
            Log.e(OffroadLog.TAG_CALIB, "Calibration offset out of range: " + newCalib);
            return false;
        }

        // 持久化 [FUN-029, NFR-008]
        boolean saved = calibrationStore.save(newCalib);
        if (!saved) {
            Log.e(OffroadLog.TAG_CALIB, "Calibration save FAILED");
            return false;
        }

        // 更新运行时缓存
        this.calibrationData = newCalib;

        // 通知 native 层
        if (useNative && OffroadBridge.isNativeLoaded()) {
            OffroadBridge.nativeApplyCalibration(newCalib.getTiltOffset(), newCalib.getPitchOffset());
        }

        // 审计日志: 清零后补偿值
        Log.w(OffroadLog.TAG_CALIB, "Calibration DONE: " + newCalib);
        return true;
    }

    /**
     * 获取当前帧数据快照(AIDL getOffroadData 使用)。
     */
    public OffroadDataBundle getCurrentData() {
        return currentData;
    }

    /**
     * 获取计算统计信息。
     */
    public String getStats() {
        long avgNs = totalComputeCount > 0 ? totalComputeTimeNs / totalComputeCount : 0;
        return "totalCompute=" + totalComputeCount
                + " avgTime=" + (avgNs / 1000) + "us"
                + " native=" + useNative;
    }

    public boolean isRunning() { return running; }
}
