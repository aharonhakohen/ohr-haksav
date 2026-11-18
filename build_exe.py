# -*- coding: utf-8 -*-
"""
Ohr HaKsav - Automated Build Script for Standalone Executable & Offline Setup Wizard
Bundles Python, PyQt6, PyTorch CPU, Mishkefet-v1 model assets, 3D icons, and offline zip payload.
Optimized to exclude unused build dependencies (transformers, scipy, matplotlib, pandas, etc.)
"""

import os
import sys
import json
import shutil
import zipfile
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_version() -> str:
    vpath = os.path.join(BASE_DIR, "version.json")
    try:
        with open(vpath, "r", encoding="utf-8") as f:
            return json.load(f).get("version", "1.3.6")
    except Exception:
        return "1.3.6"

def generate_version_info(version_str: str, original_filename: str, description: str, out_path: str) -> str:
    """Generate a PyInstaller-compatible Windows Version Info resource file."""
    parts = [int(p) for p in version_str.split('.') if p.isdigit()]
    while len(parts) < 4:
        parts.append(0)
    ver_tuple = tuple(parts)

    content = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={ver_tuple},
    prodvers={ver_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Torah uMesorah Lakewood Teachers Center'),
        StringStruct('FileDescription', '{description}'),
        StringStruct('FileVersion', '{version_str}.0'),
        StringStruct('InternalName', '{os.path.splitext(original_filename)[0]}'),
        StringStruct('LegalCopyright', 'Copyright (c) 2026 Torah uMesorah Lakewood Teachers Center'),
        StringStruct('OriginalFilename', '{original_filename}'),
        StringStruct('ProductName', 'Ohr HaKsav (אור הכתב)'),
        StringStruct('ProductVersion', '{version_str}.0')])
      ]), 
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
'''
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path

def create_payload_zip(src_dir: str, out_zip: str):
    print(f"\nCompressing offline application payload to {out_zip}...")
    t0 = time.time()
    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, src_dir)
                zf.write(full_path, rel_path)
    mb = os.path.getsize(out_zip) / (1024 * 1024)
    print(f"[SUCCESS] Payload created: {mb:.1f} MB in {time.time()-t0:.1f}s")

def build(force_rebuild: bool = False):
    version = get_version()
    print("=" * 70)
    print(f"Building Ohr HaKsav v{version} Standalone Offline Package")
    print("=" * 70)

    dist_dir = os.path.join(BASE_DIR, "dist")
    assets_dir = os.path.join(BASE_DIR, "assets")
    ico_path = os.path.join(assets_dir, "ohr_haksav.ico")
    app_output = os.path.join(dist_dir, "OhrHaKsav")
    app_exe = os.path.join(app_output, "OhrHaKsav.exe")
    payload_zip = os.path.join(dist_dir, "payload.zip")
    setup_exe = os.path.join(dist_dir, "OhrHaKsav_Setup.exe")

    # Determine if rebuild of OhrHaKsav.exe is needed
    core_files = [
        os.path.join(BASE_DIR, "version.json"),
        os.path.join(BASE_DIR, "main.py"),
        os.path.join(BASE_DIR, "ui", "main_window.py"),
        os.path.join(BASE_DIR, "ui", "dictionary_dialog.py"),
        os.path.join(BASE_DIR, "ui", "text_editor.py"),
        os.path.join(BASE_DIR, "ui", "update_dialog.py"),
        os.path.join(BASE_DIR, "ui", "update_banner.py"),
        os.path.join(BASE_DIR, "ui", "help_dialog.py"),
        os.path.join(BASE_DIR, "ui", "theme.py"),
        os.path.join(BASE_DIR, "installer", "setup_gui.py"),
        os.path.join(BASE_DIR, "ui", "i18n.py"),
        os.path.join(BASE_DIR, "core", "learning_engine.py"),
        os.path.join(BASE_DIR, "core", "ocr_engine.py"),
        os.path.join(BASE_DIR, "core", "logger.py"),
        ico_path
    ]
    needs_app_rebuild = force_rebuild or not os.path.exists(app_exe)
    if not needs_app_rebuild and os.path.exists(app_exe):
        exe_mtime = os.path.getmtime(app_exe)
        for cf in core_files:
            if os.path.exists(cf) and os.path.getmtime(cf) > exe_mtime:
                needs_app_rebuild = True
                break

    app_version_info = generate_version_info(
        version, "OhrHaKsav.exe", 
        "Ohr HaKsav - Offline Torah Notes & Hebrew Handwriting OCR Studio", 
        os.path.join(BASE_DIR, "app_version_info.txt")
    )

    if needs_app_rebuild:
        print(f"\n[1/3] Compiling OhrHaKsav.exe (v{version}) directory with optimizations & embedded version info...")
        if os.path.exists(app_output):
            shutil.rmtree(app_output, ignore_errors=True)
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--name=OhrHaKsav",
            "--noconsole",
            "--onedir",
            "--clean",
            f"--icon={ico_path}",
            f"--version-file={app_version_info}",
            "--add-data", f"{os.path.join(BASE_DIR, 'version.json')};.",
            "--add-data", f"{os.path.join(BASE_DIR, 'model_assets')};model_assets",
            "--add-data", f"{assets_dir};assets",
            "--hidden-import", "PyQt6",
            "--hidden-import", "torch",
            "--hidden-import", "PIL",
            "--hidden-import", "docx",
            "--hidden-import", "core.hebocr.recognize",
            "--hidden-import", "core.hebocr.wordlm",
            "--hidden-import", "core.hebocr.lm",
            # Optimization: Exclude unused heavy build dependencies to slim down package
            "--exclude-module", "transformers",
            "--exclude-module", "scipy",
            "--exclude-module", "matplotlib",
            "--exclude-module", "pandas",
            "--exclude-module", "onnxruntime",
            "--exclude-module", "av",
            "--exclude-module", "jedi",
            "--exclude-module", "IPython",
            "--exclude-module", "notebook",
            os.path.join(BASE_DIR, "main.py")
        ]
        subprocess.check_call(cmd, cwd=BASE_DIR)
        
        # Also create a version-named copy in app_output for explicit version visibility
        versioned_app_exe = os.path.join(app_output, f"OhrHaKsav_v{version}.exe")
        shutil.copy2(app_exe, versioned_app_exe)
        print(f" -> Created version-labeled binary: {versioned_app_exe}")
    else:
        print(f"\n[1/3] Existing OhrHaKsav application up-to-date at: {app_output}")

    # 2. Package offline payload.zip
    if not os.path.exists(payload_zip) or os.path.getmtime(payload_zip) < os.path.getmtime(app_exe):
        create_payload_zip(app_output, payload_zip)
    else:
        print(f"\n[2/3] Existing payload.zip up-to-date ({os.path.getsize(payload_zip)/(1024*1024):.1f} MB)")

    # 3. Build Standalone Offline Setup Wizard with version in filename and embedded version resource
    setup_name = f"OhrHaKsav_Setup_v{version}"
    setup_versioned_exe = os.path.join(dist_dir, f"{setup_name}.exe")
    setup_version_info = generate_version_info(
        version, f"{setup_name}.exe", 
        "Ohr HaKsav - Offline Setup Wizard", 
        os.path.join(BASE_DIR, "setup_version_info.txt")
    )

    print(f"\n[3/3] Compiling {setup_name}.exe Self-Extracting Installer Wizard with embedded version resource...")
    installer_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--add-data", f"{os.path.join(BASE_DIR, 'version.json')};.",
        "--noconfirm",
        f"--name={setup_name}",
        "--noconsole",
        "--onefile",
        "--clean",
        f"--icon={ico_path}",
        f"--version-file={setup_version_info}",
        "--add-data", f"{assets_dir};assets",
        "--add-data", f"{payload_zip};.",
        os.path.join(BASE_DIR, "installer", "setup_gui.py")
    ]
    subprocess.check_call(installer_cmd, cwd=BASE_DIR)

    # Maintain OhrHaKsav_Setup.exe copy for backward-compatibility & generic shortcuts
    shutil.copy2(setup_versioned_exe, setup_exe)
    print(f" -> Created compatibility alias: {setup_exe}")

    # Cleanup temporary version info files
    for vi_path in [app_version_info, setup_version_info]:
        if os.path.exists(vi_path):
            try:
                os.remove(vi_path)
            except Exception:
                pass

    # 4. Deploy to custom staging directory (configured via local_deploy.txt or KSAV_KOOKER_DEPLOY_DIR)
    target_drive = os.environ.get("OHR_HAKSAV_DEPLOY_DIR") or os.environ.get("KSAV_KOOKER_DEPLOY_DIR")
    if not target_drive:
        deploy_cfg = os.path.join(BASE_DIR, "local_deploy.txt")
        if os.path.exists(deploy_cfg):
            try:
                with open(deploy_cfg, "r", encoding="utf-8") as f:
                    candidate = f.read().strip()
                    if candidate and os.path.exists(candidate):
                        target_drive = candidate
            except Exception:
                pass

    if target_drive and os.path.exists(target_drive):
        try:
            print(f"\nDeploying artifacts to destination: {target_drive}...")
            
            # 1. Setup wizards (both versioned and generic)
            shutil.copy2(setup_versioned_exe, os.path.join(target_drive, f"{setup_name}.exe"))
            shutil.copy2(setup_exe, os.path.join(target_drive, "OhrHaKsav_Setup.exe"))
            print(f" -> Deployed {setup_name}.exe and OhrHaKsav_Setup.exe")

            # 2. Portable zip
            portable_zip = os.path.join(target_drive, f"OhrHaKsav-v{version}-Windows.zip")
            shutil.copy2(payload_zip, portable_zip)
            print(f" -> Deployed portable zip to {portable_zip}")

            # 3. version.json for offline update checks
            shutil.copy2(os.path.join(BASE_DIR, "version.json"), os.path.join(target_drive, "version.json"))
            print(" -> Deployed version.json for offline update checks")

            # 3. Unpacked directory
            drive_app_dir = os.path.join(target_drive, "Ohr HaKsav")
            if os.path.exists(drive_app_dir):
                shutil.rmtree(drive_app_dir, ignore_errors=True)
            shutil.copytree(app_output, drive_app_dir)
            print(f" -> Deployed unpacked app directory to {drive_app_dir}")

            print("\n[ALL DELIVERABLES READY AND DEPLOYED]")
        except Exception as e:
            print(f"Notice: Deployment error: {e}")

if __name__ == "__main__":
    force = "--force" in sys.argv
    build(force_rebuild=force)
