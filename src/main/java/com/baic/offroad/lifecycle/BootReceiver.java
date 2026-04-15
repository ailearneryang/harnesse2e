package com.baic.offroad.lifecycle;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

import com.baic.offroad.service.OffroadAlgorithmService;
import com.baic.offroad.util.OffroadLog;

/**
 * 开机自启动广播接收器。
 * 接收 BOOT_COMPLETED 广播后启动越野算法服务。
 *
 * 需求追溯: [NFR-003], architecture.md §11.1
 */
public class BootReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent != null ? intent.getAction() : "null";
        Log.i(OffroadLog.TAG_LIFECYCLE, "BootReceiver: " + action);

        if (Intent.ACTION_BOOT_COMPLETED.equals(action)
                || Intent.ACTION_LOCKED_BOOT_COMPLETED.equals(action)) {

            Intent serviceIntent = new Intent(context, OffroadAlgorithmService.class);

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(serviceIntent);
            } else {
                context.startService(serviceIntent);
            }

            Log.i(OffroadLog.TAG_LIFECYCLE, "OffroadAlgorithmService start requested on boot");
        }
    }
}
