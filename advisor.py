# Salix integra watering advisor
# The advisor uses leaf area measurement from photos to esmitate
# how the plant is doing over time.
# It looks at:
# 1: Growth rates between measurements (RGR)
# 2: The plants normal past growth pattern
# 3: Recent watering events
# 4: How much data is available and how confident it is
import math
from datetime import datetime


WATERING_RECENT_DAYS = 3
WATERING_DRY_DAYS = 7
SIGMA_STRESS = 2.0
SIGMA_WARNING = 1.0
SIGMA_GROWTH = 1.0
MIN_NOISE = 0.005
MIN_BASELINE_PAIRS = 3


class Recommendation:
    # Advisor result - everything the UI needs in one object

    def __init__(self):
        # stress | warning | stable | growth | insufficient_data | no_data
        self.status = ""
        self.latest_pct = 0.0
        self.rgr = None                  # latest RGR, 1/day
        self.rgr_baseline_mean = None
        self.rgr_baseline_std = None
        self.z_score = None
        self.n_prior_pairs = 0
        self.days_since_water = None
        self.confidence = "low" # low | medium | high
        self.confidence_score = 0
        self.title = ""
        self.message = ""
        self.action = ""
        self.level = "info" # error | warning | info | success
        self.details = []


def parse_date(s):
    # Convert date string to datetime object
    if not s:
        raise ValueError("Empty date")
    if "T" in s:
        s = s.replace("Z", "")[:19]
    return datetime.fromisoformat(s)


def compute_rgr_pairs(history):
    # Return (date2, rgr_per_day, days_between) for consecutive pairs
    pairs = []
    for i in range(len(history) - 1):
        d1, f1 = history[i]
        d2, f2 = history[i + 1]

        # Skip invalid data
        if f1 <= 0 or f2 <= 0:
            continue
        try:
            t1 = parse_date(d1)
            t2 = parse_date(d2)
        except (ValueError, TypeError):
            continue

        days = (t2 - t1).days
        if days <= 0:
            continue

        rgr = (math.log(f2) - math.log(f1)) / days
        pairs.append((t2, rgr, days))
    return pairs

def confidence_level(n_prior_pairs):
    """How confident we can be, based on how much data we have."""
    if n_prior_pairs >= 6:
        return "high"
    if n_prior_pairs >= 3:
        return "medium"
    return "low"

def compute_baseline(prior_rgrs):
    # Mean and standard deviation from historical RGRs
    n = len(prior_rgrs)
    if n >= 2:
        mean_val = sum(prior_rgrs) / n
        variance = sum((r - mean_val) ** 2 for r in prior_rgrs) / n
        return mean_val, max(math.sqrt(variance), MIN_NOISE)
    if n == 1:
        return prior_rgrs[0], MIN_NOISE
    return 0.0, MIN_NOISE


def days_since_last_water(latest_date, watering_events):
    # How many days have passed since the last watering
    if not watering_events:
        return None
    try:
        ref = parse_date(latest_date)
    except (ValueError, TypeError):
        return None

    past = []
    for d, _ in watering_events:
        if not d:
            continue
        try:
            wd = parse_date(d)
        except (ValueError, TypeError):
            continue
        if wd <= ref:
            past.append(wd)

    if not past:
        return None
    return (ref - max(past)).days


def confidence_from_context(n_measurements, n_prior_pairs, days_since_water):
    # Return label, score, and explanation lines for advisor confidence
    score = 0
    caveats = []

    if n_measurements >= 8:
        score += 2
    elif n_measurements >= 4:
        score += 1
    else:
        caveats.append("Maz mērījumu - tendence vēl var būt nejauša.")

    if n_prior_pairs >= MIN_BASELINE_PAIRS:
        score += 2
    elif n_prior_pairs >= 1:
        score += 1
        caveats.append("Bāzlīnija balstās uz nelielu iepriekšējo RGR skaitu.")
    else:
        caveats.append("Nav pietiekamas vēstures auga individuālai bāzlīnijai.")

    if days_since_water is not None:
        score += 1
    else:
        caveats.append("Nav reģistrētas laistīšanas vēstures.")

    if score >= 4:
        return "high", score, caveats
    if score >= 2:
        return "medium", score, caveats
    return "low", score, caveats


def latest_delta(history):
    # Return latest area change metrics from the last two measurements
    if len(history) < 2:
        return None, None, None

    d1, f1 = history[-2]
    d2, f2 = history[-1]
    try:
        days = (parse_date(d2) - parse_date(d1)).days
    except (ValueError, TypeError):
        days = None

    delta_points = (f2 - f1) * 100
    if f1 > 0:
        delta_relative = ((f2 - f1) / f1) * 100
    else:
        delta_relative = None
    return days, delta_points, delta_relative


def add_common_details(rec):
    # Fill the short explanation lines shown in the UI
    rec.details.append(f"Pēdējais mērījums: {rec.latest_pct:.2f}% no attēla")
    if rec.days_between_latest is not None:
        rec.details.append(
            f"Dienas starp pēdējiem mērījumiem: {rec.days_between_latest}")
    if rec.rgr is not None:
        rec.details.append(f"Pēdējais RGR: {rec.rgr * 100:+.2f}% dienā")
    if rec.rgr_baseline_mean is not None:
        rec.details.append(
            f"Bāzes RGR: {rec.rgr_baseline_mean * 100:+.2f}% dienā "
            f"(aprēķināts no {rec.n_prior_pairs} iepriekšējiem pāriem)")
    if rec.days_since_water is not None:
        rec.details.append(
            f"Pēdējā laistīšana: pirms {rec.days_since_water} dienām")
    else:
        rec.details.append("Pēdējā laistīšana: nav reģistrēta")
    rec.details.append(
        f"Pārliecība: {rec.confidence} ({rec.confidence_score}/5) - "
        "balstīta uz mērījumu skaitu, bāzlīnijas vēsturi un laistīšanas datiem")


