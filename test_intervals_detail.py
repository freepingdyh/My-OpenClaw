#!/usr/bin/env python3
"""
test_intervals_detail.py

Intervals.icu read-only detail test for Zeabur.

Required ENV:
    INTERVALS_ICU_API_KEY

Target activity:
    i177378895

This script:
1. Fetches full activity detail with intervals=true
2. Prints useful summary fields
3. Prints HR zones and HR-zone time
4. Prints interval / lap-like data
5. Fetches time-series streams
6. Prints HR / speed / cadence / distance / altitude stream statistics

NO writes.
Does NOT touch Calendar, Discord, or lobster_discord.py.
"""

import json
import os
import sys

import requests


BASE_URL = "https://intervals.icu/api/v1"
ACTIVITY_ID = "i177378895"
TIMEOUT_SECONDS = 30


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def api_get(api_key, url, label, params=None):
    response = requests.get(
        url,
        params=params,
        auth=("API_KEY", api_key),
        headers={
            "Accept": "application/json",
            "User-Agent": "xiaoxia-intervals-detail-test/1.0",
        },
        timeout=TIMEOUT_SECONDS,
    )

    print(f"{label} HTTP status: {response.status_code}")

    if response.status_code != 200:
        body = response.text.replace(api_key, "***REDACTED***")
        print(body[:1500])
        response.raise_for_status()

    return response.json()


def format_pace_from_mps(value):
    speed = as_float(value)
    if speed is None or speed <= 0:
        return "-"

    total_seconds = 1000.0 / speed
    minutes = int(total_seconds // 60)
    seconds = int(round(total_seconds % 60))

    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d}/km"


def compact(value, limit=1200):
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def print_activity_summary(detail):
    print("\nACTIVITY SUMMARY")
    print("=" * 50)

    distance_m = as_float(detail.get("distance"))
    elapsed = as_float(detail.get("elapsed_time"))
    moving = as_float(detail.get("moving_time"))
    avg_speed = as_float(detail.get("average_speed"))

    if distance_m is not None:
        print(f"distance: {distance_m / 1000.0:.2f} km")
    else:
        print("distance: -")

    if elapsed is not None:
        print(f"elapsed time: {elapsed / 60.0:.1f} min")
    else:
        print("elapsed time: -")

    if moving is not None:
        print(f"moving time: {moving / 60.0:.1f} min")
    else:
        print("moving time: -")

    print(f"id: {detail.get('id')}")
    print(f"name: {detail.get('name')}")
    print(f"type: {detail.get('type')}")
    print(f"start local: {detail.get('start_date_local')}")
    print(f"avg HR: {detail.get('average_heartrate')}")
    print(f"max HR: {detail.get('max_heartrate')}")
    print(f"avg pace: {format_pace_from_mps(avg_speed)}")
    print(f"avg cadence: {detail.get('average_cadence')}")
    print(f"training load: {detail.get('icu_training_load')}")
    print(f"HR load: {detail.get('hr_load')}")
    print(f"HR load type: {detail.get('hr_load_type')}")
    print(f"intensity: {detail.get('icu_intensity')}")
    print(f"LTHR: {detail.get('lthr')}")
    print(f"athlete max HR: {detail.get('athlete_max_hr')}")
    print(f"lap count: {detail.get('icu_lap_count')}")
    print(f"polarization index: {detail.get('polarization_index')}")
    print(f"device: {detail.get('device_name')}")
    print(f"source: {detail.get('source')}")
    print(f"file type: {detail.get('file_type')}")
    print(f"min altitude: {detail.get('min_altitude')}")
    print(f"max altitude: {detail.get('max_altitude')}")
    print(f"elevation gain: {detail.get('total_elevation_gain')}")
    print(f"elevation loss: {detail.get('total_elevation_loss')}")
    print(f"calories: {detail.get('calories')}")


def print_hr_zones(detail):
    print("\nHR ZONES")
    print("=" * 50)

    zones = detail.get("icu_hr_zones")
    times = detail.get("icu_hr_zone_times")

    print("icu_hr_zones:")
    print(compact(zones))

    print("\nicu_hr_zone_times:")
    print(compact(times))

    if isinstance(times, list) and times:
        numeric = [as_float(x) or 0.0 for x in times]
        total = sum(numeric)

        if total > 0:
            print("\nZone-time breakdown:")
            for index, seconds in enumerate(numeric, start=1):
                print(
                    f"Z{index}: "
                    f"{seconds / 60.0:.1f} min "
                    f"({seconds / total * 100.0:.1f}%)"
                )


