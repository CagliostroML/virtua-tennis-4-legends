#!/usr/bin/env python3
"""
3D Head Sculpting & OBJ Round-Trip Tool for Virtua Tennis 4 (.sdo) Player Models.
Supports ALL 57 custom players across all 19 male & female SEGA base topologies
via automatic per-SDO anatomical landmark detection (pure Python + Pillow, zero numpy).

Usage:
  python tools/sculpt_sdo_head.py --all [--audit-sheet scratch/sculpt_57/sculpt_mesh_audit_8stars.png]
  python tools/sculpt_sdo_head.py --player 26_ALC
  python tools/sculpt_sdo_head.py --profile alcaraz --in <in.sdo> --out <out.sdo> [--render-diff <png>]
  python tools/sculpt_sdo_head.py --export-obj <in.sdo> <out.obj>
  python tools/sculpt_sdo_head.py --import-obj <in.sdo> <sculpted.obj> <out.sdo>
"""
import argparse
import io
import json
import math
import os
import re
import struct
import sys
from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import lzss_decompress
from compress_sega_lzss import lzss_compress_literal
from build_ee3_rackets import parse_vbs, parse_ibs
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image, replace_sdo_tex

MODEL_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Player", "Model")
FACE_WS_DIR = os.path.join(REPO_ROOT, "assets", "face_uv_workspace")


def _p(
    jaw_w=0.0, jaw_z=0.0, cheek_w=0.0, cheek_z=0.0,
    nose_z=0.0, nose_y=0.0, nose_w=0.0,
    chin_y=0.0, chin_w=0.0, chin_z=0.0,
    crown_y=0.0, temple_w=0.0,
    hair_y=0.0, hair_x=0.0,
    eye_spacing=0.0,
    hide_visor=False,
):
    return {
        "jaw_w": jaw_w, "jaw_z": jaw_z, "cheek_w": cheek_w, "cheek_z": cheek_z,
        "nose_z": nose_z, "nose_y": nose_y, "nose_w": nose_w,
        "chin_y": chin_y, "chin_w": chin_w, "chin_z": chin_z,
        "crown_y": crown_y, "temple_w": temple_w,
        "hair_y": hair_y, "hair_x": hair_x,
        "eye_spacing": eye_spacing,
        "hide_visor": hide_visor,
    }


