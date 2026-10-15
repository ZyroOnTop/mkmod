#!/usr/bin/env python3
"""
find_offsets.py — scanner de offsets para libgame.so (MK Mobile 7.4.0 / 1449740)
Uso: python3 find_offsets.py <path_to_libgame.so>
Saída: hack_offsets.env  (variáveis de ambiente para o CI injetar no hack.h)

Estratégia:
  1. Tenta ELF symbol table (se não-stripped)
  2. Fallback: busca por byte patterns ARM64 conhecidos da UE3 mobile
  3. Fallback final: 0x0 (mod compila mas sem efeito — deriva manualmente)
"""

import sys
import struct
import re
import os

def read_u32(data, off): return struct.unpack_from('<I', data, off)[0]
def read_u64(data, off): return struct.unpack_from('<Q', data, off)[0]

def load_elf(path):
    with open(path, 'rb') as f:
        return f.read()

# ─── ELF PARSER mínimo ───────────────────────────────────────────────────────
def find_by_symbol(data, name):
    """Procura símbolo na .dynsym / .symtab do ELF."""
    if data[:4] != b'\x7fELF': return None
    bits = data[4]  # 2 = 64-bit
    if bits != 2: return None  # só ARM64

    e_shoff  = read_u64(data, 0x28)
    e_shnum  = struct.unpack_from('<H', data, 0x3C)[0]
    e_shentsize = struct.unpack_from('<H', data, 0x3A)[0]
    e_shstrndx  = struct.unpack_from('<H', data, 0x3E)[0]

    if e_shoff == 0 or e_shnum == 0: return None

    # parse section headers
    sections = []
    for i in range(e_shnum):
        base = e_shoff + i * e_shentsize
        if base + e_shentsize > len(data): break
        sh = {
            'name_off': read_u32(data, base),
            'type':     read_u32(data, base + 4),
            'flags':    read_u64(data, base + 8),
            'addr':     read_u64(data, base + 0x10),
            'offset':   read_u64(data, base + 0x18),
            'size':     read_u64(data, base + 0x20),
            'link':     read_u32(data, base + 0x28),
            'entsize':  read_u64(data, base + 0x38),
        }
        sections.append(sh)

    # shstrtab
    if e_shstrndx >= len(sections): return None
    shstr_sec = sections[e_shstrndx]
    shstr_off = shstr_sec['offset']

    def sec_name(sh):
        off = shstr_off + sh['name_off']
        end = data.index(b'\x00', off)
        return data[off:end].decode('utf-8', errors='replace')

    # achar symtab ou dynsym
    sym_sec = None
    str_sec = None
    for sh in sections:
        try:
            n = sec_name(sh)
        except Exception:
            continue
        if n in ('.symtab', '.dynsym') and sh['entsize'] > 0:
            if sym_sec is None or n == '.symtab':
                sym_sec = sh
        if n in ('.strtab', '.dynstr') and str_sec is None:
            str_sec = sh

    if not sym_sec or not str_sec: return None

    sym_off  = sym_sec['offset']
    sym_size = sym_sec['size']
    sym_ent  = sym_sec['entsize']  # 24 bytes pra ELF64
    str_off  = str_sec['offset']

    target = name.encode()
    count = sym_size // sym_ent
    for i in range(count):
        base = sym_off + i * sym_ent
        if base + sym_ent > len(data): break
        st_name  = read_u32(data, base)
        st_value = read_u64(data, base + 8)
        if st_value == 0: continue
        name_start = str_off + st_name
        name_end   = data.index(b'\x00', name_start)
        sym_str    = data[name_start:name_end].decode('utf-8', errors='replace')
        if target.decode() in sym_str:
            return st_value

    return None

# ─── PATTERN SCAN ────────────────────────────────────────────────────────────
def scan_pattern(data, pattern_hex, max_results=8):
    """
    Busca um padrão hex com wildcards '??' no binário.
    Retorna lista de offsets onde o padrão foi encontrado.
    """
    tokens = pattern_hex.strip().split()
    mask   = bytearray()
    pat    = bytearray()
    for t in tokens:
        if t == '??':
            pat.append(0x00)
            mask.append(0x00)
        else:
            pat.append(int(t, 16))
            mask.append(0xFF)

    pat  = bytes(pat)
    mask = bytes(mask)
    plen = len(pat)
    results = []

    i = 0
    data_len = len(data)
    while i <= data_len - plen and len(results) < max_results:
        match = True
        for j in range(plen):
            if mask[j] and data[i+j] != pat[j]:
                match = False
                break
        if match:
            results.append(i)
        i += 4  # ARM64 é word-aligned
    return results

