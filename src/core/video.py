from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Sequence

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - import failure depends on environment
    cv2 = None


class VideoWriter:
    """A minimal video-export wrapper for the scaffold stage."""

    def __init__(self, fps: int = 30) -> None:
        self.fps = fps

    def prepare_output_path(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path

    def ffmpeg_available(self) -> bool:
        return shutil.which("ffmpeg") is not None

    def build_ffmpeg_command(
        self,
        frame_pattern: str,
        output_path: Path,
        *,
        audio_path: Path | None = None,
        overwrite: bool = True,
        crf: int = 18,
        preset: str = "medium",
        video_codec: str = "libx264",
        pixel_format: str = "yuv420p",
        audio_codec: str = "aac",
        audio_bitrate: str = "192k",
    ) -> list[str]:
        output_path = self.prepare_output_path(output_path)
        command = [
            "ffmpeg",
            "-y" if overwrite else "-n",
            "-framerate",
            str(self.fps),
            "-i",
            frame_pattern,
        ]

        if audio_path is not None:
            command.extend(["-i", str(audio_path)])

        command.extend(
            [
                "-c:v",
                video_codec,
                "-preset",
                preset,
                "-crf",
                str(crf),
                "-pix_fmt",
                pixel_format,
                "-movflags",
                "+faststart",
                "-r",
                str(self.fps),
            ]
        )

        if audio_path is not None:
            command.extend(["-c:a", audio_codec, "-b:a", audio_bitrate, "-shortest"])
        else:
            command.append("-an")

        command.append(str(output_path))
        return command

    def mux_png_sequence_to_mp4(
        self,
        frame_pattern: str,
        output_path: Path,
        *,
        audio_path: Path | None = None,
        overwrite: bool = True,
        crf: int = 18,
        preset: str = "medium",
        video_codec: str = "libx264",
        pixel_format: str = "yuv420p",
        audio_codec: str = "aac",
        audio_bitrate: str = "192k",
    ) -> Path:
        if not self.ffmpeg_available():
            raise FileNotFoundError(
                "FFmpeg was not found on PATH. Install FFmpeg for Windows and verify that 'ffmpeg -version' works in PowerShell."
            )

        command = self.build_ffmpeg_command(
            frame_pattern,
            output_path,
            audio_path=audio_path,
            overwrite=overwrite,
            crf=crf,
            preset=preset,
            video_codec=video_codec,
            pixel_format=pixel_format,
            audio_codec=audio_codec,
            audio_bitrate=audio_bitrate,
        )

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            details = exc.stderr.strip() or exc.stdout.strip() or "Unknown FFmpeg error"
            raise RuntimeError(f"FFmpeg export failed: {details}") from exc

        return output_path

    def write_video(self, frames: Sequence[np.ndarray], output_path: Path) -> Path:
        """Write RGB numpy frames to an MP4 file using OpenCV."""

        if not frames:
            raise ValueError("frames must not be empty")
        if cv2 is None:
            raise RuntimeError("OpenCV is not available in the current environment")

        output_path = self.prepare_output_path(output_path)
        height, width = frames[0].shape[:2]
        writer = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            self.fps,
            (width, height),
        )

        if not writer.isOpened():
            raise RuntimeError("Video writer could not be opened for the target output path")

        try:
            for frame in frames:
                if frame.shape[:2] != (height, width):
                    raise ValueError("all frames must share the same dimensions")
                writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        finally:
            writer.release()

        return output_path