# Tailored 3D anatomical sculpt profiles for ALL 57 custom players (relative to their SEGA donor base).
# Units: VT4 decimeters (0.05 = 5 mm). Displacements are smoothly clamped to <= 14.0 mm max.
HEAD_SCULPT_PROFILES = {
    # --- IDs 26..37 + 29_91 ---
    # 26_ALC (base DJV): shorter/rounder nose, fuller cheeks & wider jaw, compact chin, tighter buzz crop,
    # +3.2mm/eye outward eye_spacing (fixes narrow Djokovic eyes / "cejijunto" glabella!)
    "26_ALC":    _p(jaw_w=0.095, jaw_z=0.045, cheek_w=0.060, cheek_z=0.048, nose_z=-0.095, nose_y=0.040, nose_w=0.022, chin_y=0.052, chin_w=0.035, chin_z=0.024, crown_y=-0.065, temple_w=0.025, hair_y=-0.085, hair_x=-0.07, eye_spacing=0.032),
    # 27_SIN (base DJV): lean angular Italian jaw, slightly narrower cheeks, softer straight nose, slightly wider eyes than Djokovic
    "27_SIN":    _p(jaw_w=-0.035, jaw_z=-0.010, cheek_w=-0.030, cheek_z=-0.015, nose_z=-0.045, nose_y=0.015, nose_w=-0.010, chin_y=-0.015, chin_w=-0.015, chin_z=0.020, crown_y=0.035, temple_w=-0.015, hair_y=0.045, hair_x=0.04, eye_spacing=0.020),
    # 28_SAM (base EDB): classic Greek-American strong brow/nose, fuller jaw & chin than Edberg
    "28_SAM":    _p(jaw_w=0.055, jaw_z=0.025, cheek_w=0.030, cheek_z=0.020, nose_z=0.030, nose_y=-0.015, nose_w=0.015, chin_y=-0.010, chin_w=0.025, chin_z=0.025, crown_y=-0.020, temple_w=0.020, hair_y=-0.015, hair_x=0.02),
    # 29_91_AGA (base NAD): leaner jaw & cheekbones than Nadal, sharper nose, fuller 90s mullet volume
    "29_91_AGA": _p(jaw_w=-0.045, jaw_z=-0.015, cheek_w=-0.035, cheek_z=-0.010, nose_z=0.025, nose_y=-0.010, nose_w=-0.012, chin_y=0.015, chin_w=-0.015, chin_z=0.015, crown_y=-0.025, temple_w=-0.015, hair_y=0.035, hair_x=0.05),
    # 29_AG2 (base DJV): bald Agassi '06: wider strong jaw, slightly fuller cheeks, compact smooth skull, wider eyes than Djokovic
    "29_AG2":    _p(jaw_w=0.070, jaw_z=0.030, cheek_w=0.045, cheek_z=0.025, nose_z=-0.040, nose_y=0.015, nose_w=0.015, chin_y=0.025, chin_w=0.025, chin_z=0.025, crown_y=-0.055, temple_w=0.020, hair_y=0.0, hair_x=0.0, eye_spacing=0.024),
    # 30_BOR (base RAF): chiseled Nordic cheekbones, slightly narrower athletic jaw, straighter nose, iconic full headband hair
    "30_BOR":    _p(jaw_w=-0.035, jaw_z=0.015, cheek_w=0.040, cheek_z=0.025, nose_z=-0.035, nose_y=0.015, nose_w=-0.012, chin_y=0.015, chin_w=-0.010, chin_z=0.020, crown_y=-0.015, temple_w=0.015, hair_y=0.030, hair_x=0.04),
    # 31_MCE (base RAF): rounder cheeks, slightly softer jaw, shorter upturned nose, curly 80s hair volume
    "31_MCE":    _p(jaw_w=0.045, jaw_z=0.025, cheek_w=0.045, cheek_z=0.030, nose_z=-0.045, nose_y=0.025, nose_w=0.015, chin_y=0.020, chin_w=0.020, chin_z=0.010, crown_y=0.010, temple_w=0.015, hair_y=0.040, hair_x=0.05),
    # 32_GRA (base SHA): iconic aristocratic straighter/prominent nose, sleeker/narrower athletic jaw than Sharapova
    "32_GRA":    _p(jaw_w=-0.035, jaw_z=-0.010, cheek_w=-0.020, cheek_z=0.010, nose_z=0.055, nose_y=-0.025, nose_w=-0.010, chin_y=-0.015, chin_w=-0.015, chin_z=0.020, crown_y=-0.015, temple_w=-0.010, hair_y=0.0, hair_x=0.0),
    # 33_SER (base WIL): fuller rounder cheeks & stronger jaw than Venus base, slightly softer/wider nose
    "33_SER":    _p(jaw_w=0.065, jaw_z=0.035, cheek_w=0.055, cheek_z=0.040, nose_z=-0.025, nose_y=0.015, nose_w=0.022, chin_y=0.025, chin_w=0.025, chin_z=0.015, crown_y=-0.020, temple_w=0.020, hair_y=0.0, hair_x=0.0),
    # 34_SWI (base WOZ): sleeker narrower Polish jawline, slightly sharper chin & nose than Wozniacki
    "34_SWI":    _p(jaw_w=-0.045, jaw_z=-0.015, cheek_w=-0.030, cheek_z=-0.010, nose_z=0.025, nose_y=-0.010, nose_w=-0.012, chin_y=-0.015, chin_w=-0.020, chin_z=0.018, crown_y=-0.015, temple_w=-0.015, hair_y=0.0, hair_x=0.0),
    # 35_SAB (base KUZ): stronger, more sculpted Slavic cheekbones, slightly longer/stronger jaw & chin than Kuznetsova
    "35_SAB":    _p(jaw_w=0.035, jaw_z=0.020, cheek_w=0.045, cheek_z=0.032, nose_z=-0.025, nose_y=0.010, nose_w=-0.010, chin_y=-0.025, chin_w=0.015, chin_z=0.025, crown_y=0.015, temple_w=0.015, hair_y=0.0, hair_x=0.0),
    # 36_KUE (base RAF): leaner longer Brazilian face, slightly narrower jaw, longer nose, fuller curly hair
    "36_KUE":    _p(jaw_w=-0.045, jaw_z=-0.015, cheek_w=-0.025, cheek_z=-0.010, nose_z=0.030, nose_y=-0.015, nose_w=0.010, chin_y=-0.025, chin_w=-0.015, chin_z=0.015, crown_y=0.015, temple_w=-0.010, hair_y=0.040, hair_x=0.05),
    # 37_NAV (base CHA): stronger athletic jaw & chin, slightly sharper straight nose than Chakvetadze
    "37_NAV":    _p(jaw_w=0.045, jaw_z=0.020, cheek_w=0.020, cheek_z=0.015, nose_z=0.035, nose_y=-0.015, nose_w=-0.010, chin_y=-0.015, chin_w=0.020, chin_z=0.025, crown_y=-0.020, temple_w=0.015, hair_y=-0.035, hair_x=-0.03),

    # --- Page 3 IDs 38..58 ---
    # 38_WAW (base HAS): broader strong Swiss jaw & fuller cheeks, slightly shorter nose & compact head
    "38_WAW":    _p(jaw_w=0.075, jaw_z=0.035, cheek_w=0.050, cheek_z=0.035, nose_z=-0.040, nose_y=0.020, nose_w=0.018, chin_y=0.020, chin_w=0.030, chin_z=0.020, crown_y=-0.030, temple_w=0.025, hair_y=-0.025, hair_x=-0.02),
    # 39_MED (base DEL): leaner narrower Russian face, sharper cheekbones, slightly taller receding forehead, tighter hair
    "39_MED":    _p(jaw_w=-0.055, jaw_z=-0.020, cheek_w=-0.035, cheek_z=-0.015, nose_z=-0.035, nose_y=0.010, nose_w=-0.015, chin_y=-0.015, chin_w=-0.020, chin_z=0.015, crown_y=0.030, temple_w=-0.020, hair_y=-0.045, hair_x=-0.04),
    # 40_ZVE (base DEL): sleeker angular German jaw, higher cheekbones, straighter nose, slightly fuller crown hair
    "40_ZVE":    _p(jaw_w=-0.030, jaw_z=0.010, cheek_w=0.025, cheek_z=0.018, nose_z=-0.025, nose_y=0.015, nose_w=-0.010, chin_y=-0.010, chin_w=0.010, chin_z=0.022, crown_y=0.015, temple_w=0.010, hair_y=0.035, hair_x=0.03),
    # 41_TSI (base GON): slightly narrower sculpted Greek jaw, straighter nose, longer flowing hair volume
    "41_TSI":    _p(jaw_w=-0.040, jaw_z=-0.010, cheek_w=-0.015, cheek_z=0.010, nose_z=0.025, nose_y=-0.015, nose_w=-0.012, chin_y=-0.020, chin_w=-0.015, chin_z=0.018, crown_y=0.015, temple_w=-0.010, hair_y=0.035, hair_x=0.04),
    # 42_THI (base HAS): fuller athletic cheeks & stronger square jaw than Haas, shorter nose
    "42_THI":    _p(jaw_w=0.055, jaw_z=0.028, cheek_w=0.040, cheek_z=0.030, nose_z=-0.035, nose_y=0.018, nose_w=0.012, chin_y=0.015, chin_w=0.020, chin_z=0.018, crown_y=-0.020, temple_w=0.015, hair_y=-0.015, hair_x=0.0),
    # 43_KYR (base DEL): rounder fuller cheeks, softer jaw, slightly wider nose, tighter fade hair
    "43_KYR":    _p(jaw_w=0.040, jaw_z=0.025, cheek_w=0.045, cheek_z=0.035, nose_z=-0.045, nose_y=0.022, nose_w=0.020, chin_y=0.020, chin_w=0.015, chin_z=0.010, crown_y=-0.025, temple_w=0.015, hair_y=-0.050, hair_x=-0.05),
    # 44_HEW (base ROD): leaner narrower Aussie jaw & cheeks than Roddick, slightly sharper chin
    "44_HEW":    _p(jaw_w=-0.045, jaw_z=-0.015, cheek_w=-0.030, cheek_z=-0.010, nose_z=-0.020, nose_y=0.012, nose_w=-0.010, chin_y=0.015, chin_w=-0.018, chin_z=0.015, crown_y=-0.015, temple_w=-0.015, hair_y=0.0, hair_x=0.0),
    # 45_SAF (base DEL): strong wide Russian jawline, prominent cheekbones, slightly shorter straight nose
    "45_SAF":    _p(jaw_w=0.060, jaw_z=0.030, cheek_w=0.040, cheek_z=0.025, nose_z=-0.035, nose_y=0.015, nose_w=0.012, chin_y=0.010, chin_w=0.025, chin_z=0.025, crown_y=-0.020, temple_w=0.020, hair_y=-0.020, hair_x=-0.02),
    # 46_TSO (base MON): fuller broader jaw & cheeks (Ali-like build), slightly wider nose & stronger chin than Monfils
    "46_TSO":    _p(jaw_w=0.075, jaw_z=0.038, cheek_w=0.055, cheek_z=0.040, nose_z=-0.025, nose_y=0.015, nose_w=0.022, chin_y=0.020, chin_w=0.030, chin_z=0.022, crown_y=-0.025, temple_w=0.020, hair_y=-0.040, hair_x=-0.03),
    # 47_FRR (base HAS): leaner sculpted Spanish face, slightly narrower jaw, straighter nose
    "47_FRR":    _p(jaw_w=-0.035, jaw_z=-0.010, cheek_w=-0.025, cheek_z=-0.010, nose_z=0.020, nose_y=-0.010, nose_w=-0.010, chin_y=0.010, chin_w=-0.015, chin_z=0.015, crown_y=-0.015, temple_w=-0.010, hair_y=-0.015, hair_x=-0.01),
    # 48_MOY (base NAD): slightly longer/leaner face & sharper jaw than Nadal, straighter nose
    "48_MOY":    _p(jaw_w=-0.035, jaw_z=-0.010, cheek_w=-0.025, cheek_z=-0.010, nose_z=0.025, nose_y=-0.015, nose_w=-0.010, chin_y=-0.020, chin_w=-0.010, chin_z=0.018, crown_y=0.010, temple_w=-0.010, hair_y=-0.015, hair_x=-0.01),
    # 49_FER (base KOH): slightly narrower intense Spanish jaw, sharper nose & chin than Kohlschreiber
    "49_FER":    _p(jaw_w=-0.030, jaw_z=0.010, cheek_w=-0.020, cheek_z=0.010, nose_z=0.025, nose_y=-0.010, nose_w=-0.010, chin_y=-0.015, chin_w=0.010, chin_z=0.020, crown_y=-0.015, temple_w=-0.010, hair_y=-0.020, hair_x=-0.02),
    # 50_NAL (base KOH): fuller rounder Argentine cheeks & broader strong jaw
    "50_NAL":    _p(jaw_w=0.070, jaw_z=0.038, cheek_w=0.055, cheek_z=0.042, nose_z=-0.035, nose_y=0.015, nose_w=0.016, chin_y=0.020, chin_w=0.028, chin_z=0.018, crown_y=-0.020, temple_w=0.020, hair_y=-0.025, hair_x=-0.02),
    # 51_LEN (base EDB): chiseled narrow Czech face, sharp cheekbones, slightly longer aquiline nose
    "51_LEN":    _p(jaw_w=-0.045, jaw_z=-0.015, cheek_w=-0.025, cheek_z=-0.015, nose_z=0.040, nose_y=-0.020, nose_w=-0.015, chin_y=-0.020, chin_w=-0.015, chin_z=0.022, crown_y=0.015, temple_w=-0.015, hair_y=-0.020, hair_x=-0.02),
    # 52_CON (base BEC): leaner narrower face & sharper chin than Becker, classic fuller 70s bob hair
    "52_CON":    _p(jaw_w=-0.050, jaw_z=-0.018, cheek_w=-0.035, cheek_z=-0.015, nose_z=0.020, nose_y=-0.010, nose_w=-0.012, chin_y=-0.015, chin_w=-0.015, chin_z=0.020, crown_y=-0.010, temple_w=-0.015, hair_y=0.035, hair_x=0.05),
    # 53_VIL (base RAF): strong Argentine jaw & cheekbones, slightly prominent nose, full flowing hair
    "53_VIL":    _p(jaw_w=0.050, jaw_z=0.025, cheek_w=0.035, cheek_z=0.022, nose_z=0.030, nose_y=-0.015, nose_w=0.012, chin_y=-0.010, chin_w=0.022, chin_z=0.022, crown_y=-0.010, temple_w=0.015, hair_y=0.030, hair_x=0.04),
    # 54_IVN (base DEL): long lean Croatian face, sharper nose & chin than Del Potro
    "54_IVN":    _p(jaw_w=-0.040, jaw_z=-0.015, cheek_w=-0.030, cheek_z=-0.012, nose_z=0.035, nose_y=-0.020, nose_w=-0.012, chin_y=-0.025, chin_w=-0.015, chin_z=0.020, crown_y=0.015, temple_w=-0.010, hair_y=-0.015, hair_x=-0.01),
    # 55_EVE (base CHA): classic refined cheekbones, slightly softer chin & shorter delicate nose
    "55_EVE":    _p(jaw_w=-0.025, jaw_z=0.010, cheek_w=0.025, cheek_z=0.020, nose_z=-0.035, nose_y=0.018, nose_w=-0.012, chin_y=0.015, chin_w=-0.012, chin_z=0.010, crown_y=-0.010, temple_w=0.010, hair_y=0.0, hair_x=0.0),
    # 56_SEL (base IVA): slightly fuller youthful cheeks & stronger chin than Ivanovic, shorter nose, remove visor
    "56_SEL":    _p(jaw_w=0.035, jaw_z=0.020, cheek_w=0.040, cheek_z=0.028, nose_z=-0.030, nose_y=0.015, nose_w=0.010, chin_y=0.010, chin_w=0.018, chin_z=0.022, crown_y=-0.015, temple_w=0.010, hair_y=0.0, hair_x=0.0, hide_visor=True),
    # 57_HEN (base WOZ): leaner narrower Belgian face, more sculpted cheekbones & sharper chin than Wozniacki
    "57_HEN":    _p(jaw_w=-0.050, jaw_z=-0.018, cheek_w=-0.030, cheek_z=-0.010, nose_z=0.020, nose_y=-0.010, nose_w=-0.012, chin_y=-0.015, chin_w=-0.020, chin_z=0.018, crown_y=-0.020, temple_w=-0.015, hair_y=0.0, hair_x=0.0),
    # 58_MUG (base IVA): fuller Spanish cheeks & slightly stronger jaw, slightly shorter nose than Ivanovic, remove visor
    "58_MUG":    _p(jaw_w=0.045, jaw_z=0.025, cheek_w=0.045, cheek_z=0.032, nose_z=-0.035, nose_y=0.018, nose_w=0.012, chin_y=0.015, chin_w=0.020, chin_z=0.015, crown_y=-0.015, temple_w=0.015, hair_y=0.0, hair_x=0.0, hide_visor=True),

    # --- Page 4 IDs 59..81 ---
    # 59_SHE (base MON): fuller athletic American jaw & cheeks, slightly shorter nose, fuller curly top
    "59_SHE":    _p(jaw_w=0.065, jaw_z=0.032, cheek_w=0.048, cheek_z=0.035, nose_z=-0.035, nose_y=0.018, nose_w=0.018, chin_y=0.020, chin_w=0.025, chin_z=0.020, crown_y=-0.015, temple_w=0.020, hair_y=0.030, hair_x=0.03),
    # 60_RUB (base FED): leaner narrower jaw & cheeks than Federer, shorter nose, fuller wavy top hair
    "60_RUB":    _p(jaw_w=-0.045, jaw_z=-0.015, cheek_w=-0.030, cheek_z=-0.010, nose_z=-0.055, nose_y=0.022, nose_w=-0.012, chin_y=0.015, chin_w=-0.015, chin_z=0.010, crown_y=0.015, temple_w=-0.010, hair_y=0.040, hair_x=0.04),
    # 61_RUU (base FED): wider squarer Nordic jaw & fuller cheeks than Federer, shorter straight nose
    "61_RUU":    _p(jaw_w=0.060, jaw_z=0.030, cheek_w=0.040, cheek_z=0.028, nose_z=-0.065, nose_y=0.025, nose_w=0.010, chin_y=0.020, chin_w=0.025, chin_z=0.022, crown_y=-0.020, temple_w=0.020, hair_y=-0.020, hair_x=-0.02),
    # 62_FRI (base DEL): sleeker chiseled California jaw, higher cheekbones, shorter nose
    "62_FRI":    _p(jaw_w=0.030, jaw_z=0.018, cheek_w=0.035, cheek_z=0.022, nose_z=-0.040, nose_y=0.020, nose_w=-0.010, chin_y=0.015, chin_w=0.018, chin_z=0.020, crown_y=-0.015, temple_w=0.015, hair_y=-0.015, hair_x=-0.01),
    # 63_GAU (base WIL): younger rounder cheeks & softer compact jaw/chin than Venus, delicate shorter nose
    "63_GAU":    _p(jaw_w=0.025, jaw_z=0.020, cheek_w=0.045, cheek_z=0.035, nose_z=-0.045, nose_y=0.022, nose_w=0.012, chin_y=0.030, chin_w=-0.010, chin_z=0.010, crown_y=-0.025, temple_w=0.010, hair_y=0.0, hair_x=0.0),
    # 64_RYB (base SHA): slightly fuller cheeks & softer oval jaw than Sharapova, delicate straight nose
    "64_RYB":    _p(jaw_w=0.025, jaw_z=0.015, cheek_w=0.035, cheek_z=0.025, nose_z=-0.030, nose_y=0.015, nose_w=-0.010, chin_y=0.015, chin_w=-0.010, chin_z=0.010, crown_y=-0.010, temple_w=0.010, hair_y=0.0, hair_x=0.0),
    # 65_BAD (base IVA): fuller Spanish cheekbones & slightly broader/softer youthful jaw, shorter rounder nose than Ivanovic, remove visor
    "65_BAD":    _p(jaw_w=0.045, jaw_z=0.025, cheek_w=0.050, cheek_z=0.035, nose_z=-0.045, nose_y=0.022, nose_w=0.012, chin_y=0.020, chin_w=0.015, chin_z=0.015, crown_y=-0.020, temple_w=0.015, hair_y=0.0, hair_x=0.0, hide_visor=True),
    # 66_HAL (base CHA): compact rounder Romanian cheeks & shorter delicate nose/chin
    "66_HAL":    _p(jaw_w=0.035, jaw_z=0.020, cheek_w=0.045, cheek_z=0.032, nose_z=-0.040, nose_y=0.020, nose_w=-0.010, chin_y=0.025, chin_w=0.010, chin_z=0.012, crown_y=-0.020, temple_w=0.012, hair_y=0.0, hair_x=0.0),
    # 67_COR (base KOH): leaner narrower Argentine face, slightly sharper chin & nose
    "67_COR":    _p(jaw_w=-0.040, jaw_z=-0.015, cheek_w=-0.025, cheek_z=-0.010, nose_z=0.020, nose_y=-0.010, nose_w=-0.012, chin_y=-0.015, chin_w=-0.015, chin_z=0.015, crown_y=-0.015, temple_w=-0.010, hair_y=-0.020, hair_x=-0.02),
    # 68_GAS (base HAS): rounder French cheeks, slightly shorter nose & softer jaw than Haas
    "68_GAS":    _p(jaw_w=0.035, jaw_z=0.020, cheek_w=0.040, cheek_z=0.028, nose_z=-0.035, nose_y=0.018, nose_w=0.010, chin_y=0.018, chin_w=0.015, chin_z=0.012, crown_y=-0.020, temple_w=0.012, hair_y=-0.020, hair_x=-0.02),
    # 69_NIS (base KOH): softer East Asian cheekbones, shorter flatter nose bridge, compact chin
    "69_NIS":    _p(jaw_w=0.040, jaw_z=0.022, cheek_w=0.055, cheek_z=0.035, nose_z=-0.075, nose_y=0.028, nose_w=0.018, chin_y=0.025, chin_w=0.015, chin_z=0.010, crown_y=-0.025, temple_w=0.018, hair_y=-0.015, hair_x=-0.01),
    # 70_SOD (base DEL): strong wide Swedish jaw & high cheekbones, shorter straight nose
    "70_SOD":    _p(jaw_w=0.065, jaw_z=0.030, cheek_w=0.045, cheek_z=0.028, nose_z=-0.045, nose_y=0.020, nose_w=0.012, chin_y=0.015, chin_w=0.028, chin_z=0.025, crown_y=-0.020, temple_w=0.022, hair_y=-0.030, hair_x=-0.03),
    # 71_BER (base DEL): broad square Czech jaw, slightly fuller cheeks, compact straight nose
    "71_BER":    _p(jaw_w=0.070, jaw_z=0.032, cheek_w=0.048, cheek_z=0.030, nose_z=-0.040, nose_y=0.018, nose_w=0.015, chin_y=0.020, chin_w=0.028, chin_z=0.022, crown_y=-0.025, temple_w=0.020, hair_y=-0.035, hair_x=-0.03),
    # 72_CHN (base KOH): youthful fuller Asian cheekbones, flatter shorter nose, softer compact jaw
    "72_CHN":    _p(jaw_w=0.045, jaw_z=0.025, cheek_w=0.060, cheek_z=0.038, nose_z=-0.080, nose_y=0.030, nose_w=0.020, chin_y=0.028, chin_w=0.018, chin_z=0.010, crown_y=-0.025, temple_w=0.020, hair_y=-0.020, hair_x=-0.01),
    # 73_RIO (base RAF): leaner angular Chilean face, slightly sharper cheekbones & chin
    "73_RIO":    _p(jaw_w=-0.035, jaw_z=-0.012, cheek_w=-0.020, cheek_z=-0.010, nose_z=-0.025, nose_y=0.015, nose_w=-0.010, chin_y=0.010, chin_w=-0.015, chin_z=0.015, crown_y=-0.015, temple_w=-0.010, hair_y=0.020, hair_x=0.02),
    # 74_MUS (base HAS): strong muscular Austrian jaw & chin, slightly broader face
    "74_MUS":    _p(jaw_w=0.065, jaw_z=0.032, cheek_w=0.040, cheek_z=0.025, nose_z=-0.025, nose_y=0.012, nose_w=0.014, chin_y=0.010, chin_w=0.028, chin_z=0.025, crown_y=-0.020, temple_w=0.020, hair_y=0.015, hair_x=0.02),
    # 75_BRU (base EDB): leaner Spanish face, slightly more prominent nose & narrower jaw than Edberg
    "75_BRU":    _p(jaw_w=-0.035, jaw_z=-0.012, cheek_w=-0.025, cheek_z=-0.010, nose_z=0.030, nose_y=-0.015, nose_w=-0.010, chin_y=-0.015, chin_w=-0.012, chin_z=0.018, crown_y=-0.015, temple_w=-0.010, hair_y=-0.020, hair_x=-0.02),
    # 76_CRT (base HAS): classic Mediterranean oval face, slightly fuller cheeks & shorter nose
    "76_CRT":    _p(jaw_w=0.035, jaw_z=0.018, cheek_w=0.032, cheek_z=0.022, nose_z=-0.030, nose_y=0.015, nose_w=0.010, chin_y=0.015, chin_w=0.015, chin_z=0.015, crown_y=-0.018, temple_w=0.012, hair_y=-0.020, hair_x=-0.02),
    # 77_WLD (base FED): leaner narrower Swedish jaw & shorter straighter nose than Federer
    "77_WLD":    _p(jaw_w=-0.035, jaw_z=-0.012, cheek_w=-0.020, cheek_z=-0.010, nose_z=-0.050, nose_y=0.020, nose_w=-0.012, chin_y=0.015, chin_w=-0.012, chin_z=0.015, crown_y=-0.015, temple_w=-0.010, hair_y=0.020, hair_x=0.02),
    # 78_LAV (base BEC): leaner rugged Aussie face, narrower jaw than Becker, slightly stronger nose & chin
    "78_LAV":    _p(jaw_w=-0.045, jaw_z=-0.015, cheek_w=-0.030, cheek_z=-0.012, nose_z=0.025, nose_y=-0.012, nose_w=-0.010, chin_y=-0.010, chin_w=-0.012, chin_z=0.022, crown_y=-0.020, temple_w=-0.015, hair_y=-0.025, hair_x=-0.02),
    # 79_ASV (base CHA): compact rounder Spanish cheeks & jaw, shorter nose
    "79_ASV":    _p(jaw_w=0.040, jaw_z=0.022, cheek_w=0.048, cheek_z=0.032, nose_z=-0.035, nose_y=0.018, nose_w=0.012, chin_y=0.022, chin_w=0.015, chin_z=0.012, crown_y=-0.020, temple_w=0.015, hair_y=0.0, hair_x=0.0),
    # 80_CMT (base ROB): slightly longer sculpted Spanish face, stronger chin & straighter nose than Robson
    "80_CMT":    _p(jaw_w=-0.025, jaw_z=0.010, cheek_w=-0.015, cheek_z=0.010, nose_z=0.028, nose_y=-0.012, nose_w=-0.010, chin_y=-0.018, chin_w=0.010, chin_z=0.020, crown_y=-0.010, temple_w=-0.010, hair_y=0.0, hair_x=0.0),
    # 81_CLI (base ROB): fuller Belgian cheeks & rounder athletic jaw, softer shorter nose than Robson
    "81_CLI":    _p(jaw_w=0.050, jaw_z=0.028, cheek_w=0.052, cheek_z=0.036, nose_z=-0.038, nose_y=0.020, nose_w=0.012, chin_y=0.020, chin_w=0.020, chin_z=0.014, crown_y=-0.018, temple_w=0.015, hair_y=0.0, hair_x=0.0),
}


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 == edge0:
        return 1.0 if x >= edge1 else 0.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _gauss3(x: float, y: float, z: float, cx: float, cy: float, cz: float, rx: float, ry: float, rz: float) -> float:
    dx = (x - cx) / rx
    dy = (y - cy) / ry
    dz = (z - cz) / rz
    d2 = dx * dx + dy * dy + dz * dz
    if d2 > 9.0:
        return 0.0
    return math.exp(-0.5 * d2)


