from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.audio import AudioCue
from core.events import EventKind, SearchEvent
from core.profiles import TimingConfig


@dataclass(slots=True)
class TimedEvent:
    event: SearchEvent
    frame_index: int
    time_seconds: float
    sound_type: str | None = None


@dataclass(slots=True)
class Timeline:
    fps: int
    frame_count: int
    timed_events: list[TimedEvent]
    audio_cues: list[AudioCue]
    timing: TimingConfig

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.fps if self.fps > 0 else 0.0


class TimelineBuilder:
    """Convert an event sequence into shared frame and audio timing data."""

    def __init__(
        self,
        timing: TimingConfig | None = None,
        *,
        fps: int | None = None,
        event_duration_seconds: float | None = None,
        initial_hold_seconds: float | None = None,
        final_hold_seconds: float | None = None,
        failure_hold_seconds: float | None = None,
    ) -> None:
        base = timing or TimingConfig()
        self.timing = TimingConfig(
            fps=fps or base.fps,
            event_duration_seconds=event_duration_seconds if event_duration_seconds is not None else base.event_duration_seconds,
            initial_hold_seconds=initial_hold_seconds if initial_hold_seconds is not None else base.initial_hold_seconds,
            final_hold_seconds=final_hold_seconds if final_hold_seconds is not None else base.final_hold_seconds,
            failure_hold_seconds=failure_hold_seconds if failure_hold_seconds is not None else base.failure_hold_seconds,
        )

    def build(self, events: Iterable[SearchEvent]) -> Timeline:
        timed_events: list[TimedEvent] = []
        audio_cues: list[AudioCue] = []
        event_list = list(events)
        current_frame = self._seconds_to_frames(self.timing.initial_hold_seconds)
        base_advance = max(1, self._seconds_to_frames(self.timing.event_duration_seconds))
        frontier_counter = 0

        for event in event_list:
            frame_index = current_frame
            time_seconds = frame_index / self.timing.fps
            sound_type = self._map_sound_type(event)
            timed_event = TimedEvent(
                event=event,
                frame_index=frame_index,
                time_seconds=time_seconds,
                sound_type=sound_type,
            )
            timed_events.append(timed_event)
            if sound_type is not None:
                audio_cues.append(AudioCue(time_seconds=time_seconds, sound_type=sound_type))

            advance = base_advance
            if event.kind in {EventKind.START, EventKind.FINISH}:
                advance = 0
            elif event.kind == EventKind.FRONTIER:
                frontier_counter += 1
                advance = base_advance if frontier_counter % 3 == 0 else 0

            current_frame += advance

        is_failure = any(event.kind == EventKind.NO_PATH for event in event_list)
        tail_seconds = self.timing.failure_hold_seconds if is_failure else self.timing.final_hold_seconds
        frame_count = max(1, current_frame + self._seconds_to_frames(tail_seconds))
        return Timeline(
            fps=self.timing.fps,
            frame_count=frame_count,
            timed_events=timed_events,
            audio_cues=audio_cues,
            timing=self.timing,
        )

    def _seconds_to_frames(self, seconds: float) -> int:
        if seconds <= 0:
            return 0
        return max(1, int(round(seconds * self.timing.fps)))

    @staticmethod
    def _map_sound_type(event: SearchEvent) -> str | None:
        if event.kind == EventKind.FRONTIER:
            distance = int(event.details.get("distance", 0))
            return "frontier_push" if distance % 3 == 0 else None
        if event.kind == EventKind.VISITED:
            distance = int(event.details.get("distance", 0))
            return "node_visit" if distance % 2 == 0 else None
        if event.kind == EventKind.EXPAND:
            return "node_expand"
        if event.kind == EventKind.GOAL:
            return "goal_reached"
        if event.kind == EventKind.PATH:
            path_index = int(event.details.get("path_index", 0))
            return "final_path" if path_index % 2 == 0 else None
        return None
