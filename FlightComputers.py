import math
# Note: Updated import to RocketSystems as requested
from RocketSystems import G, EARTH_MASS, EARTH_RADIUS, MOON_MASS


class GSOComputer:
    def __init__(self, target_alt):
        self.target_alt = target_alt
        self.state = "LIFTOFF"
        self.message = "Auto-Sequence Start"

    # UPDATE: We accept 'bodies' now, even if GSO doesn't use the Moon
    def control(self, rocket, bodies, dt):
        # 1. Get Telemetry
        r = math.sqrt(rocket.x**2 + rocket.y**2)
        alt = r - EARTH_RADIUS
        v_current = math.sqrt(rocket.vx**2 + rocket.vy**2)
        v_radial = (rocket.x * rocket.vx + rocket.y * rocket.vy) / r

        mu = G * EARTH_MASS
        energy = (v_current**2 / 2) - (mu / r)
        h = rocket.x * rocket.vy - rocket.y * rocket.vx
        term = (2 * energy * h**2) / (mu**2)
        eccentricity = math.sqrt(max(0, 1 + term))

        pos_angle = math.degrees(math.atan2(rocket.y, rocket.x))
        tangent_angle = pos_angle + 90

        target_angle = rocket.angle
        throttle = 0.0

        # 3. State Machine
        if self.state == "LIFTOFF":
            throttle = 1.0
            target_angle = 270
            self.message = "Liftoff"
            if alt > 2000:
                self.state = "GRAVITY_TURN"

        elif self.state == "GRAVITY_TURN":
            throttle = 1.0
            prog = min(1.0, (alt - 2000) / 80000)
            target_angle = 270 + (prog * 90)
            self.message = f"Gravity Turn: {int(prog*100)}%"

            if energy < 0:
                a = -mu / (2 * energy)
                pred_apogee = a * (1 + eccentricity) - EARTH_RADIUS
                if pred_apogee >= self.target_alt:
                    self.state = "COAST"

        elif self.state == "COAST":
            throttle = 0.0
            target_angle = tangent_angle
            self.message = f"Coasting to Apogee (v-vert: {int(v_radial)} m/s)"
            if abs(v_radial) < 10 or v_radial < -50:
                self.state = "CIRCULARIZATION"

        elif self.state == "CIRCULARIZATION":
            target_angle = tangent_angle
            v_target = math.sqrt(mu / r)
            delta_v = v_target - v_current
            self.message = f"Circularizing (e={eccentricity:.3f})"

            if delta_v > 0:
                throttle = min(1.0, delta_v / 100.0)
                throttle = max(0.1, throttle)
            else:
                throttle = 0.0

            if eccentricity < 0.02 or energy >= 0:
                self.state = "ORBIT_COMPLETE"

        elif self.state == "ORBIT_COMPLETE":
            throttle = 0.0
            self.message = "GSO Stable"
            target_angle = tangent_angle

        rocket.throttle = throttle
        diff = (target_angle - rocket.angle + 180) % 360 - 180
        rocket.angle += diff * 0.1

        return self.message

# --- LUNAR COMPUTER ---


