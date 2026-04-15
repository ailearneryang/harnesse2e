package com.baic.offroad.model;

import android.os.Parcel;
import android.os.Parcelable;
import android.os.SystemClock;

/**
 * 越野数据包 — 单帧完整越野数据。
 * 每个算法计算周期生成一个实例，通过 AIDL 推送给 UI 消费方。
 *
 * 需求追溯: [IF-006 ~ IF-017], architecture.md §8.1
 * 数据模型: data_model.md §2.1
 */
public class OffroadDataBundle implements Parcelable {

    // ---- 倾斜角 (F01) [FUN-001~004, IF-006, IF-007] ----
    /** 车辆左右倾斜角(°)，范围 ±40° */
    private float tiltAngle;
    /** 倾斜角有效标志 */
    private boolean tiltAngleValid;

    // ---- 俯仰角 (F02) [FUN-005~008, IF-008, IF-009] ----
    /** 车辆前后俯仰角(°)，范围 ±60° */
    private float pitchAngle;
    /** 俯仰角有效标志 */
    private boolean pitchAngleValid;

    // ---- 大气压力 (F04) [FUN-013~016, IF-010, IF-011] ----
    /** 大气压力(hPa)，范围 300~1100 */
    private float pressure;
    /** 大气压力有效标志 */
    private boolean pressureValid;

    // ---- 海拔高度 (F03) [FUN-009~012, IF-012, IF-013] ----
    /** 海拔高度(m)，范围 -500~9000 */
    private float altitude;
    /** 海拔有效标志 */
    private boolean altitudeValid;

    // ---- 指南针 (F05) [FUN-017~022, IF-014~017] ----
    /** 指南针方向(8方位枚举 0~7)，-1表示无效 */
    private int compassDirection;
    /** 指南针方向有效标志 */
    private boolean compassDirectionValid;
    /** 指南针角度(°)，范围 0~360 */
    private float compassAngle;
    /** 指南针角度有效标志 */
    private boolean compassAngleValid;

    /** 数据生成时间戳(elapsedRealtime ms) */
    private long timestamp;

    // ---- 常量: 数据范围约束 (data_model.md §6.1) ----
    public static final float TILT_ANGLE_MIN = -40.0f;
    public static final float TILT_ANGLE_MAX = 40.0f;
    public static final float PITCH_ANGLE_MIN = -60.0f;
    public static final float PITCH_ANGLE_MAX = 60.0f;
    public static final float PRESSURE_MIN = 300.0f;
    public static final float PRESSURE_MAX = 1100.0f;
    public static final float ALTITUDE_MIN = -500.0f;
    public static final float ALTITUDE_MAX = 9000.0f;
    public static final float COMPASS_ANGLE_MIN = 0.0f;
    public static final float COMPASS_ANGLE_MAX = 360.0f;
    public static final int COMPASS_DIR_MIN = 0;
    public static final int COMPASS_DIR_MAX = 7;
    public static final int COMPASS_DIR_INVALID = -1;

    public OffroadDataBundle() {
        // 默认值: 所有数据无效 (data_model.md §2.1)
        this.tiltAngle = 0.0f;
        this.tiltAngleValid = false;
        this.pitchAngle = 0.0f;
        this.pitchAngleValid = false;
        this.pressure = 0.0f;
        this.pressureValid = false;
        this.altitude = 0.0f;
        this.altitudeValid = false;
        this.compassDirection = COMPASS_DIR_INVALID;
        this.compassDirectionValid = false;
        this.compassAngle = 0.0f;
        this.compassAngleValid = false;
        this.timestamp = SystemClock.elapsedRealtime();
    }

    // ---- Getters & Setters ----
    public float getTiltAngle() { return tiltAngle; }
    public void setTiltAngle(float tiltAngle) { this.tiltAngle = tiltAngle; }

    public boolean isTiltAngleValid() { return tiltAngleValid; }
    public void setTiltAngleValid(boolean valid) { this.tiltAngleValid = valid; }

    public float getPitchAngle() { return pitchAngle; }
    public void setPitchAngle(float pitchAngle) { this.pitchAngle = pitchAngle; }

    public boolean isPitchAngleValid() { return pitchAngleValid; }
    public void setPitchAngleValid(boolean valid) { this.pitchAngleValid = valid; }

    public float getPressure() { return pressure; }
    public void setPressure(float pressure) { this.pressure = pressure; }

    public boolean isPressureValid() { return pressureValid; }
    public void setPressureValid(boolean valid) { this.pressureValid = valid; }

    public float getAltitude() { return altitude; }
    public void setAltitude(float altitude) { this.altitude = altitude; }

    public boolean isAltitudeValid() { return altitudeValid; }
    public void setAltitudeValid(boolean valid) { this.altitudeValid = valid; }

    public int getCompassDirection() { return compassDirection; }
    public void setCompassDirection(int direction) { this.compassDirection = direction; }

    public boolean isCompassDirectionValid() { return compassDirectionValid; }
    public void setCompassDirectionValid(boolean valid) { this.compassDirectionValid = valid; }

    public float getCompassAngle() { return compassAngle; }
    public void setCompassAngle(float angle) { this.compassAngle = angle; }

    public boolean isCompassAngleValid() { return compassAngleValid; }
    public void setCompassAngleValid(boolean valid) { this.compassAngleValid = valid; }

    public long getTimestamp() { return timestamp; }
    public void setTimestamp(long timestamp) { this.timestamp = timestamp; }

