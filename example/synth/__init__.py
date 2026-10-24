"""Synthetic source extracts for the Groundrules demo."""

import random


def rng(seed: str, name: str) -> random.Random:
    """One independent, reproducible random stream per part of the generator.

    A string seed is hashed with SHA-512, so the stream does not depend on
    Python's hash randomization. Separate streams mean that changing one part
    (say, the number of stores) does not shift the numbers of another.
    """
    return random.Random(f"{seed}:{name}")
