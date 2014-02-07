import unittest
import libvirt

from vmmaster.core.clone_factory import CloneShutdownTimer
from vmmaster.core.clone import Clone
from vmmaster.core.config import setup_config, config


def nothing():
    pass


class TestCloneShutdownTimer(unittest.TestCase):
    def setUp(self):
        setup_config('config.py')
        self.timeout = 1
        self.callback = nothing
        self.ubuntu_platform = "ubuntu-13.04-x64"

    def tearDown(self):
        pass

    def test_timer_set(self):
        clone = Clone(0, self.ubuntu_platform)
        clone.set_timer(CloneShutdownTimer(self.timeout, self.callback))
        clone.get_timer().start()
        self.assertTrue(clone.get_timer())


    def test_timer_time_elapsed(self):
        clone = Clone(0, self.ubuntu_platform)
        clone.set_timer(CloneShutdownTimer(self.timeout, self.callback))
        clone.get_timer().start()
        self.assertGreater(clone.get_timer().time_elapsed, 0)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCloneShutdownTimer)
    unittest.TextTestRunner(verbosity=2).run(suite)