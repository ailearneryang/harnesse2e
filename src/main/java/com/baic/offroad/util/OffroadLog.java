package com.baic.offroad.util;

/**
 * 日志工具类 — 统一日志 Tag 管理。
 * 需求追溯: architecture.md §10.1 日志与脱敏
 */
public final class OffroadLog {

    private OffroadLog() {}

    // ---- 日志 Tag 定义 (architecture.md §10.1) ----
    public static final String TAG_LIFECYCLE = "OffRoad.Lifecycle";
    public static final String TAG_SENSOR = "OffRoad.Sensor";
    public static final String TAG_ALGORITHM = "OffRoad.Algorithm";
    public static final String TAG_CAN = "OffRoad.CAN";
    public static final String TAG_CALIB = "OffRoad.Calib";
    public static final String TAG_STORAGE = "OffRoad.Storage";

    /** EMS_0x131 超时时长(ms)，超过此时间视为信号丢失 [FUN-015] */
    public static final long EMS_SIGNAL_TIMEOUT_MS = 5000L;

    /** 最大回调注册数 (api_design.md §2.1.2) */
    public static final int MAX_CALLBACKS = 8;

    /** 指南针记忆值 SharedPreferences 文件名 */
    public static final String SP_COMPASS_MEMORY = "offroad_compass_memory";

    /** 清零标定数据 SharedPreferences 文件名 */
    public static final String SP_CALIBRATION = "offroad_calibration";

    /** 安装配置文件路径 */
    public static final String CONFIG_FILE_PATH = "/data/local/offroad/config.json";

    /** 算法默认更新频率(Hz) [TBD-010 默认值] */
    public static final int DEFAULT_UPDATE_RATE_HZ = 20;

    /** 进程自动重拉起最大重试次数(指数退避) */
    public static final int MAX_STARTUP_RETRIES = 5;

    /** RSS 内存告警阈值(KB) (architecture.md §10.2) */
    public static final long RSS_WARNING_THRESHOLD_KB = 900;

    /** 计算周期超时告警阈值(ms) */
    public static final long COMPUTE_CYCLE_WARNING_MS = 50;
}
