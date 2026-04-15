package com.baic.offroad.sensor;

import android.util.Log;

import com.baic.offroad.util.OffroadLog;

/**
 * CAN 信号适配器 — 通过 CAN 中间件 Java API 接收和发送 CAN 信号。
 *
 * 接收: EMS_0x131 大气压力原始信号 [IF-004, FUN-016]
 * 发送: 0x4F0 越野信息报文 [FUN-023]
 * 接收: VEHICLE_ID_4F0 清零指令 [IF-005]
 * 接收: PERF_VEHICLE_SPEED 车速 [IF-003]
 *
 * 需求追溯: architecture.md §6.1 CanSignalAdapter
 */
public class CanSignalAdapter {

    // ---- CAN 信号 ID 常量 ----
    public static final int MSG_ID_EMS_0x131 = 0x131;
    public static final int MSG_ID_0x4F0 = 0x4F0;

    /** CAN 信号名(保留原文拼写，配置中同时映射两种拼写 [RISK-04]) */
    public static final String SIGNAL_EMS_BAROMETER = "VEHICLE_EMS4_N_BAROMETER";
    public static final String SIGNAL_VEHICLE_SPEED = "PERF_VEHICLE_SPEED";
    public static final String SIGNAL_CALIB_CMD = "VEHICLE_ID_4F0";

    // ---- 缓存数据 ----
    private volatile float rawPressure = 0.0f;
    private volatile boolean pressureValid = false;
    private volatile long lastPressureTimestamp = 0;

    private volatile float vehicleSpeed = 0.0f;
    private volatile long lastSpeedTimestamp = 0;

    private volatile boolean calibCommandReceived = false;

    /** CAN 中间件接口(ICC厂商提供) — 此处以接口抽象 */
    public interface CanMiddlewareInterface {
        void registerSignalListener(int msgId, String signalName, CanSignalListener listener);
        void unregisterSignalListener(int msgId, String signalName);
        boolean sendCanMessage(int msgId, byte[] data, int length);
    }

    /** CAN 信号监听回调 */
    public interface CanSignalListener {
        void onSignalReceived(String signalName, float value, long timestamp);
    }

    /** 清零指令回调 */
    public interface OnCalibrationCommandListener {
        void onCalibrationCommandReceived();
    }

    private CanMiddlewareInterface canMiddleware;
    private OnCalibrationCommandListener calibListener;

    public void setCanMiddleware(CanMiddlewareInterface middleware) {
        this.canMiddleware = middleware;
    }

    public void setCalibrationCommandListener(OnCalibrationCommandListener listener) {
        this.calibListener = listener;
    }

    /**
     * 启动 CAN 信号监听。
     * 注册 EMS_0x131(大气压力)、PERF_VEHICLE_SPEED(车速)、VEHICLE_ID_4F0(清零指令)。
     */
    public boolean start() {
        if (canMiddleware == null) {
            Log.e(OffroadLog.TAG_CAN, "CAN middleware is null, cannot start");
            return false;
        }

        // 注册大气压力信号 [IF-004]
        canMiddleware.registerSignalListener(MSG_ID_EMS_0x131, SIGNAL_EMS_BAROMETER,
                (signalName, value, timestamp) -> {
                    rawPressure = value;
                    pressureValid = true;
                    lastPressureTimestamp = timestamp;
                });

        // 注册车速信号 [IF-003]
        canMiddleware.registerSignalListener(0, SIGNAL_VEHICLE_SPEED,
                (signalName, value, timestamp) -> {
                    vehicleSpeed = value;
                    lastSpeedTimestamp = timestamp;
                });

        // 注册清零指令 [IF-005]
        canMiddleware.registerSignalListener(MSG_ID_0x4F0, SIGNAL_CALIB_CMD,
                (signalName, value, timestamp) -> {
                    if (value == 1.0f) {
                        calibCommandReceived = true;
                        Log.w(OffroadLog.TAG_CALIB, "Calibration command received via CAN");
                        if (calibListener != null) {
                            calibListener.onCalibrationCommandReceived();
                        }
                    }
                });

        Log.i(OffroadLog.TAG_CAN, "CAN signal listeners registered");
        return true;
    }

    /**
     * 停止 CAN 信号监听。
     */
    public void stop() {
        if (canMiddleware != null) {
            canMiddleware.unregisterSignalListener(MSG_ID_EMS_0x131, SIGNAL_EMS_BAROMETER);
            canMiddleware.unregisterSignalListener(0, SIGNAL_VEHICLE_SPEED);
            canMiddleware.unregisterSignalListener(MSG_ID_0x4F0, SIGNAL_CALIB_CMD);
            Log.i(OffroadLog.TAG_CAN, "CAN signal listeners unregistered");
        }
    }

    /**
     * 发送 CAN 0x4F0 越野信息报文。
     * 需求追溯: [FUN-023~025]
     *
     * @param encodedData 由 CanEncoder 编码的报文数据
     * @return 发送是否成功
     */
    public boolean sendOffroadCanMessage(byte[] encodedData) {
        if (canMiddleware == null) {
            Log.e(OffroadLog.TAG_CAN, "CAN middleware is null, cannot send 0x4F0");
            return false;
        }
        boolean success = canMiddleware.sendCanMessage(MSG_ID_0x4F0, encodedData, encodedData.length);
        if (!success) {
            // 发送失败记录日志，下一周期重试 (architecture.md §7.5)
            Log.e(OffroadLog.TAG_CAN, "CAN 0x4F0 send FAILED");
        }
        return success;
    }

    /**
     * 检查大气压力信号是否有效(未超时)。
     * 超过 EMS_SIGNAL_TIMEOUT_MS 视为信号丢失。
     * 需求追溯: [FUN-015], api_design.md §2.3.1
     */
    public boolean isPressureValid() {
        if (!pressureValid) return false;
        long elapsed = System.currentTimeMillis() - lastPressureTimestamp;
        if (elapsed > OffroadLog.EMS_SIGNAL_TIMEOUT_MS) {
            pressureValid = false;
            return false;
        }
        return true;
    }

    // ---- 数据读取 ----
    public float getRawPressure() { return rawPressure; }
    public float getVehicleSpeed() { return vehicleSpeed; }
    public long getLastPressureTimestamp() { return lastPressureTimestamp; }

    public boolean isCalibCommandReceived() { return calibCommandReceived; }
    public void clearCalibCommand() { calibCommandReceived = false; }
}
