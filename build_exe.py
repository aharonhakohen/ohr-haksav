# -*- coding: utf-8 -*-
"""
Ohr HaKsav - Automated Build Script for Standalone Executable, Delta Patch & Offline Setup Wizard (v1.4.0)
Bundles Python, PyQt6, PyTorch CPU, Mishkefet-v1 model assets, 3D icons, and offline zip payload.
Also builds:
  - Lightweight Code-Only Delta Patch (OhrHaKsav_Patch_vX.Y.Z.zip) for fast updates (~90% smaller)
  - SHA-256 cryptographic checksums injected automatically into version.json & public/version.json
  - Optional Windows Authenticode code signing via signtool.exe (OHR_HAKSAV_CERT_PFX or OHR_HAKSAV_CERT_THUMBPRINT)
"""

import os
import sys
import json
import shutil
import hashlib
import zipfile
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_version() -> str:
    vpath = os.path.join(BASE_DIR, "version.json")
    try:
        with open(vpath, "r", encoding="utf-8") as f:
            return json.load(f).get("version", "1.4.0")
    except Exception:
        return "1.4.0"


def compute_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(1024 * 256)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower()


def sign_executable(exe_path: str) -> bool:
    """
    Signs a Windows executable with Authenticode SHA-256 if signing environment variables are set:
      - OHR_HAKSAV_CERT_PFX (+ optional OHR_HAKSAV_CERT_PASS)
      - OR OHR_HAKSAV_CERT_THUMBPRINT (Windows Certificate Store)
    """
    pfx = os.environ.get("OHR_HAKSAV_CERT_PFX", "").strip()
    pfx_pass = os.environ.get("OHR_HAKSAV_CERT_PASS", "").strip()
    thumb = os.environ.get("OHR_HAKSAV_CERT_THUMBPRINT", "").strip()
    if not pfx and not thumb:
        return False

    signtool = shutil.which("signtool") or shutil.which("signtool.exe")
    if not signtool:
        print(f"Notice: Code signing configured, but signtool.exe was not found on PATH. Skipping signing for {os.path.basename(exe_path)}.")
        return False

    cmd = [signtool, "sign", "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256"]
    if pfx and os.path.exists(pfx):
        cmd.extend(["/f", pfx])
        if pfx_pass:
            cmd.extend(["/p", pfx_pass])
    elif thumb:
        cmd.extend(["/sha1", thumb])
    cmd.append(exe_path)

    try:
        subprocess.check_call(cmd)
        print(f" -> Signed executable (Authenticode SHA-256): {os.path.basename(exe_path)}")
        return True
    except Exception as e:
        print(f"Warning: Authenticode signing failed for {os.path.basename(exe_path)}: {e}")
        return False


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
    print(f"\nCompressing full offline application payload to {out_zip}...")
    t0 = time.time()
    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, src_dir)
                zf.write(full_path, rel_path)
    mb = os.path.getsize(out_zip) / (1024 * 1024)
    print(f"[SUCCESS] Full payload created: {mb:.1f} MB in {time.time()-t0:.1f}s")


def create_delta_patch_zip(src_dir: str, out_zip: str):
    """
    Creates a lightweight code-only delta patch zip excluding heavy unchanging binary engines
    (torch, PyQt6, cv2, fitz, model_assets, numpy, PIL), unchanging runtime metadata, and the
    duplicate version-labeled EXE alias (which the updater recreates locally in 0.05s).
    Updates only OhrHaKsav.exe, version.json, assets, and base_library.zip (~49 MB instead of 468 MB!).
    """
    print(f"\nPackaging lightweight code-only delta patch to {out_zip}...")
    t0 = time.time()
    skip_dirs = {
        "torch", "PyQt6", "cv2", "fitz", "pymupdf", "model_assets",
        "numpy", "PIL", "scipy", "sklearn", "sympy", "llvmlite",
        "_tcl_data", "_tk_data", "tcl8", "tk8", "tzdata", "dateutil", "certifi"
    }
    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(src_dir):
            # Prune heavy engine & unchanging metadata directories inside _internal
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.endswith(".dist-info")]
            rel_root = os.path.relpath(root, src_dir)
            for f in files:
                fl = f.lower()
                # Skip duplicate versioned EXE alias (OhrHaKsav_vX.Y.Z.exe); updater clones OhrHaKsav.exe locally
                if rel_root == "." and fl.startswith("ohrhaksav_v") and fl.endswith(".exe"):
                    continue
                # Skip large binary DLLs inside _internal (unchanging runtime libraries)
                if rel_root != "." and fl.endswith((".dll", ".pyd", ".so")):
                    continue
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, src_dir)
                zf.write(full_path, rel_path)
    mb = os.path.getsize(out_zip) / (1024 * 1024)
    print(f"[SUCCESS] Delta patch created: {mb:.1f} MB in {time.time()-t0:.1f}s")


