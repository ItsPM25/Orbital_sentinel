"""Draws the project schedule (report section 3.2) from real dates.

Exact: end dates of Exp 1/4/5 (dates on those documents) and every phase end
(git commit date). Approximate: start dates and the Exp 3 / Exp 9 dates.
"""

from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "img" / "gantt_schedule.png"

ROWS = [
    ("Analysis and design (lab experiments)", None, None, None),
    ("SRS and process model (Exp 1)", date(2026, 7, 7), date(2026, 7, 14), "done"),
    ("DFD levels 0-2 (Exp 3)", date(2026, 7, 20), date(2026, 7, 31), "done"),
    ("ER diagram (Exp 4)", date(2026, 7, 28), date(2026, 8, 4), "done"),
    ("State transition diagram (Exp 5)", date(2026, 8, 12), date(2026, 8, 19), "done"),
    ("Test skeleton, Selenium + JMeter (Exp 9)", date(2026, 9, 20), date(2026, 9, 27), "done"),
    ("Increments (build)", None, None, None),
    ("Phase 0 Foundation", date(2026, 10, 4), date(2026, 10, 5), "done"),
    ("Phase 1 Spike (Increment 0)", date(2026, 10, 5), date(2026, 10, 6), "done"),
    ("Phase 2 Ingest + detect (Inc 1)", date(2026, 10, 6), date(2026, 10, 11), "done"),
    ("81-channel training run", date(2026, 10, 11), date(2026, 10, 19), "done"),
    ("Phase 3 Explain and prioritise (Inc 2)", date(2026, 10, 9), date(2026, 10, 11), "done"),
    ("Phase 4 Dashboard (Inc 3a)", date(2026, 10, 10), date(2026, 10, 11), "done"),
    ("Phase 5 Globe (Inc 3b)", date(2026, 10, 10), date(2026, 10, 12), "done"),
    ("Performance fixes + UI redesign", date(2026, 10, 19), date(2026, 10, 20), "done"),
    ("Jira sprints (final increment)", None, None, None),
    ("Sprint 1 Evaluate and test", date(2026, 10, 22), date(2026, 10, 23), "active"),
    ("Sprint 2 Release and report", date(2026, 10, 22), date(2026, 10, 24), "planned"),
]

START, END = date(2026, 7, 1), date(2026, 10, 31)
LABEL_W, DAY_W, ROW_H, TOP = 330, 9, 26, 60
COLORS = {"done": (70, 110, 160), "active": (205, 120, 40), "planned": (170, 170, 170)}


def font(size):
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    days = (END - START).days + 1
    w = LABEL_W + days * DAY_W + 20
    h = TOP + ROW_H * len(ROWS) + 40
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    f, fb, fs = font(13), font(14), font(11)

    # Month grid.
    m = START
    while m <= END:
        x = LABEL_W + (m - START).days * DAY_W
        d.line([(x, TOP - 10), (x, h - 30)], fill=(220, 220, 220))
        d.text((x + 4, TOP - 30), m.strftime("%b %Y"), fill=(60, 60, 60), font=fb)
        m = date(m.year + (m.month // 12), m.month % 12 + 1, 1)

    for i, (label, s, e, kind) in enumerate(ROWS):
        y = TOP + i * ROW_H
        if s is None:
            d.text((8, y + 5), label, fill=(0, 0, 0), font=fb)
            d.line([(8, y + ROW_H - 2), (w - 10, y + ROW_H - 2)], fill=(200, 200, 200))
            continue
        d.text((20, y + 6), label, fill=(30, 30, 30), font=f)
        x0 = LABEL_W + (s - START).days * DAY_W
        x1 = LABEL_W + ((e - START).days + 1) * DAY_W
        d.rectangle([x0, y + 6, max(x1, x0 + 4), y + ROW_H - 6], fill=COLORS[kind])

    today = date(2026, 10, 22)
    x = LABEL_W + (today - START).days * DAY_W
    d.line([(x, TOP - 10), (x, h - 30)], fill=(200, 40, 40), width=2)
    d.text((x - 60, h - 26), "22 Oct 2026", fill=(200, 40, 40), font=fs)
    d.text((8, h - 26), "Blue: done   Orange: in progress   Grey: planned", fill=(90, 90, 90), font=fs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print("wrote", OUT, img.size)


if __name__ == "__main__":
    main()
