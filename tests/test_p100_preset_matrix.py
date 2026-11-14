"""Public synthetic mutation suite; NEVER substitutes for private Win95 parity."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0,str(Path(__file__).parent))
from p100_preset_matrix import (sf2_presets,make_plan,load_plan,events,compare_registers,
                                audit,NOTES,VELOCITIES)


def write_sf2(path: Path, tuples):
    def phdr(name,preset,bank,bag):
        return struct.pack('<20sHHHIII',name.encode('ascii').ljust(20,b'\0'),preset,bank,bag,0,0,0)
    binary=b''.join(phdr(n,p,b,i) for i,(n,b,p) in enumerate(tuples))
    binary+=phdr('EOP',0,0,len(tuples))
    pdta=b'pdta'+b'phdr'+struct.pack('<I',len(binary))+binary
    top=b'LIST'+struct.pack('<I',len(pdta))+pdta
    path.write_bytes(b'RIFF'+struct.pack('<I',len(top)+4)+b'sfbk'+top)


class MatrixPresets(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root=Path(self.dir.name)
        self.bank=self.root/'synthetic.sf2'
        # Deliberately non-contiguous, bank-program mapping is not 0..76.
        self.programs=[(f'Preset {n}',128 if n>=50 else 0,(n*7)%128)
                       for n in range(77)]
        write_sf2(self.bank,self.programs)

    def test_real_phdr_catalog_not_assumed_contiguous(self):
        presets=sf2_presets(self.bank)
        self.assertEqual(len(presets),77)
        self.assertEqual(presets[50]['bank'],128)
        self.assertEqual(presets[20]['program'],12)

    def test_complete_847_case_plan(self):
        plan=make_plan(self.bank)
        self.assertEqual(len(plan['presets']),77)
        self.assertEqual(len(plan['cases']),847)
        self.assertEqual(sum(c['kind']=='single' for c in plan['cases']),693)
        self.assertEqual(sum(c['kind']=='chord' for c in plan['cases']),77)
        self.assertEqual(sum(c['kind']=='retrigger' for c in plan['cases']),77)
        self.assertEqual(plan['notes'],list(NOTES))
        self.assertEqual(plan['velocities'],list(VELOCITIES))
        f=self.root/'plan.json';f.write_text(json.dumps(plan))
        self.assertEqual(load_plan(f),plan)

    def test_missing_preset_rejected(self):
        write_sf2(self.bank,self.programs[:-1])
        with self.assertRaisesRegex(ValueError,'expected 77'):
            make_plan(self.bank)

    def test_duplicate_bank_program_is_rejected(self):
        write_sf2(self.bank,[('A',0,0),('B',0,0)])
        with self.assertRaisesRegex(ValueError,'duplicate'):
            sf2_presets(self.bank)

    def test_bad_sf2_riff_length_rejected(self):
        self.bank.write_bytes(self.bank.read_bytes()+b'X')
        with self.assertRaisesRegex(ValueError,'RIFF'):
            sf2_presets(self.bank)

    def test_mutated_velocity_case_rejected_before_audit(self):
        plan=make_plan(self.bank)
        plan['cases'][4]['events'][0]['velocity']=72
        f=self.root/'mutated.json';f.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError,'modified'):
            load_plan(f)

    def test_reused_case_id_rejected(self):
        plan=make_plan(self.bank)
        plan['cases'][1]['id']=plan['cases'][0]['id']
        f=self.root/'duplicate.json';f.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            load_plan(f)

    def test_missing_original_evidence_is_not_success(self):
        plan=make_plan(self.bank)
        f=self.root/'plan.json';f.write_text(json.dumps(plan))
        bundle=self.root/'no-evidence';bundle.mkdir()
        report=audit(f,bundle)
        self.assertNotEqual(report['status'],'ALL_PRESET_CASES_BIT_EXACT_PASS')
        self.assertEqual(report['passed_cases'],0)
        self.assertEqual(report['expected_cases'],847)
        self.assertFalse(report['release_approved'])

    def test_register_diff_catches_one_bit_and_off_by_one_frame(self):
        original=self.root/'original.out'
        native=self.root/'native.out'
        original.write_text('# ORIGINAL_CREATIVE_WIN95_REGISTER_WRITES\n'+
                            'R 99 E22 00FF\n100 E22 0060\n100 A20 00F0\n101 E22 00A0\n101 A20 807F\n')
        def capture(clock=200, value='00F0'):
            native.write_text('# INDEPENDENT_NATIVE_P002_PORT_WRITES_ONLY\n'
                              '# CLOCK=HOST_44100_SAMPLE_FRAMES; ORIGIN=ACTIVATION\n'
                              '# SOURCE_ORIGINAL_WIN95_PROVENANCE=SEPARATELY_REQUIRED\n'
                              f'{clock} E22 0060\n{clock} A20 {value}\n'
                              f'{clock+1} E22 00A0\n{clock+1} A20 807F\n')
        capture()
        self.assertTrue(compare_registers(original,native,100,200,256)['equal'])
        capture(value='00F1')
        r=compare_registers(original,native,100,200,256)
        self.assertFalse(r['equal']);self.assertEqual(r['first_difference']['event_index'],1)
        capture(clock=201)
        self.assertFalse(compare_registers(original,native,100,200,256)['equal'])

    def test_original_read_filtered_native_read_rejected(self):
        original=self.root/'original.out'; native=self.root/'native.out'
        original.write_text('R 100 E22 0060\n101 E22 0060\n101 A20 807F\n')
        native.write_text('# INDEPENDENT_NATIVE_P002_PORT_WRITES_ONLY\n'
                          '# CLOCK=HOST_44100_SAMPLE_FRAMES; ORIGIN=ACTIVATION\n'
                          '# SOURCE_ORIGINAL_WIN95_PROVENANCE=SEPARATELY_REQUIRED\n'
                          '101 E22 0060\nR 101 E22 0060\n101 A20 807F\n')
        with self.assertRaisesRegex(ValueError,'READ'):
            compare_registers(original,native,100,100,256)

    def test_chord_and_retrigger_schedules(self):
        self.assertEqual(sum(e['type']=='note_on' for e in events('chord')),3)
        self.assertEqual(sum(e['type']=='note_on' for e in events('retrigger')),2)
        self.assertEqual(events('retrigger')[-1]['type'],'midi_reset')


if __name__=='__main__': unittest.main()
