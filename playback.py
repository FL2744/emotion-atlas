"""Text-order playback state, independent of Tk and model inference."""
from dataclasses import dataclass


@dataclass
class Timeline:
    total: int = 0
    position: int | None = None  # None means show the entire plot.
    playing: bool = False

    def reset(self, total=0):
        self.total = max(0, total)
        self.position = None
        self.playing = False

    def play(self):
        if not self.total:
            return False
        if self.position is None or self.position >= self.total:
            self.position = 0
        self.playing = True
        return True

    def pause(self):
        self.playing = False

    def seek(self, position):
        self.pause()
        self.position = min(self.total, max(0, int(position)))

    def advance(self):
        if not self.playing:
            return False
        self.position = min(self.total, (self.position or 0) + 1)
        if self.position >= self.total:
            self.pause()
        return True

    def includes(self, paragraph_id):
        return self.position is None or paragraph_id <= self.position


def revealed_rows(rows, position):
    return sorted((row for row in rows if position is None or row['id'] <= position),
                  key=lambda row: row['id'])


def consecutive_segments(rows):
    """Never draw a path across missing, filtered, or directionless paragraphs."""
    known = sorted((row for row in rows if row['direction'] is not None), key=lambda row: row['id'])
    return [(a, b) for a, b in zip(known, known[1:]) if b['id'] == a['id'] + 1]
