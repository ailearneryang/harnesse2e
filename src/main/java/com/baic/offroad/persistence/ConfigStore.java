package com.baic.offroad.persistence;

import android.util.Log;

import com.baic.offroad.model.InstallationConfig;
import com.baic.offroad.util.OffroadLog;

import org.json.JSONException;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.IOException;

/**
 * 安装姿态配置文件存储。
 * 读取 /data/vendor/offroad/config.json。
 *
 * 需求追溯: architecture.md §6.4 ConfigStore
 * 数据模型: data_model.md §2.4
 */
public class ConfigStore {

    private final String configFilePath;

    public ConfigStore() {
        this(OffroadLog.CONFIG_FILE_PATH);
    }

    /** 用于测试的构造函数，允许自定义配置文件路径 */
    public ConfigStore(String configFilePath) {
        this.configFilePath = configFilePath;
    }

    /**
     * 加载安装配置。
     * 文件不存在或解析失败时返回默认配置(单位矩阵)。
     * 需求追溯: [RISK-01] ICC安装姿态矩阵参数缺失时用单位矩阵占位
     */
    public InstallationConfig load() {
        File file = new File(configFilePath);
        if (!file.exists()) {
            Log.w(OffroadLog.TAG_STORAGE, "Config file not found: " + configFilePath
                    + ", using default config (Identity matrix)");
            return new InstallationConfig();
        }

        try {
            String json = readFileToString(file);
            InstallationConfig config = InstallationConfig.fromJson(json);
            Log.i(OffroadLog.TAG_STORAGE, "Config loaded: version=" + config.getVersion()
                    + " updateRate=" + config.getUpdateRateHz() + "Hz"
                    + " filterWindow=" + config.getPressureFilterWindow());
            return config;
        } catch (JSONException | IOException e) {
            Log.e(OffroadLog.TAG_STORAGE, "Config load/parse failed, using default", e);
            return new InstallationConfig();
        }
    }

    /**
     * 保存配置(原子写入: temp+rename)。
     * 需求追溯: architecture.md §11.3 数据完整性
     */
    public boolean save(InstallationConfig config) {
        if (config == null) return false;

        File file = new File(configFilePath);
        File dir = file.getParentFile();
        if (dir != null && !dir.exists()) {
            dir.mkdirs();
        }

        File tmpFile = new File(configFilePath + ".tmp");
        try {
            String json = config.toJson();
            try (FileOutputStream fos = new FileOutputStream(tmpFile)) {
                fos.write(json.getBytes("UTF-8"));
                fos.flush();
                fos.getFD().sync();
            }
            // 原子 rename
            if (tmpFile.renameTo(file)) {
                Log.i(OffroadLog.TAG_STORAGE, "Config saved: " + configFilePath);
                return true;
            } else {
                Log.e(OffroadLog.TAG_STORAGE, "Config rename failed");
                return false;
            }
        } catch (JSONException | IOException e) {
            Log.e(OffroadLog.TAG_STORAGE, "Config save failed", e);
            tmpFile.delete();
            return false;
        }
    }

    private String readFileToString(File file) throws IOException {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new FileInputStream(file), "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
        }
        return sb.toString();
    }
}
