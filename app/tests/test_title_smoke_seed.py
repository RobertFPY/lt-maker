import random
import unittest
from unittest.mock import patch

from app.constants import TILEX, TILEY, WINHEIGHT, WINWIDTH
from app.engine import particles
from app.utilities import static_random


TITLE_BOUNDS = (-WINHEIGHT, WINWIDTH, WINHEIGHT, WINHEIGHT + 16)


def _system():
    return particles.MapParticleSystem(
        'title', particles.Smoke, .075, TITLE_BOUNDS, (TILEX, TILEY))


class TitleSmokeSeedTests(unittest.TestCase):
    def setUp(self):
        self._random_state = random.getstate()
        self._static_state = self._static_snapshot()

    def tearDown(self):
        random.setstate(self._random_state)
        static_random.set_seed(self._static_state[0])
        static_random.set_combat_random_state(self._static_state[1])
        static_random.r.growth_random.state = self._static_state[2]
        static_random.set_other_random_state(self._static_state[3])

    @staticmethod
    def _static_snapshot():
        return (static_random.get_seed(), static_random.get_combat_random_state(),
                static_random.get_growth_random_state(),
                static_random.get_other_random_state())

    def test_seed_title_smoke_has_fixed_density_valid_lifetime_envelope_and_no_static_rng_use(self):
        def reset(smoke, pos):
            smoke.x, smoke.y = pos
            smoke.remove_me_flag = False
            return smoke

        random.seed(1701)
        with patch.object(particles.Smoke, 'reset', reset):
            system = _system()
            particles.seed_title_smoke(system)

        self.assertEqual(system.abundance, len(system.particles))
        self.assertTrue(all(isinstance(smoke, particles.Smoke)
                            for smoke in system.particles))
        self.assertTrue(all(smoke.x <= WINWIDTH and smoke.y >= -32
                            for smoke in system.particles))
        self.assertEqual(self._static_state, self._static_snapshot())

    def test_seed_avoids_the_three_hundred_prefill_updates(self):
        prefill_updates = 0

        def count_update(_system):
            nonlocal prefill_updates
            prefill_updates += 1

        with patch.object(particles.MapParticleSystem, 'update', count_update):
            _system().prefill()
        self.assertEqual(300, prefill_updates)

        def reset(smoke, pos):
            smoke.x, smoke.y = pos
            smoke.remove_me_flag = False
            return smoke

        with patch.object(particles.MapParticleSystem, 'update', count_update):
            with patch.object(particles.Smoke, 'reset', reset):
                particles.seed_title_smoke(_system())
        self.assertEqual(300, prefill_updates)
