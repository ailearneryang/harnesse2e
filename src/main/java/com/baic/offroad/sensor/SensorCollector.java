package com.baic.offroad.sensor;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.util.Log;

import com.baic.offroad.util.OffroadLog;

/**
 * IMU 传感器数据采集器。
 * 注册 SensorManager，采集加速度/角速度数据。
 *
 * 输入: TYPE_ACCELEROMETER + TYPE_GYROSCOPE
 * 输出: 三轴加速度 + 三轴角速度 (缓存到复用 float 数组)
 *
 * 需求追溯: [IF-002], architecture.md §6.1 SensorCollector
 */
public class SensorCollector implements SensorEventListener {

    private final SensorManager sensorManager;
    private Sensor accelerometer;
    private Sensor gyroscope;

    // 复用数组避免频繁对象创建 (architecture.md §11.2 内存纪律)
    private final float[] accelData = new float[3]; // x, y, z
    private final float[] gyroData = new float[3];  // x, y, z
    private volatile boolean accelValid = false;
    private volatile boolean gyroValid = false;
    private volatile long lastAccelTimestamp = 0;
    private volatile long lastGyroTimestamp = 0;

    /** 数据监听器接口 */
    public interface OnSensorDataListener {
        void onAccelUpdated(float x, float y, float z, long timestamp);
        void onGyroUpdated(float x, float y, float z, long timestamp);
    }

    private OnSensorDataListener listener;

    public SensorCollector(Context context) {
        this.sensorManager = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
    }

    /** 用于测试的构造函数 */
    public SensorCollector(SensorManager sensorManager) {
        this.sensorManager = sensorManager;
    }

    public void setListener(OnSensorDataListener listener) {
        this.listener = listener;
    }

    /**
     * 启动传感器监听。
     * 使用 SENSOR_DELAY_GAME 采样率(~50Hz)以平衡精度和内存。
     *
     * @return true 注册成功, false 传感器不可用
     */
    public boolean start() {
        if (sensorManager == null) {
            Log.e(OffroadLog.TAG_SENSOR, "SensorManager is null, cannot start");
            return false;
        }

        accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
        gyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE);

        boolean accelOk = false;
        boolean gyroOk = false;

        if (accelerometer != null) {
            accelOk = sensorManager.registerListener(this, accelerometer,
                    SensorManager.SENSOR_DELAY_GAME);
            Log.i(OffroadLog.TAG_SENSOR, "Accelerometer registered: " + accelOk);
        } else {
            Log.e(OffroadLog.TAG_SENSOR, "Accelerometer not available");
        }

        if (gyroscope != null) {
            gyroOk = sensorManager.registerListener(this, gyroscope,
                    SensorManager.SENSOR_DELAY_GAME);
            Log.i(OffroadLog.TAG_SENSOR, "Gyroscope registered: " + gyroOk);
        } else {
            Log.e(OffroadLog.TAG_SENSOR, "Gyroscope not available");
        }

        return accelOk && gyroOk;
    }

    /**
     * 停止传感器监听。
     * 休眠时调用以释放传感器资源。
     */
    public void stop() {
        if (sensorManager != null) {
            sensorManager.unregisterListener(this);
            accelValid = false;
            gyroValid = false;
            Log.i(OffroadLog.TAG_SENSOR, "Sensor listeners unregistered");
        }
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (event.sensor.getType() == Sensor.TYPE_ACCELEROMETER) {
            // 直接复制到缓存数组, 避免对象创建
            accelData[0] = event.values[0];
            accelData[1] = event.values[1];
            accelData[2] = event.values[2];
            accelValid = true;
            lastAccelTimestamp = event.timestamp;
            if (listener != null) {
                listener.onAccelUpdated(accelData[0], accelData[1], accelData[2], event.timestamp);
            }
        } else if (event.sensor.getType() == Sensor.TYPE_GYROSCOPE) {
            gyroData[0] = event.values[0];
            gyroData[1] = event.values[1];
            gyroData[2] = event.values[2];
            gyroValid = true;
            lastGyroTimestamp = event.timestamp;
            if (listener != null) {
                listener.onGyroUpdated(gyroData[0], gyroData[1], gyroData[2], event.timestamp);
            }
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
        Log.d(OffroadLog.TAG_SENSOR, "Sensor accuracy changed: " + sensor.getName()
                + " accuracy=" + accuracy);
    }

    // ---- 数据读取(AlgorithmScheduler 使用) ----

    public float[] getAccelData() { return accelData; }
    public float[] getGyroData() { return gyroData; }
    public boolean isAccelValid() { return accelValid; }
    public boolean isGyroValid() { return gyroValid; }
    public long getLastAccelTimestamp() { return lastAccelTimestamp; }
    public long getLastGyroTimestamp() { return lastGyroTimestamp; }
}
