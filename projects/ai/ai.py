import math, random, time
from config import NUM_ACTIONS


def discretize_state(bot, bots, bullets, game_map):
    enemies = [b for b in bots if b.alive and b.id != bot.id]
    if not enemies:
        return (0, 0, bot.hp, 0, 0)
    nearest = min(enemies, key=lambda b: abs(b.x - bot.x) + abs(b.y - bot.y))
    dx, dy = nearest.x - bot.x, nearest.y - bot.y
    dist = abs(dx) + abs(dy)
    dist_bucket = min(3, dist // 10)
    sector = int((math.atan2(dy, dx) + math.pi) / (math.pi / 4)) % 8
    my_bullets = sum(1 for bl in bullets if bl.owner == bot.id)
    threat = 0
    for bl in bullets:
        if bl.owner != bot.id and abs(bl.head_x - bot.x) + abs(bl.head_y - bot.y) <= 8:
            threat = 1
            break
    return (dist_bucket, sector, max(0, bot.hp), my_bullets, threat)


class QLearner:
    def __init__(self):
        self.q = {}
        self.alpha = 0.15
        self.gamma = 0.9
        self.epsilon = 1.0
        self.epsilon_min = 0.05
        self.epsilon_decay = 0.995
        self.memory = []

    def get(self, s, a):
        return self.q.get((s, a), 0.0)

    def best(self, s):
        if s is None: return 0.0
        return max(self.get(s, a) for a in range(NUM_ACTIONS))

    def choose(self, s, valid_actions):
        if not valid_actions: return None
        if random.random() < self.epsilon:
            return random.choice(valid_actions)
        return max((self.get(s, a), a) for a in valid_actions)[1]

    def learn(self, s, a, r, ns):
        if s is None or a is None: return
        old = self.get(s, a)
        new = old + self.alpha * (r + self.gamma * self.best(ns) - old)
        self.q[(s, a)] = new
        self._log(s, a, r, old, new, "TD")

    def learn_direct(self, s, a, r):
        if s is None or a is None: return
        old = self.get(s, a)
        new = old + self.alpha * (r - old)
        self.q[(s, a)] = new
        self._log(s, a, r, old, new, "direct")

    def _log(self, s, a, r, old, new, kind):
        if abs(r) < 0.5: return
        self.memory.append({
            't': round(time.time(), 1), 'state': list(s), 'action': a,
            'reward': round(r, 2), 'q_before': round(old, 2),
            'q_after': round(new, 2), 'kind': kind,
        })
        if len(self.memory) > 30: self.memory.pop(0)

    def decay(self):
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)