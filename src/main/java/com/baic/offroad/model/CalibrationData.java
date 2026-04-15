package com.baic.offroad.model;

/**
 * 清零标定数据 — 持久化实体。
 * 下线清零时记录的角度补偿值，跨重启保持。
 *
 * 需求追溯: [FUN-026~029, NFR-008, SCN-009]
 * 数据模型: data_model.md §2.3
 */
public class CalibrationData {

    /** 倾斜角补偿值(°) */
    private float tiltOffset;
    /** 俯仰角补偿值(°) */
    private float pitchOffset;
    /** 是否已执行过清零 */
    private boolean calibrated;
    /** 清零执行时间戳 */
    private long calibTimestamp;

    /** 补偿值有效上限(data_model.md §6.1): abs(v) <= 10.0 */
    public static final float MAX_OFFSET = 10.0f;

    public CalibrationData() {
        this.tiltOffset = 0.0f;
        this.pitchOffset = 0.0f;
        this.calibrated = false;
        this.calibTimestamp = 0L;
    }

    public CalibrationData(float tiltOffset, float pitchOffset, boolean calibrated, long calibTimestamp) {
        this.tiltOffset = tiltOffset;
        this.pitchOffset = pitchOffset;
        this.calibrated = calibrated;
        this.calibTimestamp = calibTimestamp;
    }

    public float getTiltOffset() { return tiltOffset; }
    public void setTiltOffset(float tiltOffset) { this.tiltOffset = tiltOffset; }

    public float getPitchOffset() { return pitchOffset; }
    public void setPitchOffset(float pitchOffset) { this.pitchOffset = pitchOffset; }

    public boolean isCalibrated() { return calibrated; }
    public void setCalibrated(boolean calibrated) { this.calibrated = calibrated; }

    public long getCalibTimestamp() { return calibTimestamp; }
    public void setCalibTimestamp(long calibTimestamp) { this.calibTimestamp = calibTimestamp; }

    /**
     * 校验补偿值是否在有效范围内。
     * 超过 ±10° 视为异常，忽略补偿。
     * 需求追溯: data_model.md §6.1
     */
    public boolean isOffsetValid() {
        return Math.abs(tiltOffset) <= MAX_OFFSET && Math.abs(pitchOffset) <= MAX_OFFSET;
    }

    @Override
    public String toString() {
        return "CalibrationData{tiltOff=" + tiltOffset + ", pitchOff=" + pitchOffset
                + ", calibrated=" + calibrated + ", ts=" + calibTimestamp + "}";
    }
}