# ─── HEURÍSTICAS ─────────────────────────────────────────────────────────────
# Patterns ARM64 para UE3 mobile (MK Mobile)
# Derivados de análise de versões anteriores — podem precisar de ajuste.

PATTERNS = {
    # TakeDamage: prologue clássico UE3 com salvamento de frame pointer + link register
    # STP X29,X30,[SP,#-0x20]! | STP X19,X20,[SP,#0x10]
    'TakeDamage': [
        'FD 7B BE A9 F4 4F 01 A9',
        'FD 7B BF A9 F4 4F 00 A9',
        'FD 7B BC A9 F3 53 01 A9',
    ],
    # GetHealth: função curta, LDR S0,[X0,#offset] seguido de RET
    # LDR S0,[X0,#??] pode variar, pattern mais confiável é a sequência FP+ret
    'GetHealth': [
        '?? ?? 40 BD C0 03 5F D6',   # LDR S0,[X?] + RET
        '?? ?? ?? BD C0 03 5F D6',
    ],
    # GetCooldown: mesma forma, float getter
    'GetCooldown': [
        '?? ?? 40 BD C0 03 5F D6',
        '?? ?? ?? 3D C0 03 5F D6',   # LDR Q0 variant
    ],
    # AITick: prologue maior (processa estado), diferente de getters curtos
    'AITick': [
        'FD 7B BF A9 F3 53 BF A9 F5 5B BF A9',
        'FD 7B BD A9 F4 4F 01 A9 F6 57 02 A9',
    ],
}

def find_candidate(data, name):
    """Tenta symbol, depois patterns. Retorna offset ou 0."""
    # 1. symbol table
    val = find_by_symbol(data, name)
    if val:
        print(f"  [{name}] found via symbol: 0x{val:X}")
        return val

    # 2. pattern scan
    for pat in PATTERNS.get(name, []):
        results = scan_pattern(data, pat, max_results=4)
        if results:
            # pega o primeiro resultado executável (heurística: offset > 0x1000)
            candidates = [r for r in results if r > 0x1000]
            if candidates:
                off = candidates[0]
                print(f"  [{name}] pattern '{pat}' hit @ 0x{off:X} ({len(candidates)} candidates)")
                return off

    print(f"  [{name}] NOT FOUND — offset will be 0x0")
    return 0

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: find_offsets.py <libgame.so>")
        sys.exit(1)

    lib_path = sys.argv[1]
    if not os.path.exists(lib_path):
        print(f"File not found: {lib_path}")
        sys.exit(1)

    file_size = os.path.getsize(lib_path)
    print(f"Loading {lib_path} ({file_size/1024/1024:.1f} MB)...")
    data = load_elf(lib_path)

    print("\nScanning offsets:")
    offsets = {}
    for name in ['TakeDamage', 'GetHealth', 'GetCooldown', 'AITick']:
        offsets[name] = find_candidate(data, name)

    # Escreve arquivo de env para o CI
    env_path = 'hack_offsets.env'
    with open(env_path, 'w') as f:
        f.write(f"OFFSET_TAKEDAMAGE=0x{offsets['TakeDamage']:X}\n")
        f.write(f"OFFSET_GETHEALTH=0x{offsets['GetHealth']:X}\n")
        f.write(f"OFFSET_GETCOOLDOWN=0x{offsets['GetCooldown']:X}\n")
        f.write(f"OFFSET_AITICK=0x{offsets['AITick']:X}\n")

    print(f"\nOffsets written to {env_path}:")
    for k, v in offsets.items():
        status = "✓" if v else "✗ (0x0 — derive manually)"
        print(f"  {k:20s} = 0x{v:X}  {status}")

    # Conta quantos achamos
    found = sum(1 for v in offsets.values() if v)
    print(f"\n{found}/{len(offsets)} offsets found automatically.")
    if found < len(offsets):
        print("Download libgame.so from the CI artifact and use Ghidra for the rest.")

if __name__ == '__main__':
    main()
