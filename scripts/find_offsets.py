#!/usr/bin/env python3
"""
find_offsets.py — V11
Scanner de offsets para libUE4.so do MK Mobile 7.4.0 (armeabi-v7a / arm64-v8a)

Estratégia por prioridade:
  1. ELF symbol table (.dynsym/.symtab) — demangled, busca por nome parcial
  2. Byte pattern scan — branches para ARMv7 e ARM64
  3. Fallback: 0x0 com diagnóstico detalhado

Saída: hack_offsets.env  (lido pelo step de inject do workflow)
"""

import sys, os, struct, re
from pathlib import Path

# ─── ELF ────────────────────────────────────────────────────────────────────

def read_u16(d, o): return struct.unpack_from('<H', d, o)[0]
def read_u32(d, o): return struct.unpack_from('<I', d, o)[0]
def read_u64(d, o): return struct.unpack_from('<Q', d, o)[0]

def elf_info(data):
    if data[:4] != b'\x7fELF':
        return None
    bits = data[4]          # 1=32bit 2=64bit
    endian = data[5]        # 1=LE
    if endian != 1:
        return None
    return {
        'bits':     bits,
        'is64':     bits == 2,
        'e_shoff':  read_u64(data, 0x28) if bits == 2 else read_u32(data, 0x20),
        'e_shnum':  read_u16(data, 0x3C) if bits == 2 else read_u16(data, 0x30),
        'e_shentsize': read_u16(data, 0x3A) if bits == 2 else read_u16(data, 0x2E),
        'e_shstrndx':  read_u16(data, 0x3E) if bits == 2 else read_u16(data, 0x32),
        'e_machine':   read_u16(data, 18),  # 40=ARM 183=AArch64
    }

def parse_sections(data, info):
    sections = []
    off = info['e_shoff']
    sz  = info['e_shentsize']
    is64 = info['is64']
    for _ in range(info['e_shnum']):
        if off + sz > len(data): break
        if is64:
            sh = {
                'name_idx': read_u32(data, off),
                'type':     read_u32(data, off + 4),
                'addr':     read_u64(data, off + 0x10),
                'offset':   read_u64(data, off + 0x18),
                'size':     read_u64(data, off + 0x20),
                'link':     read_u32(data, off + 0x28),
                'entsize':  read_u64(data, off + 0x38),
            }
        else:
            sh = {
                'name_idx': read_u32(data, off),
                'type':     read_u32(data, off + 4),
                'addr':     read_u32(data, off + 0x0C),
                'offset':   read_u32(data, off + 0x10),
                'size':     read_u32(data, off + 0x14),
                'link':     read_u32(data, off + 0x1C),
                'entsize':  read_u32(data, off + 0x24) if off + 0x28 <= len(data) else 0,
            }
        sections.append(sh)
        off += sz
    return sections

def get_section_name(data, sections, shstrndx, idx):
    if shstrndx >= len(sections): return ''
    strtab_off = sections[shstrndx]['offset']
    name_off = strtab_off + idx
    end = data.find(b'\x00', name_off)
    return data[name_off:end].decode('utf-8', errors='replace')

def find_symbol(data, info, sections, target_fragments):
    """
    Procura symbol cujo nome demangled contém qualquer fragmento da lista.
    Retorna (nome, valor) ou (None, 0).
    """
    shstrndx = info['e_shstrndx']
    is64 = info['is64']
    sym_ent = 24 if is64 else 16

    sym_sec = str_sec = None
    for sh in sections:
        n = get_section_name(data, sections, shstrndx, sh['name_idx'])
        if n in ('.symtab', '.dynsym') and sh['entsize'] > 0:
            if sym_sec is None or n == '.symtab':
                sym_sec = sh
        if n in ('.strtab', '.dynstr') and str_sec is None:
            str_sec = sh

    if not sym_sec or not str_sec:
        return None, 0

    sym_off  = sym_sec['offset']
    sym_size = sym_sec['size']
    str_off  = str_sec['offset']
    count = sym_size // (sym_sec['entsize'] or sym_ent)

    candidates = []
    for i in range(count):
        base = sym_off + i * (sym_sec['entsize'] or sym_ent)
        if base + sym_ent > len(data): break
        if is64:
            st_name  = read_u32(data, base)
            st_value = read_u64(data, base + 8)
            st_size  = read_u64(data, base + 16)
        else:
            st_name  = read_u32(data, base)
            st_value = read_u32(data, base + 4)
            st_size  = read_u32(data, base + 8)

        if st_value == 0: continue
        nm_start = str_off + st_name
        nm_end   = data.find(b'\x00', nm_start)
        sym_str  = data[nm_start:nm_end].decode('utf-8', errors='replace')

        for frag in target_fragments:
            if frag.lower() in sym_str.lower():
                candidates.append((sym_str, st_value, st_size))
                break

    if not candidates:
        return None, 0

    # Preferir símbolo menor (getters são funções pequenas, evitar blocos genéricos)
    candidates.sort(key=lambda x: x[2] if x[2] > 0 else 999999)
    name, value, _ = candidates[0]
    # ARMv7 Thumb: bit 0 setado indica Thumb — limpar para offset real
    addr = value & ~1
    return name, addr

