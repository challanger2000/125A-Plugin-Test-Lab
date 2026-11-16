// Real Ghidra postscript: compare physical applied bytes to relocation table addresses.
// Args: mode ("expect-unpatched" or "expect-correct"), output-file.
// No original Creative code is loaded in this public regression.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.address.Address;
import ghidra.program.model.reloc.Relocation;
import ghidra.program.model.reloc.RelocationTable;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.List;

public class P103CheckRelocations extends GhidraScript {
    private void require(boolean ok, String detail) {
        if (!ok) throw new IllegalStateException("P103: " + detail);
    }
    private long u32(long x) { return x & 0xffff_ffffL; }

    private void callTarget(Memory mem, MemoryBlock src, int off, long expected) throws Exception {
        Address insn=src.getStart().add(off);
        require((mem.getByte(insn) & 255)==0xE8, "E8 opcode missing: " + insn);
        long displacement=mem.getInt(insn.add(1));
        require(u32(insn.getOffset()+5+displacement)==expected,
                "physical patched call destination differs: " + insn);
    }

    private boolean relocationHere(RelocationTable table, Address a) {
        List<Relocation> entries=table.getRelocations(a);
        return entries!=null && entries.stream().anyMatch(x->x.getStatus()==Relocation.Status.APPLIED);
    }

    @Override
    public void run() throws Exception {
        String[] args=getScriptArgs();
        require(args.length==2, "expected mode and output path");
        String mode=args[0];
        require(mode.equals("expect-unpatched") || mode.equals("expect-correct"), "unsupported mode");
        Memory mem=currentProgram.getMemory();
        MemoryBlock[] obj=new MemoryBlock[6];
        for (int i=1;i<=5;i++) {
            obj[i]=mem.getBlock(".object"+i);
            require(obj[i]!=null, "missing LE object "+i);
            require(obj[i].getStart().getOffset()==i*0x100000L, "base mismatch "+i);
            require(obj[i].getSize()==(i==3?1024:512), "size mismatch "+i);
        }
        long target=obj[1].getStart().getOffset()+0x60;
        callTarget(mem,obj[3],0x10,target);
        callTarget(mem,obj[3],512+0x20,target);
        callTarget(mem,obj[4],0x30,target);

        RelocationTable rel=currentProgram.getRelocationTable();
        Address first=obj[3].getStart().add(0x11);
        Address second=obj[3].getStart().add(512+0x21);
        Address wrong=obj[3].getStart().add(4096+0x21);
        Address third=obj[4].getStart().add(0x31);
        require(relocationHere(rel,first), "missing first page fixup metadata");
        require(relocationHere(rel,third), "missing PCOD fixup metadata");
        boolean correct=relocationHere(rel,second) && !relocationHere(rel,wrong);
        boolean buggy=!relocationHere(rel,second) && relocationHere(rel,wrong);
        if(mode.equals("expect-unpatched"))
            require(buggy, "published extension does not reproduce expected incorrect page-stride metadata");
        else
            require(correct, "patched loader did not map second-page fixup metadata to 512-byte page address");
        require(rel.getSize()==3, "unexpected total relocation records " + rel.getSize());
        String outcome="P103_" + (correct?"PATCHED_CORRECT":"BASELINE_BUG_REPRODUCED") +
                 " real_vxd_objects=5 page_size=512 cross_object_e8_fixups=3" +
                 " relocation_source_pnpc_page2=" + (correct?"0x300221":"0x301021") + "\n";
        Files.writeString(Path.of(args[1]),outcome,StandardCharsets.UTF_8);
        println(outcome.trim());
    }
}
