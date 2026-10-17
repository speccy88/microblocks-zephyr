// SPDX-License-Identifier: MIT
#include <Arduino.h>
#include <Wire.h>

int main(void)
{
    Serial.begin(115200);
    Wire.begin();
    pinMode(D0, INPUT);
    for (;;) {
        // Read RTC seconds only. Do not set the clock or scan unrelated I2C addresses.
        Wire.beginTransmission(0x51);
        Wire.write(0x04);
        int status = Wire.endTransmission(false);
        int value = -1;
        if (status == 0 && Wire.requestFrom((uint8_t)0x51, (size_t)1) == 1) {
            value = Wire.read();
        }
        Serial.print("ArduinoCore-Zephyr static API: millis=");
        Serial.print(millis());
        Serial.print(" D0(GPIO1,input)=");
        Serial.print(digitalRead(D0));
        Serial.print(" RTC read status=");
        Serial.print(status);
        Serial.print(" seconds register=");
        Serial.println(value);
        delay(1000);
    }
}
