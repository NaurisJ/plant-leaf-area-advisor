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
    """Advisor result - everything the UI needs in one object."""

    def __init__(self):
        # stress | warning | stable | growth | insufficient_data | no_data
        self.status = ""
        self.latest_pct = 0.0
        self.previous_pct = None
        self.delta_pct_points = None
        self.delta_relative_pct = None
        self.days_between_latest = None
        self.rgr = None
        self.rgr_baseline_mean = None
        self.rgr_baseline_std = None
        self.z_score = None
        self.n_measurements = 0
        self.n_prior_pairs = 0
        self.days_since_water = None
        self.confidence = "low" # low | medium | high
        self.confidence_score = 0
        self.title = ""
        self.message = ""
        self.action = ""
        self.level = "info" # error | warning | info | success
        self.details = []
        self.caveats = []


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

    history: list of (date, area_fraction) sorted ascending
    watering_events: optional list of (date, amount_ml) sorted ascending
    """
    rec = Recommendation()
    rec.n_measurements = len(history)

    if not history:
        rec.status = "no_data"
        rec.title = "Nav datu"
        rec.message = "Šim augam nav pieejami mērījumi."
        rec.action = "Pievienojiet vismaz divus mērījumus ar derīgiem datumiem."
        rec.level = "info"
        rec.caveats.append("Padomdevējs izmanto tikai mērījumu laika rindu.")
        return rec

    latest_date, latest_frac = history[-1]
    rec.latest_pct = latest_frac * 100

    if len(history) >= 2:
        rec.previous_pct = history[-2][1] * 100
        days, delta_points, delta_relative = latest_delta(history)
        rec.days_between_latest = days
        rec.delta_pct_points = delta_points
        rec.delta_relative_pct = delta_relative

    rec.days_since_water = days_since_last_water(latest_date, watering_events)

    rgr_pairs = compute_rgr_pairs(history)
    if not rgr_pairs:
        rec.status = "insufficient_data"
        rec.title = "Nepietiek datu tendences aprēķinam"
        rec.message = (
            "Ir nepieciešami vismaz divi mērījumi ar derīgiem datumiem, "
            "lai aprēķinātu relatīvo augšanas ātrumu.")
        rec.action = "Veiciet nākamo mērījumu pēc 2-7 dienām līdzīgā skatā."
        rec.level = "info"
        rec.confidence, rec.confidence_score, rec.caveats = (
            confidence_from_context(rec.n_measurements, 0, rec.days_since_water))
        rec.caveats.append(
            "Rezultāts nav absolūta platība cm², bet projektētās lapotnes "
            "laukuma relatīvs rādītājs.")
        add_common_details(rec)
        return rec

    latest_rgr = rgr_pairs[-1][1]
    prior_rgrs = [r for _, r, _ in rgr_pairs[:-1]]
    n_prior = len(prior_rgrs)
    baseline_mean, baseline_std = compute_baseline(prior_rgrs)
    z = (latest_rgr - baseline_mean) / baseline_std

    rec.rgr = latest_rgr
    rec.rgr_baseline_mean = baseline_mean
    rec.rgr_baseline_std = baseline_std
    rec.z_score = z
    rec.n_prior_pairs = n_prior
    rec.confidence, rec.confidence_score, rec.caveats = confidence_from_context(
        rec.n_measurements, n_prior, rec.days_since_water)

    recently_watered = (
        rec.days_since_water is not None
        and rec.days_since_water <= WATERING_RECENT_DAYS
    )
    long_without_water = (
        rec.days_since_water is not None
        and rec.days_since_water >= WATERING_DRY_DAYS
    )

    if n_prior < MIN_BASELINE_PAIRS:
        rec.caveats.append(
            "Ieteikums ir sākotnējs, jo auga individuālā bāzlīnija vēl nav "
            "stabila.")
    rec.caveats.append(
        "Padomdevējs nevar atšķirt sausumu no apgriešanas, sezonālām "
        "izmaiņām vai fotografēšanas leņķa maiņas.")

    if z <= -SIGMA_STRESS and recently_watered:
        rec.status = "stress"
        rec.level = "warning"
        rec.title = "Spēcīgs kritums pēc nesenas laistīšanas"
        rec.message = (
            "Lapotnes relatīvais pieaugums ir būtiski zemāks nekā parasti, "
            "bet augs nesen jau ir laistīts.")
        rec.action = (
            "Nelaistiet atkārtoti automātiski. Pārbaudiet augsnes mitrumu "
            "un atkārtojiet mērījumu pēc 1-2 dienām.")

    elif z <= -SIGMA_STRESS and long_without_water:
        rec.status = "stress"
        rec.level = "error"
        rec.title = "Iespējams sausuma stress"
        rec.message = (
            "Augšanas signāls ir būtiski zemāks par šī auga ierasto "
            "līmeni, un pēdējā laistīšana bija pirms "
            f"{rec.days_since_water} dienām.")
        rec.action = (
            "Aplaistiet augu vai pārbaudiet augsnes mitrumu, pēc tam "
            "turpiniet novērošanu ar nākamo mērījumu.")

    elif z <= -SIGMA_STRESS:
        rec.status = "stress"
        rec.level = "warning"
        rec.title = "Būtisks augšanas kritums"
        rec.message = (
            "Relatīvais augšanas ātrums ir būtiski zemāks nekā šim augam "
            "ierasts.")
        rec.action = (
            "Pārbaudiet augsnes mitrumu un auga vizuālo stāvokli. Ja "
            "augsne ir sausa, aplaistiet; ja nav, atkārtojiet mērījumu.")

    elif z <= -SIGMA_WARNING:
        rec.status = "warning"
        rec.level = "warning"
        rec.title = "Augšana palēninās"
        rec.message = (
            "Augšanas signāls ir zem ierastā līmeņa, bet kritums vēl nav "
            "pietiekams stingrai trauksmei.")
        rec.action = (
            "Sekojiet līdzi tuvākajās dienās un pārbaudiet laistīšanas "
            "žurnālu vai augsnes mitrumu.")

    elif z >= SIGMA_GROWTH:
        rec.status = "growth"
        rec.level = "success"
        rec.title = "Aktīva augšana"
        rec.message = (
            "Augšanas signāls ir virs šī auga ierastā līmeņa.")
        rec.action = "Saglabājiet pašreizējo kopšanas un laistīšanas režīmu."

    else:
        rec.status = "stable"
        rec.level = "success"
        rec.title = "Stabils stāvoklis"
        rec.message = (
            "Augšanas signāls ir tuvu auga vēsturiskajai normai.")
        rec.action = "Saglabājiet pašreizējo režīmu un turpiniet mērījumus."

    add_common_details(rec)
    return rec
