/* SPDX-License-Identifier: MIT */
#include "sd_file.h"
static bool letter(unsigned char c) {
    return (c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_';
}
bool mb_sd_file_name(const char *p,size_t n) {
    if(!p||!n||n>=MB_SD_NAME_BYTES)return false;
    size_t base=0,extension=0;bool dot=false;
    for(size_t i=0;i<n;i++) {
        if(p[i]=='.') { if(dot||!base)return false;dot=true;continue; }
        if(!letter((unsigned char)p[i]))return false;
        if(dot) { if(++extension>3)return false; }
        else if(++base>8)return false;
    }
    return base&&(!dot||extension);
}
