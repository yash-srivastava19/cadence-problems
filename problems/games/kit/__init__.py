"""What every game and environment shares: the interface, the wall between a
player and the game, and playing an episode.

A game supplies an `Env` (env.py). A player is anything with
`choose(observation, legal) -> index` (player.py). `play` runs one episode and
returns its record (play.py).
"""