def _strip_to_tris(inds: list[int]) -> list[tuple[int, int, int]]:
    tris = []
    for i in range(len(inds) - 2):
        a, b, c = inds[i], inds[i + 1], inds[i + 2]
        if a == b or b == c or a == c:
            continue
        tris.append((a, c, b) if (i & 1) else (a, b, c))
    return tris


def _read_vb_xyz_nrm(dec: bytes, vb: dict, stream_idx: int = 0):
    s = vb["streams"][stream_idx]
    base = vb["data_off"] + s["off"]
    st = s["stride"]
    nv = s["nverts"]
    xyz = []
    nrm = []
    for i in range(nv):
        off = base + i * st
        xyz.append(struct.unpack_from(">3f", dec, off))
        nrm.append(struct.unpack_from(">4h", dec, off + 12))
    return xyz, nrm


def _write_vb_xyz_nrm(dec_ba: bytearray, vb: dict, xyz: list, nrm: list, stream_idx: int = 0):
    s = vb["streams"][stream_idx]
    base = vb["data_off"] + s["off"]
    st = s["stride"]
    assert len(xyz) == s["nverts"] and len(nrm) == s["nverts"]
    for i in range(s["nverts"]):
        off = base + i * st
        x, y, z = xyz[i]
        assert math.isfinite(x) and math.isfinite(y) and math.isfinite(z), f"Non-finite vertex {i}"
        struct.pack_into(">3f", dec_ba, off, x, y, z)
        nx, ny, nz, nw = nrm[i]
        struct.pack_into(">4h", dec_ba, off + 12,
                         max(-32767, min(32767, int(nx))),
                         max(-32767, min(32767, int(ny))),
                         max(-32767, min(32767, int(nz))),
                         int(nw))


