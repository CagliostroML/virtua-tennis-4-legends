/*
 * netplay.h — P2P UDP Lockstep Online Netplay (Crossplay PC <-> Android/Winlator)
 *             for Virtua Tennis 4 Legends & Next-Gen Edition.
 *
 * Wire protocol: 'NVT4' v1 little-endian UDP (default port 7777).
 *   - Host (Mode=1) binds UDP port, learns Client IP automatically from NP_PKT_HELLO,
 *     generates authoritative session_seed + negotiates DelayFrames.
 *   - Client (Mode=2) sends NP_PKT_HELLO -> PeerIP:Port and receives NP_PKT_WELCOME.
 *   - On entering a Live Match, both peers cross NP_PKT_BARRIER, synchronize PRNG seeds,
 *     promote slot 1 (P2) to Human (control_type=1), and exchange 3-byte gameplay inputs
 *     with up to 8-tick sliding redundancy for zero-desync lockstep over lossy WiFi/WAN.
 *
 * Hotkeys:
 *   F9  = Disconnect active Netplay session cleanly and continue offline.
 *   (F10 remains Screenshot, F8 NextGenFX, F2 Options, F11 Fullscreen.)
 */
#ifndef VT4_NETPLAY_H
#define VT4_NETPLAY_H

#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0600
#endif

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Standalone unit tests can define VT4_NETPLAY_STANDALONE and provide nothing else. */
#ifdef VT4_NETPLAY_STANDALONE
#ifndef NP_LOG
static inline void np_default_log(const char *fmt, ...) { (void)fmt; }
#define NP_LOG(...) np_default_log(__VA_ARGS__)
#endif
#else
#ifndef NP_LOG
#define NP_LOG(...) log_msg(__VA_ARGS__)
#endif
#endif

/* =========================================================================
 * Protocol Constants & Packed Wire Packets
 * ========================================================================= */
#define NP_MAGIC            0x3454564Eu /* 'N','V','T','4' little-endian */
#define NP_PROTO_VER        1u
#define NP_RING_SIZE        256u        /* Power-of-two ring buffer (~4.26s @ 60Hz) */
#define NP_RING_MASK        (NP_RING_SIZE - 1u)
#define NP_REDUNDANCY       8u          /* Up to 8 consecutive ticks per UDP datagram */
#define NP_HASH_RING_SIZE   64u
#define NP_RESEND_MS        12u
#define NP_CTRL_INTERVAL_MS 45u
#define NP_PEER_TIMEOUT_MS  10000u

enum {
    NP_MODE_OFF    = 0,
    NP_MODE_HOST   = 1,
    NP_MODE_CLIENT = 2
};

enum {
    NP_STATE_OFF          = 0,
    NP_STATE_HANDSHAKE    = 1,
    NP_STATE_READY_MENU   = 2,
    NP_STATE_BARRIER      = 3,
    NP_STATE_PLAYING      = 4,
    NP_STATE_DISCONNECTED = 5
};

enum {
    NP_PKT_HELLO    = 1,
    NP_PKT_WELCOME  = 2,
    NP_PKT_BARRIER  = 3,
    NP_PKT_INPUT    = 4,
    NP_PKT_BYE      = 5,
    NP_PKT_DISCOVER = 6,
    NP_PKT_OFFER    = 7
};

#pragma pack(push, 1)
typedef struct {
    uint32_t magic;
    uint8_t  ver;
    uint8_t  type;
    uint16_t flags;   /* delay_frames in WELCOME; sync flags in BARRIER */
    uint32_t arg0;    /* client_nonce in HELLO; session_seed in WELCOME/BARRIER */
    uint32_t arg1;    /* delay_pref in HELLO; host_nonce in WELCOME; p1_char in BARRIER */
    uint32_t arg2;    /* p2_char in BARRIER */
    uint32_t arg3;    /* reserved / seq */
} NpCtrlPkt;

typedef struct {
    uint32_t magic;
    uint8_t  ver;
    uint8_t  type;        /* NP_PKT_INPUT (4) */
    uint8_t  count;       /* 1..NP_REDUNDANCY */
    uint8_t  flags;       /* bit 0: state_hash valid for hash_tick */
    uint32_t base_tick;   /* tick corresponding to inputs[0] */
    uint32_t ack_tick;    /* highest contiguous RX tick received + 1 */
    uint32_t ping_ts_ms;  /* sender's current ms timestamp */
    uint32_t pong_ts_ms;  /* echoed peer ping_ts_ms */
    uint32_t state_hash;  /* periodic deterministic simulation hash */
    uint32_t hash_tick;   /* match_tick where state_hash was captured */
    uint8_t  inputs[NP_REDUNDANCY][3]; /* [stick_x, stick_y, deterministic_btns] */
} NpInputPkt;
#pragma pack(pop)

#if defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L
_Static_assert(sizeof(NpCtrlPkt) == 24, "NpCtrlPkt must be 24 bytes");
_Static_assert(sizeof(NpInputPkt) == 56, "NpInputPkt must be 56 bytes");
#endif

typedef struct {
    uint32_t tick;
    uint8_t  valid;
    uint8_t  data[3];
} NpInputSlot;

typedef struct {
    uint32_t tick;
    uint32_t hash;
    uint8_t  valid;
} NpHashSlot;

typedef uint8_t *(__thiscall *NpSampleInputFn_t)(void *mgr, uint8_t *out3, int slot, uint8_t cam_rot);

typedef struct {
    /* Settings */
    uint32_t mode;          /* 0=OFF, 1=HOST, 2=CLIENT */
    char     peer_ip[64];
    uint16_t port;
    uint16_t local_port;
    uint32_t delay_frames;  /* 1..12 */

    /* Winsock2 state */
    int      wsa_started;
    SOCKET   sock;
    int      sock_open;
    struct sockaddr_in peer_addr;
    int      has_peer_addr;

    /* High-res monotonic clock */
    LARGE_INTEGER qpc_freq;
    LARGE_INTEGER qpc_start;

    /* Session state */
    int      state;
    uint32_t local_nonce;
    uint32_t peer_nonce;
    uint32_t session_seed;
    int      has_session_seed;

    /* Barrier & match tracking */
    void    *last_match_self;
    int      p1_char;
    int      p2_char;
    int      barrier_local_ready;
    int      barrier_peer_ready;
    int      p2_promoted;
    int      seed_applied;

    /* Lockstep frame state */
    uint32_t match_tick;
    uint32_t highest_sampled_tick;
    int      in_lockstep_step;
    uint8_t  cur_p1[3];
    uint8_t  cur_p2[3];

    NpInputSlot tx_ring[NP_RING_SIZE];
    NpInputSlot rx_ring[NP_RING_SIZE];
    uint32_t    rx_contig_tick;  /* All ticks < rx_contig_tick received in order */
    uint32_t    peer_ack_tick;   /* Highest contiguous tick confirmed by peer */

    /* Retransmit, keepalive & RTT */
    uint32_t last_ctrl_tx_ms;
    uint32_t last_input_tx_ms;
    uint32_t last_rx_ms;
    uint32_t last_peer_ping_ms;
    uint32_t rtt_ms;
    int      has_rtt;

    /* Desync watchdog */
    NpHashSlot local_hashes[NP_HASH_RING_SIZE];
    uint32_t   pending_tx_hash;
    uint32_t   pending_tx_hash_tick;
    int        has_pending_tx_hash;
    uint32_t   last_sync_hash_tick;
    int        sync_ok;
    uint32_t   desync_count;

    /* Edge-trigger for F9 disconnect hotkey */
    int      prev_f9_down;
} NpContext;

