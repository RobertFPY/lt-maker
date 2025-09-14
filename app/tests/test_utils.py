import unittest
import math
from app.utilities.utils import distance

class TestDistanceFunctions(unittest.TestCase):
    def test_euclidean_distance(self):
        test_cases = [
            ((1.0, 2.0), (3.0, 4.0)),
            ((-1.5, -2.5), (2.5, 3.5)),
            ((0.0, 0.0), (0.0, 0.0)),
        ]
        
        for pos1, pos2 in test_cases:
            with self.subTest(pos1=pos1, pos2=pos2):
                expected = math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2) # naive canonical implementation
                self.assertAlmostEqual(distance(pos1, pos2), expected, places=9)

if __name__ == "__main__":
    unittest.main()
