# Guía de Juego Online P2P (Crossplay PC ↔ Android) — Virtua Tennis 4: Legends & Next-Gen

Ya puedes jugar partidos online **PC ↔ PC**, **Android ↔ Android** o **PC ↔ Android** usando el motor **Netplay P2P UDP Lockstep** (`NVT4` v1) integrado directamente en `xlive.dll` — **sin servidores de Games for Windows LIVE, sin Parsec y sin retransmitir vídeo**.

---

## 1. Cómo funciona (cero desincronización)
- El **Anfitrión (`HOST P1`)** controla al Jugador 1 (pista inferior) y genera la semilla aleatoria oficial del partido.
- El **Invitado (`CLIENT P2`)** controla al Jugador 2 (pista superior) y se conecta a la IP y puerto UDP del Anfitrión.
- Ambos dispositivos envían **solo sus pulsaciones de botones (56 bytes por paquete con redundancia de los últimos 8 ticks)** a 60 Hz exactos (`DelayFrames` por defecto = `3` ticks = 50 ms) y comprueban periódicamente el hash de posición para garantizar sincronización perfecta.
- **Ventaja clave para Android / Móvil**: El Anfitrión **aprende automáticamente la IP y puerto del Invitado** al recibir su primer paquete `HELLO`, así que el Invitado nunca tiene que abrir puertos en su móvil ni en su router.

---

## 2. Opción A — Red Local / WiFi de Casa en 15 segundos (Auto-Descubrimiento LAN)

Ya no hace falta editar `vt4_settings.ini` a mano: desde el Menú Principal abre **`EN LÍNEA`** (pantalla nativa VT4):

### En el PC o Móvil Anfitrión (`HOST P1`)
1. Entra en **`EN LÍNEA`** y cambia **`MODO DE CONEXIÓN`** a **`CREAR SALA (HOST P1)`**.
2. Pulsa **`CONECTAR / APLICAR NETPLAY`** (anota la IP local que aparece en la tarjeta derecha solo si la necesitas; en LAN el rival ni siquiera la necesita).
   *(Si tienes Firewall de Windows, permite tráfico **UDP puerto 7777** en redes privadas.)*

### En el PC o Android Invitado (`CLIENT P2` en Winlator / GameHub / Mobox)
1. Entra en **`EN LÍNEA`** y pulsa **`BUSCAR SALA EN RED LOCAL (LAN)`**. El juego detecta automáticamente la sala abierta por UDP broadcast/loopback y rellena la IP y el delay.
2. Pulsa **`CONECTAR / APLICAR NETPLAY`** -> verás **`CONECTADO CON RIVAL`** en la tarjeta de estado.
3. Pulsad **`ESC`** en ambos dispositivos y entrad en **Exhibición** eligiendo **los mismos 2 jugadores, la misma pista y las mismas reglas**.
4. Al cargar la pista verás el indicador **`NETPLAY [HOST P1 / CLIENT P2] ...ms | D=3 | SYNC OK`** en la **esquina superior derecha** (despejando el marcador TV oficial de arriba a la izquierda). ¡Listo!

---

## 3. Opción B — Por Internet con un amigo (PC ↔ Android) sin abrir puertos del router
La forma más fácil y fiable a través de Internet (especialmente desde **Android con 4G/5G/CGNAT**) es crear una LAN virtual privada en 1 minuto:

1. Instala **Tailscale** (o **ZeroTier**) tanto en el **PC** (Windows) como en el **móvil Android** (app oficial en Google Play).
2. Inicia sesión en ambos dispositivos con la misma cuenta (o comparte el nodo con tu amigo).
3. Copia la **IP virtual de Tailscale** del dispositivo que haga de Anfitrión (suele empezar por `100.x.x.x`) y ponla en `PeerIP=` del Invitado (`Mode=2`).
4. Arrancad el juego **exactamente igual que en Red Local**: atraviesa NAT y routers sin configurar redirección de puertos.

> **Alternativa directa sin VPN**: Si el **Anfitrión (`Mode=1`)** está en fibra/router de casa con IP pública, solo tiene que abrir el puerto **UDP 7777** hacia la IP local de su PC y darle su IP pública al Invitado (`Mode=2`). El Invitado en Android **no necesita abrir nada**.

---

## 4. Tabla recomendada de `DelayFrames` según tu Ping (RTT)

El HUD superior izquierdo muestra en tiempo real el ping medido (`...ms`). Ajusta `DelayFrames` en el Anfitrión (`vt4_settings.ini`) si notas pequeños tirones:

| Ping (RTT mostrado en HUD) | `DelayFrames` recomendado | Retardo de entrada equivalente | Uso típico |
|---:|---:|---:|---|
| **0 – 35 ms** | `2` | 33 ms | WiFi local / fibra misma ciudad |
| **35 – 65 ms** *(Defecto)* | `3` | 50 ms | PC ↔ Android WiFi o fibra nacional |
| **65 – 95 ms** | `4` – `5` | 67 – 83 ms | Android 4G/5G ↔ PC |
| **95 – 140 ms** | `6` – `8` | 100 – 133 ms | Larga distancia / Tailscale relay |

> **Nota**: Para garantizar sincronización 100%, durante el juego online el multiplicador de velocidad (`MatchSpeedMode`) y el desbloqueo de FPS (`UnlockFPS`) se bloquean automáticamente a **60 Hz exactos (`1.000x`)**.

---

## 5. Controles y Teclas Rápidas en Partido
| Tecla | Acción |
|---|---|
| **`F9`** | **Desconectar Netplay al instante** y seguir jugando el partido en local sin cerrar el juego. |
| **`F8`** | Activar / desactivar **NextGenFX** en PC (en Android con `PerfProfile=2` va apagado por defecto para máximo rendimiento). |
| **`F10`** | Captura de pantalla en `game\vt4_present_*.png`. |
| **`F2`** | Abrir / cerrar el menú visual **Gráficos HD y Legends**. |

---

## 6. Reglas de oro para evitar desincronizaciones (`DESYNC`)
1. **Mismo matchup y reglas**: Elegid el **mismo P1, mismo P2 y misma pista** en ambos dispositivos al entrar a Exhibición.
2. **Mismos ajustes de Mod en `[Gameplay]`**: Mismo `MultiverseMode` (`0..3`) y `WeaponMode` (`0..3`).
3. **Android con `PerfProfile=2`**: Aunque el móvil vaya con sombras reducidas y sin `NextGenFX`, la simulación interna sigue yendo a **60 Hz exactos**, así que es **100% compatible bit a bit con `PerfProfile=0` en PC Ultra**.
4. **Volver a jugar Offline**: Pon simplemente **`Mode=0`** en `[Netplay]` de `game\vt4_settings.ini` (en `Mode=0` no se abre ningún socket ni consume CPU).