static NpContext g_np;

/* =========================================================================
 * Timing & Small Socket Helpers
 * ========================================================================= */
static inline void np_init_clock(NpContext *np) {
    if (np->qpc_freq.QuadPart == 0) {
        QueryPerformanceFrequency(&np->qpc_freq);
        QueryPerformanceCounter(&np->qpc_start);
    }
}

static inline uint32_t np_now_ms(NpContext *np) {
    if (np->qpc_freq.QuadPart <= 0) {
        np_init_clock(np);
    }
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    return (uint32_t)(((now.QuadPart - np->qpc_start.QuadPart) * 1000LL) / np->qpc_freq.QuadPart);
}

static inline uint32_t np_clamp_delay(uint32_t d) {
    if (d < 1u) return 1u;
    if (d > 12u) return 12u;
    return d;
}

static void np_reset_match_state(NpContext *np) {
    np->barrier_local_ready = 0;
    np->barrier_peer_ready = 0;
    np->p2_promoted = 0;
    np->seed_applied = 0;
    np->match_tick = 0;
    np->highest_sampled_tick = 0;
    np->in_lockstep_step = 0;
    np->rx_contig_tick = 0;
    np->peer_ack_tick = 0;
    memset(np->cur_p1, 0, sizeof(np->cur_p1));
    memset(np->cur_p2, 0, sizeof(np->cur_p2));
    memset(np->tx_ring, 0, sizeof(np->tx_ring));
    memset(np->rx_ring, 0, sizeof(np->rx_ring));
    memset(np->local_hashes, 0, sizeof(np->local_hashes));
    np->has_pending_tx_hash = 0;
    np->pending_tx_hash = 0;
    np->pending_tx_hash_tick = 0;
    np->last_sync_hash_tick = 0;
    np->sync_ok = 1;
    np->desync_count = 0;
    np->last_ctrl_tx_ms = 0;
    np->last_input_tx_ms = 0;
}

static void np_prefill_initial_delay(NpContext *np) {
    uint32_t d = np_clamp_delay(np->delay_frames);
    np->delay_frames = d;
    for (uint32_t t = 0; t < d; t++) {
        NpInputSlot *tx = &np->tx_ring[t & NP_RING_MASK];
        NpInputSlot *rx = &np->rx_ring[t & NP_RING_MASK];
        tx->tick = t;
        tx->valid = 1;
        memset(tx->data, 0, 3);
        rx->tick = t;
        rx->valid = 1;
        memset(rx->data, 0, 3);
    }
    np->rx_contig_tick = d;
    np->highest_sampled_tick = d; /* First live sample will be for tick = d */
}

static void np_ctx_send_to(NpContext *np, const void *buf, int len, const struct sockaddr_in *dst) {
    if (!np->sock_open || np->sock == INVALID_SOCKET || !dst) return;
    sendto(np->sock, (const char *)buf, len, 0, (const struct sockaddr *)dst, (int)sizeof(*dst));
}

static void np_ctx_send_ctrl(NpContext *np, uint8_t type, uint16_t flags,
                             uint32_t a0, uint32_t a1, uint32_t a2, uint32_t a3) {
    if (!np->has_peer_addr) return;
    NpCtrlPkt pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.magic = NP_MAGIC;
    pkt.ver = NP_PROTO_VER;
    pkt.type = type;
    pkt.flags = flags;
    pkt.arg0 = a0;
    pkt.arg1 = a1;
    pkt.arg2 = a2;
    pkt.arg3 = a3;
    np_ctx_send_to(np, &pkt, (int)sizeof(pkt), &np->peer_addr);
}

static void np_ctx_send_bye(NpContext *np) {
    if (!np->sock_open || !np->has_peer_addr) return;
    for (int i = 0; i < 2; i++) {
        np_ctx_send_ctrl(np, NP_PKT_BYE, 0, np->local_nonce, 0, 0, 0);
    }
}

static void np_ctx_close_socket(NpContext *np) {
    if (np->sock_open && np->sock != INVALID_SOCKET) {
        closesocket(np->sock);
    }
    np->sock = INVALID_SOCKET;
    np->sock_open = 0;
}

static inline void np_ctx_disconnect(NpContext *np, const char *reason) {
    if (np->state == NP_STATE_OFF || np->state == NP_STATE_DISCONNECTED) return;
    np_ctx_send_bye(np);
    np_ctx_close_socket(np);
    np->in_lockstep_step = 0;
    np->state = NP_STATE_DISCONNECTED;
    NP_LOG("[Netplay] Disconnected (%s) after %u ticks (desyncs=%u)",
           reason ? reason : "closed", np->match_tick, np->desync_count);
}

/* =========================================================================
 * Socket Startup (Reused by xlive.c & Standalone C Tests)
 * ========================================================================= */