# ─── PATTERN SCAN ───────────────────────────────────────────────────────────

def scan_pattern(data, pattern_hex, stride=2, max_results=8):
    tokens = pattern_hex.strip().split()
    pat    = bytearray()
    mask   = bytearray()
    for t in tokens:
        if t == '??':
            pat.append(0); mask.append(0)
        else:
            pat.append(int(t, 16)); mask.append(0xFF)
    pat  = bytes(pat)
    mask = bytes(mask)
    plen = len(pat)
    results = []
    i = 0
    while i <= len(data) - plen and len(results) < max_results:
        match = all(mask[j] == 0 or data[i+j] == pat[j] for j in range(plen))
        if match:
            results.append(i)
        i += stride
    return results

# ─── PATTERNS POR ABI ───────────────────────────────────────────────────────
#
# ARMv7 Thumb2 prologue típico UE4:
#   PUSH {r4-r7, lr}  = 2D E9 F0 47  (little-endian Thumb2)
#   PUSH {r4, r5, lr} = 2D E9 30 40
#   Função curta getter (GetHealth, GetCooldown):
#     LDR r0,[r0,#offset] + BX lr = ?? 68 70 47  (Thumb16 2-byte)
#
# ARM64 prologue UE4 (XAPK arm64-v8a se detectado):
#   STP X29,X30,[SP,#-0x10]! = FD 7B BF A9
#   STP X20,X19,[SP,#-0x20]! = F3 53 BE A9

PATTERNS_ARMv7 = {
    # TakeDamage — função longa, começa com PUSH salvando vários regs
    'TakeDamage': [
        '2D E9 F0 4F',   # PUSH {r4-r11,lr} Thumb2 — mais completo
        '2D E9 F0 47',   # PUSH {r4-r7,lr}
        '2D E9 70 40',   # PUSH {r4,r5,r6,lr}
        '2D E9 30 40',   # PUSH {r4,r5,lr}
        '10 B5',         # PUSH {r4,lr} Thumb16 (função menor)
    ],
    # GetHealth — getter curto: LDR r0,[r0,#X] + BX lr
    'GetHealth': [
        '?? 68 70 47',   # LDR r0,[r0,#0] + BX lr
        '?? 69 70 47',   # LDR r0,[r0,#8..12] + BX lr — hp em offset diferente
        '?? 6A 70 47',
        '?? 6B 70 47',
        '?? 78 70 47',   # LDRB variant
    ],
    # GetCooldown — similar a GetHealth, retorna float via VFP
    'GetCooldown': [
        '?? ED D0 0A 70 47',   # VLDR s0,[r0,#X] + BX lr
        '?? ED D0 0B 70 47',
        'D0 ED ?? 0A 70 47',   # variant
        '?? 68 70 47',         # também pode ser int cast
    ],
    # AITick — função com delta float, prologue maior
    'AITick': [
        '2D E9 F0 4F',
        '2D E9 F0 47',
        '38 B5',         # PUSH {r3,r4,r5,lr}
        '10 B5',
    ],
}

PATTERNS_ARM64 = {
    'TakeDamage': [
        'FD 7B BF A9 F3 53 BE A9',
        'FD 7B BE A9 F4 4F 01 A9',
        'FD 7B BC A9 F3 53 01 A9',
    ],
    'GetHealth': [
        '?? ?? 40 BD C0 03 5F D6',
        '?? ?? ?? BD C0 03 5F D6',
    ],
    'GetCooldown': [
        '?? ?? 40 BD C0 03 5F D6',
        '?? ?? ?? 3D C0 03 5F D6',
    ],
    'AITick': [
        'FD 7B BF A9 F3 53 BF A9 F5 5B BF A9',
        'FD 7B BD A9 F4 4F 01 A9 F6 57 02 A9',
    ],
}

# ─── SÍMBOLOS UE4 a buscar (fragmentos, case-insensitive) ────────────────────
#
# UE4 C++ mangled: _ZN5AActor10TakeDamageEf...  → fragmento "TakeDamage"
# MK Mobile customizado pode usar: "UMKFighter", "UFightChar", "MKGameCharacter"
# Buscamos fragmentos genéricos que cubram os casos comuns.