def detect_face_landmarks(dec: bytes, vbs: dict) -> dict:
    """Automatically detect exact eye, nose, chin, crown, and neck-lock coordinates in world space
    from any male or female SEGA base .sdo."""
    face_vb = vbs["Face-VB"]
    pts, _ = _read_vb_xyz_nrm(dec, face_vb)
    crown_y = max(p[1] for p in pts)

    # Eyes from Eyelash-VB (always present in same world space as Face-VB across all 19 bases)
    lash_vb = vbs.get("Eyelash-VB")
    if lash_vb:
        lpts, _ = _read_vb_xyz_nrm(dec, lash_vb)
        eye_x = sum(abs(p[0]) for p in lpts) / len(lpts)
        eye_y = sum(p[1] for p in lpts) / len(lpts)
        eye_z = sum(p[2] for p in lpts) / len(lpts)
    else:
        eye_x, eye_y, eye_z = 0.30, crown_y - 1.15, 1.20

    # Nose tip: max Z on centerline slightly below eyes
    nose_cands = [p for p in pts if abs(p[0]) < 0.16 and (eye_y - 0.65) < p[1] < (eye_y + 0.05)]
    nose = max(nose_cands, key=lambda p: p[2]) if nose_cands else max(pts, key=lambda p: p[2])

    # Chin tip: max Z on centerline 0.38..0.82 dm below nose tip
    chin_cands = [p for p in pts if abs(p[0]) < 0.16 and (nose[1] - 0.82) < p[1] < (nose[1] - 0.36)]
    chin = max(chin_cands, key=lambda p: p[2]) if chin_cands else (0.0, nose[1] - 0.56, nose[2] - 0.22)

    # Mouth center: midpoint between nose and chin
    mouth_y = nose[1] * 0.48 + chin[1] * 0.52
    mouth_z = chin[2]

    # Strict neck-seam lock: 0.28 dm below chin (always cleanly above neck/collar seam!)
    neck_lock_y = chin[1] - 0.28
    return {
        "eye_x": eye_x, "eye_y": eye_y, "eye_z": eye_z,
        "nose_y": nose[1], "nose_z": nose[2],
        "chin_y": chin[1], "chin_z": chin[2],
        "mouth_y": mouth_y, "mouth_z": mouth_z,
        "crown_y": crown_y, "neck_lock_y": neck_lock_y,
    }