static int np_ctx_open_socket(NpContext *np) {
    if (np->mode != NP_MODE_HOST && np->mode != NP_MODE_CLIENT) return 0;

    if (!np->wsa_started) {
        WSADATA wsa;
        if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
            NP_LOG("[Netplay] WSAStartup failed (err=%d)", WSAGetLastError());
            return 0;
        }
        np->wsa_started = 1;
    }

    SOCKET s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (s == INVALID_SOCKET) {
        NP_LOG("[Netplay] socket() failed (err=%d)", WSAGetLastError());
        return 0;
    }

    /* Non-blocking socket so peek/pump never stalls WinMain or Present */
    u_long nonblock = 1;
    ioctlsocket(s, (long)FIONBIO, &nonblock);

    /* Ignore WSAECONNRESET (10054) from ICMP Port Unreachable while peer boots */
    BOOL new_behavior = FALSE;
    DWORD bytes_ret = 0;
    WSAIoctl(s, (DWORD)IOC_IN | (DWORD)IOC_VENDOR | 12u /* SIO_UDP_CONNRESET */,
             &new_behavior, sizeof(new_behavior), NULL, 0, &bytes_ret, NULL, NULL);

    uint16_t bind_port = (np->local_port != 0) ? np->local_port : ((np->mode == NP_MODE_HOST) ? np->port : 0);
    struct sockaddr_in local_sa;
    memset(&local_sa, 0, sizeof(local_sa));
    local_sa.sin_family = AF_INET;
    local_sa.sin_addr.s_addr = htonl(INADDR_ANY);
    local_sa.sin_port = htons(bind_port);

    if (bind(s, (struct sockaddr *)&local_sa, (int)sizeof(local_sa)) == SOCKET_ERROR) {
        NP_LOG("[Netplay] bind(:%u) failed (err=%d)", (unsigned)bind_port, WSAGetLastError());
        closesocket(s);
        return 0;
    }

    if (np->local_port == 0 && np->mode == NP_MODE_CLIENT) {
        int sa_len = (int)sizeof(local_sa);
        if (getsockname(s, (struct sockaddr *)&local_sa, &sa_len) == 0) {
            np->local_port = ntohs(local_sa.sin_port);
        }
    }

    np->sock = s;
    np->sock_open = 1;
    np->has_peer_addr = 0;

    if (np->mode == NP_MODE_CLIENT) {
        struct addrinfo hints;
        struct addrinfo *res = NULL;
        memset(&hints, 0, sizeof(hints));
        hints.ai_family = AF_INET;
        hints.ai_socktype = SOCK_DGRAM;
        char port_str[16];
        snprintf(port_str, sizeof(port_str), "%u", (unsigned)np->port);
        if (getaddrinfo(np->peer_ip, port_str, &hints, &res) == 0 && res) {
            memcpy(&np->peer_addr, res->ai_addr, sizeof(struct sockaddr_in));
            np->has_peer_addr = 1;
            freeaddrinfo(res);
        } else {
            unsigned long ip4 = inet_addr(np->peer_ip);
            if (ip4 != INADDR_NONE) {
                memset(&np->peer_addr, 0, sizeof(np->peer_addr));
                np->peer_addr.sin_family = AF_INET;
                np->peer_addr.sin_addr.s_addr = ip4;
                np->peer_addr.sin_port = htons(np->port);
                np->has_peer_addr = 1;
            }
        }
        if (!np->has_peer_addr) {
            NP_LOG("[Netplay] Failed to resolve PeerIP='%s'", np->peer_ip);
            np_ctx_close_socket(np);
            return 0;
        }
    }

    LARGE_INTEGER qpc;
    QueryPerformanceCounter(&qpc);
    np->local_nonce = (uint32_t)(qpc.LowPart ^ GetCurrentProcessId() ^ ((uint32_t)np->mode << 24));
    if (np->local_nonce == 0) np->local_nonce = 0x13572468u;
    np->state = NP_STATE_HANDSHAKE;
    np->last_rx_ms = np_now_ms(np);
    NP_LOG("[Netplay] Initialized Mode=%s BindPort=%u Peer=%s:%u Delay=%u",
           (np->mode == NP_MODE_HOST) ? "HOST(P1)" : "CLIENT(P2)",
           (unsigned)bind_port, np->peer_ip, (unsigned)np->port, np->delay_frames);
    return 1;
}

/* =========================================================================
 * Sliding Input Send, RX Drain, Handshake & Barrier Core
 * ========================================================================= */
static void np_ctx_send_input_window(NpContext *np, uint32_t base_tick, uint32_t count, uint32_t now_ms) {
    if (!np->has_peer_addr || !np->sock_open || count == 0) return;
    if (count > NP_REDUNDANCY) count = NP_REDUNDANCY;

    NpInputPkt pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.magic = NP_MAGIC;
    pkt.ver = NP_PROTO_VER;
    pkt.type = NP_PKT_INPUT;
    pkt.count = (uint8_t)count;
    pkt.flags = np->has_pending_tx_hash ? 1u : 0u;
    pkt.base_tick = base_tick;
    pkt.ack_tick = np->rx_contig_tick;
    pkt.ping_ts_ms = now_ms;
    pkt.pong_ts_ms = np->last_peer_ping_ms;
    pkt.state_hash = np->pending_tx_hash;
    pkt.hash_tick = np->pending_tx_hash_tick;

    uint32_t actual = 0;
    for (uint32_t i = 0; i < count; i++) {
        uint32_t t = base_tick + i;
        const NpInputSlot *tx = &np->tx_ring[t & NP_RING_MASK];
        if (!tx->valid || tx->tick != t) break;
        pkt.inputs[i][0] = tx->data[0];
        pkt.inputs[i][1] = tx->data[1];
        pkt.inputs[i][2] = tx->data[2];
        actual++;
    }
    if (actual == 0) return;
    pkt.count = (uint8_t)actual;

    np_ctx_send_to(np, &pkt, (int)sizeof(pkt), &np->peer_addr);
    np->last_input_tx_ms = now_ms;
}

static void np_ctx_send_input_bundle(NpContext *np, uint32_t now_ms) {
    if (!np->has_peer_addr || !np->sock_open) return;

    uint32_t end_tick = np->highest_sampled_tick; /* Exclusive */
    if (end_tick == 0) end_tick = np->match_tick + np->delay_frames;
    if (end_tick == 0) return;

    /* Always guarantee the peer receives its oldest unacknowledged ticks even under burst loss/jitter */
    if (np->peer_ack_tick < end_tick && (end_tick - np->peer_ack_tick) > NP_REDUNDANCY) {
        np_ctx_send_input_window(np, np->peer_ack_tick, NP_REDUNDANCY, now_ms);
    }

    uint32_t count = (end_tick >= NP_REDUNDANCY) ? NP_REDUNDANCY : end_tick;
    uint32_t base_tick = end_tick - count;
    np_ctx_send_input_window(np, base_tick, count, now_ms);
}

static void np_ctx_advance_rx_contig(NpContext *np) {
    while (1) {
        const NpInputSlot *rx = &np->rx_ring[np->rx_contig_tick & NP_RING_MASK];
        if (!rx->valid || rx->tick != np->rx_contig_tick) break;
        if (np->rx_contig_tick - np->match_tick >= NP_RING_SIZE - 16u) break;
        np->rx_contig_tick++;
    }
}

static void np_ctx_handle_input_pkt(NpContext *np, const NpInputPkt *pkt, uint32_t now_ms) {
    if (pkt->count == 0 || pkt->count > NP_REDUNDANCY) return;

    if (pkt->ack_tick > np->peer_ack_tick && pkt->ack_tick <= np->highest_sampled_tick) {
        np->peer_ack_tick = pkt->ack_tick;
    }

    /* Update RTT if peer echoed our ping timestamp */
    if (pkt->pong_ts_ms != 0 && now_ms >= pkt->pong_ts_ms) {
        uint32_t sample = now_ms - pkt->pong_ts_ms;
        if (sample < 2000u) {
            if (!np->has_rtt) {
                np->rtt_ms = sample;
                np->has_rtt = 1;
            } else {
                np->rtt_ms = (np->rtt_ms * 3u + sample) / 4u;
            }
        }
    }
    if (pkt->ping_ts_ms != 0) {
        np->last_peer_ping_ms = pkt->ping_ts_ms;
    }

    /* Check peer periodic simulation hash against our stored local hash */
    if ((pkt->flags & 1u) != 0) {
        const NpHashSlot *hs = &np->local_hashes[pkt->hash_tick % NP_HASH_RING_SIZE];
        if (hs->valid && hs->tick == pkt->hash_tick && np->last_sync_hash_tick != pkt->hash_tick) {
            np->last_sync_hash_tick = pkt->hash_tick;
            if (hs->hash == pkt->state_hash) {
                np->sync_ok = 1;
            } else {
                np->sync_ok = 0;
                np->desync_count++;
                NP_LOG("[Netplay] DESYNC warning at tick=%u local=0x%08x remote=0x%08x",
                       pkt->hash_tick, hs->hash, pkt->state_hash);
            }
        }
    }

    for (uint32_t i = 0; i < (uint32_t)pkt->count; i++) {
        uint32_t t = pkt->base_tick + i;
        if (t < np->match_tick) continue;
        if (t >= np->match_tick + NP_RING_SIZE - 4u) continue;
        NpInputSlot *rx = &np->rx_ring[t & NP_RING_MASK];
        if (!rx->valid || rx->tick != t) {
            rx->tick = t;
            rx->valid = 1;
            rx->data[0] = pkt->inputs[i][0];
            rx->data[1] = pkt->inputs[i][1];
            rx->data[2] = pkt->inputs[i][2];
        }
    }
    np_ctx_advance_rx_contig(np);
}

