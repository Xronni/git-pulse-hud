#!/usr/bin/env python3
"""
GitPulse HUD — Tactile Sound Engine
Generates and plays satisfying, zero-dependency tactile haptic sounds
(mechanical clicks, commit chimes, push swooshes) using pure Python wave synthesis.
"""

import os
import io
import math
import wave
import struct
import tempfile
import subprocess
import threading
import shutil

SOUND_DIR = os.path.join(tempfile.gettempdir(), "git_pulse_sounds")


class SoundEngine:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._cache = {}
        self._player = self._detect_player()
        os.makedirs(SOUND_DIR, exist_ok=True)
        self._preload_sounds()

    def _detect_player(self):
        for player in ["pw-play", "paplay", "aplay"]:
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
        except Exception as e:
            print(f"[SoundEngine] Error preloading sounds: {e}")

    def _gen_click(self, sample_rate=44100):
        # Crisp mechanical switch click (25ms)
        duration = 0.025
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-t * 220)
            val = (0.7 * math.sin(2 * math.pi * 1400 * t) + 0.3 * math.sin(2 * math.pi * 2800 * t)) * env
            sample = int(val * 32767 * 0.35)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_pop(self, sample_rate=44100):
        # Soft pop / unstage click (35ms)
        duration = 0.035
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            freq = 600 * (1.0 - t / duration * 0.5)
            env = math.sin(math.pi * (t / duration)) ** 2
            val = math.sin(2 * math.pi * freq * t) * env
            sample = int(val * 32767 * 0.4)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_commit(self, sample_rate=44100):
        # Satisfying affirmative harmonic chime (140ms)
        duration = 0.14
        n_samples = int(duration * sample_rate)
        frames = []
        # Chords: E5 (659Hz) + G#5 (830Hz) + B5 (987Hz)
        freqs = [659.25, 830.61, 987.77]
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-t * 22)
            val = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs) * env
            sample = int(val * 32767 * 0.38)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_push(self, sample_rate=44100):
        # Ascending triple tone celebration swoosh (200ms)
        duration = 0.20
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            part = t / duration
            if part < 0.33:
                freq = 523.25  # C5
            elif part < 0.66:
                freq = 659.25  # E5
            else:
                freq = 783.99  # G5
            env = math.exp(-((t % (duration / 3)) * 25))
            val = math.sin(2 * math.pi * freq * t) * env
            sample = int(val * 32767 * 0.35)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_error(self, sample_rate=44100):
        # Double low bump (80ms)
        duration = 0.08
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-t * 35)
            val = math.sin(2 * math.pi * 180 * t) * env
            sample = int(val * 32767 * 0.4)
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

        def _worker():
            try:
                subprocess.run(
                    [self._player, filepath],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()


if __name__ == "__main__":
    engine = SoundEngine(enabled=True)
    print(f"Sound engine initialized with player: {engine._player}")
    for sound in ["click", "pop", "commit", "push", "error"]:
        print(f"Testing sound: {sound}")
        engine.play(sound)
    print("Sound engine test completed.")
