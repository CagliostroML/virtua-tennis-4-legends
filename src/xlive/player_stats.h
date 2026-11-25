/*
 * Individualized Gameplay Stats for All 58 Custom Players (IDs 26..83)
 * Virtua Tennis 4: Legends & Next-Gen Edition
 *
 * Offsets verified via disassembly of PlayStyle::LoadInner (0x00541ec0):
 *   +0x00 StrokePowerF   +0x04 StrokePowerB   +0x08 SlicePowerF   +0x0c SlicePowerB
 *   +0x10 StrokeHeightF  +0x14 StrokeHeightB  +0x20 StrokeControlF +0x24 StrokeControlB
 *   +0x58 VolleyPowerF   +0x5c VolleyPowerB   +0x78 VolleyControlF +0x7c VolleyControlB
 *   +0x80 DropPower      +0x84 DropRange      +0x88 ServeSpeed     +0x94 ServeControl
 *   +0x98 MaxServeBonus  +0x9c AccelerationX  +0xa0 AccelerationZ  +0xa4 MaxSpeedX
 *   +0xa8 MaxSpeedZ      +0xac TurnSpeed      +0xb4 GaugeCoef
 */
#ifndef VT4_PLAYER_STATS_H
#define VT4_PLAYER_STATS_H

#include <stdint.h>

#define CUSTOM_STATS_FIRST_ID 26
#define CUSTOM_STATS_COUNT    58

typedef struct {
    const char *code;
    float stroke_pow_f;
    float stroke_pow_b;
    float slice_pow_f;
    float slice_pow_b;
    float stroke_h_f;
    float stroke_h_b;
    float stroke_ctrl_f;
    float stroke_ctrl_b;
    float volley_pow_f;
    float volley_pow_b;
    float volley_ctrl_f;
    float volley_ctrl_b;
    float drop_pow;
    float drop_range;
    float serve_spd;
    float serve_ctrl;
    float max_serve_bonus;
    float accel_x;
    float accel_z;
    float max_spd_x;
    float max_spd_z;
    float turn_spd;
    float gauge_coef;
    float serve_max_kmh;
} CustomPlayerStats;

