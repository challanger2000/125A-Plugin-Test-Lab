#!/usr/bin/env python3
"""P70 pixel foreground region proposal, no-click safety and adversarial CI."""
from pathlib import Path
import struct
import tempfile
import unittest
from run_gui_painted_candidates import candidate_islands, run, digest, SCHEMA


def frame(w=320, h=180, patches=()):
    rgb = bytearray(bytes((48, 36, 30)) * (w*h))
    for l, t, r, b, color in patches:
        for y in range(t, b):
            for x in range(l, r):
                i = (y*w+x)*3
                rgb[i:i+3] = bytes((color[2], color[1], color[0]))
    return w, h, bytes(rgb)


def bmp(path, scene):
    width, height, bgr = scene
    pixels = b"".join(bgr[i:i+3] + b"\xff" for i in range(0, len(bgr), 3))
    header = struct.pack("<HIHHI", 0x4d42, 54+len(pixels), 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32,
                      0, len(pixels), 0, 0, 0, 0)
    path.write_bytes(header + dib + pixels)


class PaintedVisualCandidateTests(unittest.TestCase):
    def test_detects_two_independent_painted_islands_without_ui_semantics(self):
        image = frame(patches=[
            (120, 65, 200, 115, (70,80,90)),
            (10, 10, 55, 34, (200,35,55))
        ])
        candidates, status = candidate_islands(image)
        self.assertEqual(status, "FOREGROUND_CANDIDATES")
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["bbox_xyxy"], [120,65,200,115])
        self.assertEqual((candidates[0]["x"],candidates[0]["y"]), (160,90))
        self.assertEqual(candidates[0]["control_semantics"], "UNKNOWN")
        self.assertIs(candidates[0]["approved_to_click"], False)

    def test_uniform_and_ambiguous_artwork_not_falsely_identified(self):
        candidates, status = candidate_islands(frame())
        self.assertEqual(candidates, [])
        self.assertEqual(status, "NO_VISUAL_CANDIDATES")
        ambiguous = frame(patches=[
            (0,0,1,1,(100,0,0)),(319,0,320,1,(0,100,0)),
            (0,179,1,180,(0,0,100)),(319,179,320,180,(100,100,0))
        ])
        self.assertEqual(candidate_islands(ambiguous)[1], "BACKGROUND_AMBIGUOUS")

    def test_rejects_corrupt_image_and_invalid_budget(self):
        with self.assertRaises(ValueError):
            candidate_islands((320,180,b"hello"))
        with self.assertRaises(ValueError):
            candidate_islands(frame(), max_points=0)
        with self.assertRaises(ValueError):
            candidate_islands(frame(), tile=2)

    def test_real_native_capture_wrapper_requires_opt_in_before_mouse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "Painted.vst3"
            dll = plugin / "Contents/x86_64-win/Painted.vst3"
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b"VST3 DLL")
            host = root / "host.exe"
            host.write_bytes(b"test host")
            class Done:
                returncode=0
                stdout="actual native capture"
                stderr=""
            calls=[]
            def native(command, **kwargs):
                self.assertEqual(command[1], "--snapshot-editor")
                bmp(Path(command[3]), frame(patches=[(120,65,200,115,(70,80,90))]))
                calls.append("capture")
                return Done()
            def unexpected(*a, **kw):
                raise AssertionError("default read-only P70 accidentally clicked!")
            result=run(plugin,host,root/"read-only",runner=native,explore=unexpected)
            self.assertEqual(result["schema"], SCHEMA)
            self.assertEqual(result["status"], "CANDIDATES_COMPLETE")
            self.assertEqual(result["exploration"], "NOT RUN")
            self.assertEqual(result["visual_candidates"][0]["x"],160)
            self.assertEqual(calls,["capture"])
            self.assertFalse(result["release_approved"])
            def optin(*a, **kw):
                self.assertEqual(kw["points"],"160,90")
                self.assertTrue(kw["acknowledge"])
                return {"status":"OBSERVATIONS_COMPLETE",
                        "verified_module_sha256":digest(dll),
                        "verified_gui_host_sha256":digest(host),
                        "requested_points":1,"completed_points":1,
                        "sham_verified_points":1,"release_approved":False}
            approved=run(plugin,host,root/"opt-in",runner=native,
                         explore=optin,acknowledge=True)
            self.assertEqual(approved["status"],"CANDIDATES_COMPLETE")
            self.assertEqual(approved["exploration"],"OBSERVATIONS_COMPLETE")
            def forged(*a, **kw):
                return {**optin(*a, **kw),"sham_verified_points":0}
            rejected=run(plugin,host,root/"forged",runner=native,
                         explore=forged,acknowledge=True)
            self.assertEqual(rejected["status"],"FAIL")
            self.assertFalse(rejected["release_approved"])


if __name__=="__main__":
    unittest.main()