static void np_ctx_handle_ctrl_pkt(NpContext *np, const NpCtrlPkt *pkt,
                                   const struct sockaddr_in *src, uint32_t now_ms) {
    switch (pkt->type) {
        case NP_PKT_HELLO: {
            if (np->mode != NP_MODE_HOST) break;
            uint32_t client_nonce = pkt->arg0;
            uint32_t client_delay = pkt->arg1;
            int is_new_peer = (!np->has_peer_addr || np->peer_nonce != client_nonce);
            np->peer_addr = *src;
            np->has_peer_addr = 1;
            if (is_new_peer) {
                np->peer_nonce = client_nonce;
                np->delay_frames = np_clamp_delay(client_delay > np->delay_frames ? client_delay : np->delay_frames);
                np->session_seed = (now_ms ^ client_nonce ^ np->local_nonce ^ 0xA519B3D1u) | 1u;
                np->has_session_seed = 1;
                if (np->state == NP_STATE_HANDSHAKE) {
                    np->state = NP_STATE_READY_MENU;
                }
                NP_LOG("[Netplay] Handshake OK (HOST): client=%s:%u seed=0x%08x delay=%u",
                       inet_ntoa(src->sin_addr), (unsigned)ntohs(src->sin_port),
                       np->session_seed, np->delay_frames);
            }
            np_ctx_send_ctrl(np, NP_PKT_WELCOME, (uint16_t)np->delay_frames,
                             np->session_seed, np->local_nonce, 0, 0);
            break;
        }
        case NP_PKT_WELCOME: {
            if (np->mode != NP_MODE_CLIENT) break;
            uint32_t new_delay = np_clamp_delay((uint32_t)pkt->flags);
            uint32_t new_seed = pkt->arg0;
            uint32_t host_nonce = pkt->arg1;
            if (np->state == NP_STATE_HANDSHAKE || np->peer_nonce != host_nonce || !np->has_session_seed) {
                np->delay_frames = new_delay;
                np->session_seed = new_seed;
                np->has_session_seed = 1;
                np->peer_nonce = host_nonce;
                if (np->state == NP_STATE_HANDSHAKE) {
                    np->state = NP_STATE_READY_MENU;
                }
                NP_LOG("[Netplay] Handshake OK (CLIENT): host=%s:%u seed=0x%08x delay=%u",
                       inet_ntoa(src->sin_addr), (unsigned)ntohs(src->sin_port),
                       np->session_seed, np->delay_frames);
            }
            break;
        }
        case NP_PKT_BARRIER: {
            if (!np->has_peer_addr) {
                np->peer_addr = *src;
                np->has_peer_addr = 1;
            }
            /* Host is authoritative on session_seed & delay_frames */
            if (np->mode == NP_MODE_CLIENT && pkt->arg0 != 0) {
                np->session_seed = pkt->arg0;
                np->has_session_seed = 1;
                if (pkt->flags >= 1u && pkt->flags <= 12u) {
                    np->delay_frames = np_clamp_delay((uint32_t)pkt->flags);
                }
            }
            np->barrier_peer_ready = 1;
            if (np->barrier_local_ready && np->state == NP_STATE_BARRIER) {
                np_prefill_initial_delay(np);
                np->state = NP_STATE_PLAYING;
                NP_LOG("[Netplay] Barrier OK -> PLAYING (tick=0 delay=%u seed=0x%08x)",
                       np->delay_frames, np->session_seed);
            }
            break;
        }
        case NP_PKT_BYE: {
            NP_LOG("[Netplay] Peer sent BYE at tick=%u", np->match_tick);
            np->in_lockstep_step = 0;
            np->state = NP_STATE_DISCONNECTED;
            break;
        }
        case NP_PKT_DISCOVER: {
            if (np->mode == NP_MODE_HOST) {
                NpCtrlPkt offer;
                memset(&offer, 0, sizeof(offer));
                offer.magic = NP_MAGIC;
                offer.ver   = NP_PROTO_VER;
                offer.type  = NP_PKT_OFFER;
                offer.flags = (uint16_t)np->delay_frames;
                offer.arg0  = np->local_nonce;
                offer.arg1  = (uint32_t)np->port;
                offer.arg2  = (uint32_t)np->state;
                np_ctx_send_to(np, &offer, (int)sizeof(offer), src);
            }
            break;
        }
        default:
            break;
    }
    (void)now_ms;
}

static void np_ctx_pump_rx(NpContext *np, uint32_t now_ms) {
    if (!np->sock_open || np->sock == INVALID_SOCKET) return;
    uint8_t buf[128];
    for (int iter = 0; iter < 64; iter++) {
        struct sockaddr_in src;
        int srclen = (int)sizeof(src);
        int n = recvfrom(np->sock, (char *)buf, (int)sizeof(buf), 0, (struct sockaddr *)&src, &srclen);
        if (n < 0) {
            int err = WSAGetLastError();
            if (err == WSAEWOULDBLOCK) break;
            if (err == WSAECONNRESET) continue;
            break;
        }
        if (n < (int)sizeof(NpCtrlPkt)) continue;
        const NpCtrlPkt *hdr = (const NpCtrlPkt *)buf;
        if (hdr->magic != NP_MAGIC || hdr->ver != NP_PROTO_VER) continue;

        np->last_rx_ms = now_ms;
        if (hdr->type == NP_PKT_INPUT && n >= (int)sizeof(NpInputPkt)) {
            const NpInputPkt *ipkt = (const NpInputPkt *)buf;
            if (np->state == NP_STATE_BARRIER && np->barrier_local_ready && ipkt->base_tick <= 64u) {
                /* Peer crossed barrier cleanly and already began sending tick 0.. */
                np->barrier_peer_ready = 1;
                np_prefill_initial_delay(np);
                np->state = NP_STATE_PLAYING;
                NP_LOG("[Netplay] Barrier OK (fast-start from INPUT) -> PLAYING (delay=%u seed=0x%08x)",
                       np->delay_frames, np->session_seed);
            }
            if (np->state == NP_STATE_PLAYING) {
                np_ctx_handle_input_pkt(np, ipkt, now_ms);
            }
        } else {
            np_ctx_handle_ctrl_pkt(np, hdr, &src, now_ms);
        }
    }
}

