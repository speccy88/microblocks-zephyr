/* SPDX-License-Identifier: MPL-2.0 */
#include "vm/interp.h"
#include "eyes_backend.h"
#include "pose_camera.h"
#include <string.h>
#include <stdio.h>
static OBJ boolean(bool v){return v?trueObj:falseObj;}
static OBJ text(const char *s){return newStringFromBytes(s,strlen(s));}
static bool ints(int n,OBJ *a,int count){if(n!=count){fail(notEnoughArguments);return false;}for(int i=0;i<n;i++)if(!isInt(a[i])){fail(needsIntegerError);return false;}return true;}
static OBJ begin(int n,OBJ *a){if(!ints(n,a,3))return falseObj;return boolean(p4_eyes_begin(obj2int(a[0]),obj2int(a[1]),obj2int(a[2])));}
static OBJ ready(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return boolean(p4_eyes_ready());}
static OBJ probe(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return boolean(p4_eyes_probe());}
static OBJ probing(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return boolean(p4_eyes_probing());}
static OBJ address(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(p4_eyes_address());}
static OBJ alignment(int n,OBJ *a){if(n!=1)return fail(notEnoughArguments);if(a[0]!=trueObj&&a[0]!=falseObj)return fail(needsBooleanError);eyes_config c;if(!p4_eyes_get(&c))return falseObj;c.alignment=a[0]==trueObj;return boolean(p4_eyes_set(&c));}
static OBJ status(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);char s[128];p4_eyes_status(s,sizeof(s));return text(s);}
static OBJ bus_status(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);char s[128];p4_eyes_bus_status(s,sizeof(s));return text(s);}
static OBJ stop(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);p4_eyes_stop();return trueObj;}
static OBJ mood(int n,OBJ *a){if(!ints(n,a,1))return falseObj;eyes_config c;if(!p4_eyes_get(&c))return falseObj;c.mood=obj2int(a[0]);return boolean(p4_eyes_set(&c));}
static OBJ gaze(int n,OBJ *a){if(!ints(n,a,2))return falseObj;eyes_config c;if(!p4_eyes_get(&c))return falseObj;c.x=obj2int(a[0]);c.y=obj2int(a[1]);c.idle=false;return boolean(p4_eyes_set(&c));}
static OBJ shape(int n,OBJ *a){if(!ints(n,a,4))return falseObj;eyes_config c;if(!p4_eyes_get(&c))return falseObj;c.width=obj2int(a[0]);c.eye_height=obj2int(a[1]);c.radius=obj2int(a[2]);c.spacing=obj2int(a[3]);return boolean(p4_eyes_set(&c));}
static OBJ action(int n,OBJ *a){if(!ints(n,a,1))return falseObj;return boolean(p4_eyes_action(obj2int(a[0])));}
static OBJ option(int n,OBJ *a){
    if(n!=2||!isInt(a[0]))return fail(needsIntegerError);if(a[1]!=trueObj&&a[1]!=falseObj)return fail(needsBooleanError);
    eyes_config c;if(!p4_eyes_get(&c))return falseObj;bool b=a[1]==trueObj;
    switch(obj2int(a[0])){case 0:c.curious=b;break;case 1:c.cyclops=b;break;case 2:c.sweat=b;break;default:return falseObj;}
    return boolean(p4_eyes_set(&c));
}
static OBJ automatic(int n,OBJ *a){
    if(n!=4||!isInt(a[0])||!isInt(a[2])||!isInt(a[3]))return fail(needsIntegerError);
    if(a[1]!=trueObj&&a[1]!=falseObj)return fail(needsBooleanError);
    eyes_config c;if(!p4_eyes_get(&c))return falseObj;int interval=obj2int(a[2]),variation=obj2int(a[3]);
    switch(obj2int(a[0])){case 0:c.autoblink=a[1]==trueObj;c.blink_interval=interval;c.blink_variation=variation;break;
    case 1:c.idle=a[1]==trueObj;c.idle_interval=interval;c.idle_variation=variation;break;default:return falseObj;}
    return boolean(p4_eyes_set(&c));
}
static OBJ flicker(int n,OBJ *a){if(!ints(n,a,2))return falseObj;eyes_config c;if(!p4_eyes_get(&c))return falseObj;c.horizontal_flicker=obj2int(a[0]);c.vertical_flicker=obj2int(a[1]);return boolean(p4_eyes_set(&c));}
static OBJ settings(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);eyes_config c;bool running=p4_eyes_get(&c);char out[160];snprintf(out,sizeof(out),"{\"running\":%s,\"ready\":%s,\"x\":%d,\"y\":%d,\"mood\":%d,\"idle\":%s,\"autoblink\":%s}",running?"true":"false",p4_eyes_ready()?"true":"false",c.x,c.y,c.mood,c.idle?"true":"false",c.autoblink?"true":"false");return text(out);}
static OBJ follow(int n,OBJ *a){if(n!=2)return fail(notEnoughArguments);for(int i=0;i<2;i++)if(a[i]!=trueObj&&a[i]!=falseObj)return fail(needsBooleanError);p4_pose_follow(a[0]==trueObj,a[1]==trueObj);return trueObj;}
static OBJ visible(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return boolean(p4_pose_snapshot().visible);}
static OBJ x(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(p4_pose_snapshot().x);}
static OBJ y(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(p4_pose_snapshot().y);}
static OBJ confidence(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(p4_pose_snapshot().confidence);}
static OBJ gesture(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return text(pose_gesture(p4_pose_snapshot().gesture));}
static OBJ camera_enable(int n,OBJ *a){if(n!=1)return fail(notEnoughArguments);if(a[0]!=trueObj&&a[0]!=falseObj)return fail(needsBooleanError);p4_pose_camera_enable(a[0]==trueObj);return trueObj;}
static OBJ camera_status(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);char s[128];p4_pose_camera_status(s,sizeof(s));return text(s);}
static OBJ attention(int n,OBJ *a){if(n!=2)return fail(notEnoughArguments);if(a[0]!=trueObj&&a[0]!=falseObj)return fail(needsBooleanError);if(!isInt(a[1]))return fail(needsIntegerError);int mode=obj2int(a[1]);if(mode<0||mode>2)return falseObj;p4_attention_enable(a[0]==trueObj,mode);return trueObj;}
static OBJ attention_status(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return text(p4_attention_status());}
static OBJ face_visible(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return boolean(p4_face_snapshot().visible);}
static OBJ face_x(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(p4_face_snapshot().x);}
static OBJ face_y(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(p4_face_snapshot().y);}
static OBJ eyelid(int n,OBJ *a){if(!ints(n,a,1))return falseObj;int side=obj2int(a[0]);if(side<0||side>1)return text("unknown");face_state f=p4_face_snapshot();unsigned v=side?f.right_eye:f.left_eye;return text(v==1?"open":(v==2?"closed":"unknown"));}
static OBJ direction(int n,OBJ *a){if(!ints(n,a,1))return falseObj;int kind=obj2int(a[0]);if(kind<0||kind>1)return text("unknown");face_state f=p4_face_snapshot();unsigned v=kind?f.look:f.head;return text(v==1?"left":(v==2?"center":(v==3?"right":"unknown")));}
static PrimEntry eye_entries[]={{"begin",begin},{"ready",ready},{"probe",probe},{"probing",probing},{"address",address},{"alignment",alignment},{"busStatus",bus_status},{"status",status},{"stop",stop},{"mood",mood},{"gaze",gaze},{"shape",shape},{"action",action},{"option",option},{"automatic",automatic},{"flicker",flicker},{"settings",settings}};
static PrimEntry pose_entries[]={{"follow",follow},{"visible",visible},{"x",x},{"y",y},{"confidence",confidence},{"gesture",gesture},{"cameraEnabled",camera_enable},{"cameraStatus",camera_status},{"attention",attention},{"attentionStatus",attention_status},{"faceVisible",face_visible},{"faceX",face_x},{"faceY",face_y},{"eyelid",eyelid},{"direction",direction}};
void addEyesPrims(void){addPrimitiveSet(EyesPrims,"eyes",sizeof(eye_entries)/sizeof(eye_entries[0]),eye_entries);}
void addPosePrims(void){addPrimitiveSet(PosePrims,"pose",sizeof(pose_entries)/sizeof(pose_entries[0]),pose_entries);}
