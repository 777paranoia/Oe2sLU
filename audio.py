"""
Copyright (C) 2016-2017 Jonathan Taquet

This file is part of Oe2sSLE (Open e2sSample.all Library Editor).

Oe2sSLE is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Oe2sSLE is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Oe2sSLE.  If not, see <http://www.gnu.org/licenses/>
"""

import wav_tools
import RIFF

try:
    import sounddevice as sd
except Exception:
    sd = None  # audio preview is optional; everything else still works
import numpy as np
import warnings


class Player:
    def __init__(self):
        self.stream = None

    def __del__(self):
        self.pause()

    def pause(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        return self

    def play(self):
        if self.stream and self.stream.stopped:
            self.stream.start()
        return self

class Sound(Player):
    def __init__(self, data, fmt):

        if fmt.formatTag != RIFF.WAVE_fmt_.WAVE_FORMAT_PCM:
            raise Exception()

        if fmt.samplesPerSec < 1000 or fmt.samplesPerSec > 192000:
            data, fmt = wav_tools.wav_resample_preview(data, fmt, 1000, 192000)

        audio_data = np.frombuffer(data, dtype=np.int16).reshape(-1, fmt.channels)
        self._data = audio_data
        self._pos = 0

        def callback(outdata, frames, time, status):
            remaining = len(self._data) - self._pos
            n = min(frames, remaining)
            outdata[:n] = self._data[self._pos:self._pos + n]
            if n < frames:
                outdata[n:] = 0
            self._pos += n

        self.stream = sd.OutputStream(
            samplerate=fmt.samplesPerSec,
            channels=fmt.channels,
            dtype='int16',
            callback=callback,
        ) if sd else None

class LoopWaveSource(Player):
    def __init__(self, data, fmt, esli):

        if fmt.formatTag != RIFF.WAVE_fmt_.WAVE_FORMAT_PCM:
            raise Exception()

        if fmt.samplesPerSec < 1000 or fmt.samplesPerSec > 192000:
            data, fmt = wav_tools.wav_resample_preview(data, fmt, 1000, 192000)

        self._data = data
        self.fmt = fmt
        self.esli = esli
        self._total_offset = 0
        self._offset = esli.OSC_StartPoint_address
        block_align = fmt.blockAlign

        """
        TODO: use esli.playVolume and esli.playLogScale
        """
        def callback(outdata, frames, time, status):
            n_bytes = frames * block_align
            n_read = 0
            buf = bytearray(n_bytes)
            end = self.esli.OSC_StartPoint_address + self.esli.OSC_EndPoint_offset

            while n_read < n_bytes:
                to_read = min(n_bytes - n_read, end - self._offset)
                buf[n_read:n_read + to_read] = self._data[self._offset:self._offset + to_read]
                n_read += to_read
                self._offset += to_read
                if self._offset == end:
                    if self.esli.OSC_LoopStartPoint_offset < self.esli.OSC_EndPoint_offset:
                        self._offset = self.esli.OSC_StartPoint_address + self.esli.OSC_LoopStartPoint_offset
                    else:
                        break

            audio_array = np.frombuffer(bytes(buf), dtype=np.int16).reshape(-1, fmt.channels)
            outdata[:] = audio_array
            self._total_offset += n_read

        self.stream = sd.OutputStream(
            samplerate=fmt.samplesPerSec,
            channels=fmt.channels,
            dtype='int16',
            callback=callback,
        ) if sd else None

class ApplicationPlayer:
    def __init__(self):
        self.player = None

    def play_start(self, sound):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if self.player is not None:
                self.player.pause()
            self.player = sound.play()

    def play_stop(self):
        if self.player is not None:
            self.player.pause()
            self.player = None

def terminate():
    pass  # sounddevice does not require explicit termination

player = ApplicationPlayer()
