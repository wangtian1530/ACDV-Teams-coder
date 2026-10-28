import json, os, math
from config import (MAP_W, MAP_H, BOT_COUNT, MOVE_RANGE, BULLET_SPEED,
                    BULLET_LIFE_MS, STEER_DELAY_MS, SUBSTEP_MS,
                    MAX_SIM_TIME_MS, HISTORY_SIZE, DIRS_4, DIRS_8)
from entities import GameMap, Bot, Bullet
from ai import discretize_state

LEARN_FILE = 'learning.json'


class Game:
    def __init__(self):
        self.map = GameMap(MAP_W, MAP_H)
        spawns = [(5, 5), (MAP_W - 6, 5), (5, MAP_H - 6),
                  (MAP_W - 6, MAP_H - 6), (MAP_W // 2, 5), (MAP_W // 2, MAP_H - 6)]
        self.bots = []
        for i in range(BOT_COUNT):
            x, y = spawns[i % len(spawns)]
            while self.map.is_obstacle(x, y) and x < MAP_W - 1:
                x += 1
            self.bots.append(Bot(i, x, y))
        self.bullets = []
        self.sim_time_ms = 0
        self.substep_counter = 0
        self.actor_idx = 0
        self.phase = "WAITING"          # WAITING (bot act) | RESOLVING (bullet fly)
        self.over = False
        self.result = ""
        self.history = []

    def alive_bots(self):
        return [b for b in self.bots if b.alive]

    def _advance_actor(self):
        for _ in range(BOT_COUNT):
            self.actor_idx = (self.actor_idx + 1) % BOT_COUNT
            if self.bots[self.actor_idx].alive:
                return True
        return False

    # ============================================================
    # SUBSTEP — chạy mỗi 50ms sim
    # ============================================================
    def substep(self):
        if self.over: return
        self.sim_time_ms += SUBSTEP_MS
        self.substep_counter += 1

        if self.phase == "WAITING":
            self._do_turn()
        elif self.phase == "RESOLVING":
            self._simulate_bullets(SUBSTEP_MS)
            actor = self.bots[self.actor_idx]
            if not any(b.owner == actor.id for b in self.bullets):
                self.phase = "WAITING"
                self._advance_actor()

        if self._check_end():
            return

        # Snapshot every substep for rewind
        self.history.append(self._snapshot())
        if len(self.history) > HISTORY_SIZE:
            self.history.pop(0)

    def _check_end(self):
        survivors = self.alive_bots()
        if len(survivors) <= 1:
            self.over = True
            if survivors:
                w = survivors[0]
                self.result = f"Bot {w.id} THẮNG"
                w.q.learn_direct(w.prev_state, w.prev_action, 100.0)
                w.stats['rewards'] += 100
            else:
                self.result = "Tất cả đã chết"
            return True
        if self.sim_time_ms >= MAX_SIM_TIME_MS:
            self.over = True
            self.result = "HẾT GIỜ — tất cả chết"
            for b in self.bots:
                if b.alive:
                    b.alive = False
                    b.hp = 0
                    b.q.learn_direct(b.prev_state, b.prev_action, -100.0)
                    b.stats['rewards'] -= 100
                    b.stats['deaths'] += 1
            return True
        return False

    # ============================================================
    # MỘT TURN — bot hiện tại quyết định + thực thi
    # ============================================================
    def _do_turn(self):
        bot = self.bots[self.actor_idx]
        if not bot.alive:
            self._advance_actor()
            return

        # TD update từ action trước
        if bot.prev_state is not None and bot.prev_action is not None:
            bot.prev_reward += 0.5          # survival bonus
            cur_s = discretize_state(bot, self.bots, self.bullets, self.map)
            bot.q.learn(bot.prev_state, bot.prev_action, bot.prev_reward, cur_s)
            bot.stats['rewards'] += bot.prev_reward
            bot.q.decay()
        bot.prev_reward = 0.0

        # Chọn action
        state = discretize_state(bot, self.bots, self.bullets, self.map)
        valid = self._valid_actions(bot)
        if not valid:
            self._advance_actor()
            return
        action = bot.q.choose(state, valid)
        bot.prev_state, bot.prev_action = state, action

        # Thực thi
        if action < 8:                       # shoot straight
            self._spawn_straight(bot, action)
            self.phase = "RESOLVING"
        elif action < 12:                    # move
            self._move_bot(bot, action - 8)
            self.phase = "WAITING"
            self._advance_actor()
        else:                                # curved shot
            if self._spawn_curved(bot, action):
                self.phase = "RESOLVING"
            else:
                self.phase = "WAITING"
                self._advance_actor()

    def _valid_actions(self, b):
        valid = []
        # Shoot 0-7
        for i, (dx, dy) in enumerate(DIRS_8):
            nx, ny = b.x + dx, b.y + dy
            if self.map.in_bounds(nx, ny) and not self.map.is_obstacle(nx, ny):
                valid.append(i)
        # Move 8-11
        for i, (dx, dy) in enumerate(DIRS_4):
            nx, ny = b.x + dx, b.y + dy
            if not self.map.in_bounds(nx, ny) or self.map.is_obstacle(nx, ny):
                continue
            if any(t.alive and t.id != b.id and t.x == nx and t.y == ny
                   for t in self.bots):
                continue
            valid.append(8 + i)
        # Curved 12-13
        enemies = [t for t in self.bots if t.alive and t.id != b.id]
        if enemies:
            nearest = min(enemies, key=lambda t: abs(t.x-b.x) + abs(t.y-b.y))
            ang = math.atan2(nearest.y - b.y, nearest.x - b.x)
            idx = round(ang / (math.pi / 4)) % 8
            sdx, sdy = DIRS_8[idx]
            nx, ny = b.x + sdx, b.y + sdy
            if self.map.in_bounds(nx, ny) and not self.map.is_obstacle(nx, ny):
                valid.extend([12, 13])
        return valid

    def _move_bot(self, bot, d_idx):
        dx, dy = DIRS_4[d_idx]
        for _ in range(MOVE_RANGE):
            nx, ny = bot.x + dx, bot.y + dy
            if not self.map.in_bounds(nx, ny) or self.map.is_obstacle(nx, ny):
                break
            if any(t.alive and t.id != bot.id and t.x == nx and t.y == ny
                   for t in self.bots):
                break
            bot.x, bot.y = nx, ny
        bot.stats['moves'] += 1

    def _spawn_straight(self, bot, action):
        dx, dy = DIRS_8[action]
        bx, by = bot.x + dx, bot.y + dy
        if not self.map.in_bounds(bx, by) or self.map.is_obstacle(bx, by):
            return
        bl = Bullet(bx, by, dx, dy, bot.id, bot.prev_state, bot.prev_action)
        self.bullets.append(bl)
        bot.stats['shots'] += 1
        # Immediate spawn-collision check
        self._check_spawn_collision(bl)

    def _spawn_curved(self, bot, action):
        enemies = [t for t in self.bots if t.alive and t.id != bot.id]
        if not enemies: return False
        nearest = min(enemies, key=lambda t: abs(t.x-bot.x) + abs(t.y-bot.y))
        ang = math.atan2(nearest.y - bot.y, nearest.x - bot.x)
        idx = round(ang / (math.pi / 4)) % 8
        sdx, sdy = DIRS_8[idx]
        bx, by = bot.x + sdx, bot.y + sdy
        if not self.map.in_bounds(bx, by) or self.map.is_obstacle(bx, by):
            return False
        bl = Bullet(bx, by, sdx, sdy, bot.id, bot.prev_state, bot.prev_action)
        # CW (13) hoặc CCW (12)
        if action == 13:
            ndx, ndy = -sdy, sdx
        else:
            ndx, ndy = sdy, -sdx
        bl.pending_steer = {'trigger_at': STEER_DELAY_MS, 'dx': ndx, 'dy': ndy}
        self.bullets.append(bl)
        bot.stats['shots'] += 1
        bot.stats['curved_shots'] += 1
        self._check_spawn_collision(bl)
        return True

    def _check_spawn_collision(self, bl):
        hit = next((t for t in self.bots if t.alive and t.id != bl.owner
                    and t.x == bl.head_x and t.y == bl.head_y), None)
        if hit:
            self._process_hit(hit, bl)
            bl.__dict__['_absorbed'] = True

    # ============================================================
    # BULLET SIMULATION
    # ============================================================
    def _simulate_bullets(self, dt_ms):
        remaining = []
        cells_per_substep = BULLET_SPEED * dt_ms / 1000.0

        for bl in self.bullets:
            if bl.__dict__.get('_absorbed'):
                continue
            bl.age_ms += dt_ms
            if bl.age_ms > BULLET_LIFE_MS:
                owner = self.bots[bl.owner]
                owner.stats['wasted'] += 1
                owner.q.learn_direct(bl.contributors[0][0], bl.contributors[0][1], -1.0)
                owner.stats['rewards'] -= 1
                continue

            if bl.pending_steer and bl.age_ms >= bl.pending_steer['trigger_at']:
                bl.bend(bl.pending_steer['dx'], bl.pending_steer['dy'])
                bl.pending_steer = None

            absorbed = False
            to_move = cells_per_substep

            while to_move >= 1.0:
                nx, ny = bl.head_x + bl.dx, bl.head_y + bl.dy
                bounced = False
                if nx < 0 or nx >= self.map.w:
                    bl.dx = -bl.dx; bounced = True
                if ny < 0 or ny >= self.map.h:
                    bl.dy = -bl.dy; bounced = True
                if bounced:
                    bl.bend(bl.dx, bl.dy)
                    nx = bl.head_x + bl.dx
                    ny = bl.head_y + bl.dy

                if self.map.is_obstacle(nx, ny):
                    owner = self.bots[bl.owner]
                    owner.stats['wasted'] += 1
                    owner.q.learn_direct(bl.contributors[0][0], bl.contributors[0][1], -1.0)
                    owner.stats['rewards'] -= 1
                    absorbed = True
                    break

                hit = next((t for t in self.bots
                            if t.alive and t.id != bl.owner
                            and t.x == nx and t.y == ny), None)
                if hit:
                    self._process_hit(hit, bl)
                    absorbed = True
                    break

                bl.move_to(nx, ny)
                to_move -= 1.0

            if not absorbed:
                remaining.append(bl)
        self.bullets = remaining

    def _process_hit(self, victim, bullet):
        attacker = self.bots[bullet.owner]

        victim.hp -= 1
        victim.stats['damage_taken'] += 1
        victim.q.learn_direct(victim.prev_state, victim.prev_action, -20.0)
        victim.stats['rewards'] -= 20

        if victim.hp <= 0:
            victim.alive = False
            victim.stats['deaths'] += 1
            victim.q.learn_direct(victim.prev_state, victim.prev_action, -100.0)
            victim.stats['rewards'] -= 100

        if attacker.alive and attacker.id != victim.id:
            attacker.stats['hits'] += 1
            if victim.hp <= 0:
                attacker.stats['kills'] += 1
                for s, a in bullet.contributors:
                    attacker.q.learn_direct(s, a, 60.0)
                attacker.stats['rewards'] += 60
            else:
                for s, a in bullet.contributors:
                    attacker.q.learn_direct(s, a, 3.0)
                attacker.stats['rewards'] += 3

    # ============================================================
    # SNAPSHOT / REWIND
    # ============================================================
    def _snapshot(self):
        return {
            'sim_time_ms': self.sim_time_ms,
            'substep_counter': self.substep_counter,
            'actor_idx': self.actor_idx,
            'phase': self.phase,
            'over': self.over, 'result': self.result,
            'bots': [{'x': b.x, 'y': b.y, 'hp': b.hp, 'alive': b.alive}
                     for b in self.bots],
            'bullets': [{
                'hx': bl.head_x, 'hy': bl.head_y, 'dx': bl.dx, 'dy': bl.dy,
                'owner': bl.owner, 'corners': list(bl.corners),
                'age': bl.age_ms,
                'pending': dict(bl.pending_steer) if bl.pending_steer else None,
            } for bl in self.bullets],
        }

    def rewind(self):
        if len(self.history) < 2: return False
        self.history.pop()
        prev = self.history.pop()
        self._restore(prev)
        self.history.append(prev)
        return True

    def _restore(self, snap):
        self.sim_time_ms = snap['sim_time_ms']
        self.substep_counter = snap['substep_counter']
        self.actor_idx = snap['actor_idx']
        self.phase = snap['phase']
        self.over = snap['over']
        self.result = snap['result']
        for bs, b in zip(snap['bots'], self.bots):
            b.x, b.y, b.hp, b.alive = bs['x'], bs['y'], bs['hp'], bs['alive']
        self.bullets = []
        for bs in snap['bullets']:
            bl = Bullet(bs['hx'], bs['hy'], bs['dx'], bs['dy'], bs['owner'])
            bl.corners = [tuple(c) for c in bs['corners']]
            bl.age_ms = bs['age']
            bl.pending_steer = bs['pending']
            self.bullets.append(bl)

    # ============================================================
    # JSON STATE
    # ============================================================
    def _compute_ranking(self):
        rows = []
        for b in self.bots:
            st = b.stats
            score = (st['kills'] * 100 - st['deaths'] * 50 + st['hits'] * 15
                     - st['damage_taken'] * 10 + max(0, st['rewards']))
            rows.append({
                'id': b.id, 'alive': b.alive, 'color': b.color,
                'score': round(score, 1),
                'kills': st['kills'], 'deaths': st['deaths'],
                'hits': st['hits'], 'damage': st['damage_taken'],
                'rewards': round(st['rewards'], 1),
            })
        rows.sort(key=lambda r: (-r['score'], -r['kills'], r['deaths']))
        for i, r in enumerate(rows):
            r['rank'] = i + 1
        return rows

    def state_json(self):
        return {
            'sim_time_ms': self.sim_time_ms,
            'max_sim_time_ms': MAX_SIM_TIME_MS,
            'substep': self.substep_counter,
            'over': self.over, 'result': self.result,
            'actor_idx': self.actor_idx,
            'phase': self.phase,
            'map': {'w': self.map.w, 'h': self.map.h,
                    'obstacles': [c for x, y in self.map.obstacles for c in (x, y)]},
            'bots': [{
                'id': b.id, 'x': b.x, 'y': b.y,
                'hp': b.hp, 'max_hp': b.max_hp,
                'alive': b.alive, 'color': b.color,
                'stats': dict(b.stats),
                'q_size': len(b.q.q),
                'epsilon': round(b.q.epsilon, 3),
                'memory': b.q.memory[-6:],
            } for b in self.bots],
            'bullets': [{
                'x': bl.head_x, 'y': bl.head_y,
                'dx': bl.dx, 'dy': bl.dy,
                'owner': bl.owner,
                'corners': bl.corners,
                'pending': bl.pending_steer is not None,
            } for bl in self.bullets],
            'ranking': self._compute_ranking(),
        }


# ============================================================
# Persistence
# ============================================================
def save_learning(bots, path=LEARN_FILE):
    data = []
    for b in bots:
        data.append({
            'epsilon': b.q.epsilon,
            'q': [{'s': list(s), 'a': a, 'v': v}
                  for (s, a), v in b.q.q.items()],
        })
    with open(path, 'w') as f:
        json.dump(data, f)
    print(f"💾 Saved learning: {len(data)} bots")


def load_learning(bots, path=LEARN_FILE):
    if not os.path.exists(path): return
    try:
        with open(path) as f:
            data = json.load(f)
        for i, b in enumerate(bots):
            if i >= len(data): break
            for item in data[i]['q']:
                b.q.q[(tuple(item['s']), item['a'])] = item['v']
            b.q.epsilon = data[i]['epsilon']
        print(f"📂 Loaded learning for {len(data)} bots")
    except Exception as e:
        print(f"⚠ Load failed: {e}")