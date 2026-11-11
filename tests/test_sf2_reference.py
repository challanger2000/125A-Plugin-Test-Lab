"""Offline P100 tests; never execute proprietary SoundFonts or claim hardware parity."""
import io
import copy
import hashlib
from types import SimpleNamespace
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


    def test_awe_pcm_manifest_requires_current_build_and_matching_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sf = root / 'bank.sf2'
            sf.write_bytes(make_sf2())
            wavdir = root / 'awe'
            wavdir.mkdir()
            mod = root / '125A AWE Synthesizer.vst3'
            mod.write_bytes(b'MZ' + b'actual-build-test-fixture')
            label = 'b000-p009-n060-v100'
            wav = wavdir / (label + '.wav')
            make_wav(wav)
            midi = root / (label + '.mid')
            midi.write_bytes(p.midi_bytes(9, 60, 100))
            expect = 'f308b71a4765e2402856e7be24105420542e37a1'
            manifest = {
                'schema': '125a-awe-sf2-render-v1',
                'source_kind': 'PACKAGED_WINDOWS_VST3_NATIVE_RENDER',
                'source_commit': expect,
                'module_sha256': p.digest(mod),
                'sf2_sha256': p.digest(sf),
                'sample_rate': 44100, 'fx': 'CHORUS_OFF_REVERB_OFF',
                'bank_mode': 'EXPLICIT_SF2_NO_ROM_FALLBACK',
                'midi_channel': 0, 'cc7': 100, 'cc10': 64,
                'midi_contract': {'ppq': p.PPQ, 'bpm': 120, 'on_tick': p.ON_TICKS,
                                  'off_tick': p.OFF_TICKS, 'end_tick': p.END_TICKS,
                                  'note': 60, 'velocity': 100},
                'cases': {label: {'midi_sha256': p.digest(midi),
                                  'wav_sha256': p.digest(wav)}},
            }
            mp = root / 'awe-manifest.json'
            args = SimpleNamespace(awe_dir=wavdir, awe_manifest=mp,
                                   awe_binary=mod, expected_awe_commit=expect,
                                   note=60, velocity=100)
            rows = p.sf2_presets(sf)
            def check(model):
                mp.write_text(json.dumps(model))
                return p.verify_awe_manifest(args, p.digest(sf), rows)
            self.assertEqual(check(manifest)['source_commit'], expect)
            self.assertEqual(p.verify_awe_case(manifest, label, midi, wav)['frames'], 132300)
            # Every one of these is a real negative provenance/contract mutation.
            for field, bad in (
                    ('source_commit', 'a' * 40),
                    ('source_kind', 'SYNTHETIC'),
                    ('module_sha256', 'f' * 64),
                    ('sf2_sha256', 'f' * 64),
                    ('sample_rate', 48000),
                    ('fx', 'WET'),
                    ('bank_mode', 'MAY_FALLBACK_TO_ROM'),
                    ('midi_channel', 9),
                    ('cc7', 127),
                    ('cc10', 0)):
                mutated = copy.deepcopy(manifest)
                mutated[field] = bad
                with self.subTest(field=field), self.assertRaises(ValueError):
                    check(mutated)
            for field, bad in (('note', 61), ('velocity', 20), ('on_tick', 0)):
                mutated = copy.deepcopy(manifest)
                mutated['midi_contract'][field] = bad
                with self.subTest(field=field), self.assertRaises(ValueError):
                    check(mutated)
            mutated = copy.deepcopy(manifest)
            mutated['cases']['b000-p063-n060-v100'] = mutated['cases'].pop(label)
            with self.assertRaises(ValueError):
                check(mutated)
            self.assertEqual(check(manifest)['source_commit'], expect)
            midi.write_bytes(p.midi_bytes(8, 60, 100))
            with self.assertRaisesRegex(ValueError, 'MIDI fingerprint'):
                p.verify_awe_case(manifest, label, midi, wav)
            midi.write_bytes(p.midi_bytes(9, 60, 100))
            with self.assertRaisesRegex(ValueError, 'no independently pinned'):
                p.verify_awe_case({**manifest, 'cases': {}}, label, midi, wav)
            wav.write_bytes(wav.read_bytes()[:-4] + b'nope')
            with self.assertRaisesRegex(ValueError, 'PCM fingerprint'):
                p.verify_awe_case(manifest, label, midi, wav)


    def test_genuine_redistributable_synthetic_sf2_structure(self):
        from make_p100_valid_sf2 import generate
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'real-fixture.sf2'
            generate(path)
            data = path.read_bytes()
            self.assertGreater(len(data), 85000)
            self.assertLess(len(data), 95000)
            self.assertIn(b'smpl', data)
            self.assertEqual([(z['bank'], z['program'])
                              for z in p.sf2_presets(path)], [(0, 0)])
            original = p.digest(path)
            generate(path)
            self.assertEqual(p.digest(path), original)


    def test_awe_provenance_incomplete_inputs_fail_closed(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as d:
            root = Path(d)
            args = SimpleNamespace(awe_dir=root, awe_manifest=None,
                                   awe_binary=None, expected_awe_commit=None,
                                   note=60, velocity=100)
            with self.assertRaisesRegex(ValueError, 'requires'):
                p.verify_awe_manifest(args, 'f' * 64, [])
            args.awe_dir = None
            self.assertIsNone(p.verify_awe_manifest(args, 'f' * 64, []))
            args.expected_awe_commit = 'not-a-sha'
            with self.assertRaisesRegex(ValueError, 'requires'):
                p.verify_awe_manifest(args, 'f' * 64, [])


if __name__ == '__main__':
    unittest.main()