def compute_face_displacement(x: float, y: float, z: float, lm: dict, prof: dict) -> tuple[float, float, float]:
    """Unified landmark-anchored parametric face morph with strict neck-lock, eye-lock, mouth-damper,
    and smooth 14.0 mm displacement clamp."""
    neck_y = lm["neck_lock_y"]
    neck_gate = _smoothstep(neck_y, neck_y + 0.22, y)
    if neck_gate <= 0.0:
        return (0.0, 0.0, 0.0)

    # Eye-socket safety lock (zero displacement on eyelids/sockets -> zero eyeball/eyelash clipping)
    ex, ey, ez = lm["eye_x"], lm["eye_y"], lm["eye_z"]
    eye_l = _gauss3(x, y, z, -ex, ey, ez, 0.17, 0.11, 0.22)
    eye_r = _gauss3(x, y, z, +ex, ey, ez, 0.17, 0.11, 0.22)
    eye_safe = max(0.0, 1.0 - min(1.0, (eye_l + eye_r) * 1.20))

    # Mouth aperture damper (preserves lip/teeth alignment)
    mouth_g = _gauss3(x, y, z, 0.0, lm["mouth_y"], lm["mouth_z"], 0.24, 0.11, 0.20)
    mouth_safe = max(0.15, 1.0 - 0.85 * mouth_g)

    ny, nz = lm["nose_y"], lm["nose_z"]
    cy, cz = lm["chin_y"], lm["chin_z"]
    crown_y = lm["crown_y"]

    dx = dy = dz = 0.0

    # A. Nose
    nose_tip_g = _gauss3(x, y, z, 0.0, ny + 0.02, nz - 0.08, 0.18, 0.18, 0.24)
    nose_bridge_g = _gauss3(x, y, z, 0.0, ny + 0.22, nz - 0.14, 0.14, 0.18, 0.22)
    dz += prof["nose_z"] * nose_tip_g + (prof["nose_z"] * 0.45) * nose_bridge_g
    dy += prof["nose_y"] * nose_tip_g
    nostril_g = _gauss3(abs(x), y, z, 0.11, ny - 0.01, nz - 0.16, 0.11, 0.11, 0.20)
    dx += (prof["nose_w"] if x >= 0 else -prof["nose_w"]) * nostril_g * _smoothstep(0.02, 0.08, abs(x))

    # B. Jaw & Masseter
    jaw_g = _gauss3(abs(x), y, z, 0.48, cy + 0.18, cz - 0.68, 0.34, 0.30, 0.58)
    dx += (prof["jaw_w"] if x >= 0 else -prof["jaw_w"]) * jaw_g * _smoothstep(0.05, 0.25, abs(x))
    dz += prof["jaw_z"] * jaw_g * _smoothstep(cz - 1.15, cz - 0.60, z)

    # C. Cheeks / Mid-face
    cheek_g = _gauss3(abs(x), y, z, 0.46, ny - 0.02, nz - 0.72, 0.28, 0.24, 0.42)
    dx += (prof["cheek_w"] if x >= 0 else -prof["cheek_w"]) * cheek_g * _smoothstep(0.08, 0.26, abs(x))
    dz += prof["cheek_z"] * cheek_g * _smoothstep(nz - 1.20, nz - 0.65, z)

    # D. Chin
    chin_g = _gauss3(x, y, z, 0.0, cy - 0.02, cz - 0.14, 0.28, 0.20, 0.36)
    dy += prof["chin_y"] * chin_g
    dx += (prof["chin_w"] if x >= 0 else -prof["chin_w"]) * chin_g * _smoothstep(0.02, 0.14, abs(x))
    dz += prof["chin_z"] * chin_g

    # E. Crown / Forehead & Temples
    crown_g = _smoothstep(ey + 0.26, crown_y - 0.05, y)
    dy += prof["crown_y"] * crown_g
    temple_g = _gauss3(abs(x), y, z, 0.60, ey + 0.35, ez - 0.62, 0.25, 0.35, 0.55)
    dx += (prof["temple_w"] if x >= 0 else -prof["temple_w"]) * temple_g

    gate = neck_gate * eye_safe * mouth_safe
    dx *= gate; dy *= gate; dz *= gate

    # F. Symmetric eye_spacing shift (moves eye sockets, eyelids & inner eyebrows/glabella
    # outward by exact +-eye_spacing so eyes + eyelashes + sockets stay 100% locked together
    # with zero clipping and no "cejijunto" inner-brow pinch!)
    esp = prof.get("eye_spacing", 0.0)
    if abs(esp) > 1e-5:
        # Weight = 1.0 on the eye sockets/eyelids, smoothly feathering across eyebrows/glabella/outer orbital rim
        sock_w = min(1.0, (eye_l + eye_r) * 1.45)
        brow_g = _gauss3(abs(x), y, z, ex, ey + 0.14, ez + 0.04, 0.24, 0.16, 0.28)
        eye_w = max(sock_w, brow_g) * _smoothstep(0.025, 0.11, abs(x)) * neck_gate
        dx += (esp if x >= 0 else -esp) * eye_w

    # Hard anatomical safety clamp at 14.0 mm (0.140 dm)
    mag = math.sqrt(dx * dx + dy * dy + dz * dz)
    if mag > 0.140:
        k = 0.140 / mag
        dx *= k; dy *= k; dz *= k
    return (dx, dy, dz)