def update_version_checksums(installer_sha: str, patch_sha: str):
    """Injects verified SHA-256 checksums into both version.json and public/version.json."""
    for vpath in [os.path.join(BASE_DIR, "version.json"), os.path.join(BASE_DIR, "public", "version.json")]:
        if os.path.exists(vpath):
            try:
                with open(vpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["installerSha256"] = installer_sha
                data["patchSha256"] = patch_sha
                with open(vpath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f" -> Updated SHA-256 checksums in {os.path.relpath(vpath, BASE_DIR)}")
            except Exception as e:
                print(f"Warning: Could not update checksums in {vpath}: {e}")


def build(force_rebuild: bool = False):
    version = get_version()
    print("=" * 70)
    print(f"Building Ohr HaKsav v{version} Standalone Offline Package & Delta Patch")
    print("=" * 70)

    dist_dir = os.path.join(BASE_DIR, "dist")
    assets_dir = os.path.join(BASE_DIR, "assets")
    ico_path = os.path.join(assets_dir, "ohr_haksav.ico")
    app_output = os.path.join(dist_dir, "OhrHaKsav")
    app_exe = os.path.join(app_output, "OhrHaKsav.exe")
    payload_zip = os.path.join(dist_dir, "payload.zip")
    patch_zip = os.path.join(dist_dir, f"OhrHaKsav_Patch_v{version}.zip")
    setup_exe = os.path.join(dist_dir, "OhrHaKsav_Setup.exe")

    core_files = [
        os.path.join(BASE_DIR, "version.json"),
        os.path.join(BASE_DIR, "main.py"),
        os.path.join(BASE_DIR, "ui", "main_window.py"),
        os.path.join(BASE_DIR, "ui", "image_viewer.py"),
        os.path.join(BASE_DIR, "ui", "dictionary_dialog.py"),
        os.path.join(BASE_DIR, "ui", "learn_preview_dialog.py"),
        os.path.join(BASE_DIR, "ui", "export_dialog.py"),
        os.path.join(BASE_DIR, "ui", "text_editor.py"),
        os.path.join(BASE_DIR, "ui", "update_dialog.py"),
        os.path.join(BASE_DIR, "ui", "update_banner.py"),
        os.path.join(BASE_DIR, "ui", "help_dialog.py"),
        os.path.join(BASE_DIR, "ui", "about_dialog.py"),
        os.path.join(BASE_DIR, "ui", "splash_screen.py"),
        os.path.join(BASE_DIR, "ui", "theme.py"),
        os.path.join(BASE_DIR, "installer", "setup_gui.py"),
        os.path.join(BASE_DIR, "ui", "i18n.py"),
        os.path.join(BASE_DIR, "core", "learning_engine.py"),
        os.path.join(BASE_DIR, "core", "ocr_engine.py"),
        os.path.join(BASE_DIR, "core", "docx_exporter.py"),
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
        print(f"\n[1/4] Compiling OhrHaKsav.exe (v{version}) directory with optimizations & embedded version info...")
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
            "--hidden-import", "fitz",
            "--hidden-import", "docx",
            "--hidden-import", "core.hebocr.recognize",
            "--hidden-import", "core.hebocr.wordlm",
            "--hidden-import", "core.hebocr.lm",
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

        sign_executable(app_exe)
        versioned_app_exe = os.path.join(app_output, f"OhrHaKsav_v{version}.exe")
        shutil.copy2(app_exe, versioned_app_exe)
        print(f" -> Created version-labeled binary: {versioned_app_exe}")
    else:
        print(f"\n[1/4] Existing OhrHaKsav application up-to-date at: {app_output}")

    # 2. Package lightweight code-only delta patch zip
    print("\n[2/4] Building Lightweight Delta Patch...")
    create_delta_patch_zip(app_output, patch_zip)

    # 3. Package offline payload.zip
    if not os.path.exists(payload_zip) or os.path.getmtime(payload_zip) < os.path.getmtime(app_exe):
        create_payload_zip(app_output, payload_zip)
    else:
        print(f"\n[3/4] Existing payload.zip up-to-date ({os.path.getsize(payload_zip)/(1024*1024):.1f} MB)")

    # 4. Build Standalone Offline Setup Wizard with version in filename and embedded version resource
    setup_name = f"OhrHaKsav_Setup_v{version}"
    setup_versioned_exe = os.path.join(dist_dir, f"{setup_name}.exe")
    setup_version_info = generate_version_info(
        version, f"{setup_name}.exe",
        "Ohr HaKsav - Offline Setup Wizard",
        os.path.join(BASE_DIR, "setup_version_info.txt")
    )

    print(f"\n[4/4] Compiling {setup_name}.exe Self-Extracting Installer Wizard with embedded version resource...")
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
    sign_executable(setup_versioned_exe)

    shutil.copy2(setup_versioned_exe, setup_exe)
    print(f" -> Created compatibility alias: {setup_exe}")

    # Compute & embed SHA-256 cryptographic checksums into version.json & public/version.json
    installer_sha = compute_sha256(setup_versioned_exe)
    patch_sha = compute_sha256(patch_zip)
    print(f" -> Installer SHA-256: {installer_sha}")
    print(f" -> Delta Patch SHA-256: {patch_sha}")
    update_version_checksums(installer_sha, patch_sha)

    # Cleanup temporary version info files
    for vi_path in [app_version_info, setup_version_info]:
        if os.path.exists(vi_path):
            try:
                os.remove(vi_path)
            except Exception:
                pass

    # Deploy to custom staging directory
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

            shutil.copy2(setup_versioned_exe, os.path.join(target_drive, f"{setup_name}.exe"))
            shutil.copy2(setup_exe, os.path.join(target_drive, "OhrHaKsav_Setup.exe"))
            shutil.copy2(patch_zip, os.path.join(target_drive, f"OhrHaKsav_Patch_v{version}.zip"))
            print(f" -> Deployed {setup_name}.exe, OhrHaKsav_Setup.exe & OhrHaKsav_Patch_v{version}.zip")

            portable_zip = os.path.join(target_drive, f"OhrHaKsav-v{version}-Windows.zip")
            shutil.copy2(payload_zip, portable_zip)
            print(f" -> Deployed portable zip to {portable_zip}")

            shutil.copy2(os.path.join(BASE_DIR, "version.json"), os.path.join(target_drive, "version.json"))
            print(" -> Deployed version.json (with SHA-256 hashes) for offline update checks")

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
