package com.baic.offroad.model;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * 安装姿态配置 — 只读配置实体。
 * ICC安装姿态矩阵和IMU布置姿态参数，由标定工具写入。
 *
 * 需求追溯: [FUN-002, FUN-006, TBD-001]
 * 数据模型: data_model.md §2.4
 */
public class InstallationConfig {

    /** 配置文件版本号 */
    private int version;
    /** ICC安装姿态3×3旋转矩阵(行优先) */
    private float[] iccAttitudeMatrix;
    /** IMU布置姿态3×3旋转矩阵 */
    private float[] imuAttitudeMatrix;
    /** 大气压力滤波窗口大小 [TBD-011] */
    private int pressureFilterWindow;
    /** 算法更新频率(Hz) [TBD-010] */
    private int updateRateHz;

    /** 默认单位矩阵(Identity) — 姿态矩阵参数缺失时的占位值 [RISK-01] */
    private static final float[] IDENTITY_MATRIX = {
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
        0.0f, 0.0f, 1.0f
    };

    /** 默认滤波窗口大小 */
    public static final int DEFAULT_FILTER_WINDOW = 10;
    /** 默认更新频率 */
    public static final int DEFAULT_UPDATE_RATE_HZ = 20;
    /** 矩阵有效性检验容差: 行列式 ≈ 1.0 (±0.01) */
    public static final float DETERMINANT_TOLERANCE = 0.01f;

    public InstallationConfig() {
        this.version = 1;
        this.iccAttitudeMatrix = IDENTITY_MATRIX.clone();
        this.imuAttitudeMatrix = IDENTITY_MATRIX.clone();
        this.pressureFilterWindow = DEFAULT_FILTER_WINDOW;
        this.updateRateHz = DEFAULT_UPDATE_RATE_HZ;
    }

    // ---- Getters & Setters ----
    public int getVersion() { return version; }
    public void setVersion(int version) { this.version = version; }

    public float[] getIccAttitudeMatrix() { return iccAttitudeMatrix; }
    public void setIccAttitudeMatrix(float[] matrix) { this.iccAttitudeMatrix = matrix; }

    public float[] getImuAttitudeMatrix() { return imuAttitudeMatrix; }
    public void setImuAttitudeMatrix(float[] matrix) { this.imuAttitudeMatrix = matrix; }

    public int getPressureFilterWindow() { return pressureFilterWindow; }
    public void setPressureFilterWindow(int window) { this.pressureFilterWindow = window; }

    public int getUpdateRateHz() { return updateRateHz; }
    public void setUpdateRateHz(int hz) { this.updateRateHz = hz; }

    /**
     * 计算3×3矩阵行列式。
     * 用于校验旋转矩阵有效性(行列式 ≈ 1.0)。
     * 需求追溯: data_model.md §6.1
     */
    public static float determinant3x3(float[] m) {
        if (m == null || m.length != 9) return 0.0f;
        return m[0] * (m[4] * m[8] - m[5] * m[7])
             - m[1] * (m[3] * m[8] - m[5] * m[6])
             + m[2] * (m[3] * m[7] - m[4] * m[6]);
    }

    /**
     * 校验旋转矩阵有效性: 行列式 ≈ 1.0 (±0.01)。
     * 不满足时应回退到单位矩阵。
     */
    public static boolean isValidRotationMatrix(float[] m) {
        float det = determinant3x3(m);
        return Math.abs(det - 1.0f) <= DETERMINANT_TOLERANCE;
    }

    /**
     * 校验并修复配置。
     * 无效矩阵回退为单位矩阵。
     */
    public void validateAndFix() {
        if (!isValidRotationMatrix(iccAttitudeMatrix)) {
            iccAttitudeMatrix = IDENTITY_MATRIX.clone();
        }
        if (!isValidRotationMatrix(imuAttitudeMatrix)) {
            imuAttitudeMatrix = IDENTITY_MATRIX.clone();
        }
        if (pressureFilterWindow <= 0) {
            pressureFilterWindow = DEFAULT_FILTER_WINDOW;
        }
        if (updateRateHz <= 0 || updateRateHz > 200) {
            updateRateHz = DEFAULT_UPDATE_RATE_HZ;
        }
    }

    /**
     * 从 JSON 字符串解析配置。
     * 需求追溯: architecture.md §6.4 ConfigStore
     */
    public static InstallationConfig fromJson(String json) throws JSONException {
        JSONObject obj = new JSONObject(json);
        InstallationConfig config = new InstallationConfig();
        config.version = obj.optInt("version", 1);

        JSONArray iccArr = obj.optJSONArray("iccAttitudeMatrix");
        if (iccArr != null && iccArr.length() == 9) {
            float[] matrix = new float[9];
            for (int i = 0; i < 9; i++) {
                matrix[i] = (float) iccArr.getDouble(i);
            }
            config.iccAttitudeMatrix = matrix;
        }

        JSONArray imuArr = obj.optJSONArray("imuAttitudeMatrix");
        if (imuArr != null && imuArr.length() == 9) {
            float[] matrix = new float[9];
            for (int i = 0; i < 9; i++) {
                matrix[i] = (float) imuArr.getDouble(i);
            }
            config.imuAttitudeMatrix = matrix;
        }

        config.pressureFilterWindow = obj.optInt("pressureFilterWindow", DEFAULT_FILTER_WINDOW);
        config.updateRateHz = obj.optInt("updateRateHz", DEFAULT_UPDATE_RATE_HZ);

        config.validateAndFix();
        return config;
    }

    /**
     * 序列化为 JSON 字符串。
     */
    public String toJson() throws JSONException {
        JSONObject obj = new JSONObject();
        obj.put("version", version);

        JSONArray iccArr = new JSONArray();
        for (float v : iccAttitudeMatrix) iccArr.put(v);
        obj.put("iccAttitudeMatrix", iccArr);

        JSONArray imuArr = new JSONArray();
        for (float v : imuAttitudeMatrix) imuArr.put(v);
        obj.put("imuAttitudeMatrix", imuArr);

        obj.put("pressureFilterWindow", pressureFilterWindow);
        obj.put("updateRateHz", updateRateHz);

        return obj.toString(2);
    }
}
