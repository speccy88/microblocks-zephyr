"""Optional Paho v2 MQTT network loop, with bounded messages and no replay queue."""
# SPDX-License-Identifier: MIT
from collections import deque
import threading
from ..api import ExtensionError,arguments,text


class Extension:
    def __init__(self,settings,context):
        if set(settings)-{'host','port','tls','client_id','max_messages','wait_seconds'}:raise ExtensionError('configuration','Unknown MQTT setting')
        self.host=text(settings.get('host',''),253,'MQTT host')
        if not self.host or '/' in self.host or any(c.isspace() for c in self.host):raise ExtensionError('configuration','Configure an MQTT broker hostname')
        self.tls=settings.get('tls',True);self.port=settings.get('port',8883 if self.tls else 1883)
        self.maximum=settings.get('max_messages',32);self.wait=settings.get('wait_seconds',1)
        if type(self.tls) is not bool or type(self.port) is not int or not 1<=self.port<=65535 or type(self.maximum) is not int or not 1<=self.maximum<=64 or type(self.wait) not in (int,float) or not .05<=self.wait<=2:raise ExtensionError('configuration','Invalid MQTT connection/queue bounds')
        self.client_id=text(settings.get('client_id',''),64,'MQTT client ID')
        self.client=None;self.connected=threading.Event();self.guard=threading.Lock();self.messages=deque();self.dropped=0;self.subscriptions=set()
        self.operations={'publish':self.publish,'subscribe':self.subscribe,'next':self.next_message,'status':self.status}

    def start(self):
        if self.client is None:
            try:import paho.mqtt.client as mqtt
            except ImportError:raise ExtensionError('dependency_missing','Install the official paho-mqtt 2.x package in the configured Python environment') from None
            self.mqtt=mqtt
            client=mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,client_id=self.client_id,clean_session=True,reconnect_on_failure=False)
            client.max_queued_messages_set(1);client.max_inflight_messages_set(1)
            client.on_connect=self.on_connect;client.on_disconnect=self.on_disconnect;client.on_message=self.on_message
            if self.tls:client.tls_set() # default certificate and hostname verification
            self.client=client
            client.connect_async(self.host,self.port,keepalive=30);client.loop_start()
        if not self.connected.wait(self.wait):raise ExtensionError('mqtt_unavailable','MQTT broker is not connected; check the configured broker and certificate','not_sent')

    def on_connect(self,client,userdata,flags,reason,properties):
        if reason==0:
            self.connected.set()
            with self.guard:topics=list(self.subscriptions)
            for topic in topics:client.subscribe(topic,qos=0)
        else:self.connected.clear()

    def on_disconnect(self,client,userdata,flags,reason,properties):self.connected.clear()

    def on_message(self,client,userdata,message):
        try:
            if len(message.payload)>4096:raise ValueError('payload limit')
            payload=message.payload.decode('utf-8');topic=text(message.topic,256,'MQTT topic')
            if '\0' in payload:raise ValueError('binary payload')
            value={'topic':topic,'payload':payload,'retained':bool(message.retain),'qos':int(message.qos)}
        except (ValueError,UnicodeError,ExtensionError):
            with self.guard:self.dropped+=1
            return
        with self.guard:
            if len(self.messages)>=self.maximum:self.messages.popleft();self.dropped+=1
            self.messages.append(value)

    def publish(self,args):
        arguments(args,{'topic','payload','qos','retain'},{'topic','payload'})
        topic=text(args['topic'],256,'MQTT topic');payload=text(args['payload'],4096,'MQTT payload')
        qos=args.get('qos',0);retain=args.get('retain',False)
        if not topic or any(c in topic for c in ['#','+','\0']) or type(qos) is not int or qos not in (0,1) or type(retain) is not bool:raise ExtensionError('arguments','Use a concrete MQTT topic, QoS 0/1 and boolean retain')
        self.start()
        info=self.client.publish(topic,payload=payload,qos=qos,retain=retain)
        if info.rc!=self.mqtt.MQTT_ERR_SUCCESS:raise ExtensionError('mqtt_publish','MQTT publish was not accepted; check the broker connection','unknown')
        info.wait_for_publish(timeout=self.wait)
        if not info.is_published():
            # Drop the connection/client and its pending queue. Explicit new
            # calls may reconnect; an uncertain write is never replayed here.
            self.close()
            raise ExtensionError('mqtt_timeout','MQTT publish acknowledgement timed out; delivery is unknown. Do not retry automatically','unknown')
        return {'published':True,'qos':qos,'delivery':'sent' if qos==0 else 'broker_acknowledged'}

    def subscribe(self,args):
        arguments(args,{'topic'},{'topic'});topic=text(args['topic'],256,'MQTT subscription')
        if not topic or '\0' in topic:raise ExtensionError('arguments','MQTT subscription topic is required')
        with self.guard:
            if topic not in self.subscriptions and len(self.subscriptions)>=16:raise ExtensionError('limit','At most 16 MQTT subscriptions')
        self.start();result,_=self.client.subscribe(topic,qos=0)
        if result!=self.mqtt.MQTT_ERR_SUCCESS:raise ExtensionError('mqtt_subscribe','MQTT subscription was not accepted','unknown')
        with self.guard:self.subscriptions.add(topic)
        return {'subscribed':True,'broker_acknowledged':False}

    def next_message(self,args):
        arguments(args,set());self.start()
        with self.guard:return {'available':bool(self.messages),'message':self.messages.popleft() if self.messages else None,'dropped':self.dropped}

    def status(self,args):
        arguments(args,set())
        with self.guard:return {'connected':self.connected.is_set(),'queued':len(self.messages),'dropped':self.dropped}

    def close(self):
        client,self.client=self.client,None;self.connected.clear()
        if client:client.disconnect();client.loop_stop()
