<!-- KyotoServices · organization profile -->

<p align="center">
  <a href="https://kyotopvp.com">
    <img src="./assets/banner.svg" alt="Kyoto Services — the engineering org behind the KyotoPVP competitive Minecraft network" width="100%">
  </a>
</p>

<p align="center">
  <b>The development team behind <a href="https://kyotopvp.com">KyotoPVP</a></b> — a premium, competitive Minecraft PvP network<br>
  with automatic tier testing, real-time stats, and a thriving global community.
</p>

<p align="center">
  <a href="https://kyotopvp.com"><img src="https://img.shields.io/badge/Website-kyotopvp.com-cf2c2c?style=for-the-badge&labelColor=08080b" alt="Website"></a>
  <a href="https://discord.kyotopvp.com"><img src="https://img.shields.io/badge/Discord-Join-5865F2?style=for-the-badge&logo=discord&logoColor=white&labelColor=08080b" alt="Discord"></a>
  <a href="https://stats.kyotopvp.com"><img src="https://img.shields.io/badge/Stats-Leaderboards-ef4444?style=for-the-badge&labelColor=08080b" alt="Stats"></a>
  <a href="https://store.kyotopvp.com"><img src="https://img.shields.io/badge/Store-Support_us-22c55e?style=for-the-badge&labelColor=08080b" alt="Store"></a>
  <a href="https://twitter.com/kyotopvp"><img src="https://img.shields.io/badge/Follow-@kyotopvp-1DA1F2?style=for-the-badge&logo=x&logoColor=white&labelColor=08080b" alt="Twitter / X"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/play.kyotopvp.com-Java_1.8_–_1.21-f3f4f6?style=flat-square&labelColor=08080b&color=141419" alt="Server IP: play.kyotopvp.com">
</p>

---

## 👋 Who we are

**Kyoto Services** is the team that designs, builds, and operates the technology stack powering the
KyotoPVP network — from the in-game plugins that run matches, to the services that score every
fight, to the websites and Discord tooling players see every day.

We care about **competitive integrity**, **low-latency gameplay**, and **a clean player experience**.
Everything below is built and maintained in-house.

## 🧩 What we build

> A purpose-built stack — Kotlin on the server side, Angular on the web, glued together by Redis and a REST core.

### ⚔️ In-game (Minecraft)

| Component | What it does |
|-----------|--------------|
| **Network Core** | Ranks, punishments, knockback, HUD, menus & cross-server state — the shared foundation every game server runs on. |
| **Practice** | Competitive duels, ranked ELO, tournaments, parties & custom arenas. |
| **Lobby** | The hub experience — server selector, cosmetics & scoreboards. |
| **Proxy** | Cross-server chat, parties, friends & network routing. |
| **Anticheat** | A custom, packet-level, latency-compensated anticheat tuned for high-level PvP. |

### 🌐 Services & web

| Component | What it does |
|-----------|--------------|
| **Public API** | The REST backbone — player profiles, leaderboards, ELO & seasons. |
| **Discord Bot** | Account linking, rank ↔ role sync, moderation & live network vitals. |
| **kyotopvp.com** | The public homepage & announcements. |
| **stats.kyotopvp.com** | Player stats, leaderboards & MCRanks-style profiles. |
| **Status page** | Real-time network health, uptime history & incident reports. |

## 🛠️ Tech stack

<p>
  <img src="https://img.shields.io/badge/Kotlin-7F52FF?style=for-the-badge&logo=kotlin&logoColor=white" alt="Kotlin">
  <img src="https://img.shields.io/badge/Java_21-ED8B00?style=for-the-badge&logo=openjdk&logoColor=white" alt="Java 21">
  <img src="https://img.shields.io/badge/Paper-204020?style=for-the-badge&logo=spigotmc&logoColor=white" alt="Paper">
  <img src="https://img.shields.io/badge/Velocity-1A91D7?style=for-the-badge&logoColor=white" alt="Velocity">
  <img src="https://img.shields.io/badge/Ktor-087CFA?style=for-the-badge&logo=ktor&logoColor=white" alt="Ktor">
  <img src="https://img.shields.io/badge/Gradle-02303A?style=for-the-badge&logo=gradle&logoColor=white" alt="Gradle">
</p>
<p>
  <img src="https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white" alt="Angular">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white" alt="MySQL">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/JDA-23272A?style=for-the-badge&logo=discord&logoColor=white" alt="JDA">
</p>

## 🏗️ Architecture at a glance

```mermaid
flowchart TD
    P([Players]) --> PX[Velocity Proxy]
    PX --> L[Lobby]
    PX --> PR[Practice]
    PX --> SG[Survival Games]

    L -.-> CORE[(Network Core)]
    PR -.-> CORE
    SG -.-> CORE

    CORE <--> R[(Redis)]
    CORE <--> DB[(MySQL)]

    API[Public REST API] <--> DB
    API <--> R
    PR --> API
    BOT[Discord Bot] <--> API

    WEB[Web · homepage · stats · status] --> API

    classDef game fill:#141419,stroke:#cf2c2c,color:#f3f4f6;
    classDef svc fill:#0f0f14,stroke:#ef4444,color:#f3f4f6;
    classDef store fill:#08080b,stroke:#374151,color:#9ca3af;
    class L,PR,SG,PX game;
    class CORE,API,BOT,WEB svc;
    class R,DB store;
```

<sub>High-level view. Real-time cross-server state flows over Redis pub/sub; durable data lives in MySQL; the REST core ties web, Discord, and game servers together.</sub>

## 📊 By the numbers

<p align="center">
  <img src="https://img.shields.io/badge/Registered_players-12k+-f3f4f6?style=flat-square&labelColor=08080b&color=141419" alt="12k+ players">
  &nbsp;
  <img src="https://img.shields.io/badge/Client_support-1.8_↔_1.21-f3f4f6?style=flat-square&labelColor=08080b&color=141419" alt="1.8 to 1.21">
  &nbsp;
  <img src="https://img.shields.io/badge/Languages-8-f3f4f6?style=flat-square&labelColor=08080b&color=141419" alt="8 languages">
  &nbsp;
  <img src="https://img.shields.io/badge/Built_with-Kotlin_%2B_Angular-cf2c2c?style=flat-square&labelColor=08080b" alt="Kotlin + Angular">
</p>

## 🔗 Connect

<table align="center">
  <tr>
    <td align="center"><a href="https://kyotopvp.com">🌐<br><b>Website</b></a></td>
    <td align="center"><a href="https://discord.kyotopvp.com">💬<br><b>Discord</b></a></td>
    <td align="center"><a href="https://stats.kyotopvp.com">📈<br><b>Stats</b></a></td>
    <td align="center"><a href="https://store.kyotopvp.com">🛒<br><b>Store</b></a></td>
    <td align="center"><a href="https://twitter.com/kyotopvp">🐦<br><b>@kyotopvp</b></a></td>
  </tr>
</table>

<p align="center">
  <sub>Hop on at <code>play.kyotopvp.com</code> — Java Edition 1.7 through 26.2.</sub>
</p>

---

<p align="center">
  <sub>Made with ⚔️ &nbsp;by the <b>Kyoto Services</b> team · © 2026 KyotoPVP</sub>
</p>
