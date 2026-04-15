package com.baic.offroad.sensor;

import android.content.Context;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Bundle;
import android.os.Looper;
import android.util.Log;

import com.baic.offroad.util.OffroadLog;

/**
 * GPS/GNSS 数据采集器。
 * 注册 LocationManager，采集经纬度/海拔/航向/速度。
 *
 * 需求追溯: [IF-001], architecture.md §6.1 LocationCollector
 */
public class LocationCollector implements LocationListener {

    private final LocationManager locationManager;

    // 缓存最新位置数据 (避免频繁对象创建)
    private volatile double latitude;
    private volatile double longitude;
    private volatile float gpsAltitude;
    private volatile float gpsBearing;
    private volatile float gpsSpeed;
    private volatile boolean gpsValid = false;
    private volatile long lastUpdateTimestamp = 0;

    /** GPS 更新间隔(ms): 1Hz 足够指南针融合 */
    private static final long MIN_TIME_MS = 1000L;
    /** GPS 最小位移(m): 0 表示仅按时间触发 */
    private static final float MIN_DISTANCE_M = 0.0f;
    /** GPS 数据超时(ms): 超过此时间视为信号丢失 [SCN-005] */
    private static final long GPS_TIMEOUT_MS = 10000L;

    public LocationCollector(Context context) {
        this.locationManager = (LocationManager) context.getSystemService(Context.LOCATION_SERVICE);
    }

    /** 用于测试的构造函数 */
    public LocationCollector(LocationManager locationManager) {
        this.locationManager = locationManager;
    }

    /**
     * 启动位置监听。
     * 需要 ACCESS_FINE_LOCATION 权限(系统预装APK预授权)。
     * 需求追溯: [IF-001], architecture.md §9.1
     */
    @SuppressWarnings("MissingPermission")
    public boolean start() {
        if (locationManager == null) {
            Log.e(OffroadLog.TAG_SENSOR, "LocationManager is null, cannot start");
            return false;
        }

        try {
            locationManager.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER,
                    MIN_TIME_MS,
                    MIN_DISTANCE_M,
                    this,
                    Looper.getMainLooper());
            Log.i(OffroadLog.TAG_SENSOR, "GPS location updates registered");
            return true;
        } catch (SecurityException e) {
            Log.e(OffroadLog.TAG_SENSOR, "GPS permission denied", e);
            return false;
        } catch (IllegalArgumentException e) {
            Log.e(OffroadLog.TAG_SENSOR, "GPS provider not available", e);
            return false;
        }
    }

    /**
     * 停止位置监听。
     */
    public void stop() {
        if (locationManager != null) {
            locationManager.removeUpdates(this);
            gpsValid = false;
            Log.i(OffroadLog.TAG_SENSOR, "GPS location updates unregistered");
        }
    }

    @Override
    public void onLocationChanged(Location location) {
        if (location == null) return;

        latitude = location.getLatitude();
        longitude = location.getLongitude();
        gpsAltitude = (float) location.getAltitude();
        gpsBearing = location.getBearing();
        gpsSpeed = location.getSpeed();
        gpsValid = true;
        lastUpdateTimestamp = System.currentTimeMillis();
    }

    @Override
    public void onStatusChanged(String provider, int status, Bundle extras) {
        Log.d(OffroadLog.TAG_SENSOR, "GPS status changed: " + provider + " status=" + status);
    }

    @Override
    public void onProviderEnabled(String provider) {
        Log.i(OffroadLog.TAG_SENSOR, "GPS provider enabled: " + provider);
    }

    @Override
    public void onProviderDisabled(String provider) {
        Log.w(OffroadLog.TAG_SENSOR, "GPS provider disabled: " + provider);
        gpsValid = false;
    }

    /**
     * 检查 GPS 数据是否有效(未超时)。
     * 超过 GPS_TIMEOUT_MS 未更新视为信号丢失。
     * 需求追溯: [SCN-005, FUN-021]
     */
    public boolean isGpsValid() {
        if (!gpsValid) return false;
        long elapsed = System.currentTimeMillis() - lastUpdateTimestamp;
        if (elapsed > GPS_TIMEOUT_MS) {
            gpsValid = false;
            return false;
        }
        return true;
    }

    // ---- 数据读取 ----
    public double getLatitude() { return latitude; }
    public double getLongitude() { return longitude; }
    public float getGpsAltitude() { return gpsAltitude; }
    public float getGpsBearing() { return gpsBearing; }
    public float getGpsSpeed() { return gpsSpeed; }
    public long getLastUpdateTimestamp() { return lastUpdateTimestamp; }
}
