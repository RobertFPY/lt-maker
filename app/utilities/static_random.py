# https://en.wikipedia.org/wiki/Linear_congruential_generator
from __future__ import annotations
from typing import Any, Optional, Sequence, TypeVar
from app.utilities import utils

T = TypeVar('T')

class LCG(object):
    def __init__(self, seed: int = 1) -> None:
        self.state = seed

    def _random(self) -> int:
        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.state >> 16  # Only use the top 30..16 bits, the lower bits have a periodicity on even moduli

    def random(self) -> float:
        return self._random() / (2147483647 >> 16)  # 0x7FFFFFFF in decimal (have to use the same top 30..16 bits)

    def randint(self, a: int, b: int) -> int:
        rng = self._random() % (b - a + 1)
        return rng + a

    def randrange(self, end: int) -> int:
        return self.randint(0, end - 1)

    def choice(self, seq: Sequence[T]) -> T:
        return seq[int(self.random() * len(seq))]  # raises IndexError if seq is empty

    def shuffle(self, seq: list[Any]) -> None:
        for i in reversed(range(1, len(seq))):
            # pick an element in x[:i+1] with which to exchange x[i]
            j = int(self.random() * (i+1))
            seq[i], seq[j] = seq[j], seq[i]

    def serialize(self) -> int:
        return self.state

    def deserialize(self, seed: int) -> None:
        self.state = seed

class StaticRandom(object):
    def __init__(self, seed: int = 0) -> None:
        self.set_seed(seed)

    def set_seed(self, seed: int) -> None:
        self.seed = seed
        self.combat_random = LCG(seed)
        self.growth_random = LCG(seed + 1)
        self.other_random = LCG(seed + 2)

r = StaticRandom()

def set_seed(seed: int) -> None:
    r.set_seed(seed)

def get_seed() -> int:
    return r.seed

def get_combat() -> int:
    return r.combat_random.randint(0, 99)

def get_randint(a: int, b: int) -> int:
    return r.combat_random.randint(a, b)

def get_growth() -> int:
    return r.growth_random.randint(0, 99)

def get_levelup(u_id: str, lvl: int) -> LCG:
    # Multiply by 1024 so seed + lvl can't ever recreate the
    # same state on a different seed with a different level
    # since seed only goes from 0 - 1023
    return LCG(utils.strhash(u_id) + lvl * 1024 + r.seed)

def get_generator(offset: int) -> LCG:
    return LCG(offset * 1024 + r.seed)

def get_generator_from_pos(pos: tuple[int, int], offset: int) -> LCG:
    return LCG(pos[0] * 1024**3 + pos[1] * 1024**2 + offset * 1024 + r.seed)

def get_generator_from_unit(unit_nid: str, offset: int = 0) -> LCG:
    return LCG(utils.strhash(unit_nid) + offset * 1024 + r.seed)

def get_combat_random_state() -> int:
    return r.combat_random.state

def set_combat_random_state(state: int) -> None:
    r.combat_random.state = state

def shuffle(lst: list[Any]) -> list[Any]:
    r.combat_random.shuffle(lst)
    return lst

def get_other(a: int, b: int) -> int:
    return r.other_random.randint(a, b)

def get_other_random_state() -> int:
    return r.other_random.state

def set_other_random_state(state: int) -> None:
    r.other_random.state = state

def get_random_float() -> float:
    return r.other_random.random()

def get_random_choice(choices: Sequence[T]) -> T:
    idx = get_other(0, len(choices) - 1)
    return list(choices)[idx]

# === Returns the index of a weighted list
def weighted_choice(choices: Sequence[int], generator: Optional[LCG] = None) -> int:
    if generator:
        rn = generator.randint(0, sum(choices) - 1)
    else:
        rn = r.growth_random.randint(0, sum(choices) - 1)
    upto = 0
    for index, w in enumerate(choices):
        upto += w
        if upto > rn:
            return index
    assert False, "Shouldn't get here"

if __name__ == '__main__':
    print(get_combat())
    state = r.combat_random.serialize()
    print(get_combat())
    print(get_combat())
    r.combat_random.deserialize(state)
    print(get_combat())
    print(get_combat())
    L = [1, 2, 3, 4, 5, 6, 7]
    print(L)
    shuffle(L)
    print(L)
    p = StaticRandom(1)
    # Make sure randomness is centered around 0.5
    rng_sum = sum([p.combat_random.random() for _ in range(1000)]) / 1000
    assert 0.49 < rng_sum < 0.51, rng_sum

    assert all(0 <= p.combat_random.randrange(5) < 5 for _ in range(1000))
