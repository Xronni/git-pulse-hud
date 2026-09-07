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

SOUND_DIR = os.path.join(tempfile.gettempdir(), "git_pulse_sounds")


class SoundEngine:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._cache = {}
        self._player = self._detect_player()
        os.makedirs(SOUND_DIR, exist_ok=True)
        self._preload_sounds()
        self._prewarm_audio()

    def _detect_player(self):
        # canberra-gtk-play is the official GNOME event sound utility, lowest latency & zero-drop
        for player in ["canberra-gtk-play", "pw-play", "paplay", "aplay"]:
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
        """Wakes up the audio daemon (PipeWire / PulseAudio) silently on startup."""
        if not self._player:
            return
        warmup_file = self._cache.get("warmup")
        if warmup_file and os.path.exists(warmup_file):
            try:
                if self._player == "canberra-gtk-play":
                    subprocess.Popen(
                        ["canberra-gtk-play", "-f", warmup_file],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    subprocess.Popen(
                        [self._player, warmup_file],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
            except Exception:
                pass

    def _gen_warmup(self, sample_rate=44100):
        # 5ms of near-silence to open sink immediately
        frames = [struct.pack('<h', 0) for _ in range(int(0.005 * sample_rate))]
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_click(self, sample_rate=44100):
        # Crisp tactile mechanical click (30ms)
        duration = 0.030
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-t * 200)
            val = (0.75 * math.sin(2 * math.pi * 1400 * t) + 0.25 * math.sin(2 * math.pi * 2600 * t)) * env
            sample = int(val * 32767 * 0.45)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_pop(self, sample_rate=44100):
        # Soft pop (35ms)
        duration = 0.035
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            freq = 650 * (1.0 - t / duration * 0.5)
            env = math.sin(math.pi * (t / duration)) ** 2
            val = math.sin(2 * math.pi * freq * t) * env
            sample = int(val * 32767 * 0.45)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_commit(self, sample_rate=44100):
        # Affirmative harmonic chime (140ms)
        duration = 0.14
        n_samples = int(duration * sample_rate)
        frames = []
        freqs = [659.25, 830.61, 987.77]
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-t * 22)
            val = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs) * env
            sample = int(val * 32767 * 0.45)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_push(self, sample_rate=44100):
        # Ascending swoosh (200ms)
        duration = 0.20
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
            env = math.exp(-((t % (duration / 3)) * 25))
            val = math.sin(2 * math.pi * freq * t) * env
            sample = int(val * 32767 * 0.42)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_error(self, sample_rate=44100):
        duration = 0.08
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-t * 35)
            val = math.sin(2 * math.pi * 180 * t) * env
            sample = int(val * 32767 * 0.45)
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
            if self._player == "canberra-gtk-play":
                subprocess.Popen(
                    ["canberra-gtk-play", "-f", filepath],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(
                    [self._player, filepath],
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
