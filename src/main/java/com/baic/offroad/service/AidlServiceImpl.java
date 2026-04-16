package com.baic.offroad.service;

import android.content.Context;
import android.os.IBinder;
import android.os.RemoteCallbackList;
import android.os.RemoteException;
import android.util.Log;

import com.baic.offroad.aidl.v1.IOffroadCallback;
import com.baic.offroad.aidl.v1.IOffroadService;
import com.baic.offroad.model.OffroadDataBundle;
import com.baic.offroad.scheduler.AlgorithmScheduler;
import com.baic.offroad.util.OffroadLog;

/**
 * AIDL 服务接口实现。
 * 管理 UI 回调列表，推送数据。
 *
 * 需求追溯: architecture.md §6.1 AidlServiceImpl, api_design.md §2
 */
public class AidlServiceImpl extends IOffroadService.Stub {

    private final Context context;
    private final AlgorithmScheduler scheduler;

    /**
     * 使用 RemoteCallbackList 管理回调，自动处理死亡通知。
     * 需求追溯: api_design.md §2.1.3, architecture.md §7.5
     */
    private final RemoteCallbackList<IOffroadCallback> callbacks
            = new RemoteCallbackList<>();

    public AidlServiceImpl(Context context, AlgorithmScheduler scheduler) {
        this.context = context;
        this.scheduler = scheduler;
    }

    /**
     * 同步获取当前越野数据快照。
     * 需求追溯: [IF-006~IF-017], api_design.md §2.1.1
     */
    @Override
    public OffroadDataBundle getOffroadData() {
        enforceAccessPermission();
        return scheduler.getCurrentData();
    }

    /**
     * 注册数据推送回调。
     * 需求追溯: api_design.md §2.1.2
     *
     * 约束:
     * - 最大同时注册 8 个 [OffroadLog.MAX_CALLBACKS]
     * - 同一客户端重复注册会被忽略(基于 IBinder identity 去重)
     */
    @Override
    public void registerCallback(IOffroadCallback callback) {
        enforceAccessPermission();
        if (callback == null) return;

        // [H2 fix] 使用 RemoteCallbackList 内部计数替代手动 callbackCount
        int currentCount = callbacks.getRegisteredCallbackCount();
        if (currentCount >= OffroadLog.MAX_CALLBACKS) {
            Log.w(OffroadLog.TAG_LIFECYCLE, "registerCallback rejected: max callbacks reached ("
                    + OffroadLog.MAX_CALLBACKS + ")");
            return;
        }

        boolean registered = callbacks.register(callback);
        if (registered) {
            Log.i(OffroadLog.TAG_LIFECYCLE, "Callback registered, count="
                    + callbacks.getRegisteredCallbackCount());
        }
    }

    /**
     * 反注册回调。
     * 需求追溯: api_design.md §2.1.3
     */
    @Override
    public void unregisterCallback(IOffroadCallback callback) {
        enforceAccessPermission();
        if (callback == null) return;

        boolean unregistered = callbacks.unregister(callback);
        if (unregistered) {
            Log.i(OffroadLog.TAG_LIFECYCLE, "Callback unregistered, count="
                    + callbacks.getRegisteredCallbackCount());
        }
    }

    /**
     * 广播越野数据到所有注册回调。
     * 在每个计算周期调用。
     * 需求追溯: api_design.md §2.2.1
     */
    public void broadcastData(OffroadDataBundle data) {
        int count = callbacks.beginBroadcast();
        for (int i = 0; i < count; i++) {
            try {
                callbacks.getBroadcastItem(i).onOffroadDataUpdated(data);
            } catch (RemoteException e) {
                // Binder死亡，RemoteCallbackList 自动清除
                Log.w(OffroadLog.TAG_LIFECYCLE, "Callback broadcast failed, client may be dead", e);
            }
        }
        callbacks.finishBroadcast();
    }

    /**
     * 获取当前回调数量。
     * [H2 fix] 直接委托 RemoteCallbackList，自动扣除死亡客户端。
     */
    public int getCallbackCount() {
        return callbacks.getRegisteredCallbackCount();
    }

    private void enforceAccessPermission() {
        context.enforceCallingOrSelfPermission(
                OffroadLog.PERMISSION_ACCESS_OFFROAD_SERVICE,
                "Requires " + OffroadLog.PERMISSION_ACCESS_OFFROAD_SERVICE);
    }
}
