/* SPDX-License-Identifier: MIT */
#pragma once

/* PCF85063A stores 2000..2099. Return Sunday=0..Saturday=6, or -1.
 * Validate the complete Gregorian date before any RTC/I2C operation. */
static inline int rlcd_utc_weekday(int year, int month, int day,
                                 int hour, int minute, int second)
{
    static const unsigned char month_days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
    static const unsigned char weekday_offsets[] = {0,3,2,5,0,3,5,1,4,6,2,4};
    if (year < 2000 || year > 2099 || month < 1 || month > 12 ||
        hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59)
        return -1;
    int limit = month_days[month - 1];
    if (month == 2 && (year % 4 == 0) && ((year % 100 != 0) || (year % 400 == 0))) ++limit;
    if (day < 1 || day > limit) return -1;
    int y = year - (month < 3);
    return (y + y / 4 - y / 100 + y / 400 + weekday_offsets[month - 1] + day) % 7;
}
