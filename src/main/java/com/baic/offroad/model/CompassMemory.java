package com.baic.offroad.model;

/**
 * 指南针记忆值 — 持久化实体。
 * 车辆由移动→停止时存储的指南针方向和角度，跨电源周期保持。
 *
 * 需求追溯: [FUN-019, FUN-020, NFR-007, SCN-001~004]
 * 数据模型: data_model.md §2.2
 */
public class CompassMemory {

    /** 方向枚举(0~7)，-1表示无有效记忆值 */
    private int direction;
    /** 角度(0°~360°) */
    private float angle;
    /** 记忆值存储时间(System.currentTimeMillis) */
    private long timestamp;
    /** 记忆值是否有效(首次使用前为false) */
    private boolean valid;

    public CompassMemory() {
        this.direction = OffroadDataBundle.COMPASS_DIR_INVALID;
        this.angle = 0.0f;
        this.timestamp = 0L;
        this.valid = false;
    }

    public CompassMemory(int direction, float angle, long timestamp, boolean valid) {
        this.direction = direction;
        this.angle = angle;
        this.timestamp = timestamp;
        this.valid = valid;
    }

    public int getDirection() { return direction; }
    public void setDirection(int direction) { this.direction = direction; }

    public float getAngle() { return angle; }
    public void setAngle(float angle) { this.angle = angle; }

    public long getTimestamp() { return timestamp; }
    public void setTimestamp(long timestamp) { this.timestamp = timestamp; }

    public boolean isValid() { return valid; }
    public void setValid(boolean valid) { this.valid = valid; }

    @Override
    public String toString() {
        return "CompassMemory{dir=" + direction + ", angle=" + angle
                + ", ts=" + timestamp + ", valid=" + valid + "}";
    }
}
