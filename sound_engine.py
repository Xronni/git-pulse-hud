#!/usr/bin/env python3
"""
GitPulse HUD — Tactile Sound Engine (High Reliability & Low Latency)
Uses native GStreamer pipeline caching for zero-latency haptic UI audio feedback.
"""

import os
import io
import math
import wave
import struct
import tempfile
import subprocess
import shutil

import gi
try:
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
    HAS_GST = True
except Exception:
    HAS_GST = False

SOUND_DIR = os.path.join(tempfile.gettempdir(), "git_pulse_sounds")


class SoundEngine:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._cache = {}
        self._gst_players = {}
        self._fallback_player = self._detect_fallback_player()
        os.makedirs(SOUND_DIR, exist_ok=True)
        self._preload_sounds()
        self._init_gst_players()

    def _detect_fallback_player(self):
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

    def _init_gst_players(self):
        if not HAS_GST:
            return
        for name, path in self._cache.items():
            try:
                uri = f"file://{os.path.abspath(path)}"
                player = Gst.ElementFactory.make("playbin", f"player-{name}")
                if player:
                    player.set_property("uri", uri)
                    self._gst_players[name] = player
            except Exception as e:
                print(f"[SoundEngine] Error initializing GStreamer player for {name}: {e}")

    def _gen_click(self, sample_rate=44100):
        # Crisp mechanical switch click (25ms)
        duration = 0.025
        n_samples = int(duration * sample_rate)
        frames = []
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-t * 220)
            val = (0.7 * math.sin(2 * math.pi * 1400 * t) + 0.3 * math.sin(2 * math.pi * 2800 * t)) * env
            sample = int(val * 32767 * 0.40)
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
            sample = int(val * 32767 * 0.45)
            frames.append(struct.pack('<h', max(-32768, min(32767, sample))))
        return self._build_wav(b''.join(frames), sample_rate)

    def _gen_commit(self, sample_rate=44100):
        # Satisfying affirmative harmonic chime (140ms)
        duration = 0.14
        n_samples = int(duration * sample_rate)
        frames = []
        freqs = [659.25, 830.61, 987.77]
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-t * 22)
            val = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs) * env
            sample = int(val * 32767 * 0.42)
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
            sample = int(val * 32767 * 0.40)
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
        if not self.enabled:
            return

        # 1. Primary: GStreamer instant cached pipeline
        player = self._gst_players.get(sound_name)
        if player:
            try:
                player.set_state(Gst.State.READY)
                player.set_state(Gst.State.PLAYING)
                return
            except Exception:
                pass

        # 2. Fallback: commandline player
        filepath = self._cache.get(sound_name)
        if filepath and self._fallback_player and os.path.exists(filepath):
            try:
                subprocess.Popen(
                    [self._fallback_player, filepath],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass


if __name__ == "__main__":
    engine = SoundEngine(enabled=True)
    print("Testing reliable GStreamer sound engine:")
    for s in ["click", "pop", "commit", "push", "error"]:
        print(f"Playing {s}...")
        engine.play(s)
    print("Test finished.")
