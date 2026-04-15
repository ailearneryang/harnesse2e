// IOffroadCallback.aidl
// 数据推送回调接口 — 每个计算周期推送一次完整越野数据
// 需求追溯: 架构设计 §7.2
package com.baic.offroad.aidl.v1;

import com.baic.offroad.aidl.v1.OffroadDataBundle;

interface IOffroadCallback {
    /**
     * 越野数据更新回调。
     * 每个计算周期(~50ms @20Hz)推送一次完整数据。
     * 回调在 Binder 线程池上执行，UI 消费方需自行切换到主线程。
     */
    void onOffroadDataUpdated(in OffroadDataBundle data);
}