/* Calibrated within verified safe VT4 engine bounds */
static const CustomPlayerStats g_custom_player_stats[CUSTOM_STATS_COUNT] = {
    /* ID 26: Alcaraz — Explosive all-court power, dropshot & athleticism */
    { "ALC", 17.5f, 13.0f,  0.0f,  0.0f, 0.70f, 0.40f, 11.0f,  9.0f,  7.0f,  7.0f, 20.0f, 18.0f, 2.5f, 2.0f, 11.0f, 1.52f, 15.0f, 0.120f, 0.085f, 0.082f, 0.062f, 0.062f, 0.72f, 224.0f },
    /* ID 27: Sinner — Relentless flat/heavy two-wing baseline pace & return */
    { "SIN", 18.0f, 16.0f,  0.0f,  0.0f, 0.45f, 0.35f, 12.0f, 12.0f,  4.0f,  4.0f, 14.0f, 14.0f, 0.8f, 0.6f, 14.0f, 1.54f, 17.0f, 0.105f, 0.078f, 0.075f, 0.056f, 0.058f, 0.64f, 228.0f },
    /* ID 28: Sampras — Cannon serve, running forehand & elite net finish */
    { "SAM", 14.0f,  6.0f, -2.0f,  0.0f, 0.15f, 0.25f,  9.0f,  5.0f, 10.5f, 10.0f, 26.0f, 24.0f, 0.0f, 0.0f, 18.0f, 1.58f, 21.0f, 0.075f, 0.065f, 0.055f, 0.045f, 0.045f, 0.48f, 232.0f },
    /* ID 29: Agassi — Early-ball return & laser groundstrokes */
    { "AGA", 15.0f, 14.5f,  0.0f,  0.0f, 0.20f, 0.15f, 12.0f, 12.0f,  2.0f,  2.0f, 10.0f, 10.0f, 0.5f, 0.5f,  8.0f, 1.50f, 12.0f, 0.085f, 0.070f, 0.062f, 0.048f, 0.052f, 0.56f, 212.0f },
    /* ID 30: Borg — Iron lungs, heavy topspin & unbreakable defense */
    { "BOR", 13.0f, 11.5f,  0.0f,  0.0f, 1.05f, 0.60f, 12.0f, 11.0f,  3.0f,  3.0f, 15.0f, 15.0f, 0.5f, 0.5f,  7.0f, 1.48f, 11.0f, 0.125f, 0.088f, 0.084f, 0.064f, 0.064f, 0.80f, 206.0f },
    /* ID 31: McEnroe — Surgical lefty serve + all-time touch volleys */
    { "MCE",  7.0f,  6.5f, -3.5f, -3.5f, 0.05f, 0.10f, 11.0f, 10.0f, 11.0f, 11.0f, 28.0f, 28.0f, 2.0f, 1.8f, 10.0f, 1.56f, 14.0f, 0.072f, 0.076f, 0.050f, 0.054f, 0.056f, 0.52f, 208.0f },
    /* ID 32: Graf — Iconic inside-out forehand & biting backhand slice */
    { "GRA", 16.5f,  4.0f,  0.0f, -4.0f, 0.20f, 0.10f, 11.0f,  9.0f,  5.0f,  5.0f, 16.0f, 16.0f, 0.8f, 0.8f,  9.0f, 1.48f, 13.0f, 0.110f, 0.080f, 0.078f, 0.058f, 0.058f, 0.68f, 198.0f },
    /* ID 33: Serena — Explosive serve & overpowering two-wing strikes */
    { "SER", 17.0f, 14.0f,  0.0f,  0.0f, 0.25f, 0.20f,  8.0f,  8.0f,  4.0f,  3.0f, 12.0f, 12.0f, 0.0f, 0.0f, 15.0f, 1.52f, 18.0f, 0.068f, 0.055f, 0.048f, 0.038f, 0.042f, 0.52f, 207.0f },
    /* ID 34: Swiatek — Whippy heavy clay topspin + relentless movement */
    { "SWI", 15.5f, 12.0f,  0.0f,  0.0f, 1.10f, 0.55f, 11.0f, 10.0f,  2.0f,  2.0f, 10.0f, 10.0f, 0.6f, 0.6f,  6.0f, 1.46f, 10.0f, 0.115f, 0.082f, 0.078f, 0.058f, 0.060f, 0.76f, 196.0f },
    /* ID 35: Sabalenka — Maximum flat-ball firepower & big serve */
    { "SAB", 17.5f, 14.5f,  0.0f,  0.0f, 0.20f, 0.15f,  6.0f,  6.0f,  3.0f,  2.0f, 10.0f,  9.0f, 0.2f, 0.2f, 14.0f, 1.44f, 17.0f, 0.065f, 0.050f, 0.046f, 0.036f, 0.040f, 0.48f, 206.0f },
    /* ID 36: Kuerten — Heavy clay topspin + booming 1H backhand */
    { "KUE", 15.0f, 13.5f,  0.0f,  0.0f, 1.05f, 0.90f,  9.0f, 10.0f,  4.0f,  4.0f, 14.0f, 14.0f, 1.2f, 1.0f, 11.0f, 1.48f, 15.0f, 0.092f, 0.068f, 0.066f, 0.048f, 0.050f, 0.70f, 218.0f },
    /* ID 37: Navratilova — Dominant lefty serve-and-volley perfection */
    { "NAV",  9.0f,  7.0f, -2.5f, -3.5f, 0.10f, 0.15f,  9.0f,  9.0f, 11.0f, 11.0f, 28.0f, 28.0f, 1.2f, 1.0f, 10.0f, 1.54f, 14.0f, 0.095f, 0.082f, 0.068f, 0.056f, 0.058f, 0.58f, 194.0f },
    /* ID 38: Wawrinka — Blistering one-handed backhand & heavy strikes */
    { "WAW", 15.0f, 16.5f,  0.0f,  0.0f, 0.65f, 0.75f,  8.0f, 10.0f,  4.0f,  4.0f, 13.0f, 14.0f, 0.4f, 0.4f, 12.0f, 1.48f, 16.0f, 0.068f, 0.054f, 0.050f, 0.040f, 0.042f, 0.54f, 224.0f },
    /* ID 39: Medvedev — Octopus court defense, flat deep depth & big serve */
    { "MED", 11.0f, 13.0f,  0.0f,  0.0f, 0.05f, 0.05f, 12.0f, 12.0f,  4.0f,  4.0f, 14.0f, 14.0f, 0.8f, 0.8f, 14.5f, 1.52f, 18.0f, 0.108f, 0.080f, 0.078f, 0.058f, 0.056f, 0.66f, 225.0f },
    /* ID 40: Zverev — Twin-tower serve + elite two-handed backhand cannon */
    { "ZVE", 13.0f, 15.5f,  0.0f,  0.0f, 0.45f, 0.30f,  9.0f, 11.0f,  5.0f,  5.0f, 15.0f, 15.0f, 0.4f, 0.4f, 17.0f, 1.50f, 20.0f, 0.088f, 0.066f, 0.064f, 0.048f, 0.046f, 0.62f, 232.0f },
    /* ID 41: Tsitsipas — Whippy inside-out forehand & net approach */
    { "TSI", 15.5f,  9.0f,  0.0f, -1.5f, 0.80f, 0.45f, 10.0f,  7.0f,  7.0f,  6.5f, 19.0f, 17.0f, 0.8f, 0.6f, 13.0f, 1.48f, 16.0f, 0.082f, 0.068f, 0.060f, 0.048f, 0.048f, 0.58f, 222.0f },
    /* ID 42: Thiem — Heavy-spin brute power from both wings */
    { "THI", 17.0f, 15.0f,  0.0f, -1.5f, 1.05f, 0.90f,  8.0f,  8.5f,  3.0f,  3.0f, 12.0f, 12.0f, 0.6f, 0.6f, 12.0f, 1.46f, 15.0f, 0.095f, 0.072f, 0.070f, 0.052f, 0.052f, 0.72f, 224.0f },
    /* ID 43: Kyrgios — Lighting serve, trick-shot touch & tweener/dropshot */
    { "KYR", 14.5f,  9.5f, -1.5f, -1.5f, 0.15f, 0.10f,  7.0f,  7.0f,  7.5f,  7.5f, 19.0f, 18.0f, 2.2f, 1.8f, 18.5f, 1.54f, 21.5f, 0.060f, 0.052f, 0.044f, 0.036f, 0.040f, 0.42f, 234.0f },
    /* ID 44: Hewitt — Tireless counterpunching speed + lob/passing king */
    { "HEW",  9.5f, 10.5f,  0.0f,  0.0f, 0.25f, 0.20f, 12.0f, 12.0f,  5.0f,  5.0f, 17.0f, 17.0f, 1.0f, 0.8f,  7.0f, 1.50f, 11.0f, 0.122f, 0.086f, 0.083f, 0.062f, 0.064f, 0.76f, 210.0f },
    /* ID 45: Safin — Heavy Russian cannon from both baseline wings */
    { "SAF", 16.5f, 15.5f,  0.0f,  0.0f, 0.35f, 0.30f,  7.5f,  8.5f,  4.0f,  4.0f, 14.0f, 14.0f, 0.5f, 0.5f, 15.5f, 1.46f, 19.0f, 0.064f, 0.050f, 0.046f, 0.036f, 0.040f, 0.50f, 229.0f },
    /* ID 46: Tsonga — Explosive forehand smash & athletic net surges */
    { "TSO", 16.5f,  9.5f,  0.0f,  0.0f, 0.40f, 0.25f,  7.5f,  6.5f,  7.5f,  7.0f, 18.0f, 17.0f, 0.8f, 0.6f, 16.0f, 1.48f, 19.5f, 0.078f, 0.065f, 0.056f, 0.044f, 0.046f, 0.54f, 233.0f },
    /* ID 47: Ferrero — Crisp clay forehand & lightning-quick footwork */
    { "FRR", 14.5f, 10.0f,  0.0f,  0.0f, 0.85f, 0.45f, 11.0f, 10.0f,  3.0f,  3.0f, 12.0f, 12.0f, 1.0f, 0.8f,  7.0f, 1.48f, 11.0f, 0.112f, 0.080f, 0.076f, 0.056f, 0.058f, 0.70f, 210.0f },
    /* ID 48: Moya — Huge inside-out topspin forehand */
    { "MOY", 18.0f,  7.5f,  0.0f,  0.0f, 0.90f, 0.30f,  9.5f,  7.5f,  3.0f,  3.0f, 11.0f, 11.0f, 0.5f, 0.5f, 12.0f, 1.46f, 15.0f, 0.082f, 0.064f, 0.058f, 0.044f, 0.046f, 0.60f, 218.0f },
    /* ID 49: Ferrer — Unstoppable defensive wall + stamina */
    { "FER", 11.5f, 11.0f,  0.0f,  0.0f, 0.60f, 0.40f, 12.0f, 12.0f,  3.0f,  3.0f, 13.0f, 13.0f, 0.8f, 0.8f,  5.0f, 1.46f,  9.0f, 0.125f, 0.088f, 0.085f, 0.064f, 0.065f, 0.84f, 204.0f },
    /* ID 50: Nalbandian — Razor-sharp two-handed cross-court angles */
    { "NAL", 13.5f, 16.0f,  0.0f,  0.0f, 0.30f, 0.35f, 12.0f, 12.0f,  4.0f,  5.0f, 15.0f, 16.0f, 1.2f, 1.0f,  7.5f, 1.50f, 11.5f, 0.080f, 0.064f, 0.058f, 0.044f, 0.052f, 0.60f, 211.0f },
    /* ID 51: Lendl — Heavy topspin forehand + robotic baseline pace */
    { "LEN", 17.5f, 12.5f,  0.0f,  0.0f, 0.70f, 0.55f, 10.5f, 10.0f,  4.0f,  4.0f, 14.0f, 14.0f, 0.0f, 0.0f, 14.0f, 1.50f, 17.0f, 0.088f, 0.068f, 0.064f, 0.048f, 0.048f, 0.68f, 216.0f },
    /* ID 52: Connors — Lefty flat-ball aggression & fierce return */
    { "CON", 12.0f, 14.5f,  0.0f,  0.0f, 0.05f, 0.05f, 11.5f, 12.0f,  6.0f,  6.5f, 19.0f, 20.0f, 0.6f, 0.6f,  5.0f, 1.46f,  9.0f, 0.105f, 0.078f, 0.074f, 0.056f, 0.060f, 0.74f, 198.0f },
    /* ID 53: Vilas — Lefty heavy-spin clay endurance & passing shots */
    { "VIL", 13.5f, 12.5f,  0.0f, -2.0f, 1.05f, 0.80f, 11.0f, 10.5f,  3.5f,  3.5f, 13.0f, 13.0f, 0.8f, 0.8f,  6.0f, 1.46f, 10.0f, 0.112f, 0.080f, 0.076f, 0.058f, 0.056f, 0.82f, 198.0f },
    /* ID 54: Ivanisevic — Left-handed 230+ km/h Ace machine */
    { "IVN", 13.0f,  9.5f, -1.5f, -1.5f, 0.15f, 0.15f,  7.0f,  7.0f,  8.5f,  8.0f, 21.0f, 20.0f, 0.2f, 0.2f, 19.0f, 1.56f, 22.0f, 0.062f, 0.054f, 0.044f, 0.038f, 0.040f, 0.44f, 236.0f },
    /* ID 55: Evert — Ice-cold baseline precision & consistency */
    { "EVE", 10.0f, 11.0f,  0.0f,  0.0f, 0.25f, 0.25f, 12.0f, 12.0f,  3.0f,  3.0f, 14.0f, 14.0f, 1.0f, 0.8f,  2.0f, 1.48f,  6.0f, 0.095f, 0.072f, 0.068f, 0.052f, 0.054f, 0.78f, 182.0f },
    /* ID 56: Seles — Two-handed lefty power on both wings */
    { "SEL", 15.5f, 15.5f,  0.0f,  0.0f, 0.20f, 0.20f, 10.5f, 10.5f,  2.0f,  2.0f, 10.0f, 10.0f, 0.4f, 0.4f,  6.5f, 1.46f, 10.0f, 0.082f, 0.064f, 0.060f, 0.046f, 0.048f, 0.62f, 190.0f },
    /* ID 57: Henin — All-time 1H backhand & lightning agility */
    { "HEN", 13.0f, 14.5f,  0.0f, -2.5f, 0.45f, 0.40f, 11.0f, 12.0f,  7.5f,  7.5f, 21.0f, 21.0f, 1.4f, 1.2f,  8.5f, 1.50f, 12.5f, 0.112f, 0.082f, 0.078f, 0.058f, 0.062f, 0.68f, 196.0f },
    /* ID 58: Muguruza — Flat heavy power & aggressive court stance */
    { "MUG", 15.0f, 14.0f,  0.0f,  0.0f, 0.25f, 0.20f,  8.5f,  9.0f,  5.0f,  4.5f, 14.0f, 14.0f, 0.2f, 0.2f, 11.0f, 1.46f, 14.0f, 0.072f, 0.058f, 0.052f, 0.042f, 0.044f, 0.56f, 198.0f },
    /* ID 59: Shelton — 240 km/h lefty bomb serve & dynamic power */
    { "SHE", 15.5f, 11.0f,  0.0f,  0.0f, 0.55f, 0.30f,  7.0f,  7.0f,  7.0f,  6.5f, 17.0f, 16.0f, 0.5f, 0.5f, 19.0f, 1.50f, 22.0f, 0.088f, 0.068f, 0.064f, 0.048f, 0.050f, 0.54f, 240.0f },
    /* ID 60: Rublev — Non-stop inside-out forehand sledgehammer */
    { "RUB", 18.0f, 11.5f,  0.0f,  0.0f, 0.40f, 0.25f,  8.5f,  8.5f,  2.0f,  2.0f, 10.0f, 10.0f, 0.2f, 0.2f, 11.5f, 1.48f, 15.0f, 0.086f, 0.064f, 0.062f, 0.046f, 0.048f, 0.62f, 220.0f },
    /* ID 61: Ruud — Heavy clay topspin forehand & endurance */
    { "RUU", 16.5f,  9.5f,  0.0f,  0.0f, 1.15f, 0.45f, 11.0f,  9.5f,  3.5f,  3.5f, 13.0f, 13.0f, 0.8f, 0.6f, 10.0f, 1.48f, 14.0f, 0.102f, 0.076f, 0.072f, 0.054f, 0.054f, 0.72f, 218.0f },
    /* ID 62: Fritz — Precision heavy first serve & crisp two-wing flat pace */
    { "FRI", 15.0f, 13.5f,  0.0f,  0.0f, 0.30f, 0.25f,  9.5f, 10.0f,  4.0f,  4.0f, 13.0f, 13.0f, 0.3f, 0.3f, 17.5f, 1.54f, 20.0f, 0.070f, 0.056f, 0.050f, 0.040f, 0.042f, 0.54f, 232.0f },
    /* ID 63: Gauff — Elite speed, defense & athletic counterpunching */
    { "GAU", 11.5f, 13.5f,  0.0f,  0.0f, 0.60f, 0.35f,  9.0f, 11.0f,  6.0f,  6.0f, 17.0f, 17.0f, 0.8f, 0.8f, 11.5f, 1.42f, 15.0f, 0.122f, 0.086f, 0.082f, 0.062f, 0.062f, 0.72f, 205.0f },
    /* ID 64: Rybakina — Effortless serve bombs & laser groundstrokes */
    { "RYB", 15.5f, 14.0f,  0.0f,  0.0f, 0.15f, 0.15f,  9.5f,  9.5f,  5.0f,  5.0f, 15.0f, 15.0f, 0.2f, 0.2f, 16.0f, 1.54f, 19.0f, 0.070f, 0.055f, 0.050f, 0.040f, 0.042f, 0.54f, 208.0f },
    /* ID 65: Badosa — Aggressive baseline striker + strong serve */
    { "BAD", 14.0f, 13.0f,  0.0f,  0.0f, 0.45f, 0.30f,  9.0f,  9.0f,  3.5f,  3.5f, 12.0f, 12.0f, 0.5f, 0.5f, 10.5f, 1.48f, 14.0f, 0.084f, 0.064f, 0.060f, 0.046f, 0.048f, 0.58f, 196.0f },
    /* ID 66: Halep — Counterpuncher speed & cross-court backhand */
    { "HAL", 10.5f, 12.5f,  0.0f,  0.0f, 0.40f, 0.30f, 12.0f, 12.0f,  4.0f,  4.0f, 14.0f, 14.0f, 1.0f, 0.8f,  5.0f, 1.48f,  9.0f, 0.120f, 0.084f, 0.080f, 0.060f, 0.062f, 0.76f, 186.0f },
    /* ID 67: Coria — El Mago: clay-court speed & impossible dropshots */
    { "COR", 11.5f, 10.5f,  0.0f, -1.5f, 0.85f, 0.55f, 12.0f, 12.0f,  5.0f,  5.0f, 16.0f, 16.0f, 3.0f, 2.5f,  3.0f, 1.44f,  7.0f, 0.125f, 0.088f, 0.085f, 0.064f, 0.065f, 0.80f, 194.0f },
    /* ID 68: Gasquet — Signature sweeping 1H backhand artistry */
    { "GAS", 10.5f, 15.0f,  0.0f, -2.0f, 0.55f, 0.75f,  9.0f, 11.5f,  5.5f,  6.0f, 16.0f, 17.0f, 1.0f, 0.8f,  9.0f, 1.48f, 13.0f, 0.082f, 0.064f, 0.058f, 0.046f, 0.050f, 0.62f, 212.0f },
    /* ID 69: Nishikori — Take-it-early baseline speed & backhand DTL */
    { "NIS", 12.0f, 14.0f,  0.0f,  0.0f, 0.35f, 0.30f, 11.0f, 12.0f,  5.0f,  5.0f, 15.0f, 15.0f, 1.2f, 1.0f,  6.5f, 1.48f, 10.0f, 0.110f, 0.080f, 0.075f, 0.056f, 0.058f, 0.68f, 206.0f },
    /* ID 70: Soderling — Heavy thunderbolt flat groundstrokes & serve */
    { "SOD", 18.5f, 14.0f,  0.0f,  0.0f, 0.30f, 0.25f,  7.0f,  7.5f,  4.0f,  4.0f, 12.0f, 12.0f, 0.0f, 0.0f, 16.5f, 1.48f, 19.5f, 0.062f, 0.048f, 0.044f, 0.036f, 0.038f, 0.50f, 230.0f },
    /* ID 71: Berdych — Clean flat ball striking & big serve */
    { "BER", 16.5f, 13.5f,  0.0f,  0.0f, 0.20f, 0.20f,  9.0f,  9.5f,  5.0f,  5.0f, 15.0f, 15.0f, 0.2f, 0.2f, 16.0f, 1.50f, 19.0f, 0.068f, 0.054f, 0.048f, 0.038f, 0.040f, 0.54f, 228.0f },
    /* ID 72: Chang — Never-say-die speed, lobs & court coverage */
    { "CHN",  9.0f,  9.5f,  0.0f,  0.0f, 0.40f, 0.35f, 12.0f, 12.0f,  4.0f,  4.0f, 14.0f, 14.0f, 1.5f, 1.2f,  4.0f, 1.46f,  8.0f, 0.125f, 0.088f, 0.085f, 0.064f, 0.065f, 0.84f, 198.0f },
    /* ID 73: Rios — Lefty magician: impossible angles, feel & dropshots */
    { "RIO", 13.0f, 13.5f, -1.0f, -1.5f, 0.30f, 0.30f, 12.0f, 12.0f,  7.0f,  7.5f, 21.0f, 21.0f, 2.8f, 2.2f,  7.5f, 1.50f, 11.5f, 0.104f, 0.076f, 0.072f, 0.054f, 0.060f, 0.62f, 206.0f },
    /* ID 74: Muster — Relentless lefty clay physicality & heavy forehand */
    { "MUS", 15.5f, 10.5f,  0.0f,  0.0f, 1.15f, 0.70f, 10.0f,  9.0f,  3.5f,  3.5f, 12.0f, 12.0f, 0.4f, 0.4f,  8.0f, 1.46f, 12.0f, 0.115f, 0.082f, 0.078f, 0.058f, 0.056f, 0.85f, 206.0f },
    /* ID 75: Bruguera — Twin-champion Roland Garros heavy topspin */
    { "BRU", 15.0f, 11.0f,  0.0f,  0.0f, 1.20f, 0.65f, 10.5f, 10.0f,  3.0f,  3.0f, 12.0f, 12.0f, 1.0f, 0.8f,  7.5f, 1.46f, 11.5f, 0.105f, 0.076f, 0.072f, 0.054f, 0.054f, 0.78f, 208.0f },
    /* ID 76: Corretja — Classic Spanish clay grinding + solid 1H BH */
    { "CRT", 13.0f, 11.5f,  0.0f, -1.5f, 0.95f, 0.65f, 11.5f, 11.0f,  4.5f,  4.5f, 15.0f, 15.0f, 1.2f, 1.0f,  8.5f, 1.48f, 12.0f, 0.105f, 0.076f, 0.072f, 0.054f, 0.054f, 0.76f, 210.0f },
    /* ID 77: Wilander — Steel tactician, topspin lob & all-surface IQ */
    { "WLD", 11.5f, 11.5f,  0.0f, -2.0f, 0.75f, 0.55f, 12.0f, 12.0f,  5.5f,  5.5f, 18.0f, 18.0f, 1.0f, 0.8f,  7.0f, 1.50f, 11.0f, 0.108f, 0.078f, 0.074f, 0.056f, 0.056f, 0.78f, 202.0f },
    /* ID 78: Laver — The Rocket: explosive lefty wrist whip & net mastery */
    { "LAV", 14.5f, 12.0f, -2.0f, -2.5f, 0.45f, 0.40f, 11.5f, 11.0f, 10.5f, 10.5f, 27.0f, 27.0f, 1.5f, 1.2f, 12.0f, 1.56f, 15.5f, 0.108f, 0.082f, 0.074f, 0.058f, 0.060f, 0.72f, 210.0f },
    /* ID 79: Arantxa Sanchez — Tireless clay retrieval & passing shots */
    { "ASV",  9.5f, 10.5f,  0.0f,  0.0f, 0.60f, 0.45f, 12.0f, 12.0f,  6.0f,  6.0f, 19.0f, 19.0f, 1.2f, 1.0f,  2.5f, 1.48f,  6.5f, 0.125f, 0.088f, 0.084f, 0.064f, 0.065f, 0.84f, 182.0f },
    /* ID 80: Conchita Martinez — Wimbledon touch, high topspin & slice variety */
    { "CMT", 12.5f,  9.0f,  0.0f, -3.0f, 0.90f, 0.40f, 11.0f, 10.0f,  6.5f,  6.5f, 20.0f, 20.0f, 1.4f, 1.2f,  6.0f, 1.48f, 10.0f, 0.092f, 0.068f, 0.064f, 0.048f, 0.052f, 0.70f, 188.0f },
    /* ID 81: Clijsters — Splits athleticism & heavy clean baseline power */
    { "CLI", 14.5f, 13.5f,  0.0f,  0.0f, 0.35f, 0.25f, 10.5f, 10.5f,  6.0f,  6.0f, 18.0f, 18.0f, 0.8f, 0.8f,  9.5f, 1.48f, 13.5f, 0.114f, 0.082f, 0.078f, 0.058f, 0.060f, 0.68f, 196.0f },
    /* ID 82: Mirra Andreeva — Prodigy court IQ, redirect BH & smooth variety */
    { "AND", 12.0f, 13.5f,  0.0f,  0.0f, 0.45f, 0.30f, 11.0f, 11.5f,  5.0f,  5.0f, 16.0f, 16.0f, 1.4f, 1.2f,  8.5f, 1.48f, 12.5f, 0.112f, 0.080f, 0.076f, 0.058f, 0.058f, 0.68f, 195.0f },
    /* ID 83: Billie Jean King — Fierce serve-and-volley pioneer & net instincts */
    { "BJK",  9.5f,  8.5f, -2.0f, -3.0f, 0.15f, 0.15f, 10.5f, 10.0f, 10.5f, 10.5f, 27.0f, 27.0f, 1.2f, 1.0f,  8.0f, 1.54f, 12.0f, 0.098f, 0.082f, 0.068f, 0.056f, 0.058f, 0.64f, 188.0f }
};

