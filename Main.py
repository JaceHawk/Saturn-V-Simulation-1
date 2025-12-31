import pygame
import math
# RocketSystems handles Physics
from RocketSystems import (create_saturn_v, draw_rocket_stack, EARTH_RADIUS, Body,
                           EARTH_MASS, MOON_DISTANCE, MOON_MASS, MOON_RADIUS,
                           MOON_VELOCITY)

# FlightComputers handles Logic
from FlightComputers import GSOComputer, LunarComputer

# --- SETUP ---
pygame.init()
WIDTH, HEIGHT = 1000, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 20)
title_font = pygame.font.SysFont("Arial", 40, bold=True)


def run_simulation(autopilot_mode=False):
    # --- INITIATE SIMULATION OBJECTS ---
    earth = Body(0, 0, EARTH_MASS, EARTH_RADIUS, (0, 100, 50), is_fixed=True)
    moon = Body(MOON_DISTANCE, 0, MOON_MASS, MOON_RADIUS,
                (150, 150, 150), vy=MOON_VELOCITY)
    bodies = [earth, moon]
    rocket = create_saturn_v()

    # Initiate Autopilot if requested
    computer = None
    if autopilot_mode == 1:  # GSO
        computer = GSOComputer(target_alt=35786000)
    elif autopilot_mode == 2:  # MOON
        computer = LunarComputer()

    current_scale = 0.0005
    sim_running = True

    while sim_running:
        # --- TIME WARP ---
        sim_steps = 1
        dt = 0.1
        keys = pygame.key.get_pressed()

        # Keep your warp keys
        if keys[pygame.K_t]:
            sim_steps = 10
        if keys[pygame.K_y]:
            sim_steps = 100
        if keys[pygame.K_u]:
            sim_steps = 1000
        if keys[pygame.K_i]:
            sim_steps = 10000

        # --- EVENTS ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False  # Quit the whole app
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and not autopilot_mode:
                    rocket.activate_stage()
                if event.key == pygame.K_ESCAPE:
                    return True  # Go back to Menu

        # --- ZOOM LOGIC ---
        if keys[pygame.K_q]:
            current_scale *= 1.02
        if keys[pygame.K_a]:
            current_scale /= 1.02

        # --- PHYSICS & CONTROLS LOOP ---
        # We define msg default in case autopilot is off
        msg = "Manual Control"

        # We move the Autopilot Logic INSIDE the warp loop
        for _ in range(sim_steps):

            # 1. Autopilot Logic (Think every step)
            if autopilot_mode and computer:
                # Pass bodies so it can see the Moon
                msg = computer.control(rocket, bodies, dt)

                # Auto-Staging Logic (Must also happen inside loop!)
                active = rocket.stages[-1]
                if rocket.throttle > 0.9 and active.fuel_mass <= 0:
                    rocket.activate_stage()

            # 2. Manual Logic (Only if autopilot is OFF)
            elif not autopilot_mode:
                if keys[pygame.K_LEFT]:
                    rocket.angle += 1
                if keys[pygame.K_RIGHT]:
                    rocket.angle -= 1
                if keys[pygame.K_UP]:
                    rocket.throttle = min(1.0, rocket.throttle + 0.01)
                if keys[pygame.K_DOWN]:
                    rocket.throttle = max(0.0, rocket.throttle - 0.01)

            # 3. Physics Update (Move every step)
            rocket.update(bodies, dt)
            moon.update(earth, dt)

        # --- RENDER ---
        screen.fill((20, 20, 30))
        for b in bodies:
            b.draw(screen, rocket.x, rocket.y, current_scale, WIDTH, HEIGHT)

        draw_rocket_stack(screen, rocket, rocket.x, rocket.y,
                          current_scale, WIDTH, HEIGHT)

        # --- TRAJECTORY PREDICTION (Dynamic) ---
        dist_sq = rocket.x**2 + rocket.y**2

        # Default settings (Launch/LEO)
        pred_steps = 20000
        pred_dt = 10.0

        # Deep Space Mode (> 50,000 km)
        if dist_sq > (50000000)**2:
            pred_steps = 15000    # Fewer steps
            pred_dt = 100.0      # Larger time jumps

        # Calculate the path
        pred_path, time_to_impact = rocket.get_trajectory(
            bodies, steps=pred_steps, dt_pred=pred_dt)

        # Get Status (Now passing 'bodies')
        status_text, status_color = rocket.get_orbit_status(bodies)

        # --- DRAW THE LINE ---
        if len(pred_path) > 1:
            pts = []
            for pt in pred_path:
                px = int(WIDTH // 2 + (pt[0] - rocket.x) * current_scale)
                py = int(HEIGHT // 2 + (pt[1] - rocket.y) * current_scale)
                pts.append((px, py))

            # Draw the trajectory line
            pygame.draw.lines(screen, status_color, False, pts, 1)

        # --- HUD INFO ---
        # Compass
        center_x, center_y = WIDTH // 2, HEIGHT // 2
        compass_radius = 80
        pygame.draw.circle(screen, (80, 80, 80),
                           (center_x, center_y), compass_radius, 1)

        nose_rad = math.radians(rocket.angle)
        nose_x = center_x + math.cos(nose_rad) * compass_radius
        nose_y = center_y + math.sin(nose_rad) * compass_radius
        pygame.draw.line(screen, (100, 50, 50),
                         (center_x, center_y), (nose_x, nose_y), 1)
        pygame.draw.circle(screen, (255, 50, 50),
                           (int(nose_x), int(nose_y)), 4)

        speed = math.sqrt(rocket.vx**2 + rocket.vy**2)
        if speed > 10:
            vel_angle = math.atan2(rocket.vy, rocket.vx)
            vel_x = center_x + math.cos(vel_angle) * compass_radius
            vel_y = center_y + math.sin(vel_angle) * compass_radius
            pygame.draw.circle(screen, (0, 255, 0),
                               (int(vel_x), int(vel_y)), 3)

        # Text Info
        active_stage = rocket.stages[-1]
        alt_km = (math.sqrt(rocket.x**2 + rocket.y**2) - EARTH_RADIUS)/1000

        info = [
            f"Mode: {'AUTOPILOT' if autopilot_mode else 'MANUAL'}",
            f"Computer: {msg}",
            f"Stage: {active_stage.name}",
            f"Fuel: {int(active_stage.fuel_mass)}",
            f"Alt: {alt_km:.1f} km",
            f"Speed: {speed:.0f} m/s",
            f"Time Warp: {sim_steps}x",
            "Press ESC to Return to Menu"
        ]

        for i, line in enumerate(info):
            screen.blit(font.render(line, True, (255, 255, 255)),
                        (10, 10 + i*25))

        pygame.display.flip()
        clock.tick(60)

    return True


# --- MAIN MENU LOOP ---
app_running = True
while app_running:
    screen.fill((10, 10, 20))

    # Title
    title = title_font.render("SATURN V SIMULATOR", True, (255, 255, 255))
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 200))

    # Options
    opt1 = font.render("1. Manual Pilot", True, (200, 200, 200))
    opt2 = font.render("2. Autopilot: GSO", True, (200, 200, 200))
    opt3 = font.render("3. Autopilot: MOON", True, (200, 200, 200))
    opt4 = font.render("Q. Quit", True, (200, 200, 200))

    screen.blit(opt1, (WIDTH//2 - 50, 300))
    screen.blit(opt2, (WIDTH//2 - 50, 350))
    screen.blit(opt3, (WIDTH//2 - 50, 400))
    screen.blit(opt4, (WIDTH//2 - 50, 450))

    pygame.display.flip()

    # --- EVENT LOOP STARTS HERE ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            app_running = False

        if event.type == pygame.KEYDOWN:
            # OPTION 1: Manual
            if event.key == pygame.K_1:
                keep_going = run_simulation(autopilot_mode=False)
                if not keep_going:
                    app_running = False

            # OPTION 2: GSO
            if event.key == pygame.K_2:
                keep_going = run_simulation(autopilot_mode=1)
                if not keep_going:
                    app_running = False

            # OPTION 3: MOON
            if event.key == pygame.K_3:
                keep_going = run_simulation(autopilot_mode=2)
                if not keep_going:
                    app_running = False

            # OPTION Q: Quit
            if event.key == pygame.K_q:
                app_running = False

pygame.quit()
