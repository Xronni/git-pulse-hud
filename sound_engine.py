#!/usr/bin/env python3
"""
GitPulse HUD — Tactile Sound Engine
Uses libcanberra (canberra-gtk-play) with audio stream pre-warming for instant,
zero-drop tactile haptic UI feedback on Linux.
"""

import os
import io
import math
import wave
import struct
import tempfile
import subprocess
import shutil

SOUND_DIR = os.path.join(tempfile.gettempdir(), "git_pulse_sounds_v3")


class SoundEngine:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._cache = {}
        self._player = self._detect_player()
        os.makedirs(SOUND_DIR, exist_ok=True)
        self._preload_sounds()
        self._prewarm_audio()

    def _detect_player(self):
        # Native PipeWire (pw-play) and PulseAudio (paplay) offer direct zero-drop socket playback
        for player in ["pw-play", "paplay", "canberra-gtk-play", "aplay"]:
            if shutil.which(player):
                return player
        return None

    def _generate_wav(self, generator_func, filename):
        filepath = os.path.join(SOUND_DIR, filename)
        if not os.path.exists(filepath):
            data = generator_func()
            with open(filepath, "wb") as f:
                f.write(data)
        return filepath

    def _preload_sounds(self):
        try:
            self._cache["click"] = self._generate_wav(self._gen_click, "click.wav")
            self._cache["pop"] = self._generate_wav(self._gen_pop, "pop.wav")
            self._cache["commit"] = self._generate_wav(self._gen_commit, "commit.wav")
            self._cache["push"] = self._generate_wav(self._gen_push, "push.wav")
            self._cache["error"] = self._generate_wav(self._gen_error, "error.wav")
            self._cache["warmup"] = self._generate_wav(self._gen_warmup, "warmup.wav")
        except Exception as e:
            print(f"[SoundEngine] Preload error: {e}")

    def _prewarm_audio(self):
        """Wakes up the audio daemon (PipeWire / PulseAudio / USB DAC) on startup."""
        if not self._player:
            return
        warmup_file = self._cache.get("warmup")
        if warmup_file and os.path.exists(warmup_file):
            try:
                cmd = ["canberra-gtk-play", "-f", warmup_file] if self._player == "canberra-gtk-play" else [self._player, warmup_file]
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

    def _gen_warmup(self, sample_rate=44100):
        # 40ms of gentle low dither to wake up audio sink & wireless DAC
        duration = 0.040
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            val = math.sin(2 * math.pi * 60 * (i / sample_rate)) * 0.001
            sample = int(val * 32767)
            frames.append(struct.pack('<h', sample))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_click(self, sample_rate=44100):
        # Crisp tactile mechanical switch click (50ms)
        duration = 0.050
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-t * 90)
            val = (0.70 * math.sin(2 * math.pi * 1400 * t) + 0.30 * math.sin(2 * math.pi * 2600 * t)) * env
            sample = int(val * 32767 * 0.55)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_pop(self, sample_rate=44100):
        # Tactile soft pop (55ms)
        duration = 0.055
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            freq = 700 * (1.0 - t / duration * 0.45)
            env = math.sin(math.pi * (t / duration)) ** 1.8
            val = math.sin(2 * math.pi * freq * t) * env
            sample = int(val * 32767 * 0.55)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_commit(self, sample_rate=44100):
        # Affirmative harmonic chime (160ms)
        duration = 0.16
        n_samples = int(duration * sample_rate)
        frames = []
        freqs = [659.25, 830.61, 987.77, 1318.51]  # E5, G#5, B5, E6
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-t * 18)
            val = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs) * env
            sample = int(val * 32767 * 0.55)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_push(self, sample_rate=44100):
        # Ascending swoosh (220ms)
        duration = 0.22
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            part = t / duration
            if part < 0.33:
                freq = 523.25
            elif part < 0.66:
                freq = 659.25
            else:
                freq = 783.99
            env = math.exp(-((t % (duration / 3)) * 20))
            val = math.sin(2 * math.pi * freq * t) * env
            sample = int(val * 32767 * 0.50)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_error(self, sample_rate=44100):
        # Subtle double muted knock (120ms)
        duration = 0.12
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-((t % 0.06) * 45))
            val = math.sin(2 * math.pi * 220 * t) * env
            sample = int(val * 32767 * 0.50)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _build_wav(self, pcm_data, sample_rate):
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        return buf.getvalue()

    def play(self, sound_name):
        if not self.enabled or not self._player:
            return

        filepath = self._cache.get(sound_name)
        if not filepath or not os.path.exists(filepath):
            return

        try:
            cmd = ["canberra-gtk-play", "-f", filepath] if self._player == "canberra-gtk-play" else [self._player, filepath]
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


if __name__ == "__main__":
    import time
    engine = SoundEngine(enabled=True)
    print("Testing pre-warmed instant sound:")
    for s in ["click", "pop", "commit", "push", "error"]:
        print(f"Playing {s}...")
        engine.play(s)
        time.sleep(0.1)
    print("Sound test completed.")