def advise(history, watering_events=None):
    """
    Main advisor function.

    history: list of date, area in [0, 1] sorted ascending
    watering_events: optional list of date, amount_ml sorted ascending
    """
    rec = Recommendation()

    # Case 1: no data at all
    if not history:
        rec.status = "no_data"
        rec.title = "Nav datu"
        rec.message = "Šim augam nav pieejami mērījumi."
        rec.level = "info"
        return rec

    # Latest measurement
    latest_date, latest_frac = history[-1]
    rec.latest_pct = latest_frac * 100

    # Compute RGR pairs
    rgr_pairs = compute_rgr_pairs(history)

    # Case 2: not enough data to compute a trend
    if not rgr_pairs:
        rec.status = "insufficient_data"
        rec.title = "Nepietiek datu tendences aprēķinam"
        rec.message = (
            "Ir nepieciešami vismaz divi mērījumi ar derīgiem datumiem, "
            "lai aprēķinātu auga relatīvo augšanas ātrumu (RGR).")
        rec.level = "info"
        return rec

    # Split: latest RGR and all prior ones (used for the baseline)
    latest_rgr = rgr_pairs[-1][1]
    prior_rgrs = [r for _, r, _ in rgr_pairs[:-1]]
    n_prior = len(prior_rgrs)

    # Baseline - mean and standard deviation
    baseline_mean, baseline_std = compute_baseline(prior_rgrs)

    # Z-score - how many standard deviations the latest RGR is from the norm
    z = (latest_rgr - baseline_mean) / baseline_std

    # Fill in the basic fields
    rec.rgr = latest_rgr
    rec.rgr_baseline_mean = baseline_mean
    rec.rgr_baseline_std = baseline_std
    rec.z_score = z
    rec.n_prior_pairs = n_prior
    rec.confidence = confidence_level(n_prior)
    rec.days_since_water = days_since_last_water(latest_date, watering_events)

    # Was the plant watered recently?
    recently_watered = (
        rec.days_since_water is not None
        and rec.days_since_water <= WATERING_RECENT_DAYS
    )

    # Detailed info - shown under the main recommendation
    rec.details.append(f"Pēdējais RGR: {latest_rgr * 100:+.2f}% dienā")
    rec.details.append(
        f"Bāzlīnijas vidējais RGR: {baseline_mean * 100:+.2f}% ± "
        f"{baseline_std * 100:.2f}% dienā (n={n_prior} pāri)")
    rec.details.append(f"Z-rādītājs: {z:+.2f}σ")
    rec.details.append(f"Pārliecība: {rec.confidence}")
    if rec.days_since_water is not None:
        rec.details.append(
            f"Pēdējā laistīšana: pirms {rec.days_since_water} dienām")
    else:
        rec.details.append("Pēdējā laistīšana: nav reģistrēta")

    # Classify the state
    if z <= -SIGMA_STRESS and recently_watered:
        # Big drop, but watered recently - don't increase the dose right away
        rec.status = "stress"
        rec.level = "warning"
        rec.title = "Iespējams stress, bet augs nesen laistīts"
        rec.message = (
            f"Lapotnes laukums būtiski samazinājies "
            f"({z:+.1f}σ no bāzlīnijas), tomēr augs tika laistīts "
            f"pirms {rec.days_since_water} dienām. Ieteicams nogaidīt "
            f"un veikt papildu mērījumu pēc 1-2 dienām, pirms "
            f"palielināt laistīšanas devu.")

    elif z <= -SIGMA_STRESS:
        # Big drop and not recently watered - drought stress
        rec.status = "stress"
        rec.level = "error"
        rec.title = "Sausuma stress — steidzami laistīt"
        rec.message = (
            f"Auga relatīvais augšanas ātrums ir {z:+.1f} standartnoviržu "
            f"zem šī auga vēsturiskās bāzlīnijas. Tas norāda uz "
            f"iespējamu sausuma stresu. Ieteicams nekavējoties palielināt "
            f"laistīšanas biežumu un pārbaudīt augsnes mitrumu.")

    elif z <= -SIGMA_WARNING:
        # Slightly below the norm - warning
        rec.status = "warning"
        rec.level = "warning"
        rec.title = "Lēna augšana — sekojiet līdzi"
        rec.message = (
            f"Augšanas ātrums ir nedaudz zem auga normas "
            f"({z:+.1f}σ). Vēl nav kritiski, bet ieteicams veikt "
            f"papildu mērījumu tuvāko dienu laikā un pārbaudīt "
            f"augsnes mitrumu.")

    elif z >= SIGMA_GROWTH:
        # Above the norm - the plant is growing actively
        rec.status = "growth"
        rec.level = "success"
        rec.title = "Aktīva augšana"
        rec.message = (
            f"Augs aug aktīvi ({z:+.1f}σ virs bāzlīnijas). "
            f"Saglabājiet pašreizējo laistīšanas režīmu.")

    else:
        # Within the norm - stable
        rec.status = "stable"
        rec.level = "success"
        rec.title = "Stabils stāvoklis"
        rec.message = (
            f"Auga augšanas ātrums atbilst tā vēsturiskajai normai "
            f"({z:+.1f}σ). Saglabājiet pašreizējo laistīšanas režīmu.")

    return rec