SYMBOL_TARGETS = {
    'TakeDamage': [
        'TakeDamage',
        'ApplyDamage',
        'DealDamage',
        'ReceiveDamage',
        'OnTakeAnyDamage',
    ],
    'GetHealth': [
        'GetHealth',
        'GetCurrentHealth',
        'GetHP',
        'CurrentHealth',
        'HealthValue',
    ],
    'GetCooldown': [
        'GetCooldown',
        'GetRemainingCooldown',
        'SpecialCooldown',
        'AbilityCooldown',
        'GetCooldownTime',
    ],
    'AITick': [
        'AITick',
        'TickAI',
        'UpdateAI',
        'AIController',
        'BehaviorTree',
        'TickComponent',
    ],
}

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: find_offsets.py <lib.so>")
        sys.exit(1)

    lib_path = sys.argv[1]
    if not os.path.exists(lib_path):
        print(f"[error] File not found: {lib_path}")
        sys.exit(1)

    file_size = os.path.getsize(lib_path)
    print(f"[scanner] Loading {lib_path} ({file_size/1024/1024:.1f} MB)...")
    data = Path(lib_path).read_bytes()

    info = elf_info(data)
    if not info:
        print("[error] Not a valid LE ELF file")
        sys.exit(1)

    abi = 'arm64-v8a' if info['is64'] else 'armeabi-v7a'
    machine_name = {40: 'ARM', 183: 'AArch64'}.get(info['e_machine'], f"e_machine={info['e_machine']}")
    print(f"[scanner] ELF: {'64-bit' if info['is64'] else '32-bit'} / {machine_name} / ABI={abi}")

    sections = parse_sections(data, info)
    patterns  = PATTERNS_ARM64 if info['is64'] else PATTERNS_ARMv7
    stride    = 4 if info['is64'] else 2  # ARM64=4bytes, Thumb2 min=2bytes

    offsets = {}
    for func_name, fragments in SYMBOL_TARGETS.items():
        print(f"\n[scanner] Searching: {func_name}")

        # 1 — symbol table
        sym_name, sym_val = find_symbol(data, info, sections, fragments)
        if sym_val:
            print(f"  [sym] {sym_name} → 0x{sym_val:X}")
            offsets[func_name] = sym_val
            continue

        # 2 — pattern scan
        found = False
        for pat in patterns.get(func_name, []):
            results = scan_pattern(data, pat, stride=stride, max_results=5)
            candidates = [r for r in results if r > 0x1000]
            if candidates:
                # Para getters curtos (GetHealth, GetCooldown), escolher resultado
                # menor offset (geralmente código, não dados)
                # Para funções longas, pode ter muitos hits — pegar o primeiro em .text
                addr = candidates[0]
                # ARMv7 Thumb: o endereço de chamada é addr|1 mas o offset no .so é addr
                print(f"  [pat] '{pat}' → 0x{addr:X} ({len(candidates)} hits)")
                offsets[func_name] = addr
                found = True
                break

        if not found:
            print(f"  [miss] {func_name} not found — offset will be 0x0")
            offsets[func_name] = 0

    # ── Diagnóstico ──────────────────────────────────────────────────────────
    print(f"\n[scanner] Results ({abi}):")
    found_count = 0
    for k, v in offsets.items():
        status = f"0x{v:X}" if v else "0x0 (NOT FOUND)"
        print(f"  {k:20s} = {status}")
        if v: found_count += 1

    print(f"\n[scanner] {found_count}/{len(offsets)} found.")

    if found_count == 0:
        print("[scanner] WARNING: zero offsets found.")
        print("[scanner] This is expected for stripped UE4 binaries without debug symbols.")
        print("[scanner] To derive offsets manually:")
        print("  1. Download libUE4.so from the CI artifact")
        print("  2. Open in Ghidra 11.x (AARCH64 LE 64-bit or ARM LE 32-bit)")
        print("  3. Auto-analyze, then search Symbol Table for 'TakeDamage', 'GetHealth'")
        print("  4. If stripped, use the Search > Memory with byte patterns")
        print("  5. Update hack.h with real offsets and re-run the workflow")

    # ── Escreve env file ─────────────────────────────────────────────────────
    env_lines = [
        f"OFFSET_TAKEDAMAGE=0x{offsets.get('TakeDamage', 0):X}",
        f"OFFSET_GETHEALTH=0x{offsets.get('GetHealth', 0):X}",
        f"OFFSET_GETCOOLDOWN=0x{offsets.get('GetCooldown', 0):X}",
        f"OFFSET_AITICK=0x{offsets.get('AITick', 0):X}",
    ]
    Path('hack_offsets.env').write_text('\n'.join(env_lines) + '\n')
    print(f"\n[scanner] hack_offsets.env written.")

if __name__ == '__main__':
    main()
