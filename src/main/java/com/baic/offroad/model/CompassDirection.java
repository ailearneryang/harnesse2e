package com.baic.offroad.model;

/**
 * 指南针方向枚举 — 8方位定义。
 * 需求追溯: [FUN-017], data_model.md §2.1 方向枚举定义
 */
public enum CompassDirection {
    N(0, "北", 337.5f, 22.5f),
    NE(1, "东北", 22.5f, 67.5f),
    E(2, "东", 67.5f, 112.5f),
    SE(3, "东南", 112.5f, 157.5f),
    S(4, "南", 157.5f, 202.5f),
    SW(5, "西南", 202.5f, 247.5f),
    W(6, "西", 247.5f, 292.5f),
    NW(7, "西北", 292.5f, 337.5f);

    private final int code;
    private final String label;
    private final float minAngle;
    private final float maxAngle;

    CompassDirection(int code, String label, float minAngle, float maxAngle) {
        this.code = code;
        this.label = label;
        this.minAngle = minAngle;
        this.maxAngle = maxAngle;
    }

    public int getCode() { return code; }
    public String getLabel() { return label; }

    /**
     * 根据角度(0~360)计算所属8方位。
     * 北方(N)跨越 337.5°~22.5°，需特殊处理。
     *
     * @param angle 角度值 0.0~360.0
     * @return 对应方位枚举
     */
    public static CompassDirection fromAngle(float angle) {
        // 归一化到 [0, 360)
        angle = ((angle % 360.0f) + 360.0f) % 360.0f;

        // 北方跨越 360°/0° 边界
        if (angle >= 337.5f || angle < 22.5f) {
            return N;
        }

        for (CompassDirection dir : values()) {
            if (dir == N) continue; // N 已处理
            if (angle >= dir.minAngle && angle < dir.maxAngle) {
                return dir;
            }
        }
        return N; // 不应到达
    }

    /**
     * 根据整数编码(0~7)获取方向枚举。
     * @param code 方向编码
     * @return 对应枚举, 无效编码返回 null
     */
    public static CompassDirection fromCode(int code) {
        for (CompassDirection dir : values()) {
            if (dir.code == code) {
                return dir;
            }
        }
        return null;
    }
}
