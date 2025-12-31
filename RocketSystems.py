import pygame
import math

# --- PHYSICS CONSTANTS ---
G = 6.67430e-11
EARTH_MASS = 5.972e24
EARTH_RADIUS = 6.371e6
MOON_MASS = 7.34767e22
MOON_RADIUS = 1.7371e6
MOON_DISTANCE = 3.844e8
MOON_VELOCITY = 1022
g0 = 9.81

# --- CLASSES ---


class Body:
    def __init__(self, x, y, mass, radius, color, is_fixed=False, vy=0):
        self.x = x
        self.y = y
        self.mass = mass
        self.radius = radius
        self.color = color
        self.is_fixed = is_fixed
        self.vx = 0
        self.vy = vy
        self.trail = []  # For drawing the orbit line

    def update(self, main_body, dt):
        if self.is_fixed:
            return

        # Gravity from main_body (Earth)
        dx = main_body.x - self.x
        dy = main_body.y - self.y
        dist_sq = dx**2 + dy**2
        f = (G * self.mass * main_body.mass) / dist_sq
        theta = math.atan2(dy, dx)

        ax = (math.cos(theta) * f) / self.mass
        ay = (math.sin(theta) * f) / self.mass

        self.vx += ax * dt
        self.vy += ay * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

        # Record Trail (Will continue to print moon's path for as long as simlation runs)
        if len(self.trail) == 0 or (abs(self.x - self.trail[-1][0]) > 1000000):
            self.trail.append((self.x, self.y))

    def draw(self, screen, camera_x, camera_y, scale, width, height):
        cx, cy = width // 2, height // 2
        screen_x = int(cx + (self.x - camera_x) * scale)
        screen_y = int(cy + (self.y - camera_y) * scale)
        r = int(self.radius * scale)

        # Draw Trail
        if len(self.trail) > 1:
            pts = []
            for tx, ty in self.trail:
                px = int(cx + (tx - camera_x) * scale)
                py = int(cy + (ty - camera_y) * scale)
                pts.append((px, py))
            pygame.draw.lines(screen, (50, 50, 50), False, pts, 1)

        pygame.draw.circle(screen, self.color, (screen_x, screen_y), max(2, r))


class Stage:
    def __init__(self, name, dry_mass, fuel_mass, thrust, isp, color):
        self.name = name
        self.dry_mass = dry_mass
        self.fuel_mass = fuel_mass
        self.thrust = thrust
        self.isp = isp
        self.color = color

        if isp > 0:
            # More playable than real physics (Easier with 3x Efficiency):
            self.flow_rate = (thrust / (g0 * isp)) / 3.0
        else:
            self.flow_rate = 0

    def get_mass(self):
        return self.dry_mass + self.fuel_mass

    def burn(self, dt, throttle):
        if self.fuel_mass > 0:
            burn_amount = self.flow_rate * dt * throttle
            if burn_amount > self.fuel_mass:
                burn_amount = self.fuel_mass
            self.fuel_mass -= burn_amount
            if self.fuel_mass <= 0:
                self.fuel_mass = 0
                return 0
            return self.thrust * throttle
        return 0


