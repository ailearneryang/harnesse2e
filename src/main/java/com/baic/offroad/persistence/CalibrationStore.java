package com.baic.offroad.persistence;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import com.baic.offroad.model.CalibrationData;
import com.baic.offroad.util.OffroadLog;

/**
 * 清零标定数据存储 — 使用 SharedPreferences 持久化。
 *
 * 写入时机: 收到清零指令(VEHICLE_ID_4F0信号值=1) + 车速=0 [SCN-009]
 * 读取时机: 每次启动时加载；每帧计算时应用补偿
 *
 * 需求追溯: [FUN-026~029, NFR-008], architecture.md §6.4
 * 数据模型: data_model.md §2.3
 */
public class CalibrationStore {

    private static final String KEY_TILT_OFFSET = "tiltOffset";
    private static final String KEY_PITCH_OFFSET = "pitchOffset";
    private static final String KEY_CALIBRATED = "calibrated";
    private static final String KEY_CALIB_TIMESTAMP = "calibTimestamp";

    private final SharedPreferences prefs;

    public CalibrationStore(Context context) {
        this.prefs = context.getSharedPreferences(
                OffroadLog.SP_CALIBRATION, Context.MODE_PRIVATE);
    }

    /** 用于测试的构造函数 */
    public CalibrationStore(SharedPreferences prefs) {
        this.prefs = prefs;
    }

    /**
     * 保存清零标定数据。
     * 使用 commit() 同步写入。
     * 需求追溯: [FUN-029], data_model.md §6.2
     */
    public boolean save(CalibrationData data) {
        if (data == null) {
            Log.w(OffroadLog.TAG_CALIB, "save: CalibrationData is null, skip");
            return false;
        }
        // 审计日志: 清零操作必须记录 (architecture.md §9.3)
        Log.w(OffroadLog.TAG_CALIB, "Calibration save: tiltOff=" + data.getTiltOffset()
                + " pitchOff=" + data.getPitchOffset()
                + " calibrated=" + data.isCalibrated()
                + " ts=" + data.getCalibTimestamp());

        boolean success = prefs.edit()
                .putFloat(KEY_TILT_OFFSET, data.getTiltOffset())
                .putFloat(KEY_PITCH_OFFSET, data.getPitchOffset())
                .putBoolean(KEY_CALIBRATED, data.isCalibrated())
                .putLong(KEY_CALIB_TIMESTAMP, data.getCalibTimestamp())
                .commit();
        Log.i(OffroadLog.TAG_STORAGE, "CalibrationData save: " + (success ? "OK" : "FAIL"));
        return success;
    }

    /**
     * 加载清零标定数据。
     * 文件损坏时返回默认值(补偿为零)。
     * 需求追溯: architecture.md §8.4
     */
    public CalibrationData load() {
        try {
            CalibrationData data = new CalibrationData();
            data.setTiltOffset(prefs.getFloat(KEY_TILT_OFFSET, 0.0f));
            data.setPitchOffset(prefs.getFloat(KEY_PITCH_OFFSET, 0.0f));
            data.setCalibrated(prefs.getBoolean(KEY_CALIBRATED, false));
            data.setCalibTimestamp(prefs.getLong(KEY_CALIB_TIMESTAMP, 0L));
            Log.i(OffroadLog.TAG_STORAGE, "CalibrationData load: " + data);
            return data;
        } catch (Exception e) {
            Log.e(OffroadLog.TAG_STORAGE, "CalibrationData load failed, use default", e);
            return new CalibrationData();
        }
    }

    /**
     * 清除标定数据(仅供测试或重置使用)。
     */
    public void clear() {
        prefs.edit().clear().commit();
        Log.i(OffroadLog.TAG_STORAGE, "CalibrationData cleared");
    }
}