class LunarComputer:
    def __init__(self):
        self.state = "LIFTOFF"
        self.message = "Lunar Mission Start"
        # Bumped to 250km for safety margin
        self.target_park_alt = 250000

    def control(self, rocket, bodies, dt):
        earth = bodies[0]
        moon = bodies[1]

        # --- TELEMETRY ---
        r_sq = rocket.x**2 + rocket.y**2
        r = math.sqrt(r_sq)
        alt = r - EARTH_RADIUS

        v_sq = rocket.vx**2 + rocket.vy**2
        v = math.sqrt(v_sq)
        v_radial = (rocket.x * rocket.vx + rocket.y * rocket.vy) / r

        # --- ORBITAL MECHANICS ---
        mu = G * EARTH_MASS
        energy = (v**2 / 2) - (mu / r)

        # Calculate Periapsis (Lowest projected point)
        if energy != 0:
            a = -mu / (2 * energy)
        else:
            a = r

        h = rocket.x * rocket.vy - rocket.y * rocket.vx
        term = (2 * energy * h**2) / (mu**2)
        eccentricity = math.sqrt(max(0, 1 + term))

        # Periapsis Radius
        rp = a * (1 - eccentricity)
        periapsis_alt = rp - EARTH_RADIUS

        # --- NAVIGATION ---
        pos_angle = math.degrees(math.atan2(rocket.y, rocket.x))
        earth_tangent = pos_angle + 90

        throttle = 0.0
        target_angle = rocket.angle

        # --- STATE MACHINE ---
        if self.state == "LIFTOFF":
            throttle = 1.0
            target_angle = 270
            self.message = "Liftoff - Target: LEO Parking"
            if alt > 2000:
                self.state = "GRAVITY_TURN"

        elif self.state == "GRAVITY_TURN":
            throttle = 1.0
            prog = min(1.0, (alt - 2000) / 80000)
            target_angle = 270 + (prog * 90)
            self.message = f"Ascent: {int(prog*100)}%"

            # Predict Apogee
            if energy < 0:
                pred_apogee = a * (1 + eccentricity) - EARTH_RADIUS
                if pred_apogee >= self.target_park_alt:
                    self.state = "LEO_COAST"

        elif self.state == "LEO_COAST":
            throttle = 0.0
            target_angle = earth_tangent
            self.message = f"Coasting (Ap: {int(periapsis_alt/1000)}km)"

            # Wait for Apogee OR Panic if falling
            if abs(v_radial) < 10 or v_radial < -20:
                self.state = "LEO_CIRC"

        elif self.state == "LEO_CIRC":
            target_angle = earth_tangent
            v_needed = math.sqrt(G * EARTH_MASS / r)
            delta_v = v_needed - v
            self.message = f"Parking (Pe: {int(periapsis_alt/1000)}km)"

            if delta_v > 0:
                throttle = min(1.0, delta_v / 50.0)
                throttle = max(0.1, throttle)
            else:
                throttle = 0.0

            # Pitch Up Correction
            if v_radial < -10:
                target_angle -= 5

            # STOP CONDITION: PERIAPSIS CHECK
            if periapsis_alt > 200000:
                throttle = 0.0
                self.state = "PHASING_WAIT"

        elif self.state == "PHASING_WAIT":
            throttle = 0.0
            target_angle = earth_tangent

            # Station Keeping
            if alt < 180000:
                throttle = 1.0
                self.message = "ALTITUDE WARNING - STATION KEEPING"
            else:
                theta_r = math.atan2(rocket.y, rocket.x)
                theta_m = math.atan2(moon.y, moon.x)
                phase_rad = (theta_m - theta_r) % (2 * math.pi)
                phase_deg = math.degrees(phase_rad)

                self.message = f"Waiting for Moon. Phase: {int(phase_deg)} (Target: 110)"

                if 108 < phase_deg < 112:
                    self.state = "TLI_BURN"

        elif self.state == "TLI_BURN":
            throttle = 1.0
            target_angle = earth_tangent
            self.message = "TRANS-LUNAR INJECTION BURN"

            # Case 1: Elliptical Orbit (Standard)
            if energy < 0:
                pred_apogee = a * (1 + eccentricity) - EARTH_RADIUS
                # Check if we reach the Moon's altitude
                if pred_apogee > 375000000:
                    self.state = "TRANS_LUNAR_COAST"

            # Case 2: Hyperbolic/Escape Trajectory (Safety Cutoff)
            else:
                # We have hit escape velocity, so stop immediately.
                self.state = "TRANS_LUNAR_COAST"

        elif self.state == "TRANS_LUNAR_COAST":
            throttle = 0.0
            target_angle = earth_tangent

            dx_m = rocket.x - moon.x
            dy_m = rocket.y - moon.y
            dist_moon = math.sqrt(dx_m**2 + dy_m**2)

            self.message = f"To the Moon! Dist: {int(dist_moon/1000)} km"

            # WAKE UP AT 66,000 km
            if dist_moon < 66000000:
                self.state = "LUNAR_APPROACH"

        elif self.state == "LUNAR_APPROACH":
            throttle = 0.0

            vx_m = rocket.vx - moon.vx
            vy_m = rocket.vy - moon.vy
            retro_angle = math.degrees(math.atan2(vy_m, vx_m)) + 180
            target_angle = retro_angle

            dx_m = rocket.x - moon.x
            dy_m = rocket.y - moon.y
            dist_moon = math.sqrt(dx_m**2 + dy_m**2)

            self.message = f"Approaching Perilune (Dist: {int(dist_moon/1000)} km)"

            v_rad_moon = (dx_m * vx_m + dy_m * vy_m) / dist_moon

            # TRIGGER INSERTION at 5,000 km
            if dist_moon < 5000000:
                self.state = "LUNAR_INSERTION"
            elif v_rad_moon > 0:
                self.state = "LUNAR_INSERTION"

        elif self.state == "LUNAR_INSERTION":
            self.message = "Lunar Orbit Insertion Burn"

            vx_m = rocket.vx - moon.vx
            vy_m = rocket.vy - moon.vy
            v_moon_mag = math.sqrt(vx_m**2 + vy_m**2)
            dx_m = rocket.x - moon.x
            dy_m = rocket.y - moon.y
            dist_moon = math.sqrt(dx_m**2 + dy_m**2)

            retro_angle = math.degrees(math.atan2(vy_m, vx_m)) + 180
            target_angle = retro_angle

            v_target = math.sqrt(G * MOON_MASS / dist_moon)

            if v_moon_mag > v_target:
                delta_v = v_moon_mag - v_target
                throttle = min(1.0, delta_v / 50.0)
                throttle = max(0.1, throttle)
            else:
                throttle = 0.0
                self.state = "LUNAR_ORBIT"

        elif self.state == "LUNAR_ORBIT":
            throttle = 0.0
            vx_m = rocket.vx - moon.vx
            vy_m = rocket.vy - moon.vy
            self.message = "Welcome to Low Lunar Orbit."
            target_angle = math.degrees(math.atan2(vy_m, vx_m))

        # --- IMPORTANT OUTPUT SECTION ---
        # This was likely missing in your file!
        rocket.throttle = throttle
        diff = (target_angle - rocket.angle + 180) % 360 - 180
        rocket.angle += diff * 0.1

        return self.message
