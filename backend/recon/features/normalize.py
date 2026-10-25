import re
from typing import Literal

from capstone import CS_GRP_CALL, CS_GRP_JUMP, CS_GRP_RET, CsInsn
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

from recon.schemas import Instruction


def register_class(name: str) -> str:
    if name in {"rip", "eip", "ip"}:
        return "IP"
    if name in {"rsp", "esp", "sp", "spl"}:
        return "SP"
    if name in {"rbp", "ebp", "bp", "bpl"}:
        return "BP"
    if re.match(r"[xyz]mm", name):
        return "VEC"
    return "REG"


def normalize(ins: CsInsn) -> Instruction:
    flow: Literal["next", "conditional", "jump", "return", "call", "stop"] = "next"
    target = None
    if ins.group(CS_GRP_RET):
        flow = "return"
    elif ins.group(CS_GRP_JUMP):
        flow = "jump" if ins.mnemonic in {"jmp", "ljmp"} else "conditional"
    elif ins.group(CS_GRP_CALL):
        flow = "call"
    elif ins.mnemonic in {"ud2", "hlt", "int3", "sysret", "iretq"}:
        flow = "stop"
    operands = []
    for operand in ins.operands:
        if operand.type == X86_OP_REG:
            operands.append(f"{register_class(ins.reg_name(operand.reg))}{operand.size * 8}")
        elif operand.type == X86_OP_IMM:
            if flow in {"call", "jump", "conditional"}:
                target = int(operand.imm)
                operands.append("ADDR")
            else:
                operands.append(
                    "ZERO" if operand.imm == 0 else "ONE" if operand.imm == 1 else "IMM"
                )
        elif operand.type == X86_OP_MEM:
            base = register_class(ins.reg_name(operand.mem.base)) if operand.mem.base else "ABS"
            operands.append(f"MEM{operand.size * 8}_{base}")
        else:
            operands.append("OTHER")
    return Instruction(
        address=ins.address,
        size=ins.size,
        mnemonic=ins.mnemonic,
        operands=ins.op_str,
        token=ins.mnemonic + "|" + ",".join(operands),
        bytes_hex=ins.bytes.hex(),
        branch_target=target,
        flow=flow,
    )
