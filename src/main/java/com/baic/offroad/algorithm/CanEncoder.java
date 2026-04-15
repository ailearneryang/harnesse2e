package com.baic.offroad.algorithm;

import android.util.Log;

import com.baic.offroad.model.OffroadDataBundle;
import com.baic.offroad.util.OffroadLog;

/**
 * CAN 0x4F0 报文编码器。
 * 将 12 路越野信号编码为 CAN 报文字节数据。
 *
 * 注: CAN 0x4F0 的 DBC 定义待确认 [TBD-003]。
 * 当前采用参数化设计，DBC 确认后仅需修改配置参数。
 *
 * 需求追溯: [FUN-023~025], architecture.md §6.3 CanEncoder
 */
public class CanEncoder {

    /** CAN 报文长度(字节)，标准 CAN 帧最大 8 字节 */
    public static final int CAN_FRAME_LENGTH = 8;

    /**
     * 将越野数据编码为 CAN 0x4F0 报文。
     *
     * 临时编码方案 [TBD-003 待确认后更新]:
     * Byte 0: 倾斜角 (offset=40, factor=0.5, range 0~160 → ±40°) + valid bit7
     * Byte 1: 俯仰角 (offset=60, factor=0.5, range 0~240 → ±60°) + valid (bit7 of byte2)
     * Byte 2: 大气压力高字节 (offset=300, factor=4, range 0~200 → 300~1100hPa) + valid bit7
     * Byte 3: 海拔高字节 (offset=500, factor=50, range 0~190 → -500~9000m)
     * Byte 4: 海拔有效(bit7) + 指南针方向(bit4~6) + 方向有效(bit3)
     * Byte 5: 指南针角度高字节 (factor=2, range 0~180 → 0~360°) + valid bit7
     * Byte 6-7: 预留
     *
     * @param data 越野数据包
     * @return 8字节 CAN 报文数据
     */
    public static byte[] encode(OffroadDataBundle data) {
        byte[] frame = new byte[CAN_FRAME_LENGTH];

        if (data == null) {
            return frame; // 全零帧
        }

        // Byte 0: 倾斜角 (offset=40, factor=0.5)
        int tiltEncoded = (int) ((data.getTiltAngle() + 40.0f) / 0.5f);
        tiltEncoded = clamp(tiltEncoded, 0, 160);
        frame[0] = (byte) (tiltEncoded & 0x7F);
        if (data.isTiltAngleValid()) {
            frame[0] |= (byte) 0x80; // bit7 = valid
        }

        // Byte 1: 俯仰角 (offset=60, factor=0.5)
        int pitchEncoded = (int) ((data.getPitchAngle() + 60.0f) / 0.5f);
        pitchEncoded = clamp(pitchEncoded, 0, 240);
        frame[1] = (byte) (pitchEncoded & 0xFF);

        // Byte 2: 大气压力 (offset=300, factor=4) + 俯仰valid(bit7) + 压力valid(bit6)
        int pressureEncoded = (int) ((data.getPressure() - 300.0f) / 4.0f);
        pressureEncoded = clamp(pressureEncoded, 0, 200);
        frame[2] = (byte) (pressureEncoded & 0x3F);
        if (data.isPitchAngleValid()) {
            frame[2] |= (byte) 0x80; // bit7 = pitch valid
        }
        if (data.isPressureValid()) {
            frame[2] |= (byte) 0x40; // bit6 = pressure valid
        }

        // Byte 3: 海拔 (offset=500, factor=50)
        int altEncoded = (int) ((data.getAltitude() + 500.0f) / 50.0f);
        altEncoded = clamp(altEncoded, 0, 190);
        frame[3] = (byte) (altEncoded & 0xFF);

        // Byte 4: 海拔valid(bit7) + 指南针方向(bit4~6) + 方向valid(bit3) + 角度valid(bit2)
        frame[4] = 0;
        if (data.isAltitudeValid()) {
            frame[4] |= (byte) 0x80;
        }
        int dir = data.getCompassDirection();
        if (dir >= 0 && dir <= 7) {
            frame[4] |= (byte) ((dir & 0x07) << 4);
        }
        if (data.isCompassDirectionValid()) {
            frame[4] |= (byte) 0x08;
        }
        if (data.isCompassAngleValid()) {
            frame[4] |= (byte) 0x04;
        }

        // Byte 5: 指南针角度 (factor=2, range 0~180 → 0~360°)
        int angleEncoded = (int) (data.getCompassAngle() / 2.0f);
        angleEncoded = clamp(angleEncoded, 0, 180);
        frame[5] = (byte) (angleEncoded & 0xFF);

        // Byte 6-7: 预留
        frame[6] = 0;
        frame[7] = 0;

        return frame;
    }

    /**
     * 从 CAN 报文解码(用于验证/测试)。
     */
    public static OffroadDataBundle decode(byte[] frame) {
        if (frame == null || frame.length < CAN_FRAME_LENGTH) {
            return new OffroadDataBundle();
        }

        OffroadDataBundle data = new OffroadDataBundle();

        // Byte 0: 倾斜角
        int tiltEncoded = frame[0] & 0x7F;
        data.setTiltAngle(tiltEncoded * 0.5f - 40.0f);
        data.setTiltAngleValid((frame[0] & 0x80) != 0);

        // Byte 1: 俯仰角
        int pitchEncoded = frame[1] & 0xFF;
        data.setPitchAngle(pitchEncoded * 0.5f - 60.0f);

        // Byte 2: 大气压力 + valid flags
        int pressureEncoded = frame[2] & 0x3F;
        data.setPressure(pressureEncoded * 4.0f + 300.0f);
        data.setPitchAngleValid((frame[2] & 0x80) != 0);
        data.setPressureValid((frame[2] & 0x40) != 0);

        // Byte 3: 海拔
        int altEncoded = frame[3] & 0xFF;
        data.setAltitude(altEncoded * 50.0f - 500.0f);

        // Byte 4: flags + direction
        data.setAltitudeValid((frame[4] & 0x80) != 0);
        data.setCompassDirection((frame[4] >> 4) & 0x07);
        data.setCompassDirectionValid((frame[4] & 0x08) != 0);
        data.setCompassAngleValid((frame[4] & 0x04) != 0);

        // Byte 5: 指南针角度
        int angleEncoded = frame[5] & 0xFF;
        data.setCompassAngle(angleEncoded * 2.0f);

        return data;
    }

    private static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }
}