def _shift_eye_bones(dec_ba: bytearray, eye_spacing: float) -> int:
    """Shift LeftEye_zero & RightEye_zero bone Translations symmetrically outward by eye_spacing
    (preserving each eyeball's exact local rotation pivot for looking left/right/up/down)."""
    p0 = dec_ba.find(b"Scene_Root\x00")
    if p0 < 0 or abs(eye_spacing) < 1e-5:
        return 0
    pos_map = {}
    for bone in (b"LeftEye_zero", b"RightEye_zero"):
        idx = dec_ba.find(bone + b"\x00", p0)
        if idx < 0:
            continue
        nxt = dec_ba.find(b"\x04Node", idx)
        chunk = dec_ba[idx : nxt if nxt > idx else idx + 512]
        m = re.search(b"Parameter.Translation\x07Variant\x02", chunk)
        if m:
            tpos = idx + m.end()
            pos_map[bone] = (tpos, list(struct.unpack_from(">3f", dec_ba, tpos)))
    if len(pos_map) != 2:
        return 0
    lpos, lv = pos_map[b"LeftEye_zero"]
    rpos, rv = pos_map[b"RightEye_zero"]
    # Find the symmetric lateral axis (opposite signs between LeftEye_zero and RightEye_zero)
    lat_axis = max(range(3), key=lambda a: abs(lv[a] - rv[a]))
    lv[lat_axis] += (-eye_spacing if lv[lat_axis] < 0 else eye_spacing)
    rv[lat_axis] += (-eye_spacing if rv[lat_axis] < 0 else eye_spacing)
    struct.pack_into(">3f", dec_ba, lpos, *lv)
    struct.pack_into(">3f", dec_ba, rpos, *rv)
    return 2


def _recalc_blended_normals(xyz: list, orig_nrm: list, inds: list[int], blend: float = 0.45):
    n = len(xyz)
    acc = [[0.0, 0.0, 0.0] for _ in range(n)]
    for a, b, c in _strip_to_tris(inds):
        if a >= n or b >= n or c >= n:
            continue
        ax, ay, az = xyz[a]; bx, by, bz = xyz[b]; cx, cy, cz = xyz[c]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx = uy * vz - uz * vy; ny = uz * vx - ux * vz; nz = ux * vy - uy * vx
        acc[a][0] += nx; acc[a][1] += ny; acc[a][2] += nz
        acc[b][0] += nx; acc[b][1] += ny; acc[b][2] += nz
        acc[c][0] += nx; acc[c][1] += ny; acc[c][2] += nz

    out = []
    for i in range(n):
        onx, ony, onz, onw = orig_nrm[i]
        olen = math.sqrt(onx * onx + ony * ony + onz * onz) or 16384.0
        ox, oy, oz = onx / olen, ony / olen, onz / olen
        cx, cy, cz = acc[i]
        clen = math.sqrt(cx * cx + cy * cy + cz * cz)
        if clen > 1e-9:
            cx /= clen; cy /= clen; cz /= clen
            if cx * ox + cy * oy + cz * oz < 0.0:
                cx, cy, cz = -cx, -cy, -cz
            mx = ox * (1.0 - blend) + cx * blend
            my = oy * (1.0 - blend) + cy * blend
            mz = oz * (1.0 - blend) + cz * blend
            mlen = math.sqrt(mx * mx + my * my + mz * mz) or 1.0
            out.append((round((mx / mlen) * 16384.0), round((my / mlen) * 16384.0), round((mz / mlen) * 16384.0), onw))
        else:
            out.append(orig_nrm[i])
    return out


def _find_ib_for_vb(ibs: dict, vb_name: str):
    stem = vb_name.removesuffix("-VB")
    for k, ib in ibs.items():
        if k.startswith(stem + "-"):
            return ib
    return None


