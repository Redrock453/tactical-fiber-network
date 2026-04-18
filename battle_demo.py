#!/usr/bin/env python3
"""
TFN Battle Demo — Визуальная демонстрация DAS-разведки
======================================================

Запуск: python battle_demo.py

Показывает в ASCII-графике работу тактической fiber-сети:
- Развёртывание mesh
- DAS-обнаружение целей
- Артобстрел + обрывы
- Трофейное подключение
"""

import random
import time
import sys
import math


FIBER_VISUAL_LENGTH = 80
EVENT_DURATION = 1.5


TARGET_ICONS = {
    "silence": "·",
    "footstep_single": "f",
    "footstep_group": "F",
    "wheeled_vehicle": "O",
    "tracked_vehicle": "T",
    "artillery_fire": "!",
    "explosion": "*",
    "drone_hover": "d",
    "drone_flyby": ">",
    "ew_interference": "~",
    "digging": "#",
}

THREAT_COLORS = {
    "none": "\033[90m",
    "low": "\033[93m",
    "medium": "\033[33m",
    "high": "\033[31m",
    "critical": "\033[91m\033[1m",
}
RESET = "\033[0m"
GREEN = "\033[92m"
CYAN = "\033[96m"
DIM = "\033[90m"
BOLD = "\033[1m"


def clear():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def draw_header():
    print(f"{BOLD}{CYAN}{'═' * 80}{RESET}")
    print(f"{BOLD}{CYAN}  TFN SPIDERLINK — BATTLE DASHBOARD{RESET}")
    print(f"{CYAN}{'═' * 80}{RESET}")
    print()


def draw_fiber(events_on_fiber, fiber_length_m):
    print(f"  {DIM}FIBER: 0m{'─' * (FIBER_VISUAL_LENGTH - 8)}{fiber_length_m}m{RESET}")
    print(f"  {DIM}       ", end="")

    channel = [' '] * FIBER_VISUAL_LENGTH
    colors = [DIM] * FIBER_VISUAL_LENGTH

    for event in events_on_fiber:
        pos = int((event["position_m"] / fiber_length_m) * FIBER_VISUAL_LENGTH)
        pos = max(0, min(pos, FIBER_VISUAL_LENGTH - 1))
        icon = TARGET_ICONS.get(event["target"], "?")
        color = THREAT_COLORS.get(event["threat"], DIM)
        channel[pos] = icon
        colors[pos] = color

    for i in range(FIBER_VISUAL_LENGTH):
        sys.stdout.write(f"{colors[i]}{channel[i]}{RESET}")
    print()
    print()


def draw_events(events):
    print(f"  {BOLD}{'TIME':>8} {'THREAT':<10} {'TARGET':<20} {'POS':>8} {'CONF':>6}  {'DETAILS'}{RESET}")
    print(f"  {DIM}{'─' * 76}{RESET}")

    for evt in events[-15:]:
        threat_color = THREAT_COLORS.get(evt["threat"], DIM)
        icon = TARGET_ICONS.get(evt["target"], "?")
        target_name = evt["target"].replace("_", " ").upper()
        pos_str = f"{evt['position_m']:.0f}m"
        conf_str = f"{evt['confidence']*100:.0f}%"

        print(f"  {evt['time']:>7.1f}s "
              f"{threat_color}{evt['threat']:<10}{RESET} "
              f"{threat_color}{icon} {target_name:<18}{RESET} "
              f"{pos_str:>8} "
              f"{conf_str:>6}  "
              f"{evt.get('desc', '')}")

    if len(events) > 15:
        print(f"  {DIM}  ... and {len(events) - 15} earlier events{RESET}")
    print()


def draw_network_status(nodes_alive, nodes_total, links_active, links_total,
                        battery_avg, connectivity):
    bar_len = 20

    def pct_bar(pct, char="█"):
        filled = int(pct / 100 * bar_len)
        return f"{GREEN}{char * filled}{DIM}{char * (bar_len - filled)}{RESET} {pct:.0f}%"

    print(f"  {BOLD}NETWORK STATUS{RESET}")
    print(f"  {DIM}{'─' * 50}{RESET}")
    print(f"  Nodes:      {nodes_alive}/{nodes_total} alive")
    print(f"  Links:      {links_active}/{links_total} active")
    print(f"  Connect:    {pct_bar(connectivity)}")
    print(f"  Battery:    {pct_bar(battery_avg / 100 * 100)} ({battery_avg:.0f}h avg)")
    print()