static void np_ctx_pump_ctrl_tx(NpContext *np, uint32_t now_ms) {
    if (np->last_ctrl_tx_ms != 0 && (now_ms - np->last_ctrl_tx_ms) < NP_CTRL_INTERVAL_MS) {
        return;
    }
    np->last_ctrl_tx_ms = now_ms;

    if (np->state == NP_STATE_HANDSHAKE && np->mode == NP_MODE_CLIENT) {
        np_ctx_send_ctrl(np, NP_PKT_HELLO, 0, np->local_nonce, np->delay_frames, 0, 0);
    } else if (np->state == NP_STATE_BARRIER && np->barrier_local_ready && np->has_peer_addr) {
        np_ctx_send_ctrl(np, NP_PKT_BARRIER, (uint16_t)np->delay_frames,
                         np->session_seed, (uint32_t)np->p1_char, (uint32_t)np->p2_char, 0);
    }
}

/*
 * Non-blocking UDP LAN Broadcast + Loopback Auto-Discovery.
 * Sends NP_PKT_DISCOVER on `port` to 255.255.255.255 and 127.0.0.1 and waits up to `timeout_ms`
 * for an NP_PKT_OFFER from any active HOST P1 room. Returns 1 if found, 0 otherwise.
 */
static int netplay_lan_discover(uint16_t port, char *out_ip, size_t ip_cap,
                                uint16_t *out_port, uint32_t *out_delay, uint32_t timeout_ms) {
    if (port == 0) port = 7777u;
    if (timeout_ms == 0 || timeout_ms > 2000u) timeout_ms = 320u;

    WSADATA wsa;
    if (!g_np.wsa_started) {
        if (WSAStartup(MAKEWORD(2, 2), &wsa) == 0) {
            g_np.wsa_started = 1;
        } else {
            return 0;
        }
    }

    SOCKET s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (s == INVALID_SOCKET) return 0;

    int bcast = 1;
    setsockopt(s, SOL_SOCKET, SO_BROADCAST, (const char *)&bcast, sizeof(bcast));
    u_long nb = 1;
    ioctlsocket(s, FIONBIO, &nb);

    struct sockaddr_in baddr;
    memset(&baddr, 0, sizeof(baddr));
    baddr.sin_family = AF_INET;
    baddr.sin_port = htons(0);
    baddr.sin_addr.s_addr = htonl(INADDR_ANY);
    bind(s, (const struct sockaddr *)&baddr, sizeof(baddr));

    NpCtrlPkt req;
    memset(&req, 0, sizeof(req));
    req.magic = NP_MAGIC;
    req.ver   = NP_PROTO_VER;
    req.type  = NP_PKT_DISCOVER;

    struct sockaddr_in dst_bcast, dst_lo;
    memset(&dst_bcast, 0, sizeof(dst_bcast));
    dst_bcast.sin_family = AF_INET;
    dst_bcast.sin_port = htons(port);
    dst_bcast.sin_addr.s_addr = htonl(INADDR_BROADCAST);

    memset(&dst_lo, 0, sizeof(dst_lo));
    dst_lo.sin_family = AF_INET;
    dst_lo.sin_port = htons(port);
    dst_lo.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    sendto(s, (const char *)&req, (int)sizeof(req), 0, (const struct sockaddr *)&dst_bcast, sizeof(dst_bcast));
    sendto(s, (const char *)&req, (int)sizeof(req), 0, (const struct sockaddr *)&dst_lo, sizeof(dst_lo));

    DWORD t0 = GetTickCount();
    int resent = 0;
    int found = 0;
    while ((DWORD)(GetTickCount() - t0) < timeout_ms) {
        if (!resent && (DWORD)(GetTickCount() - t0) >= timeout_ms / 2u) {
            resent = 1;
            sendto(s, (const char *)&req, (int)sizeof(req), 0, (const struct sockaddr *)&dst_bcast, sizeof(dst_bcast));
            sendto(s, (const char *)&req, (int)sizeof(req), 0, (const struct sockaddr *)&dst_lo, sizeof(dst_lo));
        }
        fd_set rfds;
        FD_ZERO(&rfds);
        FD_SET(s, &rfds);
        struct timeval tv;
        tv.tv_sec = 0;
        tv.tv_usec = 20000;
        int rc = select(0, &rfds, NULL, NULL, &tv);
        if (rc > 0 && FD_ISSET(s, &rfds)) {
            uint8_t buf[64];
            struct sockaddr_in from;
            int flen = (int)sizeof(from);
            int n = recvfrom(s, (char *)buf, (int)sizeof(buf), 0, (struct sockaddr *)&from, &flen);
            if (n >= (int)sizeof(NpCtrlPkt)) {
                const NpCtrlPkt *hdr = (const NpCtrlPkt *)buf;
                if (hdr->magic == NP_MAGIC && hdr->ver == NP_PROTO_VER && hdr->type == NP_PKT_OFFER) {
                    if (out_ip && ip_cap > 0) {
                        const char *ip_s = inet_ntoa(from.sin_addr);
                        strncpy(out_ip, ip_s ? ip_s : "127.0.0.1", ip_cap - 1);
                        out_ip[ip_cap - 1] = '\0';
                    }
                    if (out_port) *out_port = (hdr->arg1 > 0 && hdr->arg1 <= 65535u) ? (uint16_t)hdr->arg1 : port;
                    if (out_delay) *out_delay = np_clamp_delay((uint32_t)hdr->flags);
                    found = 1;
                    break;
                }
            }
        }
    }

    closesocket(s);
    return found;
}

/* =========================================================================
 * Integration API (Called from xlive.c)
 * ========================================================================= */
#ifndef VT4_NETPLAY_STANDALONE

