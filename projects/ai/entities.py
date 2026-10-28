import random
from config import (BOT_HP, COLORS, OBSTACLE_DENSITY, MAX_CORNERS)
from ai import QLearner


def generate_obstacles(w, h, density):
    obs, target, tries = set(), int(w * h * density), 0
    while len(obs) < target and tries < target * 10:
        tries += 1
        x, y = random.randint(0, w - 1), random.randint(0, h - 1)
        for _ in range(random.randint(1, 4)):
            nx, ny = x + random.randint(-1, 1), y + random.randint(-1, 1)
            if 0 <= nx < w and 0 <= ny < h:
                obs.add((nx, ny))
    return obs


class GameMap:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.obstacles = generate_obstacles(w, h, OBSTACLE_DENSITY)
    def in_bounds(self, x, y): return 0 <= x < self.w and 0 <= y < self.h
    def is_obstacle(self, x, y): return (x, y) in self.obstacles


class Bullet:
    """Laser polyline: corners[] + head."""
    def __init__(self, x, y, dx, dy, owner, s_state=None, s_action=None):
        self.head_x, self.head_y = x, y
        self.dx, self.dy = dx, dy
        self.owner = owner
        self.age_ms = 0
        self.corners = [(x, y)]
        self.pending_steer = None
        self.contributors = []
        if s_state is not None:
            self.contributors.append((s_state, s_action))

    def move_to(self, nx, ny):
        self.head_x, self.head_y = nx, ny

    def bend(self, ndx, ndy):
        self.corners.append((self.head_x, self.head_y))
        self.dx, self.dy = ndx, ndy
        if len(self.corners) > MAX_CORNERS:
            self.corners = self.corners[-MAX_CORNERS:]


class Bot:
    def __init__(self, bid, x, y):
        self.id, self.x, self.y = bid, x, y
        self.hp = self.max_hp = BOT_HP
        self.alive = True
        self.color = COLORS[bid % len(COLORS)]
        self.q = QLearner()
        self.prev_state = None
        self.prev_action = None
        self.prev_reward = 0.0
        self.stats = {
            'kills': 0, 'deaths': 0, 'hits': 0, 'damage_taken': 0,
            'moves': 0, 'shots': 0, 'curved_shots': 0,
            'wasted': 0, 'rewards': 0.0,
        }