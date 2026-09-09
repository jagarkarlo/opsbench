import unittest

import opsbench


class PackageTests(unittest.TestCase):
    def test_exposes_version(self) -> None:
        self.assertEqual(opsbench.__version__, "0.6.4")

    def test_exposes_monitoring_path_verification_contract(self) -> None:
        self.assertIn("signal_emitted", opsbench.MONITORING_STAGE_IDS)
        self.assertIn("passed", opsbench.STAGE_STATUSES)


if __name__ == "__main__":
    unittest.main()