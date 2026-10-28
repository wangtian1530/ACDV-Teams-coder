# ===== MAP =====
MAP_W, MAP_H = 60, 40
OBSTACLE_DENSITY = 0.01

# ===== BOTS =====
BOT_COUNT = 6
BOT_HP = 5
MOVE_RANGE = 5

# ===== TIME =====
SUBSTEP_MS = 50                      # 1 substep = 50ms sim
MAX_SIM_TIME_MS = 120_000            # 2 phút sim time
SPEED_MULT = {1: 0.5, 2: 1.0, 3: 2.0, 4: 3.0, 5: 5.0}  # x1 = nửa tốc độ

# ===== LASER =====
BULLET_SPEED = 60                    # ô / giây → 3 ô / substep
BULLET_LIFE_MS = 3000                # an toàn: bay max 3s
STEER_DELAY_MS = 500
MAX_CORNERS = 30

# ===== AI =====
NUM_ACTIONS = 14                     # 8 shoot + 4 move + 2 curved shoot
HISTORY_SIZE = 200

DIRS_8 = [(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1)]
DIRS_4 = [(0,-1),(0,1),(-1,0),(1,0)]
COLORS = ['#ff5252','#52ff52','#5252ff','#ffff52','#ff52ff','#52ffff']