def sculpt_sdo_bytes(dec_ba: bytearray, prof: dict) -> dict:
    """Apply parametric 3D sculpt in-place on a decompressed .sdo bytearray. Returns audit stats."""
    vbs = {v["short_name"]: v for v in parse_vbs(dec_ba)}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(dec_ba)}
    lm = detect_face_landmarks(dec_ba, vbs)

    stats = {
        "lm": lm, "face_verts": 0, "moved": 0, "max_disp_mm": 0.0,
        "neck_seam_mm": 0.0, "eye_max_mm": 0.0, "hair_vbs": 0,
        "orig_face": None, "new_face": None,
    }

    # 1. Morph Face-VB & Face_lodL-VB
    for vb_name in ("Face-VB", "Face_lodL-VB"):
        if vb_name not in vbs:
            continue
        vb = vbs[vb_name]
        xyz, nrm = _read_vb_xyz_nrm(dec_ba, vb)
        new_xyz = []
        for x, y, z in xyz:
            dx, dy, dz = compute_face_displacement(x, y, z, lm, prof)
            d_mm = math.sqrt(dx * dx + dy * dy + dz * dz) * 100.0
            if y <= lm["neck_lock_y"] and d_mm > stats["neck_seam_mm"]:
                stats["neck_seam_mm"] = d_mm
            # Check strict eye-center clearance (relative to the rigid eye_spacing shift!)
            esp = prof.get("eye_spacing", 0.0)
            if (abs(abs(x) - lm["eye_x"]) < 0.08 and abs(y - lm["eye_y"]) < 0.05 and abs(z - lm["eye_z"]) < 0.10):
                exp_dx = (esp if x >= 0 else -esp)
                rel_mm = math.sqrt((dx - exp_dx) ** 2 + dy * dy + dz * dz) * 100.0
                if rel_mm > stats["eye_max_mm"]:
                    stats["eye_max_mm"] = rel_mm
            if d_mm > stats["max_disp_mm"]:
                stats["max_disp_mm"] = d_mm
            if vb_name == "Face-VB" and d_mm > 0.001:
                stats["moved"] += 1
            new_xyz.append((x + dx, y + dy, z + dz))
        ib = _find_ib_for_vb(ibs, vb_name)
        new_nrm = _recalc_blended_normals(new_xyz, nrm, ib["inds"], blend=0.45) if ib else nrm
        _write_vb_xyz_nrm(dec_ba, vb, new_xyz, new_nrm)
        if vb_name == "Face-VB":
            stats["face_verts"] = len(xyz)
            stats["orig_face"] = xyz
            stats["new_face"] = new_xyz

    # 1b. Symmetric eye_spacing shift on LeftEye_zero / RightEye_zero bones + Eyelash VBs
    esp = prof.get("eye_spacing", 0.0)
    if abs(esp) > 1e-5:
        _shift_eye_bones(dec_ba, esp)
        for lash_name in ("Eyelash-VB", "Eyelash_lodL-VB"):
            if lash_name not in vbs:
                continue
            lvb = vbs[lash_name]
            lxyz, lnrm = _read_vb_xyz_nrm(dec_ba, lvb)
            lnew = [(x + (esp if x >= 0 else -esp), y, z) for (x, y, z) in lxyz]
            _write_vb_xyz_nrm(dec_ba, lvb, lnew, lnrm)

    # 2. Morph rigid crown/top Hair VBs (skip cloth ponytails `cloth` / `bone` so physics stays clean)
    hy, hx = prof["hair_y"], prof["hair_x"]
    if abs(hy) > 1e-4 or abs(hx) > 1e-4:
        for vb_name, vb in vbs.items():
            low = vb_name.lower()
            if "hair" not in low or "cloth" in low or "bone" in low or "band" in low:
                continue
            if vb["streams"][0]["nverts"] <= 4 or vb["streams"][0]["attrs"][0] != (4, 3):
                continue
            hxyz, hnrm = _read_vb_xyz_nrm(dec_ba, vb)
            ymin = min(p[1] for p in hxyz); ymax = max(p[1] for p in hxyz)
            yspan = max(0.2, ymax - ymin)
            h_new = []
            for x, y, z in hxyz:
                t = _smoothstep(ymin + yspan * 0.1, ymax, y)
                dy = hy * (0.25 + 0.75 * t)
                dx = x * (hx * _smoothstep(0.20, 0.65, abs(x)))
                dz = -0.020 * t if hy < -0.04 else 0.0
                h_new.append((x + dx, y + dy, z + dz))
            ib = _find_ib_for_vb(ibs, vb_name)
            h_nrm = _recalc_blended_normals(h_new, hnrm, ib["inds"], blend=0.35) if ib else hnrm
            _write_vb_xyz_nrm(dec_ba, vb, h_new, h_nrm)
            stats["hair_vbs"] += 1

    # 3. Hide unwanted donor visor (Stream 0 of Accessory-VB / Accessory_lodL-VB on P_W_IVA_IT)
    # while keeping Stream 1 (3D hairtop crown mesh!) 100% intact!
    stats["visor_removed"] = 0
    if prof.get("hide_visor", False):
        for acc_name in ("Accessory-VB", "Accessory_lodL-VB"):
            if acc_name in vbs and len(vbs[acc_name]["streams"]) >= 2:
                avb = vbs[acc_name]
                _, anrm = _read_vb_xyz_nrm(dec_ba, avb, stream_idx=0)
                zero_xyz = [(0.0, 0.0, 0.0)] * len(anrm)
                _write_vb_xyz_nrm(dec_ba, avb, zero_xyz, anrm, stream_idx=0)
                stats["visor_removed"] += len(anrm)

    return stats


def _draw_silhouette_panel(draw, x0, y0, pw, ph, title, orig_face, new_face, lm):
    draw.rectangle((x0, y0, x0 + pw - 1, y0 + ph - 1), fill=(20, 22, 29), outline=(48, 54, 68))
    draw.text((x0 + 8, y0 + 6), title, fill=(145, 240, 185))
    y_min = lm["neck_lock_y"] - 0.35
    y_max = lm["crown_y"] + 0.12
    scale = (ph - 42) / max(1.0, y_max - y_min)
    cx_f = x0 + pw * 0.27
    cx_s = x0 + pw * 0.73
    z_mid = (lm["nose_z"] + lm["chin_z"]) * 0.5 - 0.45

    def pf(x, y):
        return int(cx_f + x * scale), int(y0 + ph - 10 - (y - y_min) * scale)

    def ps(z, y):
        return int(cx_s + (z - z_mid) * scale), int(y0 + ph - 10 - (y - y_min) * scale)

    _, ny = pf(0, lm["neck_lock_y"])
    draw.line([(x0 + 6, ny), (x0 + pw - 6, ny)], fill=(55, 195, 105), width=1)

    for x, y, z in orig_face:
        if y < y_min:
            continue
        fx, fy = pf(x, y)
        draw.point((fx, fy), fill=(45, 190, 225))
        if x >= -0.05:
            sx, sy = ps(z, y)
            draw.point((sx, sy), fill=(45, 190, 225))
    for x, y, z in new_face:
        if y < y_min:
            continue
        fx, fy = pf(x, y)
        draw.point((fx, fy), fill=(255, 80, 175))
        if x >= -0.05:
            sx, sy = ps(z, y)
            draw.point((sx, sy), fill=(255, 80, 175))


def export_obj(sdo_path: str, out_obj: str):
    dec = lzss_decompress(open(sdo_path, "rb").read())
    vbs = {v["short_name"]: v for v in parse_vbs(dec)}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(dec)}
    face_vb = vbs["Face-VB"]
    face_xyz, _ = _read_vb_xyz_nrm(dec, face_vb)
    face_ib = _find_ib_for_vb(ibs, "Face-VB")
    os.makedirs(os.path.dirname(os.path.abspath(out_obj)), exist_ok=True)
    with open(out_obj, "w", encoding="utf-8") as f:
        f.write(f"# VT4 SDO Head Export from {os.path.basename(sdo_path)}\no Face-VB\n")
        for x, y, z in face_xyz:
            f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for a, b, c in _strip_to_tris(face_ib["inds"]):
            f.write(f"f {a + 1} {b + 1} {c + 1}\n")
    print(f"Exported {len(face_xyz)} face verts -> {out_obj}")


