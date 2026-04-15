package com.baic.offroad.lifecycle;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.os.Build;
import android.util.Log;

import com.baic.offroad.util.OffroadLog;

/**
 * 进程生命周期管理器。
 * 管理前台服务通知、白名单保护、异常恢复。
 *
 * 需求追溯:
 * - [NFR-003] 上电自启动
 * - [NFR-005] 白名单保护
 * - [NFR-006] 异常关闭自动拉起
 * - architecture.md §6.1 LifecycleManager, §11.3
 */
public class LifecycleManager {

    private static final String CHANNEL_ID = "offroad_service_channel";
    private static final int NOTIFICATION_ID = 1001;

    private final Context context;

    /** 进程重启计数(每小时告警阈值: >3次 [architecture.md §10.2]) */
    private static int restartCount = 0;
    private static long firstRestartTime = 0;

    public LifecycleManager(Context context) {
        this.context = context;
    }

    /**
     * 启动前台服务。
     * 通过 Foreground Service 防止进程被后台清理。
     * 需求追溯: [NFR-005], architecture.md §11.3
     *
     * @param service 宿主 Service 实例
     */
    public void startForeground(Service service) {
        createNotificationChannel();

        Notification notification = buildNotification();
        service.startForeground(NOTIFICATION_ID, notification);
        Log.i(OffroadLog.TAG_LIFECYCLE, "Foreground service started");
    }

    /**
     * 创建通知渠道(Android O+)。
     */
    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "越野算法服务",
                    NotificationManager.IMPORTANCE_LOW); // 低优先级通知
            channel.setDescription("越野信息算法后台运行通知");
            channel.setShowBadge(false);

            NotificationManager nm = context.getSystemService(NotificationManager.class);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    /**
     * 构建前台服务通知。
     * 低优先级通知，用户基本不可见。
     */
    private Notification buildNotification() {
        Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder = new Notification.Builder(context, CHANNEL_ID);
        } else {
            builder = new Notification.Builder(context);
        }

        return builder
                .setContentTitle("越野信息")
                .setContentText("越野算法运行中")
                .setSmallIcon(android.R.drawable.ic_menu_compass) // 系统图标占位
                .setOngoing(true)
                .build();
    }

    /**
     * 记录进程重启事件，检查是否超过告警阈值。
     * 需求追溯: architecture.md §10.2 "进程重启次数 > 3次/小时 告警"
     */
    public void onProcessRestarted() {
        long now = System.currentTimeMillis();
        if (firstRestartTime == 0 || now - firstRestartTime > 3600_000) {
            // 重置每小时计数
            firstRestartTime = now;
            restartCount = 1;
        } else {
            restartCount++;
        }

        Log.w(OffroadLog.TAG_LIFECYCLE, "Process restarted, count=" + restartCount
                + " in current hour window");

        if (restartCount > 3) {
            Log.e(OffroadLog.TAG_LIFECYCLE, "WARNING: Process restart count exceeds threshold (>3/hour)!");
        }
    }

    /**
     * 获取当前小时内重启次数。
     */
    public int getRestartCount() {
        return restartCount;
    }
}