static void netplay_init(const char *ini_path) {
    memset(&g_np, 0, sizeof(g_np));
    g_np.sock = INVALID_SOCKET;
    np_init_clock(&g_np);

    g_np.mode = GetPrivateProfileIntA("Netplay", "Mode", 0, ini_path);
    if (g_np.mode > NP_MODE_CLIENT) g_np.mode = NP_MODE_OFF;
    GetPrivateProfileStringA("Netplay", "PeerIP", "127.0.0.1", g_np.peer_ip, sizeof(g_np.peer_ip), ini_path);
    uint32_t port = GetPrivateProfileIntA("Netplay", "Port", 7777, ini_path);
    uint32_t lport = GetPrivateProfileIntA("Netplay", "LocalPort", 0, ini_path);
    g_np.delay_frames = np_clamp_delay(GetPrivateProfileIntA("Netplay", "DelayFrames", 3, ini_path));

    char env_buf[128];
    if (GetEnvironmentVariableA("VT4_NET_MODE", env_buf, sizeof(env_buf)) > 0) {
        uint32_t m = (uint32_t)atoi(env_buf);
        if (m <= NP_MODE_CLIENT) g_np.mode = m;
    }
    if (GetEnvironmentVariableA("VT4_NET_IP", env_buf, sizeof(env_buf)) > 0 && env_buf[0]) {
        strncpy(g_np.peer_ip, env_buf, sizeof(g_np.peer_ip) - 1);
        g_np.peer_ip[sizeof(g_np.peer_ip) - 1] = '\0';
    }
    if (GetEnvironmentVariableA("VT4_NET_PORT", env_buf, sizeof(env_buf)) > 0) {
        uint32_t p = (uint32_t)atoi(env_buf);
        if (p > 0 && p <= 65535u) port = p;
    }
    if (GetEnvironmentVariableA("VT4_NET_LOCAL_PORT", env_buf, sizeof(env_buf)) > 0) {
        uint32_t lp = (uint32_t)atoi(env_buf);
        if (lp <= 65535u) lport = lp;
    }
    if (GetEnvironmentVariableA("VT4_NET_DELAY", env_buf, sizeof(env_buf)) > 0) {
        g_np.delay_frames = np_clamp_delay((uint32_t)atoi(env_buf));
    }

    if (port == 0 || port > 65535u) port = 7777u;
    g_np.port = (uint16_t)port;
    g_np.local_port = (lport <= 65535u) ? (uint16_t)lport : 0;

    if (g_np.mode == NP_MODE_OFF) {
        g_np.state = NP_STATE_OFF;
        return;
    }

    if (!np_ctx_open_socket(&g_np)) {
        g_np.state = NP_STATE_DISCONNECTED;
    }
}

static void netplay_shutdown(void) {
    if (g_np.sock_open) {
        np_ctx_send_bye(&g_np);
        np_ctx_close_socket(&g_np);
    }
    if (g_np.wsa_started) {
        WSACleanup();
        g_np.wsa_started = 0;
    }
    g_np.in_lockstep_step = 0;
    g_np.state = NP_STATE_OFF;
}

static inline int netplay_is_enabled(void) {
    return (g_np.mode != NP_MODE_OFF &&
            g_np.state != NP_STATE_OFF &&
            g_np.state != NP_STATE_DISCONNECTED);
}

static inline int netplay_is_stepping(void) {
    return (g_np.state == NP_STATE_PLAYING && g_np.in_lockstep_step != 0);
}

static inline const uint8_t *netplay_get_slot_input(int slot) {
    if (slot == 0) return g_np.cur_p1;
    if (slot == 1) return g_np.cur_p2;
    return NULL;
}

static inline int netplay_has_session_seed(void) {
    return (netplay_is_enabled() && g_np.has_session_seed);
}

static inline uint32_t netplay_get_session_seed(void) {
    return g_np.session_seed;
}

/* Safe wrapper around VT4's PlayerMgr::GetPlayerBySlot (0x00541d00 + 0x005415b0) */
static inline void *np_get_player_by_slot(int slot) {
    typedef void *(__cdecl *GetMgr_t)(void);
    typedef void *(__thiscall *GetPlayer_t)(void *, int);
    void *mgr = ((GetMgr_t)0x00541d00)();
    if (!mgr || (uintptr_t)mgr < 0x10000u) return NULL;
    void *p = ((GetPlayer_t)0x005415b0)(mgr, slot);
    if (!p || (uintptr_t)p < 0x10000u) return NULL;
    return p;
}

static void netplay_ensure_p2_human(void *match_self) {
    (void)match_self;
    if (!netplay_is_enabled()) return;
    void *p2 = np_get_player_by_slot(1);
    if (!p2) return;
    int *ctrl_ptr = (int *)((char *)p2 + 0x244);
    if (*ctrl_ptr != 1) {
        *ctrl_ptr = 1;
        if (!g_np.p2_promoted) {
            g_np.p2_promoted = 1;
            NP_LOG("[Netplay] P2 promoted to Human (control_type=1, ptr=%p)", p2);
        }
    }
}

static inline void np_apply_vt4_rng_seed(uint32_t seed) {
    if (!seed) return;
    typedef void *(__cdecl *GetRngMgr_t)(void);
    typedef void (__thiscall *SetSeed_t)(void *, const char *, uint32_t);
    typedef void (__cdecl *CrtSrand_t)(unsigned int);
    void *rng_mgr = ((GetRngMgr_t)0x00632f30)();
    if (rng_mgr && (uintptr_t)rng_mgr >= 0x10000u) {
        ((SetSeed_t)0x00632cf0)(rng_mgr, (const char *)0x007e89e5, seed);
    }
    CrtSrand_t real_srand = *(CrtSrand_t *)0x007883e8;
    if (real_srand) real_srand(seed);
}

static uint32_t np_compute_sim_hash(uint32_t seed) {
    uint32_t h = 2166136261u ^ seed;
    for (int slot = 0; slot < 2; slot++) {
        void *p = np_get_player_by_slot(slot);
        if (p) {
            const uint32_t *coords = (const uint32_t *)((const char *)p + 0x18);
            for (int k = 0; k < 3; k++) {
                /* Round/mask lowest 2 mantissa bits to tolerate x87/SSE tiny float noise if any */
                uint32_t v = coords[k] & 0xFFFFFFFCu;
                h ^= v;
                h *= 16777619u;
            }
        }
    }
    return h ? h : 1u;
}

static void netplay_on_live_match_ready(void *match_self, int p1_char, int p2_char) {
    if (!netplay_is_enabled()) return;
    if (match_self == g_np.last_match_self &&
        (g_np.state == NP_STATE_BARRIER || g_np.state == NP_STATE_PLAYING)) {
        return;
    }

    g_np.last_match_self = match_self;
    np_reset_match_state(&g_np);
    g_np.p1_char = p1_char;
    g_np.p2_char = p2_char;
    g_np.barrier_local_ready = 1;
    g_np.last_rx_ms = np_now_ms(&g_np);

    if (g_np.has_session_seed) {
        np_apply_vt4_rng_seed(g_np.session_seed);
        g_np.seed_applied = 1;
    }

    if (g_np.state == NP_STATE_READY_MENU || g_np.state == NP_STATE_BARRIER || g_np.state == NP_STATE_PLAYING) {
        g_np.state = NP_STATE_BARRIER;
        NP_LOG("[Netplay] Entering Match BARRIER (mode=%u peer=%s:%u p1=%d p2=%d seed=0x%08x)",
               g_np.mode, g_np.peer_ip, (unsigned)g_np.port, p1_char, p2_char, g_np.session_seed);
    } else {
        NP_LOG("[Netplay] Match ready while still in HANDSHAKE (waiting for peer)");
    }
    netplay_ensure_p2_human(match_self);
}

static void netplay_poll_background(void) {
    if (!netplay_is_enabled()) return;

    /* F9 clean disconnect hotkey (never collides with F10 screenshot!) */
    int f9 = (GetAsyncKeyState(VK_F9) & 0x8000) ? 1 : 0;
    if (f9 && !g_np.prev_f9_down) {
        g_np.prev_f9_down = 1;
        np_ctx_disconnect(&g_np, "F9 hotkey");
        return;
    }
    g_np.prev_f9_down = f9;

    uint32_t now_ms = np_now_ms(&g_np);
    np_ctx_pump_rx(&g_np, now_ms);
    if (g_np.state == NP_STATE_HANDSHAKE || g_np.state == NP_STATE_BARRIER) {
        np_ctx_pump_ctrl_tx(&g_np, now_ms);
    }
}

