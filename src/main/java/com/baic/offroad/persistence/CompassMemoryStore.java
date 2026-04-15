package com.baic.offroad.persistence;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import com.baic.offroad.model.CompassMemory;
import com.baic.offroad.util.OffroadLog;

/**
 * 指南针记忆值存储 — 使用 SharedPreferences 持久化。
 *
 * 写入时机: 车速从 >0 变为 =0 时(运动→静止) [SCN-001]
 * 读取时机: 上电启动[SCN-002]、休眠→唤醒[SCN-003]、车机重启[SCN-004]
 *
 * 需求追溯: [FUN-019, FUN-020, NFR-007], architecture.md §6.4
 * 数据模型: data_model.md §2.2
 */
public class CompassMemoryStore {

    private static final String KEY_DIRECTION = "direction";
    private static final String KEY_ANGLE = "angle";
    private static final String KEY_TIMESTAMP = "timestamp";
    private static final String KEY_VALID = "valid";

    private final SharedPreferences prefs;

    public CompassMemoryStore(Context context) {
        this.prefs = context.getSharedPreferences(
                OffroadLog.SP_COMPASS_MEMORY, Context.MODE_PRIVATE);
    }

    /** 用于测试的构造函数 */
    public CompassMemoryStore(SharedPreferences prefs) {
        this.prefs = prefs;
    }

    /**
     * 保存指南针记忆值。
     * 使用 commit() 同步写入，确保数据不丢失。
     * 需求追溯: [FUN-019], data_model.md §6.2
     */
    public boolean save(CompassMemory memory) {
        if (memory == null) {
            Log.w(OffroadLog.TAG_STORAGE, "save: CompassMemory is null, skip");
            return false;
        }
        boolean success = prefs.edit()
                .putInt(KEY_DIRECTION, memory.getDirection())
                .putFloat(KEY_ANGLE, memory.getAngle())
                .putLong(KEY_TIMESTAMP, memory.getTimestamp())
                .putBoolean(KEY_VALID, memory.isValid())
                .commit();
        Log.i(OffroadLog.TAG_STORAGE, "CompassMemory save: " + (success ? "OK" : "FAIL")
                + " dir=" + memory.getDirection() + " angle=" + memory.getAngle());
        return success;
    }

    /**
     * 加载指南针记忆值。
     * 文件损坏时返回默认值(方向无效、补偿为零)。
     * 需求追溯: [FUN-020, SCN-002~004], architecture.md §8.4
     */
    public CompassMemory load() {
        try {
            CompassMemory memory = new CompassMemory();
            memory.setDirection(prefs.getInt(KEY_DIRECTION, -1));
            memory.setAngle(prefs.getFloat(KEY_ANGLE, 0.0f));
            memory.setTimestamp(prefs.getLong(KEY_TIMESTAMP, 0L));
            memory.setValid(prefs.getBoolean(KEY_VALID, false));
            Log.i(OffroadLog.TAG_STORAGE, "CompassMemory load: " + memory);
            return memory;
        } catch (Exception e) {
            Log.e(OffroadLog.TAG_STORAGE, "CompassMemory load failed, use default", e);
            return new CompassMemory();
        }
    }

    /**
     * 清除记忆值(仅供测试或重置使用)。
     */
    public void clear() {
        prefs.edit().clear().commit();
        Log.i(OffroadLog.TAG_STORAGE, "CompassMemory cleared");
    }
}
