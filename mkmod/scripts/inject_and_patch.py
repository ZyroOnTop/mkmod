#!/usr/bin/env python3
"""
inject_and_patch.py — injeta offsets no hack.h e faz patch smali no MainActivity
Uso: python3 inject_and_patch.py <hack_offsets.env> <hack.h> <smali_dir>
"""

import sys
import os
import re
import glob

def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env

def inject_offsets(hack_h_path, env):
    with open(hack_h_path) as f:
        content = f.read()

    replacements = {
        'OFFSET_TAKEDAMAGE':  env.get('OFFSET_TAKEDAMAGE',  '0x0'),
        'OFFSET_GETHEALTH':   env.get('OFFSET_GETHEALTH',   '0x0'),
        'OFFSET_GETCOOLDOWN': env.get('OFFSET_GETCOOLDOWN', '0x0'),
        'OFFSET_AITICK':      env.get('OFFSET_AITICK',      '0x0'),
    }

    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)

    with open(hack_h_path, 'w') as f:
        f.write(content)

    print(f"[inject] hack.h updated with offsets:")
    for k, v in replacements.items():
        print(f"  {k} = {v}")

def patch_smali(smali_dir):
    """
    Insere System.loadLibrary("MKMod") no onCreate do MainActivity.
    Suporta smali/ smali_classes2/ smali_classes3/ etc.
    """
    load_lib_smali = (
        '\n'
        '    # MKMod inject\n'
        '    const-string v0, "MKMod"\n'
        '    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V\n'
    )

    # Procura MainActivity.smali em todos os diretórios smali
    pattern = os.path.join(smali_dir, '**/MainActivity.smali')
    candidates = glob.glob(pattern, recursive=True)

    if not candidates:
        # Procura também por NativeActivity, SplashActivity
        for name in ['NativeActivity', 'SplashActivity', 'GameActivity']:
            p = os.path.join(smali_dir, f'**/{name}.smali')
            candidates += glob.glob(p, recursive=True)

    if not candidates:
        print(f"[smali] WARNING: MainActivity.smali not found in {smali_dir}")
        print("[smali] Listing .smali files found:")
        all_smali = glob.glob(os.path.join(smali_dir, '**/*.smali'), recursive=True)
        for s in all_smali[:20]:
            print(f"  {s}")
        return False

    patched = 0
    for smali_path in candidates:
        with open(smali_path) as f:
            content = f.read()

        # Já tem o patch?
        if 'MKMod' in content:
            print(f"[smali] Already patched: {smali_path}")
            patched += 1
            continue

        # Acha o método onCreate
        oncreate_match = re.search(
            r'(\.method public onCreate\(Landroid/os/Bundle;\)V.*?\n)',
            content
        )
        if not oncreate_match:
            print(f"[smali] onCreate not found in {smali_path}")
            continue

        insert_pos = oncreate_match.end()

        # Aumenta .locals se necessário
        locals_match = re.search(
            r'(    \.locals )(\d+)',
            content[insert_pos:insert_pos+200]
        )
        if locals_match:
            n = int(locals_match.group(2))
            if n < 1:
                content = content[:insert_pos + locals_match.start()] + \
                          f'    .locals 1' + \
                          content[insert_pos + locals_match.end():]

        # Injeta o loadLibrary após a abertura do método
        content = content[:insert_pos] + load_lib_smali + content[insert_pos:]

        with open(smali_path, 'w') as f:
            f.write(content)

        print(f"[smali] Patched: {smali_path}")
        patched += 1

    return patched > 0

def main():
    if len(sys.argv) < 4:
        print("Usage: inject_and_patch.py <hack_offsets.env> <hack.h> <apktool_decompiled_dir>")
        sys.exit(1)

    env_path    = sys.argv[1]
    hack_h_path = sys.argv[2]
    smali_dir   = sys.argv[3]

    env = load_env(env_path)
    inject_offsets(hack_h_path, env)

    ok = patch_smali(smali_dir)
    if not ok:
        print("[smali] FAILED — APK will not load the mod lib")
        sys.exit(1)

    print("\n[inject_and_patch] Done.")

if __name__ == '__main__':
    main()