def print_intervals(detail):
    print("\nINTERVAL / LAP DATA")
    print("=" * 50)

    keys = (
        "intervals",
        "icu_intervals",
        "interval_summary",
        "laps",
        "lengths",
    )

    found = False

    for key in keys:
        value = detail.get(key)

        if isinstance(value, list) and value:
            found = True
            print(f"\n{key}: {len(value)} item(s)")

            for index, item in enumerate(value[:15], start=1):
                print(f"{index}: {compact(item, 1000)}")

            if len(value) > 15:
                print(f"... {len(value) - 15} more item(s)")

    if not found:
        print("No interval/lap list returned by the detail endpoint.")


def normalize_streams(payload):
    result = {}

    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, list):
                result[str(key)] = value

            elif isinstance(value, dict):
                data = value.get("data")
                if isinstance(data, list):
                    result[str(key)] = data

    elif isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue

            stream_type = (
                item.get("type")
                or item.get("name")
                or item.get("stream_type")
            )

            data = item.get("data")

            if stream_type and isinstance(data, list):
                result[str(stream_type)] = data

    return result


def numeric_stats(values):
    numbers = []

    for value in values:
        number = as_float(value)
        if number is not None:
            numbers.append(number)

    if not numbers:
        return None

    return {
        "count": len(numbers),
        "min": min(numbers),
        "max": max(numbers),
        "mean": sum(numbers) / len(numbers),
    }


def find_stream(streams, aliases):
    lower_map = {key.lower(): key for key in streams.keys()}

    for alias in aliases:
        real_key = lower_map.get(alias.lower())
        if real_key:
            return real_key, streams[real_key]

    return None, None


def print_streams(payload):
    print("\nTIME-SERIES STREAMS")
    print("=" * 50)

    streams = normalize_streams(payload)

    if not streams:
        print("Could not normalize streams payload.")
        print("Raw preview:")
        print(compact(payload, 2500))
        return

    print("Stream types returned:")
    for key in sorted(streams.keys()):
        print(f"- {key}: {len(streams[key])} value(s)")

    wanted = {
        "heart rate": ("heartrate", "heart_rate", "hr"),
        "speed": ("velocity_smooth", "speed", "velocity"),
        "cadence": ("cadence",),
        "distance": ("distance",),
        "altitude": ("altitude", "elevation"),
        "time": ("time", "elapsed_time", "seconds"),
    }

    print("\nKey stream statistics:")

    for label, aliases in wanted.items():
        key, values = find_stream(streams, aliases)

        if values is None:
            print(f"{label}: not returned")
            continue

        stats = numeric_stats(values)

        if stats is None:
            print(f"{label} ({key}): no numeric values")
            continue

        if label == "speed":
            mean_kmh = stats["mean"] * 3.6
            min_kmh = stats["min"] * 3.6
            max_kmh = stats["max"] * 3.6

            print(
                f"{label} ({key}): "
                f"n={stats['count']}, "
                f"mean={mean_kmh:.2f} km/h "
                f"({format_pace_from_mps(stats['mean'])}), "
                f"min={min_kmh:.2f}, "
                f"max={max_kmh:.2f} km/h"
            )

        elif label == "distance":
            print(
                f"{label} ({key}): "
                f"n={stats['count']}, "
                f"start/min={stats['min']:.1f} m, "
                f"end/max={stats['max']:.1f} m"
            )

        else:
            print(
                f"{label} ({key}): "
                f"n={stats['count']}, "
                f"min={stats['min']:.2f}, "
                f"mean={stats['mean']:.2f}, "
                f"max={stats['max']:.2f}"
            )

        print("  first 12 values:", list(values[:12]))


def main():
    api_key = os.environ.get("INTERVALS_ICU_API_KEY", "").strip()

    if not api_key:
        print("FAIL: INTERVALS_ICU_API_KEY is missing or empty.")
        return 2

    print("Intervals.icu Activity Detail + Streams Test")
    print("=" * 50)
    print("API key: configured (value hidden)")
    print(f"Activity ID: {ACTIVITY_ID}")
    print("READ ONLY")
    print("No Calendar / Discord / lobster_discord.py writes.\n")

    detail = api_get(
        api_key,
        f"{BASE_URL}/activity/{ACTIVITY_ID}",
        "Activity detail",
        params={"intervals": "true"},
    )

    if not isinstance(detail, dict):
        print("FAIL: detail response is not a JSON object.")
        return 3

    print_activity_summary(detail)
    print_hr_zones(detail)
    print_intervals(detail)

    print(f"\nFetching streams for {ACTIVITY_ID} ...")

    streams = api_get(
        api_key,
        f"{BASE_URL}/activity/{ACTIVITY_ID}/streams.json",
        "Streams",
    )

    print_streams(streams)

    print("\n" + "=" * 50)
    print("READ-ONLY DETAIL TEST COMPLETE")
    print("=" * 50)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