static inline void apply_custom_player_stats(void *ps_obj, int orig_char_id, int log_flag) {
    if (!ps_obj) return;
    if (orig_char_id < CUSTOM_STATS_FIRST_ID ||
        orig_char_id >= CUSTOM_STATS_FIRST_ID + CUSTOM_STATS_COUNT) {
        return;
    }
    const CustomPlayerStats *st = &g_custom_player_stats[orig_char_id - CUSTOM_STATS_FIRST_ID];
    char *p = (char *)ps_obj;

    *(float *)(p + 0x00) = st->stroke_pow_f;
    *(float *)(p + 0x04) = st->stroke_pow_b;
    *(float *)(p + 0x08) = st->slice_pow_f;
    *(float *)(p + 0x0c) = st->slice_pow_b;
    *(float *)(p + 0x10) = st->stroke_h_f;
    *(float *)(p + 0x14) = st->stroke_h_b;
    *(float *)(p + 0x20) = st->stroke_ctrl_f;
    *(float *)(p + 0x24) = st->stroke_ctrl_b;
    *(float *)(p + 0x58) = st->volley_pow_f;
    *(float *)(p + 0x5c) = st->volley_pow_b;
    *(float *)(p + 0x78) = st->volley_ctrl_f;
    *(float *)(p + 0x7c) = st->volley_ctrl_b;
    *(float *)(p + 0x80) = st->drop_pow;
    *(float *)(p + 0x84) = st->drop_range;
    *(float *)(p + 0x88) = st->serve_spd;
    *(float *)(p + 0x94) = st->serve_ctrl;
    *(float *)(p + 0x98) = st->max_serve_bonus;
    *(float *)(p + 0x9c) = st->accel_x;
    *(float *)(p + 0xa0) = st->accel_z;
    *(float *)(p + 0xa4) = st->max_spd_x;
    *(float *)(p + 0xa8) = st->max_spd_z;
    *(float *)(p + 0xac) = st->turn_spd;
    *(float *)(p + 0xb4) = st->gauge_coef;

    if (log_flag) {
        log_msg("[VT4-Mod] [STATS] Applied ID %d (%s): F=%.1f B=%.1f V=%.1f Srv=%.1f (Max %.0f km/h) SpdX=%.3f",
                orig_char_id, st->code, st->stroke_pow_f, st->stroke_pow_b,
                st->volley_pow_f, st->serve_spd, st->serve_max_kmh, st->max_spd_x);
    }
}

#endif /* VT4_PLAYER_STATS_H */
