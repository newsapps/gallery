#!/usr/bin/env python
import sys,os.path
import unittest
APP_PATH = os.path.join(os.path.dirname(__file__),os.path.realpath('app'))
if not APP_PATH in sys.path:
    sys.path.append(APP_PATH)

try:
    import render_gallery
except ImportError, e:
    raise Exception(e.message + '\n'.join(sys.path))

class TestSequenceFunctions(unittest.TestCase):
    def test_segment_list(self):
        l = range(0,10)
        maxlen = 3
        parts = render_gallery.segment_list(l,maxlen)
        for p in parts:
            self.assertTrue(len(p) <= maxlen)
        l2 = reduce(lambda x,y: x + y,parts,[])
        self.assertEqual(len(l2),len(l))
        self.assertEqual(l2,l)
        for a,b in zip(l,l2):
            self.assertEqual(b,a)
        

if __name__ == '__main__':
    unittest.main()
    