def draw_mesh_ascii(nodes, links):
    grid_w, grid_h = 30, 10
    grid = [[' ' for _ in range(grid_w)] for _ in range(grid_h)]

    positions = {}
    for i, (nid, node) in enumerate(nodes.items()):
        row = int((i % 4) * (grid_h / 4)) + 1
        col = int((i // 4) * (grid_w / 2)) + 2
        positions[nid] = (row, col)
        grid[row][col] = '●'

    print(f"  {BOLD}MESH TOPOLOGY{RESET}")
    print(f"  {DIM}{'─' * 30}{RESET}")
    print(f"  {DIM}+", end="")
    for _ in range(grid_w):
        print(f"─", end="")
    print(f"+{RESET}")
    for row in range(grid_h):
        print(f"  {DIM}│{RESET}", end="")
        for col in range(grid_w):
            char = grid[row][col]
            if char == '●':
                print(f"{GREEN}●{RESET}", end="")
            else:
                print(f" ", end="")
        print(f"{DIM}│{RESET}")
    print(f"  {DIM}+", end="")
    for _ in range(grid_w):
        print(f"─", end="")
    print(f"+{RESET}")
    print()


def simulate_battle():
    fiber_length = 5000
    events_log = []
    tick = 0

    nodes = {
        "CP": {"name": "Command Post", "alive": True},
        "POS-A": {"name": "Position Alpha", "alive": True},
        "POS-B": {"name": "Position Bravo", "alive": True},
        "POS-C": {"name": "Position Charlie", "alive": True},
        "OBS-1": {"name": "Observation Post", "alive": True},
        "RELAY": {"name": "Relay Node", "alive": True},
        "REAR": {"name": "Rear Base", "alive": True},
        "DAS-1": {"name": "DAS Interrogator", "alive": True},
    }
    links_total = 12
    links_active = 12

    scenarios = [
        {
            "phase": "PHASE 1: NETWORK DEPLOYMENT",
            "duration": 3,
            "fiber_events": [],
            "network": {"alive": 8, "total": 8, "active": 12, "total_links": 12, "battery": 95, "conn": 100},
            "message": f"  {GREEN}✔ Deploying mesh network: 8 nodes, 12 fiber links{RESET}",
        },
        {
            "phase": "PHASE 2: DAS MONITORING — SECTOR ALPHA",
            "duration": 5,
            "fiber_events": [
                {"position_m": 800, "target": "footstep_single", "threat": "low", "confidence": 0.78, "desc": "Single pedestrian"},
                {"position_m": 850, "target": "footstep_single", "threat": "low", "confidence": 0.72, "desc": "Moving north"},
            ],
            "network": {"alive": 8, "total": 8, "active": 12, "total_links": 12, "battery": 92, "conn": 100},
            "message": f"  {THREAT_COLORS['low']}⚠ Infantry detected at 800m — patrol?{RESET}",
        },
        {
            "phase": "PHASE 3: VEHICLE MOVEMENT DETECTED",
            "duration": 4,
            "fiber_events": [
                {"position_m": 2200, "target": "wheeled_vehicle", "threat": "medium", "confidence": 0.87, "desc": "Wheeled vehicle ×2"},
                {"position_m": 2500, "target": "wheeled_vehicle", "threat": "medium", "confidence": 0.82, "desc": "Speed ~35 km/h, North"},
                {"position_m": 800, "target": "footstep_single", "threat": "low", "confidence": 0.65, "desc": "Still there"},
            ],
            "network": {"alive": 8, "total": 8, "active": 12, "total_links": 12, "battery": 88, "conn": 100},
            "message": f"  {THREAT_COLORS['medium']}⚠ Wheeled convoy moving north — supply route?{RESET}",
        },
        {
            "phase": "PHASE 4: HEAVY ARMOR DETECTED!",
            "duration": 3,
            "fiber_events": [
                {"position_m": 3500, "target": "tracked_vehicle", "threat": "high", "confidence": 0.93, "desc": "TRACKED VEHICLE — tank?"},
                {"position_m": 3550, "target": "tracked_vehicle", "threat": "high", "confidence": 0.89, "desc": "Second tracked unit"},
                {"position_m": 2200, "target": "wheeled_vehicle", "threat": "medium", "confidence": 0.75, "desc": "Convoy stopped"},
            ],
            "network": {"alive": 8, "total": 8, "active": 12, "total_links": 12, "battery": 84, "conn": 100},
            "message": f"  {THREAT_COLORS['high']}!!! TRACKED ARMOR at 3500m — preparing positions!{RESET}",
        },
        {
            "phase": "PHASE 5: RF-Opto — EW STATION DETECTED",
            "duration": 3,
            "fiber_events": [
                {"position_m": 3800, "target": "ew_interference", "threat": "high", "confidence": 0.91, "desc": "EW station — 2.4GHz, ~500W"},
                {"position_m": 3500, "target": "tracked_vehicle", "threat": "high", "confidence": 0.90, "desc": "Armor near EW"},
                {"position_m": 3600, "target": "digging", "threat": "low", "confidence": 0.73, "desc": "Fortification work"},
            ],
            "network": {"alive": 8, "total": 8, "active": 12, "total_links": 12, "battery": 80, "conn": 100},
            "message": f"  {THREAT_COLORS['high']}!!! EW STATION at 3800m — passive detection via Kerr effect{RESET}",
        },
        {
            "phase": "PHASE 6: ARTILLERY STRIKE ON OUR SECTOR!",
            "duration": 3,
            "fiber_events": [
                {"position_m": 1200, "target": "artillery_fire", "threat": "critical", "confidence": 0.98, "desc": "ARTILLERY IMPACT!"},
                {"position_m": 1500, "target": "explosion", "threat": "critical", "confidence": 0.97, "desc": "EXPLOSION"},
                {"position_m": 3500, "target": "tracked_vehicle", "threat": "high", "confidence": 0.85, "desc": "Armor repositioning"},
            ],
            "network": {"alive": 7, "total": 8, "active": 9, "total_links": 12, "battery": 78, "conn": 75},
            "message": f"  {THREAT_COLORS['critical']}████ ARTILLERY STRIKE! 3 links broken, 1 node down!{RESET}",
        },
        {
            "phase": "PHASE 7: MESH SELF-HEALING",
            "duration": 3,
            "fiber_events": [
                {"position_m": 1200, "target": "explosion", "threat": "critical", "confidence": 0.95, "desc": "Secondary explosion"},
                {"position_m": 3500, "target": "tracked_vehicle", "threat": "high", "confidence": 0.82, "desc": "Armor moving"},
            ],
            "network": {"alive": 7, "total": 8, "active": 9, "total_links": 12, "battery": 75, "conn": 75},
            "message": f"  {GREEN}✔ Mesh re-routing: 9/12 links active, traffic redirected{RESET}",
        },
        {
            "phase": "PHASE 8: TROPHY INTELLIGENCE",
            "duration": 4,
            "fiber_events": [
                {"position_m": 4500, "target": "footstep_group", "threat": "medium", "confidence": 0.84, "desc": "Enemy patrol (via THEIR cable!)"},
                {"position_m": 4800, "target": "wheeled_vehicle", "threat": "medium", "confidence": 0.79, "desc": "Enemy supply truck"},
                {"position_m": 4900, "target": "ew_interference", "threat": "high", "confidence": 0.88, "desc": "Enemy CP — generator 50Hz"},
            ],
            "network": {"alive": 7, "total": 8, "active": 9, "total_links": 12, "battery": 72, "conn": 75},
            "message": f"  {CYAN}★ TROPHY: Connected to enemy fiber — reading their positions!{RESET}",
        },
        {
            "phase": "PHASE 9: COUNTER-BATTERY FIRE",
            "duration": 3,
            "fiber_events": [
                {"position_m": 3500, "target": "artillery_fire", "threat": "critical", "confidence": 0.99, "desc": "OUR artillery firing"},
                {"position_m": 4000, "target": "explosion", "threat": "critical", "confidence": 0.96, "desc": "Direct hit on enemy position"},
                {"position_m": 3800, "target": "ew_interference", "threat": "low", "confidence": 0.45, "desc": "EW signal fading..."},
            ],
            "network": {"alive": 7, "total": 8, "active": 10, "total_links": 12, "battery": 70, "conn": 83},
            "message": f"  {GREEN}✔ Counter-battery: Enemy EW suppressed!{RESET}",
        },
        {
            "phase": "PHASE 10: SITUATION STABLE",
            "duration": 3,
            "fiber_events": [
                {"position_m": 800, "target": "footstep_single", "threat": "low", "confidence": 0.60, "desc": "Patrol returning"},
            ],
            "network": {"alive": 7, "total": 8, "active": 10, "total_links": 12, "battery": 68, "conn": 83},
            "message": f"  {GREEN}✔ Sector stable. Monitoring continues. Battery: 68h avg.{RESET}",
        },
    ]

    for scenario in scenarios:
        for sub_tick in range(scenario["duration"]):
            tick += 1
            clear()
            draw_header()

            print(f"  {BOLD}{CYAN}{scenario['phase']}{RESET}  {DIM}T={tick * 10}s{RESET}")
            print()

            draw_fiber(scenario["fiber_events"], fiber_length)

            for evt in scenario["fiber_events"]:
                evt_copy = evt.copy()
                evt_copy["time"] = tick * 10 - sub_tick * 3 + random.uniform(-1, 1)
                events_log.append(evt_copy)

            draw_events(events_log)

            n = scenario["network"]
            draw_network_status(
                n["alive"], n["total"],
                n["active"], n["total_links"],
                n["battery"], n["conn"]
            )

            print(scenario["message"])
            print()

            print(f"  {DIM}Press Ctrl+C to exit | Tick {tick}{RESET}")
            sys.stdout.flush()
            time.sleep(EVENT_DURATION)

    clear()
    draw_header()
    print(f"  {BOLD}{GREEN}SIMULATION COMPLETE{RESET}")
    print()
    print(f"  Total events: {len(events_log)}")
    high_threats = sum(1 for e in events_log if e["threat"] in ("high", "critical"))
    print(f"  High/critical threats: {high_threats}")
    print(f"  Final network: 7/8 nodes alive, 10/12 links active")
    print()
    print(f"  {DIM}SpiderLink TFN — Zero-Emission Tactical Intelligence{RESET}")


if __name__ == "__main__":
    try:
        simulate_battle()
    except KeyboardInterrupt:
        print(f"\n\n  {DIM}Stopped.{RESET}")
