// Ghidra headless postScript. Only synthetic input, no original Creative bytes.
// Checks *loaded and applied* LE fixups, rather than trusting successful import.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.address.Address;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;

public class P102VerifyVxd extends GhidraScript {
    private void require(boolean ok, String detail) {
        if (!ok) throw new IllegalStateException("P102: " + detail);
    }
    private long u32(long x) { return x & 0xffff_ffffL; }
    private void assertCall(Memory mem, MemoryBlock src, int off, long target) throws Exception {
        Address instruction = src.getStart().add(off);
        require((mem.getByte(instruction) & 255) == 0xE8, "missing E8 at " + instruction);
        long displacement = mem.getInt(instruction.add(1)); // LE32 signed PC-relative
        long resolved = u32(instruction.getOffset() + 5 + displacement);
        require(resolved == target, "E8 fixup target wrong at " + instruction +
                ": got " + Long.toHexString(resolved) + ", expected " + Long.toHexString(target));
    }
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        require(a.length==1, "expected one output path");
        Memory mem = currentProgram.getMemory();
        MemoryBlock[] blocks = new MemoryBlock[6];
        for (int i=1; i<=5; i++) {
            blocks[i] = mem.getBlock(".object" + i);
            require(blocks[i] != null, "missing VxD LE .object" + i);
            require(blocks[i].getSize() == 512, "wrong object size at " + i);
            require(blocks[i].getStart().getOffset() == i*0x100000L, "wrong mapped base of object " + i);
        }
        require((mem.getByte(blocks[1].getStart().add(0x60)) & 255)==0x66,
                "LCOD original instruction missing");
        long expected = blocks[1].getStart().getOffset() + 0x60;
        assertCall(mem,blocks[3],0x10,expected);
        assertCall(mem,blocks[4],0x20,expected);
        require((mem.getByte(blocks[5].getStart().add(0x30)) & 255)=='P',
                "PDAT payload lost");
        String evidence = "P102_VXD_IMPORT_PASS objects=5 self_relative_fixups=2 " +
                "target=LCOD+0x60 language=" + currentProgram.getLanguageID() + "\n";
        Files.writeString(Path.of(a[0]),evidence,StandardCharsets.UTF_8);
        println(evidence.trim());
    }
}
