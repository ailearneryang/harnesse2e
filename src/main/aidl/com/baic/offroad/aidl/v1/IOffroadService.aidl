// IOffroadService.aidl
// 越野数据服务接口 — 供 UI 应用绑定获取越野数据
// 需求追溯: 架构设计 §7.2
package com.baic.offroad.aidl.v1;

import com.baic.offroad.aidl.v1.OffroadDataBundle;
import com.baic.offroad.aidl.v1.IOffroadCallback;

interface IOffroadService {
    /**
     * 同步获取当前越野数据快照。
     * 适用于 UI 首次绑定时拉取最新数据。
     * [IF-006 ~ IF-017]
     */
    OffroadDataBundle getOffroadData();

    /**
     * 注册数据推送回调。
     * 算法服务在每个计算周期结束后向所有已注册回调推送最新数据。
     * 同一客户端重复注册会被忽略（基于 IBinder identity 去重）。
     * 最大同时注册回调数: 8 个。
     */
    void registerCallback(IOffroadCallback callback);

    /**
     * 反注册回调。客户端销毁前必须调用。
     * 服务端同时通过 DeathRecipient 监控客户端死亡，自动清除失效回调。
     */
    void unregisterCallback(IOffroadCallback callback);
}
