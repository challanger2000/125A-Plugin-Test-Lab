#!/usr/bin/env python3
"""P100: read SoundFont preset inventory and optionally render *FluidSynth* dry references.

Never treats FluidSynth as original EMU8000 hardware or as a fidelity PASS.
Only bank-zero melodic instruments are rendered in v1; other banks stay NOT_RUN.
No SF2, ROM or WAV is included with the public test runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys
import wave

RATE = 44100
PPQ = 480
ON_TICKS = 240                 # 250 ms at 120 BPM
OFF_TICKS = 1200               # 1250 ms
END_TICKS = 2160               # 2250 ms including 1000 ms after note-off
MAX_SF2_BYTES = 512 * 1024 * 1024
MAX_WAV_BYTES = 16 * 1024 * 1024
VERSION_MIN = (2, 4, 5)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _riff_chunks(data: bytes, start: int, stop: int):
    offset = start
    while offset + 8 <= stop:
        tag = data[offset:offset + 4]
        length = struct.unpack_from('<I', data, offset + 4)[0]
        body = offset + 8
        end = body + length
        if end > stop:
            raise ValueError('truncated RIFF chunk')
        yield tag, body, end
        offset = end + (length & 1)
    if offset != stop:
        raise ValueError('invalid RIFF padding or trailing bytes')


def sf2_presets(path: Path) -> list[dict]:
    """Parse only sfbk/pdta/phdr: real presets, never fill to MIDI 128."""
    size = path.stat().st_size
    if not 24 <= size <= MAX_SF2_BYTES:
        raise ValueError('SF2 file size out of bounds')
    data = path.read_bytes()
    if data[:4] != b'RIFF' or data[8:12] != b'sfbk':
        raise ValueError('not a RIFF sfbk SoundFont')
    declared = struct.unpack_from('<I', data, 4)[0]
    if declared != len(data) - 8:
        raise ValueError('RIFF byte count mismatch')
    found = []
    for tag, body, end in _riff_chunks(data, 12, len(data)):
        if tag != b'LIST' or end - body < 4 or data[body:body + 4] != b'pdta':
            continue
        for subtag, first, last in _riff_chunks(data, body + 4, end):
            if subtag == b'phdr':
                found.append(data[first:last])
    if len(found) != 1 or len(found[0]) < 76 or len(found[0]) % 38:
        raise ValueError('missing, duplicated or invalid phdr table')
    records = found[0]
    rows = []
    for offset in range(0, len(records), 38):
        name, program, bank, bag_index, _lib, _genre, _morph = struct.unpack_from(
            '<20sHHHIII', records, offset)
        label = name.split(b'\0', 1)[0].decode('latin-1').strip()
        rows.append({'name': label, 'program': program, 'bank': bank,
                     'bag_index': bag_index})
    if rows[-1]['name'] != 'EOP':
        raise ValueError('missing terminal EOP preset')
    presets = rows[:-1]
    if not presets:
        raise ValueError('no presets in phdr')
    seen = set()
    previous_bag = -1
    for item in rows:
        if item['bag_index'] < previous_bag:
            raise ValueError('descending preset bag index')
        previous_bag = item['bag_index']
    for item in presets:
        key = (item['bank'], item['program'])
        if key in seen:
            raise ValueError('duplicate SF2 bank/program address')
        seen.add(key)
        if not 0 <= item['program'] <= 127:
            raise ValueError('SF2 program outside MIDI 0-127')
    for item in presets:
        del item['bag_index']
    return presets


def vlq(n: int) -> bytes:
    if not 0 <= n < 0x10000000:
        raise ValueError('MIDI delta time out of bounds')
    result = [n & 127]
    n >>= 7
    while n:
        result.insert(0, (n & 127) | 128)
        n >>= 7
    return bytes(result)


def midi_bytes(program: int, note: int, velocity: int) -> bytes:
    if any(not 0 <= v <= 127 for v in (program, note)) or not 1 <= velocity <= 127:
        raise ValueError('invalid MIDI note, velocity or program')
    # SMF format 0; 120 BPM; bank 0, ch 1, deterministic note-on/off and postroll.
    events = [
        (0, b'\xff\x51\x03\x07\xa1\x20'),
        (0, b'\xb0\x00\x00'), (0, b'\xb0\x20\x00'),
        (0, b'\xb0\x07\x64'), (0, b'\xb0\x0a\x40'),
        (0, bytes((0xc0, program))),
        (ON_TICKS, bytes((0x90, note, velocity))),
        (OFF_TICKS, bytes((0x80, note, 0))),
        (END_TICKS, b'\xff\x2f\x00'),
    ]
    stream = bytearray()
    elapsed = 0
    for absolute, message in events:
        stream.extend(vlq(absolute - elapsed))
        stream.extend(message)
        elapsed = absolute
    return b'MThd' + struct.pack('>IHHH', 6, 0, 1, PPQ) + b'MTrk' + struct.pack('>I', len(stream)) + stream


def version_triplet(output: str) -> tuple[int, int, int]:
    m = re.search(r'(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)', output)
    if not m:
        raise ValueError('could not establish FluidSynth version')
    return tuple(map(int, m.groups()))


def render_command(exe: Path, sf2: Path, midi: Path, wav: Path) -> list[str]:
    # Both FX modules disabled explicitly: 0% native AWE production sends are dry.
    return [str(exe), '-i', '-n', '-C', '0', '-R', '0', '-r', str(RATE),
            '-g', '0.2', '-T', 'wav', '-O', 's16', '-F', str(wav),
            str(sf2), str(midi)]


def read_audio(path: Path) -> dict:
    if not path.is_file() or not 44 <= path.stat().st_size <= MAX_WAV_BYTES:
        raise ValueError('WAV missing or size out of bounds')
    with wave.open(str(path), 'rb') as fh:
        nch, rate, width, count = (fh.getnchannels(), fh.getframerate(),
                                   fh.getsampwidth(), fh.getnframes())
        if fh.getcomptype() != 'NONE' or nch != 2 or rate != RATE or width not in (2, 3):
            raise ValueError('reference WAV must be stereo, PCM16/24, 44100 Hz')
        if not RATE // 2 <= count <= RATE * 5:
            raise ValueError('reference WAV duration invalid')
        raw = fh.readframes(count)
    if len(raw) != count * nch * width:
        raise ValueError('truncated audio frames')
    vals = [int.from_bytes(raw[i:i + width], 'little', signed=True)
            for i in range(0, len(raw), width)]
    scale = float(1 << (8 * width - 1))
    left = [v / scale for v in vals[0::2]]
    right = [v / scale for v in vals[1::2]]
    return {'frames': count, 'channels': [left, right], 'sha256': digest(path),
            'bits': 8 * width}


def _window_rms(samples: list[float], start_seconds: float, stop_seconds: float) -> float:
    first = max(0, int(start_seconds * RATE))
    last = min(len(samples), int(stop_seconds * RATE))
    if last <= first:
        return 0.0
    return math.sqrt(sum(v * v for v in samples[first:last]) / (last - first))


def audio_metrics(audio: dict) -> dict:
    a, b = audio['channels']
    peak = max(max(map(abs, a)), max(map(abs, b)))
    rms = math.sqrt((sum(x * x for x in a) + sum(x * x for x in b)) / (2 * len(a)))
    pre = max(_window_rms(a, 0, .20), _window_rms(b, 0, .20))
    early = max(_window_rms(a, .26, .40), _window_rms(b, .26, .40))
    sustain = max(_window_rms(a, .50, 1.20), _window_rms(b, .50, 1.20))
    release = max(_window_rms(a, 1.35, 2.20), _window_rms(b, 1.35, 2.20))
    return {'peak': round(peak, 8), 'rms': round(rms, 8),
            'pre_note_rms': round(pre, 8), 'early_rms': round(early, 8),
            'sustain_rms': round(sustain, 8), 'release_rms': round(release, 8),
            'duration_seconds': round(audio['frames'] / RATE, 6)}


def compare_metrics(fluid: dict, awe: dict) -> dict:
    f = audio_metrics(fluid)
    a = audio_metrics(awe)
    def db_ratio(num: float, den: float):
        return round(20 * math.log10(num / den), 4) if min(num, den) > 1e-8 else None
    return {'status': 'OBSERVATION_ONLY', 'meaning': 'AWE minus FluidSynth; not EMU8000 fidelity',
            'rms_delta_db': db_ratio(a['rms'], f['rms']),
            'early_delta_db': db_ratio(a['early_rms'], f['early_rms']),
            'sustain_delta_db': db_ratio(a['sustain_rms'], f['sustain_rms']),
            'release_delta_db': db_ratio(a['release_rms'], f['release_rms']),
            'fluid': f, 'awe': a, 'awe_sha256': awe['sha256']}



def _is_hex(value: object, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{%d}' % length, value) is not None


def verify_awe_manifest(args, sf2_hash: str, presets: list[dict]) -> dict | None:
    """Fail closed: arbitrary WAV filenames are not a current-source VST3 oracle.

    Provenance supplied by a trusted native render host is REQUIRED. The manifest
    itself does not independently prove the host actually executed the VST3.
    """
    compare_requested = any(x is not None for x in (
        args.awe_dir, args.awe_manifest, args.awe_binary, args.expected_awe_commit))
    if not compare_requested:
        return None
    if (args.awe_dir is None or args.awe_manifest is None or
            args.awe_binary is None or args.expected_awe_commit is None):
        raise ValueError('AWE comparison requires --awe-dir, --awe-manifest, '
                         '--awe-binary and --expected-awe-commit together')
    if not _is_hex(args.expected_awe_commit, 40):
        raise ValueError('expected AWE source commit must be 40 lowercase hex digits')
    awe_dir = args.awe_dir.resolve(strict=True)
    if not awe_dir.is_dir():
        raise ValueError('AWE render directory missing')
    binary = args.awe_binary.resolve(strict=True)
    if not binary.is_file() or binary.stat().st_size < 2:
        raise ValueError('actual Windows VST3 module binary is missing or not PE')
    with binary.open('rb') as fp:
        if fp.read(2) != b'MZ':
            raise ValueError('actual Windows VST3 module binary is missing or not PE')
    mf = args.awe_manifest.resolve(strict=True)
    if not mf.is_file() or not 2 <= mf.stat().st_size <= 2 * 1024 * 1024:
        raise ValueError('AWE manifest is missing or outside size limit')
    data = json.loads(mf.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema') != '125a-awe-sf2-render-v1':
        raise ValueError('invalid independent AWE manifest schema')
    if data.get('source_kind') != 'PACKAGED_WINDOWS_VST3_NATIVE_RENDER':
        raise ValueError('AWE render provenance is not a native packaged Windows VST3')
    if data.get('source_commit') != args.expected_awe_commit:
        raise ValueError('AWE rendered source commit does not match independently selected current source')
    if not _is_hex(data.get('module_sha256'), 64) or digest(binary) != data['module_sha256']:
        raise ValueError('actual AWE VST3 binary hash mismatch')
    if data.get('sf2_sha256') != sf2_hash:
        raise ValueError('AWE render used a different SoundFont')
    expected_midi = {'ppq': PPQ, 'bpm': 120, 'on_tick': ON_TICKS,
                     'off_tick': OFF_TICKS, 'end_tick': END_TICKS,
                     'note': args.note, 'velocity': args.velocity}
    if data.get('midi_contract') != expected_midi:
        raise ValueError('AWE MIDI schedule/note/velocity does not match FluidSynth')
    if data.get('sample_rate') != RATE or data.get('fx') != 'CHORUS_OFF_REVERB_OFF':
        raise ValueError('AWE render must be dry at the same 44100 Hz sample rate')
    if data.get('bank_mode') != 'EXPLICIT_SF2_NO_ROM_FALLBACK':
        raise ValueError('AWE SF2 preset mapping or ROM fallback not proven disabled')
    if data.get('midi_channel') != 0 or data.get('cc7') != 100 or data.get('cc10') != 64:
        raise ValueError('AWE MIDI channel/CC gain/pan settings differ')
    cases = data.get('cases')
    if not isinstance(cases, dict) or len(cases) > 1024:
        raise ValueError('AWE case manifest missing or over limit')
    allowed = {'b%03d-p%03d-n%03d-v%03d' %
               (x['bank'], x['program'], args.note, args.velocity)
               for x in presets if x['bank'] == 0}
    for name, item in cases.items():
        if name not in allowed or not isinstance(item, dict):
            raise ValueError('unexpected AWE render case')
        if not _is_hex(item.get('midi_sha256'), 64) or not _is_hex(item.get('wav_sha256'), 64):
            raise ValueError('AWE case hashes missing or invalid')
    return data


def verify_awe_case(manifest: dict, label: str, midi_path: Path, wav_path: Path) -> dict:
    """Exact MIDI/PCM fingerprints reject stale, guessed or switched recordings."""
    row = manifest.get('cases', {}).get(label)
    if row is None:
        raise ValueError('AWE WAV has no independently pinned case provenance')
    if digest(midi_path) != row['midi_sha256']:
        raise ValueError('AWE MIDI fingerprint does not match rendered fixture')
    if digest(wav_path) != row['wav_sha256']:
        raise ValueError('AWE PCM fingerprint does not match recorded VST3 render')
    audio = read_audio(wav_path)
    if audio_metrics(audio)['pre_note_rms'] > 0.0005:
        raise ValueError('AWE pre-note audio violates the identical MIDI timeline')
    return audio

def run(args) -> dict:
    sf2 = args.sf2.resolve(strict=True)
    if not sf2.is_file():
        raise ValueError('SF2 is not a regular file')
    presets = sf2_presets(sf2)
    result = {'schema': '125a-sf2-reference-v1', 'reference_kind': 'FLUIDSYNTH_SF2_COMPATIBILITY',
              'hardware_fidelity': 'NOT_COVERED', 'awe_product_modified': False,
              'sf2_sha256': digest(sf2), 'preset_count': len(presets),
              'presets': presets, 'sample_rate': RATE,
              'midi_contract': {'ppq': PPQ, 'bpm': 120, 'on_tick': ON_TICKS,
                                'off_tick': OFF_TICKS, 'end_tick': END_TICKS,
                                'note': args.note, 'velocity': args.velocity},
              'fx': 'CHORUS_OFF_REVERB_OFF', 'render_cases': [],
              'awe_comparison': 'NOT_RUN', 'status': 'INVENTORY_ONLY'}
    if args.mode == 'inventory':
        if any(x is not None for x in (args.awe_dir, args.awe_manifest,
                                      args.awe_binary, args.expected_awe_commit)):
            raise ValueError('AWE comparison only available in render mode')
        return result
    if args.mode != 'render' or args.fluidsynth is None or args.out is None:
        raise ValueError('render mode requires --fluidsynth and --out')
    awe_manifest = verify_awe_manifest(args, result['sf2_sha256'], presets)
    if awe_manifest is not None:
        result['awe_source_commit'] = awe_manifest['source_commit']
        result['awe_module_sha256'] = awe_manifest['module_sha256']
        result['awe_manifest_sha256'] = digest(args.awe_manifest.resolve(strict=True))
    exe = args.fluidsynth.resolve(strict=True)
    if not exe.is_file():
        raise ValueError('FluidSynth executable is not a file')
    v = subprocess.run([str(exe), '-V'], capture_output=True, text=True, timeout=15,
                       check=True)
    version = version_triplet(v.stdout + v.stderr)
    if version < VERSION_MIN:
        raise ValueError('FluidSynth 2.4.5 or newer required')
    result['fluidsynth_version'] = '.'.join(map(str, version))
    result['fluidsynth_binary_sha256'] = digest(exe)
    out = args.out.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError('output directory must be absent or empty (no stale renders)')
    out.mkdir(parents=True, exist_ok=True)
    compared = 0
    failed = 0
    rendered = 0
    for item in presets:
        bank, program = item['bank'], item['program']
        case = {'bank': bank, 'program': program, 'name': item['name']}
        if bank != 0:
            case.update(status='NOT_RUN', reason='v1 bank-select policy only supports melodic SF2 bank 0')
            result['render_cases'].append(case)
            continue
        label = 'b%03d-p%03d-n%03d-v%03d' % (bank, program, args.note, args.velocity)
        midi_path = out / (label + '.mid')
        wav_path = out / (label + '.wav')
        midi_path.write_bytes(midi_bytes(program, args.note, args.velocity))
        case['midi_sha256'] = digest(midi_path)
        cmd = render_command(exe, sf2, midi_path, wav_path)
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
            if completed.returncode:
                raise ValueError('FluidSynth nonzero exit (%d): %s' %
                                 (completed.returncode, (completed.stderr + completed.stdout)[-500:]))
            audio = read_audio(wav_path)
            metrics = audio_metrics(audio)
            if metrics['peak'] >= .99999:
                raise ValueError('clipped reference PCM')
            if metrics['pre_note_rms'] > 0.0005:
                raise ValueError('reference audio before scheduled MIDI note')
            if metrics['peak'] <= 0.0001:
                case.update(status='NOT_SOUNDED', reason='no audible sample at selected MIDI note')
            else:
                case.update(status='REFERENCE_RENDERED', fluid_sha256=audio['sha256'],
                            metrics=metrics)
                rendered += 1
            if args.awe_dir is not None and case['status'] == 'REFERENCE_RENDERED':
                awe_file = args.awe_dir / (label + '.wav')
                if awe_file.is_file():
                    awe_audio = verify_awe_case(awe_manifest, label, midi_path, awe_file)
                    if awe_audio['frames'] != audio['frames']:
                        raise ValueError('AWE/FluidSynth audio durations differ')
                    case['awe_comparison'] = compare_metrics(audio, awe_audio)
                    compared += 1
                else:
                    case['awe_comparison'] = {'status': 'NOT_RUN', 'reason': 'no independently sourced AWE WAV'}
        except (ValueError, OSError, subprocess.TimeoutExpired, wave.Error) as exc:
            case.update(status='FAIL', reason=str(exc)[:500])
            failed += 1
        result['render_cases'].append(case)
    result['rendered_count'] = rendered
    result['failed_count'] = failed
    result['awe_compared_count'] = compared
    result['awe_comparison'] = 'OBSERVATION_ONLY' if compared else 'NOT_RUN'
    result['status'] = 'FAIL' if failed else ('REFERENCE_RENDERED' if rendered else 'NOT_RUN')
    (out / 'SF2-REFERENCE-RESULT.json').write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sf2', type=Path, required=True)
    parser.add_argument('--mode', choices=('inventory', 'render'), default='inventory')
    parser.add_argument('--fluidsynth', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--awe-dir', type=Path,
                        help='Optional actual VST3-rendered AWE WAV directory; provenance required')
    parser.add_argument('--awe-manifest', type=Path,
                        help='Trusted native AWE render case/source/MIDI/WAV hash manifest')
    parser.add_argument('--awe-binary', type=Path,
                        help='Exact packaged Windows AWE VST3 PE binary used for WAV capture')
    parser.add_argument('--expected-awe-commit',
                        help='40-character independently selected CURRENT AWE source SHA')
    parser.add_argument('--note', type=int, default=60)
    parser.add_argument('--velocity', type=int, default=100)
    parser.add_argument('--timeout', type=int, default=45)
    args = parser.parse_args(argv)
    try:
        if not 0 <= args.note <= 127 or not 1 <= args.velocity <= 127:
            raise ValueError('invalid MIDI note or velocity')
        if not 1 <= args.timeout <= 300:
            raise ValueError('timeout must be 1-300 seconds')
        output = run(args)
        print(json.dumps({k: v for k, v in output.items() if k not in ('presets', 'render_cases')},
                         indent=2, ensure_ascii=False))
        return 1 if output['status'] == 'FAIL' else 0
    except (OSError, ValueError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, wave.Error) as exc:
        print('SF2-REFERENCE-FAIL: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())