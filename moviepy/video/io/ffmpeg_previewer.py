"""
On the long term this will implement several methods to make videos
out of VideoClips
"""

import subprocess as sp

import numpy as np
from proglog import proglog

from moviepy.config import FFMPEG_BINARY, FFPLAY_BINARY
from moviepy.tools import cross_platform_popen_params


class FFMPEG_VideoPreviewer:
    """A class for FFMPEG-based (ffplay) video preview.

    Parameters
    ----------

    size : tuple or list
      Size of the output video in pixels (width, height).

    fps : int
      Frames per second in the output video file.

    pixel_format : str
      Pixel format for the output video file, ``rgb24`` for normal video, ``rgba`` 
      if video with mask.
    """

    def __init__(
        self,
        size,
        fps,
        pixel_format,
    ):
        # order is important
        cmd = [
            FFPLAY_BINARY,
            "-autoexit", # If you dont precise, ffplay dont stop at end
            "-f",
            "rawvideo",
            "-pixel_format",
            pixel_format,
            "-video_size",
            "%dx%d" % (size[0], size[1]),
            "-framerate",
            "%.02f" % fps,
            "-",
        ]

        popen_params = cross_platform_popen_params(
            {"stdout": sp.DEVNULL, "stderr": sp.STDOUT, "stdin": sp.PIPE}
        )

        self.proc = sp.Popen(cmd, **popen_params)

    def show_frame(self, img_array):
        """Writes one frame in the file."""
        try:
            self.proc.stdin.write(img_array.tobytes())
        except IOError as err:
            _, ffplay_error = self.proc.communicate()
            if ffplay_error is not None:
                ffplay_error = ffplay_error.decode()

            error = (
                f"{err}\n\nMoviePy error: FFPALY encountered the following error while "
                f"previewing clip :\n\n {ffplay_error}"
            )

            raise IOError(error)

    def close(self):
        """Closes the writer, terminating the subprocess if is still alive."""
        if self.proc:
            self.proc.stdin.close()
            if self.proc.stderr is not None:
                self.proc.stderr.close()
            self.proc.wait()

            self.proc = None

    # Support the Context Manager protocol, to ensure that resources are cleaned up.

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def ffmpeg_preview_video(
    clip,
    fps,
    pixel_format=None,
    audio_flag=None,
    video_flag=None
):
    """Preview the clip using ffplay. See VideoClip.preview for details
    on the parameters.

    Parameters
    ----------

    clip : VideoClip
      The clip to preview

    fps : int
      Number of frames per seconds in the displayed video.

    pixel_format : str, optional
      Pixel format for the output video file, ``rgb24`` for normal video, ``rgba`` 
      if video with mask.

    audio_flag : Thread.Event, optional
      A thread event that video will wait for. If not provided we ignore audio

    video_flag : Thread.Event, optional
      A thread event that video will set after first frame has been shown. If not
      provided, we simply ignore
    """
    if not pixel_format:
        pixel_format = "rgba" if clip.mask is not None else "rgb24"


    with FFMPEG_VideoPreviewer(
        clip.size,
        fps,
        pixel_format
    ) as previewer:
        first_frame = True
        for t, frame in clip.iter_frames(
            with_times=True, fps=fps, dtype="uint8"
        ):
            if clip.mask is not None:
                mask = 255 * clip.mask.get_frame(t)
                if mask.dtype != "uint8":
                    mask = mask.astype("uint8")
                frame = np.dstack([frame, mask])

            previewer.show_frame(frame)

            # After first frame is shown, if we have audio/video flag, set video ready and wait for audio
            if first_frame :
                first_frame = False

                if video_flag :
                    video_flag.set()  # say to the audio: video is ready

                if audio_flag :
                    audio_flag.wait()  # wait for the audio to be ready

            