class MultistageRocket:
    def __init__(self, stages):
        self.stages = stages
        self.x = 0
        self.y = -EARTH_RADIUS
        self.vx = 0
        self.vy = 0
        self.angle = 270
        self.throttle = 0.0

    def get_total_mass(self):
        total = 0
        for stage in self.stages:
            total += stage.get_mass()
        return total

    def activate_stage(self):
        if len(self.stages) > 1:
            dropped_stage = self.stages.pop()
            print(f"SEPARATION: Dropped {dropped_stage.name}!")

    def update(self, bodies, dt):
        active_stage = self.stages[-1]
        thrust_force = active_stage.burn(dt, self.throttle)

        # --- N-BODY GRAVITY LOOP ---
        fg_x = 0
        fg_y = 0
        current_mass = self.get_total_mass()

        for body in bodies:
            dx = self.x - body.x
            dy = self.y - body.y
            dist_sq = dx**2 + dy**2
            dist = math.sqrt(dist_sq)

            # Crash Check (Ground)
            if dist < body.radius:
                theta = math.atan2(dy, dx)
                overlap = body.radius - dist
                self.x += math.cos(theta) * overlap  # <--- GOOD! Pushes OUT
                self.y += math.sin(theta) * overlap  # <--- GOOD! Pushes OUT
                self.vx = 0
                self.vy = 0
                continue

            # Gravity Force
            f = (G * current_mass * body.mass) / dist_sq
            theta = math.atan2(dy, dx)

            fg_x += -math.cos(theta) * f
            fg_y += -math.sin(theta) * f

        # Thrust Vector
        rad = math.radians(self.angle)
        ft_x = math.cos(rad) * thrust_force
        ft_y = math.sin(rad) * thrust_force

        ax = (fg_x + ft_x) / current_mass
        ay = (fg_y + ft_y) / current_mass

        self.vx += ax * dt
        self.vy += ay * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    def get_trajectory(self, bodies, steps, dt_pred):
        path = []
        sim_x, sim_y = self.x, self.y
        sim_vx, sim_vy = self.vx, self.vy
        mass = self.get_total_mass()
        crash_time = None

        # Create Ghost Bodies
        sim_bodies = []
        for b in bodies:
            sim_bodies.append({
                'x': b.x, 'y': b.y, 'vx': b.vx, 'vy': b.vy,
                'm': b.mass, 'r': b.radius, 'fixed': b.is_fixed
            })

        for i in range(steps):
            # 1. Update Ghost Rocket Gravity
            gx, gy = 0, 0
            crashed = False
            for b in sim_bodies:
                dx = sim_x - b['x']
                dy = sim_y - b['y']
                d_sq = dx**2 + dy**2
                if d_sq < b['r']**2:
                    crash_time = i * dt_pred
                    crashed = True
                    break
                f = (G * mass * b['m']) / d_sq
                th = math.atan2(dy, dx)
                gx += -math.cos(th) * f
                gy += -math.sin(th) * f

            if crashed:
                break

            sim_vx += (gx/mass) * dt_pred
            sim_vy += (gy/mass) * dt_pred
            sim_x += sim_vx * dt_pred
            sim_y += sim_vy * dt_pred

            # 2. Update Ghost Moon (Orbit Earth)
            earth = sim_bodies[0]  # Assumes Earth is index 0
            for b in sim_bodies:
                if b['fixed']:
                    continue

                # Gravity from Earth -> Moon
                edx = earth['x'] - b['x']
                edy = earth['y'] - b['y']
                ed_sq = edx**2 + edy**2
                ef = (G * b['m'] * earth['m']) / ed_sq
                eth = math.atan2(edy, edx)

                b['vx'] += (math.cos(eth)*ef/b['m']) * dt_pred
                b['vy'] += (math.sin(eth)*ef/b['m']) * dt_pred
                b['x'] += b['vx'] * dt_pred
                b['y'] += b['vy'] * dt_pred
            # Only record every 15th point for performance
            if i % 15 == 0:
                path.append((sim_x, sim_y))

        return path, crash_time

    def get_orbit_status(self, bodies=None):

        # 1. Check Moon Capture First (if bodies provided)
        if bodies and len(bodies) > 1:
            moon = bodies[1]
            dx = self.x - moon.x
            dy = self.y - moon.y
            dist_moon = math.sqrt(dx**2 + dy**2)

            # If inside Moon SOI (66,000 km), check Moon Orbit
            if dist_moon < 66000000:
                v_moon_x = self.vx - moon.vx
                v_moon_y = self.vy - moon.vy
                v_mag = math.sqrt(v_moon_x**2 + v_moon_y**2)

                # Moon Escape Velocity: sqrt(2GM/r)
                esc_moon = math.sqrt(2 * G * MOON_MASS / dist_moon)

                if v_mag < esc_moon:
                    # Cyan for Moon Orbit
                    return "LUNAR ORBIT", (100, 255, 255)
                else:
                    return "LUNAR ESCAPE", (255, 100, 100)

        # 2. Standard Earth Checks
        r = math.sqrt(self.x**2 + self.y**2)
        v_sq = self.vx**2 + self.vy**2
        mu = G * EARTH_MASS
        energy = (v_sq / 2) - (mu / r)

        if energy >= 0:
            return "ESCAPING", (255, 100, 100)

        h = self.x * self.vy - self.y * self.vx
        term = (2 * energy * h**2) / (mu**2)
        e = math.sqrt(max(0, 1 + term))
        a = -mu / (2 * energy)
        periapsis = a * (1 - e)

        if periapsis > EARTH_RADIUS + 1000:
            return "ORBIT ACHIEVED", (50, 255, 50)
        else:
            return "SUB-ORBITAL", (255, 50, 50)

