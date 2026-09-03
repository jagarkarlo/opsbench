import unittest

import opsbench


class PackageTests(unittest.TestCase):
    def test_exposes_version(self) -> None:
        self.assertEqual(opsbench.__version__, "0.5.4")


if __name__ == "__main__":
    unittest.main()