static void np_sample_local_keyboard_fallback(uint8_t out3[3]) {
    int8_t sx = 0, sy = 0;
    if (is_key_down(VK_LEFT)  || is_key_down('A')) sx = -127;
    else if (is_key_down(VK_RIGHT) || is_key_down('D')) sx = 127;
    if (is_key_down(VK_UP)    || is_key_down('W')) sy = 127;
    else if (is_key_down(VK_DOWN)  || is_key_down('S')) sy = -127;
    uint8_t btns = 0;
    if (is_key_down('Z') || is_key_down('J') || is_key_down(VK_RETURN)) btns |= 0x09u;
    if (is_key_down('X') || is_key_down('L')) btns |= 0x19u;
    if (is_key_down('C') || is_key_down('K')) btns |= 0x0Au;
    if (is_key_down('V') || is_key_down('I')) btns |= 0x0Cu;
    out3[0] = (uint8_t)sx;
    out3[1] = (uint8_t)sy;
    out3[2] = btns;
}

static int netplay_pre_step(void *match_input_mgr, NpSampleInputFn_t real_sample_fn) {
    if (!netplay_is_enabled()) return 1;

    uint32_t now_ms = np_now_ms(&g_np);

    /* Ensure F9 hotkey works even if hk_Present hasn't fired since last step */
    int f9 = (GetAsyncKeyState(VK_F9) & 0x8000) ? 1 : 0;
    if (f9 && !g_np.prev_f9_down) {
        g_np.prev_f9_down = 1;
        np_ctx_disconnect(&g_np, "F9 hotkey");
        return 1;
    }
    g_np.prev_f9_down = f9;

    np_ctx_pump_rx(&g_np, now_ms);

    if (g_np.state == NP_STATE_READY_MENU && g_np.barrier_local_ready) {
        g_np.state = NP_STATE_BARRIER;
    }

    if (g_np.state == NP_STATE_HANDSHAKE || g_np.state == NP_STATE_BARRIER) {
        if (g_np.barrier_local_ready && g_np.has_session_seed && !g_np.seed_applied) {
            np_apply_vt4_rng_seed(g_np.session_seed);
            g_np.seed_applied = 1;
        }
        np_ctx_pump_ctrl_tx(&g_np, now_ms);
        return 0; /* Hold FrameStep cleanly while Present pumps window events */
    }

    if (g_np.state != NP_STATE_PLAYING) return 1;

    if (g_np.has_session_seed && !g_np.seed_applied) {
        np_apply_vt4_rng_seed(g_np.session_seed);
        g_np.seed_applied = 1;
    }

    /* Sample local input ONCE for future tick (match_tick + delay_frames) */
    uint32_t target_tick = g_np.match_tick + g_np.delay_frames;
    if (g_np.highest_sampled_tick <= target_tick) {
        uint8_t local_pkt[3] = { 0, 0, 0 };
        if (real_sample_fn &&
            match_input_mgr && (uintptr_t)match_input_mgr > 0x10000u &&
            *(uintptr_t *)((char *)match_input_mgr + 4) > 0x10000u) {
            real_sample_fn(match_input_mgr, local_pkt, 0, 1);
        } else {
            np_sample_local_keyboard_fallback(local_pkt);
        }
        /* Mask out non-deterministic local camera/pause bits 5..7 on the wire */
        local_pkt[2] &= 0x1Fu;

        NpInputSlot *tx = &g_np.tx_ring[target_tick & NP_RING_MASK];
        tx->tick = target_tick;
        tx->valid = 1;
        memcpy(tx->data, local_pkt, 3);
        g_np.highest_sampled_tick = target_tick + 1u;

        /* Capture deterministic state hash every 60 ticks */
        if (g_np.match_tick > 0 && (g_np.match_tick % 60u) == 0) {
            uint32_t h = np_compute_sim_hash(g_np.session_seed);
            NpHashSlot *hs = &g_np.local_hashes[g_np.match_tick % NP_HASH_RING_SIZE];
            hs->tick = g_np.match_tick;
            hs->hash = h;
            hs->valid = 1;
            g_np.pending_tx_hash = h;
            g_np.pending_tx_hash_tick = g_np.match_tick;
            g_np.has_pending_tx_hash = 1;
        }

        np_ctx_send_input_bundle(&g_np, now_ms);
        np_ctx_pump_rx(&g_np, now_ms);
    }

    const NpInputSlot *tx_cur = &g_np.tx_ring[g_np.match_tick & NP_RING_MASK];
    const NpInputSlot *rx_cur = &g_np.rx_ring[g_np.match_tick & NP_RING_MASK];

    if (tx_cur->valid && tx_cur->tick == g_np.match_tick &&
        rx_cur->valid && rx_cur->tick == g_np.match_tick) {
        if (g_np.mode == NP_MODE_HOST) {
            memcpy(g_np.cur_p1, tx_cur->data, 3);
            memcpy(g_np.cur_p2, rx_cur->data, 3);
        } else {
            memcpy(g_np.cur_p1, rx_cur->data, 3);
            memcpy(g_np.cur_p2, tx_cur->data, 3);
        }
        g_np.in_lockstep_step = 1;
        g_np.match_tick++;
        return 1;
    }

    /* Waiting for remote input at match_tick: resend bundle + timeout safety */
    if ((now_ms - g_np.last_input_tx_ms) >= NP_RESEND_MS) {
        np_ctx_send_input_bundle(&g_np, now_ms);
    }
    if ((now_ms - g_np.last_rx_ms) > NP_PEER_TIMEOUT_MS) {
        np_ctx_disconnect(&g_np, "peer timeout 10s");
        return 1;
    }
    return 0;
}

static inline void netplay_post_step(void) {
    g_np.in_lockstep_step = 0;
}

static void netplay_get_local_ip(char *out, size_t cap) {
    if (!out || cap == 0) return;
    strncpy(out, "127.0.0.1", cap - 1);
    out[cap - 1] = '\0';
    if (!g_np.wsa_started) {
        WSADATA wsa;
        if (WSAStartup(MAKEWORD(2, 2), &wsa) == 0) {
            g_np.wsa_started = 1;
        } else {
            return;
        }
    }
    char host[128] = {0};
    if (gethostname(host, sizeof(host) - 1) == 0 && host[0]) {
        struct hostent *he = gethostbyname(host);
        if (he && he->h_addr_list) {
            for (int i = 0; he->h_addr_list[i] != NULL; i++) {
                struct in_addr a;
                memcpy(&a, he->h_addr_list[i], sizeof(a));
                const char *s = inet_ntoa(a);
                if (s && strncmp(s, "127.", 4) != 0) {
                    strncpy(out, s, cap - 1);
                    out[cap - 1] = '\0';
                    return;
                }
            }
        }
    }
}