# --- HELPER FUNCTIONS ---


def create_saturn_v():
    payload = Stage("Payload", dry_mass=5000, fuel_mass=0,
                    thrust=0, isp=0, color=(200, 200, 200))
    s_ivb = Stage("Stage 3", dry_mass=2000, fuel_mass=25000,
                  thrust=300000, isp=380, color=(220, 220, 220))
    s_ii = Stage("Stage 2", dry_mass=4000, fuel_mass=60000,
                 thrust=2000000, isp=340, color=(240, 240, 240))
    s_ic = Stage("Stage 1", dry_mass=10000, fuel_mass=250000,
                 thrust=12000000, isp=280, color=(255, 255, 255))
    return MultistageRocket([payload, s_ivb, s_ii, s_ic])


def draw_rocket_stack(screen, rocket, camera_x, camera_y, scale, width, height):
    screen_cx = width // 2
    screen_cy = height // 2

    rad = math.radians(rocket.angle)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    for i in range(len(rocket.stages) - 1, -1, -1):
        stage = rocket.stages[i]
        w = 4000 * scale * (0.8 + (i * 0.1))
        h = 8000 * scale
        shift_dist = (h * (len(rocket.stages)/2 - i)) - (h/2)
        stage_cx = screen_cx + (cos_a * shift_dist)
        stage_cy = screen_cy + (sin_a * shift_dist)

        p1 = (stage_cx + (cos_a * h/2) - (sin_a * w/2),
              stage_cy + (sin_a * h/2) + (cos_a * w/2))
        p2 = (stage_cx + (cos_a * h/2) + (sin_a * w/2),
              stage_cy + (sin_a * h/2) - (cos_a * w/2))
        p3 = (stage_cx - (cos_a * h/2) + (sin_a * w/2),
              stage_cy - (sin_a * h/2) - (cos_a * w/2))
        p4 = (stage_cx - (cos_a * h/2) - (sin_a * w/2),
              stage_cy - (sin_a * h/2) + (cos_a * w/2))

        pygame.draw.polygon(screen, stage.color, [p1, p2, p3, p4])
        pygame.draw.polygon(screen, (0, 0, 0), [p1, p2, p3, p4], 2)

        if i == len(rocket.stages) - 1 and rocket.throttle > 0 and stage.fuel_mass > 0:
            flame_len = 10000 * scale * rocket.throttle + \
                (math.sin(pygame.time.get_ticks()*0.1)*5)
            flame_end = (stage_cx - (cos_a * (h/2 + flame_len)),
                         stage_cy - (sin_a * (h/2 + flame_len)))
            flame_base = (stage_cx - (cos_a * h/2), stage_cy - (sin_a * h/2))
            pygame.draw.line(screen, (255, 100, 0),
                             flame_base, flame_end, int(w/2))
        # Active Stage Glow
        is_active = (i == len(rocket.stages) - 1)
        if is_active:
            base_c = stage.color
            pulse = abs(math.sin(pygame.time.get_ticks() * 0.005)) * 50
            draw_color = (min(255, base_c[0] + pulse), base_c[1], base_c[2])
        else:
            draw_color = stage.color
        pygame.draw.polygon(screen, draw_color, [p1, p2, p3, p4])

