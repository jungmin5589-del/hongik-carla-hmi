import threading,unittest
from unittest.mock import patch
from event_writer import QueuedWriter
class WriterTests(unittest.TestCase):
 def test_slow_disk_cannot_block_controller_enqueue_and_close_drains(self):
  entered=threading.Event();release=threading.Event();returned=threading.Event();saved=[]
  class SlowFile:
   def write(self,text):entered.set();release.wait(2.);saved.append(text)
   def close(self):pass
  with patch('event_writer.open',return_value=SlowFile()):writer=QueuedWriter('unused')
  try:
   def emit():writer.write('first');writer.write('second');returned.set()
   thread=threading.Thread(target=emit);thread.start()
   self.assertTrue(returned.wait(.5));self.assertTrue(entered.wait(.5))
   self.assertEqual(saved,[])
  finally:release.set();thread.join();writer.close()
  self.assertEqual(saved,['first','second'])
