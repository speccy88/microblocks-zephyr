"""Explicit API fixtures, not a real Paho package or commissioned MQTT broker."""
# SPDX-License-Identifier: MIT
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from linux.extensions.api import Context,ExtensionError
from linux.extensions.plugins.mqtt import Extension


class ClientFixture:
    def __init__(self):self.publishes=[];self.subs=[];self.closed=False;self.ack=True
    def publish(self,topic,**kwargs):
        self.publishes.append((topic,kwargs))
        return SimpleNamespace(rc=0,wait_for_publish=lambda timeout:None,is_published=lambda:self.ack)
    def subscribe(self,topic,qos):self.subs.append(topic);return (0,1)
    def disconnect(self):self.closed=True
    def loop_stop(self):pass


class MQTTTests(unittest.TestCase):
    def extension(self):
        extension=Extension({'host':'broker.invalid','max_messages':2},Context(Path('.'),'linux-test'))
        extension.client=ClientFixture();extension.mqtt=SimpleNamespace(MQTT_ERR_SUCCESS=0);extension.connected.set()
        return extension
    def test_publish_subscription_and_bounded_callback_queue(self):
        extension=self.extension()
        self.assertEqual(extension.publish({'topic':'room/temperature','payload':'21500'})['delivery'],'sent')
        self.assertFalse(extension.subscribe({'topic':'room/#'})['broker_acknowledged'])
        for value in ['one','two','three']:
            extension.on_message(None,None,SimpleNamespace(payload=value.encode(),topic='room/temp',retain=False,qos=0))
        result=extension.next_message({});self.assertEqual((result['message']['payload'],result['dropped']),('two',1))
        self.assertEqual(extension.next_message({})['message']['payload'],'three');self.assertFalse(extension.next_message({})['available'])
        extension.on_message(None,None,SimpleNamespace(payload=b'\0',topic='room/temp',retain=False,qos=0))
        self.assertEqual(extension.status({})['dropped'],2)
    def test_unknown_publish_stops_client_and_is_never_replayed(self):
        extension=self.extension();client=extension.client;client.ack=False
        with self.assertRaises(ExtensionError) as caught:extension.publish({'topic':'room/value','payload':'write','qos':1})
        self.assertEqual(caught.exception.outcome,'unknown');self.assertTrue(client.closed);self.assertIsNone(extension.client);self.assertEqual(len(client.publishes),1)
    def test_topics_settings_and_subscription_bounds(self):
        extension=self.extension()
        for topic in ['','room/#','room/+','x\0y']:
            with self.assertRaises(ExtensionError):extension.publish({'topic':topic,'payload':'x'})
        for i in range(16):extension.subscribe({'topic':str(i)})
        with self.assertRaises(ExtensionError):extension.subscribe({'topic':'overflow'})
        with self.assertRaises(ExtensionError):Extension({'host':'broker.invalid','tls':'false'},Context(Path('.'),'linux-test'))


if __name__=='__main__':unittest.main()
