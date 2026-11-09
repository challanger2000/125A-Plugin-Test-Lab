"""Offline P100 tests; never execute proprietary SoundFonts or claim hardware parity."""
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_sf2_reference as p


def chunk(tag, data):
    return tag + struct.pack('<I', len(data)) + data + (b'\0' if len(data) & 1 else b'')


def make_sf2(presets=((0, 0), (0, 9)), terminal=True):
    records = bytearray()
    for index, (bank, program) in enumerate(presets):
        records += struct.pack('<20sHHHIII', ('Test%d' % index).encode(),
                               program, bank, index, 0, 0, 0)
    records += struct.pack('<20sHHHIII', b'EOP' if terminal else b'END', 0, 0,
                           len(presets), 0, 0, 0)
    body = chunk(b'LIST', b'pdta' + chunk(b'phdr', records))
    return b'RIFF' + struct.pack('<I', len(body) + 4) + b'sfbk' + body


def make_wav(path, value=3200, frames=p.RATE * 3, early=False):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(p.RATE)
        if early:
            w.writeframes(struct.pack('<hh', value, -value) * frames)
        else:
            pre = int(p.RATE * .25)
            w.writeframes(b'\0\0\0\0' * pre +
                          struct.pack('<hh', value, -value) * (frames - pre))


class SoundFontReferenceTests(unittest.TestCase):
    def test_inventory_exact_phdr_no_fill_128(self):
        with tempfile.TemporaryDirectory() as d:
            sf = Path(d) / 'x.sf2'
            sf.write_bytes(make_sf2())
            rows = p.sf2_presets(sf)
            self.assertEqual([(r['bank'], r['program']) for r in rows], [(0, 0), (0, 9)])
            self.assertEqual(len(rows), 2)

    def test_bad_sf2_must_fail(self):
        with tempfile.TemporaryDirectory() as d:
            sf = Path(d) / 'x.sf2'
            for data in (b'garbage', make_sf2(terminal=False), make_sf2()[:-2],
                         make_sf2(((0, 0), (0, 0)))):
                sf.write_bytes(data)
                with self.assertRaises(ValueError):
                    p.sf2_presets(sf)

    def test_midi_event_timing_and_program(self):
        m = p.midi_bytes(9, 60, 100)
        self.assertTrue(m.startswith(b'MThd\0\0\0\x06\0\0\0\x01\x01\xe0MTrk'))
        self.assertEqual(struct.unpack_from('>I', m, 18)[0], len(m) - 22)
        self.assertIn(bytes((0xc0, 9)), m)
        self.assertIn(p.vlq(240) + b'\x90\x3c\x64', m)
        self.assertIn(p.vlq(960) + b'\x80\x3c\x00', m)
        self.assertIn(p.vlq(960) + b'\xff\x2f\x00', m)
        with self.assertRaises(ValueError):
            p.midi_bytes(128, 60, 100)
        with self.assertRaises(ValueError):
            p.midi_bytes(1, 60, 0)

    def test_fx_and_version_are_explicit(self):
        a = p.render_command(Path('fluid.exe'), Path('bank.sf2'), Path('a.mid'), Path('a.wav'))
        self.assertIn('-C', a)
        self.assertEqual(a[a.index('-C') + 1], '0')
        self.assertEqual(a[a.index('-R') + 1], '0')
        self.assertEqual(a[a.index('-r') + 1], '44100')
        self.assertEqual(p.version_triplet('FluidSynth runtime version 2.4.5'), (2, 4, 5))
        with self.assertRaises(ValueError):
            p.version_triplet('unknown')

    def test_audio_negative_controls(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'valid.wav'
            make_wav(f)
            a = p.read_audio(f)
            x = p.audio_metrics(a)
            self.assertLess(x['pre_note_rms'], .00001)
            self.assertGreater(x['sustain_rms'], .01)
            bad = Path(d) / 'bad.wav'
            make_wav(bad, early=True)
            self.assertGreater(p.audio_metrics(p.read_audio(bad))['pre_note_rms'], .01)
            with self.assertRaises(ValueError):
                p.read_audio(Path(d) / 'missing.wav')
            # Intentionally mismatched lengths, formats and malformed header
            f.write_bytes(b'RIFF' + b'X' * 32)
            with self.assertRaises((ValueError, EOFError, wave.Error)):
                p.read_audio(f)

    def test_compatibility_is_observation_not_hardware_pass(self):
        with tempfile.TemporaryDirectory() as d:
            pth = Path(d) / 'reference.wav'
            make_wav(pth)
            x = p.read_audio(pth)
            result = p.compare_metrics(x, x)
            self.assertEqual(result['status'], 'OBSERVATION_ONLY')
            self.assertEqual(result['rms_delta_db'], 0)
            self.assertNotIn('PASS', json.dumps(result))


if __name__ == '__main__':
    unittest.main()