static void netplay_get_config(uint32_t *mode, char *ip_out, size_t ip_cap, uint16_t *port, uint32_t *delay) {
    if (mode) *mode = g_np.mode;
    if (ip_out && ip_cap > 0) {
        if (g_np.peer_ip[0]) {
            strncpy(ip_out, g_np.peer_ip, ip_cap - 1);
            ip_out[ip_cap - 1] = '\0';
        } else {
            strncpy(ip_out, "127.0.0.1", ip_cap - 1);
            ip_out[ip_cap - 1] = '\0';
        }
    }
    if (port) *port = g_np.port ? g_np.port : 7777u;
    if (delay) *delay = np_clamp_delay(g_np.delay_frames ? g_np.delay_frames : 3u);
}

static int netplay_reconfigure_live(uint32_t mode, const char *peer_ip, uint16_t port,
                                    uint32_t delay_frames, const char *ini_path) {
    int keep_wsa = g_np.wsa_started;
    LARGE_INTEGER keep_freq = g_np.qpc_freq;
    LARGE_INTEGER keep_start = g_np.qpc_start;

    if (g_np.sock_open) {
        np_ctx_send_bye(&g_np);
        np_ctx_close_socket(&g_np);
    }

    memset(&g_np, 0, sizeof(g_np));
    g_np.sock = INVALID_SOCKET;
    g_np.wsa_started = keep_wsa;
    g_np.qpc_freq = keep_freq;
    g_np.qpc_start = keep_start;
    np_init_clock(&g_np);

    if (mode > NP_MODE_CLIENT) mode = NP_MODE_OFF;
    g_np.mode = mode;
    if (peer_ip && peer_ip[0]) {
        strncpy(g_np.peer_ip, peer_ip, sizeof(g_np.peer_ip) - 1);
        g_np.peer_ip[sizeof(g_np.peer_ip) - 1] = '\0';
    } else {
        strcpy(g_np.peer_ip, "127.0.0.1");
    }
    g_np.port = (port > 0) ? port : 7777u;
    g_np.local_port = 0;
    g_np.delay_frames = np_clamp_delay(delay_frames);

    if (ini_path && ini_path[0]) {
        char buf[64];
        snprintf(buf, sizeof(buf), "%u", (unsigned)g_np.mode);
        WritePrivateProfileStringA("Netplay", "Mode", buf, ini_path);
        WritePrivateProfileStringA("Netplay", "PeerIP", g_np.peer_ip, ini_path);
        snprintf(buf, sizeof(buf), "%u", (unsigned)g_np.port);
        WritePrivateProfileStringA("Netplay", "Port", buf, ini_path);
        snprintf(buf, sizeof(buf), "%u", (unsigned)g_np.delay_frames);
        WritePrivateProfileStringA("Netplay", "DelayFrames", buf, ini_path);
    }

    if (g_np.mode == NP_MODE_OFF) {
        g_np.state = NP_STATE_OFF;
        NP_LOG("[Netplay] Switched to OFFLINE (Mode=0)");
        return 1;
    }

    if (!np_ctx_open_socket(&g_np)) {
        g_np.state = NP_STATE_DISCONNECTED;
        return 0;
    }
    return 1;
}

static void netplay_get_status_spanish(char *buf, size_t cap, uint32_t *out_argb) {
    if (!buf || cap == 0) return;
    if (g_np.mode == NP_MODE_OFF || g_np.state == NP_STATE_OFF) {
        snprintf(buf, cap, "Estado: DESACTIVADO (Juego local sin red)");
        if (out_argb) *out_argb = 0xFFB8C0D0;
        return;
    }
    switch (g_np.state) {
        case NP_STATE_HANDSHAKE:
            if (g_np.mode == NP_MODE_HOST) {
                snprintf(buf, cap, "Estado: HOST ESCUCHANDO UDP :%u (esperando al rival...)", (unsigned)g_np.port);
            } else {
                snprintf(buf, cap, "Estado: CONECTANDO COMO CLIENTE a %s:%u...", g_np.peer_ip, (unsigned)g_np.port);
            }
            if (out_argb) *out_argb = 0xFFFFD54F;
            break;
        case NP_STATE_READY_MENU:
        case NP_STATE_BARRIER:
        case NP_STATE_PLAYING:
            snprintf(buf, cap, "Estado: CONECTADO CON RIVAL (%u ms | Delay=%u) -> Entra en EXHIBICION!",
                     g_np.has_rtt ? g_np.rtt_ms : 0u, g_np.delay_frames);
            if (out_argb) *out_argb = 0xFF60FFA0;
            break;
        default:
            snprintf(buf, cap, "Estado: ERROR / DESCONECTADO (revisa IP o puerto :%u)", (unsigned)g_np.port);
            if (out_argb) *out_argb = 0xFFFF6E6E;
            break;
    }
}

static int netplay_get_hud_text(char *buf, size_t cap, uint32_t *out_argb) {
    if (!buf || cap == 0 || g_np.mode == NP_MODE_OFF) return 0;
    const char *role = (g_np.mode == NP_MODE_HOST) ? "HOST P1" : "CLIENT P2";
    uint32_t col = 0xFF80FFB0;
    switch (g_np.state) {
        case NP_STATE_HANDSHAKE:
            if (g_np.mode == NP_MODE_HOST) {
                snprintf(buf, cap, "NETPLAY [%s] ESPERANDO RIVAL :%u (F9=Salir)", role, (unsigned)g_np.port);
            } else {
                snprintf(buf, cap, "NETPLAY [%s] CONECTANDO %s:%u (F9=Salir)", role, g_np.peer_ip, (unsigned)g_np.port);
            }
            if (out_argb) *out_argb = 0xFFFFD54F;
            return 1;
        case NP_STATE_READY_MENU:
        case NP_STATE_BARRIER:
            snprintf(buf, cap, "NETPLAY [%s] CONECTADO -> SINCRONIZANDO PARTIDO D=%u", role, g_np.delay_frames);
            col = 0xFF40E8FF;
            if (out_argb) *out_argb = col;
            return 1;
        case NP_STATE_PLAYING: {
            const char *sync_str = (g_np.desync_count == 0) ? "SYNC OK" : "DESYNC!";
            col = (g_np.desync_count == 0) ? 0xFF80FFB0 : 0xFFFF5252;
            snprintf(buf, cap, "NETPLAY [%s] %ums | D=%u | T=%u | %s | F9=Salir",
                     role, g_np.has_rtt ? g_np.rtt_ms : 0u, g_np.delay_frames, g_np.match_tick, sync_str);
            if (out_argb) *out_argb = col;
            return 1;
        }
        case NP_STATE_DISCONNECTED:
            snprintf(buf, cap, "NETPLAY [%s] DESCONECTADO (MODO LOCAL)", role);
            col = 0xFFFF8A65;
            if (out_argb) *out_argb = col;
            return 1;
        default:
            return 0;
    }
}

#endif /* VT4_NETPLAY_STANDALONE */

#ifdef __cplusplus
}
#endif

#endif /* VT4_NETPLAY_H */
