import time
import unittest
from unittest.mock import patch
import numpy as np
from app.camera import CameraSource
from app.cameras import CameraManager

class FakeCapture:
    attempts=0
    def __init__(self,*args):
        FakeCapture.attempts+=1
        self.opened=FakeCapture.attempts==1
        self.reads=0
    def isOpened(self): return self.opened
    def set(self,*args): return True
    def read(self):
        self.reads+=1
        if self.reads==1: return True,np.zeros((48,64,3),dtype=np.uint8)
        return False,None
    def release(self): pass

class CameraTests(unittest.TestCase):
    def test_disconnect_is_reported_and_reconnect_attempted(self):
        FakeCapture.attempts=0
        with patch('app.camera.cv2.VideoCapture',FakeCapture):
            camera=CameraSource()
            camera.start()
            time.sleep(1.3)
            status=camera.status()
            sequence,_,frame=camera.latest()
            camera.close()
        self.assertGreaterEqual(FakeCapture.attempts,2)
        self.assertEqual(sequence,1)
        self.assertEqual(frame.shape,(48,64,3))
        self.assertFalse(status['connected'])

    def test_manager_exposes_stable_friendly_device(self):
        class Hint:
            index=0; name='USB Classroom Camera'; backend='DSHOW'; path='\\\\?\\usb#camera-1'
        class Capture:
            def __init__(self,*args): pass
            def isOpened(self): return True
            def get(self,prop): return {3:1280,4:720,5:30}.get(prop,0)
            def release(self): pass
        manager=CameraManager(max_indices=1,enumerator=lambda:[Hint()],capture_factory=Capture)
        with patch('app.cameras.platform.system',return_value='Windows'):
            devices=manager.discover()
        self.assertEqual(devices[0]['name'],'USB Classroom Camera')
        self.assertEqual(devices[0]['device_id'],Hint.path)
        self.assertEqual(devices[0]['resolution'],[1280,720])

if __name__=='__main__': unittest.main()