    /**
     * 对数据进行范围校验和截断。
     * 违反范围约束的数据置对应有效标志为 false。
     * 需求追溯: data_model.md §6.1 校验规则
     */
    public void validate() {
        // 倾斜角校验: abs(v) <= 40.0, 截断到 ±40°, 置 valid=false
        if (Math.abs(tiltAngle) > TILT_ANGLE_MAX) {
            tiltAngle = Math.max(TILT_ANGLE_MIN, Math.min(TILT_ANGLE_MAX, tiltAngle));
            tiltAngleValid = false;
        }

        // 俯仰角校验: abs(v) <= 60.0, 截断到 ±60°, 置 valid=false
        if (Math.abs(pitchAngle) > PITCH_ANGLE_MAX) {
            pitchAngle = Math.max(PITCH_ANGLE_MIN, Math.min(PITCH_ANGLE_MAX, pitchAngle));
            pitchAngleValid = false;
        }

        // 大气压力校验: 300 <= v <= 1100, 超量程置 valid=false
        if (pressure < PRESSURE_MIN || pressure > PRESSURE_MAX) {
            pressureValid = false;
        }

        // 海拔校验: -500 <= v <= 9000, 超量程置 valid=false
        if (altitude < ALTITUDE_MIN || altitude > ALTITUDE_MAX) {
            altitudeValid = false;
        }

        // 指南针角度: 取模 360.0
        if (compassAngle < COMPASS_ANGLE_MIN || compassAngle >= COMPASS_ANGLE_MAX) {
            compassAngle = ((compassAngle % COMPASS_ANGLE_MAX) + COMPASS_ANGLE_MAX) % COMPASS_ANGLE_MAX;
        }

        // 指南针方向: 0~7, 否则置 valid=false
        if (compassDirection < COMPASS_DIR_MIN || compassDirection > COMPASS_DIR_MAX) {
            if (compassDirection != COMPASS_DIR_INVALID) {
                compassDirectionValid = false;
            }
        }
    }

    // ---- Parcelable 实现 ----

    protected OffroadDataBundle(Parcel in) {
        tiltAngle = in.readFloat();
        tiltAngleValid = in.readByte() != 0;
        pitchAngle = in.readFloat();
        pitchAngleValid = in.readByte() != 0;
        pressure = in.readFloat();
        pressureValid = in.readByte() != 0;
        altitude = in.readFloat();
        altitudeValid = in.readByte() != 0;
        compassDirection = in.readInt();
        compassDirectionValid = in.readByte() != 0;
        compassAngle = in.readFloat();
        compassAngleValid = in.readByte() != 0;
        timestamp = in.readLong();
    }

    @Override
    public void writeToParcel(Parcel dest, int flags) {
        dest.writeFloat(tiltAngle);
        dest.writeByte((byte) (tiltAngleValid ? 1 : 0));
        dest.writeFloat(pitchAngle);
        dest.writeByte((byte) (pitchAngleValid ? 1 : 0));
        dest.writeFloat(pressure);
        dest.writeByte((byte) (pressureValid ? 1 : 0));
        dest.writeFloat(altitude);
        dest.writeByte((byte) (altitudeValid ? 1 : 0));
        dest.writeInt(compassDirection);
        dest.writeByte((byte) (compassDirectionValid ? 1 : 0));
        dest.writeFloat(compassAngle);
        dest.writeByte((byte) (compassAngleValid ? 1 : 0));
        dest.writeLong(timestamp);
    }

    @Override
    public int describeContents() {
        return 0;
    }

    public static final Creator<OffroadDataBundle> CREATOR = new Creator<OffroadDataBundle>() {
        @Override
        public OffroadDataBundle createFromParcel(Parcel in) {
            return new OffroadDataBundle(in);
        }

        @Override
        public OffroadDataBundle[] newArray(int size) {
            return new OffroadDataBundle[size];
        }
    };

    /**
     * 从 float 数组构建(JNI 结果解包用)。
     * 数组布局与 OffroadBridge.nativeCompute() 返回值对应。
     * 需求追溯: architecture.md §6.2 桥接契约
     */
    public static OffroadDataBundle fromFloatArray(float[] result) {
        if (result == null || result.length < 12) {
            return new OffroadDataBundle();
        }
        OffroadDataBundle bundle = new OffroadDataBundle();
        bundle.tiltAngle = result[0];
        bundle.tiltAngleValid = result[1] > 0.5f;
        bundle.pitchAngle = result[2];
        bundle.pitchAngleValid = result[3] > 0.5f;
        bundle.pressure = result[4];
        bundle.pressureValid = result[5] > 0.5f;
        bundle.altitude = result[6];
        bundle.altitudeValid = result[7] > 0.5f;
        bundle.compassDirection = (int) result[8];
        bundle.compassDirectionValid = result[9] > 0.5f;
        bundle.compassAngle = result[10];
        bundle.compassAngleValid = result[11] > 0.5f;
        bundle.timestamp = SystemClock.elapsedRealtime();
        bundle.validate();
        return bundle;
    }

    @Override
    public String toString() {
        return "OffroadDataBundle{" +
                "tilt=" + tiltAngle + "(v=" + tiltAngleValid + ")" +
                ", pitch=" + pitchAngle + "(v=" + pitchAngleValid + ")" +
                ", pressure=" + pressure + "(v=" + pressureValid + ")" +
                ", altitude=" + altitude + "(v=" + altitudeValid + ")" +
                ", dir=" + compassDirection + "(v=" + compassDirectionValid + ")" +
                ", angle=" + compassAngle + "(v=" + compassAngleValid + ")" +
                ", ts=" + timestamp +
                '}';
    }
}