def import_obj(sdo_path: str, sculpted_obj: str, out_sdo: str):
    dec = bytearray(lzss_decompress(open(sdo_path, "rb").read()))
    vbs = {v["short_name"]: v for v in parse_vbs(dec)}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(dec)}
    verts = []
    with open(sculpted_obj, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("v "):
                p = line.split()
                verts.append((float(p[1]), float(p[2]), float(p[3])))
    face_vb = vbs["Face-VB"]
    nf = face_vb["streams"][0]["nverts"]
    if len(verts) < nf:
        raise ValueError(f"OBJ vertex count {len(verts)} < Face-VB ({nf})")
    orig_xyz, orig_nrm = _read_vb_xyz_nrm(dec, face_vb)
    new_xyz = verts[:nf]
    face_ib = _find_ib_for_vb(ibs, "Face-VB")
    new_nrm = _recalc_blended_normals(new_xyz, orig_nrm, face_ib["inds"], blend=0.45)
    _write_vb_xyz_nrm(dec, face_vb, new_xyz, new_nrm)
    os.makedirs(os.path.dirname(os.path.abspath(out_sdo)), exist_ok=True)
    open(out_sdo, "wb").write(lzss_compress_literal(bytes(dec)))
    max_d = max(math.dist(a, b) for a, b in zip(orig_xyz, new_xyz))
    print(f"Imported {sculpted_obj} -> {out_sdo} (max disp = {max_d * 100:.2f} mm)")


def run_all(audit_sheet_path: str | None, single_player: str | None = None):
    manifest = json.load(open(os.path.join(FACE_WS_DIR, "manifest.json"), encoding="utf-8"))
    targets = [single_player] if single_player else sorted(manifest.keys())

    audit_stars = ["26_ALC", "27_SIN", "39_MED", "30_BOR", "65_BAD", "35_SAB", "34_SWI", "32_GRA"]
    star_panels = {}
    fails = []
    max_all_disp = 0.0
    max_all_neck = 0.0
    max_all_eye = 0.0
    max_m0 = 0.0
    max_m1 = 0.0

    for folder in targets:
        if folder not in manifest or folder not in HEAD_SCULPT_PROFILES:
            raise KeyError(f"Missing manifest/profile entry for {folder}")
        info = manifest[folder]
        sdo_path = os.path.join(MODEL_DIR, info["sdo"])
        dec = bytearray(lzss_decompress(open(sdo_path, "rb").read()))
        stats = sculpt_sdo_bytes(dec, HEAD_SCULPT_PROFILES[folder])
        open(sdo_path, "wb").write(lzss_compress_literal(bytes(dec)))

        # Verify mip-0 and mip-1 face diffuse diff (no regression!)
        slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
        fslot = slots[info["face_slot"]]
        ed_path = os.path.join(FACE_WS_DIR, folder, "edited_face_uv.png")
        diff_m0 = diff_m1 = 0.0
        if os.path.isfile(ed_path):
            e_small = Image.open(ed_path).convert("RGB").resize((128, 128)).tobytes()
            sdo_m0 = extract_slot_image(dec, fslot).convert("RGB").resize((128, 128)).tobytes()
            diff_m0 = sum(abs(a - b) for a, b in zip(sdo_m0, e_small)) / len(e_small)
            mip0_sz = (fslot["w"] // 4) * (fslot["h"] // 4) * 16
            mip1_sz = (fslot["w"] // 8) * (fslot["h"] // 8) * 16
            hdr = bytearray(dec[fslot["off"] : fslot["off"] + 128])
            struct.pack_into("<IIIII", hdr, 12, fslot["h"] // 2, fslot["w"] // 2, mip1_sz, 0, 1)
            m1_im = Image.open(io.BytesIO(bytes(hdr) + dec[fslot["off"] + 128 + mip0_sz : fslot["off"] + 128 + mip0_sz + mip1_sz])).convert("RGB")
            diff_m1 = sum(abs(a - b) for a, b in zip(m1_im.resize((128, 128)).tobytes(), e_small)) / len(e_small)

        max_all_disp = max(max_all_disp, stats["max_disp_mm"])
        max_all_neck = max(max_all_neck, stats["neck_seam_mm"])
        max_all_eye = max(max_all_eye, stats["eye_max_mm"])
        max_m0 = max(max_m0, diff_m0)
        max_m1 = max(max_m1, diff_m1)

        ok = (stats["neck_seam_mm"] == 0.0 and stats["max_disp_mm"] <= 15.0 and stats["eye_max_mm"] <= 2.5 and diff_m0 < 3.5 and diff_m1 < 3.5)
        if not ok:
            fails.append((folder, stats["max_disp_mm"], stats["neck_seam_mm"], stats["eye_max_mm"], diff_m0, diff_m1))
        print(f"  [{'OK' if ok else 'FAIL'}] {folder:9s} {info['sdo']:14s} v={stats['face_verts']:4d} max={stats['max_disp_mm']:5.2f}mm neck={stats['neck_seam_mm']:.4f}mm eye={stats['eye_max_mm']:.2f}mm hairVBs={stats['hair_vbs']} m0={diff_m0:.2f} m1={diff_m1:.2f}")

        if folder in audit_stars:
            star_panels[folder] = (f"{folder} ({info['sdo']}) max={stats['max_disp_mm']:.1f}mm", stats["orig_face"], stats["new_face"], stats["lm"])

    print(f"\nSUMMARY: {len(targets)}/{len(targets)} sculpted | fails={len(fails)} | max_disp={max_all_disp:.2f}mm | max_neck={max_all_neck:.4f}mm | max_eye={max_all_eye:.2f}mm | max_m0={max_m0:.2f} | max_m1={max_m1:.2f}")
    if fails:
        print("FAILURES:", fails)

    if audit_sheet_path and star_panels:
        cols, rows = 4, 2
        pw, ph, pad, hdr = 360, 290, 10, 48
        sheet = Image.new("RGB", (cols * pw + (cols + 1) * pad, rows * ph + (rows + 1) * pad + hdr), (14, 16, 22))
        draw = ImageDraw.Draw(sheet)
        draw.text((16, 10), "VT4 3D HEAD SCULPT AUDIT (8 KEY STARS: 4 MALE + 4 FEMALE)", fill=(240, 245, 255))
        draw.text((16, 28), "CYAN = Original SEGA Base  |  MAGENTA = Sculpted 3D Head  |  GREEN LINE = Neck Lock (0.0000mm below)", fill=(175, 185, 200))
        for idx, star in enumerate(audit_stars):
            if star not in star_panels:
                continue
            r, c = divmod(idx, cols)
            x0 = pad + c * (pw + pad)
            y0 = hdr + pad + r * (ph + pad)
            title, of, nf, lm = star_panels[star]
            _draw_silhouette_panel(draw, x0, y0, pw, ph, title, of, nf, lm)
        os.makedirs(os.path.dirname(os.path.abspath(audit_sheet_path)), exist_ok=True)
        sheet.save(audit_sheet_path)
        print(f"Saved 8-star 3D sculpt audit sheet -> {audit_sheet_path}")


def main():
    ap = argparse.ArgumentParser(description="3D Head Sculpting & OBJ Round-Trip for VT4 .sdo")
    ap.add_argument("--all", action="store_true", help="Sculpt and verify all 57 custom .sdo models")
    ap.add_argument("--player", help="Sculpt single player folder in-place, e.g. 26_ALC")
    ap.add_argument("--audit-sheet", default=os.path.join(REPO_ROOT, "scratch", "sculpt_57", "sculpt_mesh_audit_8stars.png"))
    ap.add_argument("--export-obj", nargs=2, metavar=("IN_SDO", "OUT_OBJ"))
    ap.add_argument("--import-obj", nargs=3, metavar=("IN_SDO", "SCULPTED_OBJ", "OUT_SDO"))
    ap.add_argument("--profile", help="Profile key (e.g. 26_ALC or alcaraz) for standalone --in/--out")
    ap.add_argument("--in", dest="in_sdo")
    ap.add_argument("--out", dest="out_sdo")
    args = ap.parse_args()

    if args.export_obj:
        export_obj(args.export_obj[0], args.export_obj[1])
    elif args.import_obj:
        import_obj(args.import_obj[0], args.import_obj[1], args.import_obj[2])
    elif args.all or args.player:
        run_all(args.audit_sheet if args.all else None, single_player=args.player)
    elif args.profile:
        key = "26_ALC" if args.profile.lower() == "alcaraz" else args.profile
        dec = bytearray(lzss_decompress(open(args.in_sdo, "rb").read()))
        stats = sculpt_sdo_bytes(dec, HEAD_SCULPT_PROFILES[key])
        os.makedirs(os.path.dirname(os.path.abspath(args.out_sdo)), exist_ok=True)
        open(args.out_sdo, "wb").write(lzss_compress_literal(bytes(dec)))
        print(f"Sculpted {key} -> {args.out_sdo} (max={stats['max_disp_mm']:.2f}mm, neck={stats['neck_seam_mm']:.4f}mm)")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
