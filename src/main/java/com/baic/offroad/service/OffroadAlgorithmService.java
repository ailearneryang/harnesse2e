package com.baic.offroad.service;

import android.app.Service;
import android.content.pm.PackageManager;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;

import com.baic.offroad.algorithm.OffroadBridge;
import com.baic.offroad.lifecycle.LifecycleManager;
import com.baic.offroad.model.CompassMemory;
import com.baic.offroad.model.InstallationConfig;
import com.baic.offroad.model.OffroadDataBundle;
import com.baic.offroad.persistence.CalibrationStore;
import com.baic.offroad.persistence.CompassMemoryStore;
import com.baic.offroad.persistence.ConfigStore;
import com.baic.offroad.scheduler.AlgorithmScheduler;
import com.baic.offroad.sensor.CanSignalAdapter;
import com.baic.offroad.sensor.LocationCollector;
import com.baic.offroad.sensor.SensorCollector;
import com.baic.offroad.util.OffroadLog;

/**
 * 越野算法主服务 — 独立进程运行。
 *
 * 生命周期:
 * 1. onCreate: 初始化所有模块
 * 2. onStartCommand: 启动前台服务 + 算法循环
 * 3. onBind: 返回 AIDL Binder
 * 4. onDestroy: 保存状态 + 释放资源
 *
 * 需求追溯:
 * - [NFR-003] 上电自启动
 * - [NFR-005] 白名单保护(persistent + foreground)
 * - [NFR-006] 异常自动拉起
 * - architecture.md §4.3, §11.1
 */
public class OffroadAlgorithmService extends Service {

    private static final String TAG = OffroadLog.TAG_LIFECYCLE;

    // ---- 模块实例 ----
    private LifecycleManager lifecycleManager;
    private SensorCollector sensorCollector;
    private LocationCollector locationCollector;
    private CanSignalAdapter canSignalAdapter;
    private CompassMemoryStore compassMemoryStore;
    private CalibrationStore calibrationStore;
    private ConfigStore configStore;
    private AlgorithmScheduler scheduler;
    private AidlServiceImpl aidlService;
    private InstallationConfig installConfig;

    /** 服务状态 (architecture.md §8.2) */
    private enum ServiceState {
        STARTING, RUNNING, SLEEPING, CRASHED
    }
    private ServiceState state = ServiceState.STARTING;

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "OffroadAlgorithmService onCreate");

        try {
            initModules();
            state = ServiceState.STARTING;
        } catch (Exception e) {
            Log.e(TAG, "onCreate failed", e);
            state = ServiceState.CRASHED;
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.i(TAG, "onStartCommand flags=" + flags + " startId=" + startId);

        // 启动前台服务 [NFR-005]
        lifecycleManager.startForeground(this);

        // 记录重启事件
        lifecycleManager.onProcessRestarted();

        // 启动算法计算循环
        startAlgorithm();

        // START_STICKY: 被杀后系统自动重启 [NFR-006]
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        if (checkCallingOrSelfPermission(OffroadLog.PERMISSION_ACCESS_OFFROAD_SERVICE)
                != PackageManager.PERMISSION_GRANTED) {
            Log.w(TAG, "Unauthorized bind attempt: missing "
                    + OffroadLog.PERMISSION_ACCESS_OFFROAD_SERVICE);
            return null;
        }

        Log.i(TAG, "onBind authorized");
        return aidlService != null ? (IBinder) aidlService : null;
    }

    @Override
    public void onDestroy() {
        Log.i(TAG, "onDestroy");
        state = ServiceState.CRASHED; // 非预期销毁视为 CRASHED

        stopAlgorithm();
        super.onDestroy();
    }

    // ---- 初始化 ----

    /**
     * 初始化所有模块。
     * 需求追溯: architecture.md §11.1 启动时序
     */
    private void initModules() {
        // 1. 加载配置文件 [ASM-05]
        configStore = new ConfigStore();
        installConfig = configStore.load();
        Log.i(TAG, "Config loaded: version=" + installConfig.getVersion());

        // 2~3. 初始化持久化存储
        compassMemoryStore = new CompassMemoryStore(this);
        calibrationStore = new CalibrationStore(this);

        // 3. 恢复指南针记忆值 [SCN-002~004]
        CompassMemory memory = compassMemoryStore.load();
        Log.i(TAG, "Compass memory restored: " + memory);

        // 4~5. 初始化传感器采集器
        sensorCollector = new SensorCollector(this);
        locationCollector = new LocationCollector(this);

        // 6. 初始化 CAN 适配器
        canSignalAdapter = new CanSignalAdapter();

        // 7. 加载 native 库
        OffroadBridge.loadLibrary();

        // 8. 初始化调度器
        scheduler = new AlgorithmScheduler(
                sensorCollector, locationCollector, canSignalAdapter,
                compassMemoryStore, calibrationStore, installConfig);

        // 9. 初始化 AIDL 服务
        aidlService = new AidlServiceImpl(this, scheduler);

        // 注册清零指令监听 [IF-005]
        canSignalAdapter.setCalibrationCommandListener(() -> {
            Log.w(OffroadLog.TAG_CALIB, "Calibration command received, executing...");
            boolean success = scheduler.executeCalibration();
            Log.w(OffroadLog.TAG_CALIB, "Calibration result: " + (success ? "SUCCESS" : "FAILED"));
        });

        // 设置算法结果回调 → AIDL 广播
        scheduler.setResultListener(data -> {
            if (aidlService != null) {
                aidlService.broadcastData(data);
            }
        });

        // 初始化生命周期管理
        lifecycleManager = new LifecycleManager(this);
    }

    /**
     * 启动算法计算循环。
     */
    private void startAlgorithm() {
        if (state == ServiceState.RUNNING) {
            Log.w(TAG, "Algorithm already running");
            return;
        }

        // 注册传感器 [IF-002]
        boolean sensorOk = sensorCollector.start();
        Log.i(TAG, "Sensor registration: " + (sensorOk ? "OK" : "PARTIAL"));

        // 注册 GPS [IF-001]
        boolean gpsOk = locationCollector.start();
        Log.i(TAG, "GPS registration: " + (gpsOk ? "OK" : "FAILED"));

        // 注册 CAN [IF-003, IF-004]
        boolean canOk = canSignalAdapter.start();
        Log.i(TAG, "CAN registration: " + (canOk ? "OK" : "FAILED (middleware not set)"));

        // 启动算法调度器
        scheduler.start();

        state = ServiceState.RUNNING;
        Log.i(TAG, "OffroadAlgorithmService RUNNING");
    }

    /**
     * 停止算法计算循环。
     */
    private void stopAlgorithm() {
        scheduler.stop();
        sensorCollector.stop();
        locationCollector.stop();
        canSignalAdapter.stop();
        Log.i(TAG, "Algorithm stopped, stats: " + scheduler.getStats());
    }

}
