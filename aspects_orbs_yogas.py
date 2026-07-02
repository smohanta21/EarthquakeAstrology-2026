
def get_aspects(planets):
    results = []
    names = list(planets.keys())

    ASPECTS = {
        "Conjunction": 0,
        "Opposition": 180,
        "Trine": 120,
        "Square": 90,
        "Sextile": 60,
    }

    ORBS = {
        "Conjunction": 8,
        "Opposition": 8,
        "Trine": 6,
        "Square": 6,
        "Sextile": 4,
    }

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            p1, p2 = names[i], names[j]
            lon1, lon2 = planets[p1], planets[p2]
            angle = abs(lon1 - lon2) % 360
            if angle > 180:
                angle = 360 - angle
            for aspect_name, aspect_angle in ASPECTS.items():
                orb = ORBS[aspect_name]
                if abs(angle - aspect_angle) <= orb:
                    results.append({
                        "Planet1": p1,
                        "Planet2": p2,
                        "Aspect": aspect_name,
                        "Angle": round(angle, 2),
                        "Orb": round(abs(angle - aspect_angle), 2)
                    })
    return results
