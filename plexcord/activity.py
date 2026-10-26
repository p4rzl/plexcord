import asyncio
import contextlib
import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict

from aiohttp import WSMsgType, web

from .plex import PlexError, Track, valid_url
from .store import UserLink

ACTIVITY_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#07080d">
<title>Plexcord</title>
<style>
:root{
  --bg:#07080d;
  --surface:rgba(16,18,26,.76);
  --surface-2:rgba(24,27,38,.72);
  --surface-3:rgba(35,39,54,.88);
  --border:rgba(255,255,255,.07);
  --border-hi:rgba(255,255,255,.15);
  --text:#f5f7fb;
  --text-dim:#949db0;
  --accent:#5865f2;
  --accent-hi:#6d78ff;
  --gold:#e5a00d;
  --gold-hi:#f5b627;
  --ok:#23a55a;
  --danger:#e5484d;
  --radius-lg:18px;
  --radius-md:12px;
  --radius-sm:9px;
  --safe-top:env(safe-area-inset-top,0px);
  --safe-bottom:env(safe-area-inset-bottom,0px);
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{
  width:100%;
  height:100%;
  height:100dvh;
  overflow:hidden;
  background:var(--bg);
  color:var(--text);
  font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  user-select:none;
  -webkit-font-smoothing:antialiased;
}
body{display:flex;flex-direction:column;position:relative}
svg{width:16px;height:16px;fill:currentColor;flex-shrink:0;display:block}

#ambient-bg{
  position:fixed;inset:-60px;
  background-size:cover;background-position:center;
  filter:blur(72px) saturate(1.9) brightness(.3);
  opacity:0;
  transition:opacity .8s ease,background-image .8s ease;
  pointer-events:none;z-index:0;
}
#ambient-grad{
  position:fixed;inset:0;
  background:
    radial-gradient(circle at 15% 15%,rgba(88,101,242,.13),transparent 50%),
    radial-gradient(circle at 85% 85%,rgba(229,160,13,.1),transparent 50%);
  pointer-events:none;z-index:0;
}

/* Topbar */
header{
  position:relative;z-index:10;
  display:flex;align-items:center;justify-content:space-between;
  padding:calc(10px + var(--safe-top)) 16px 10px;
  background:rgba(10,12,18,.78);
  backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);
  border-bottom:1px solid var(--border);
  gap:10px;flex-shrink:0;
}
.brand{display:flex;align-items:center;gap:9px;min-width:0;flex:1}
.logo-mark{
  width:30px;height:30px;border-radius:9px;
  background:linear-gradient(135deg,var(--gold),#d97706 55%,var(--accent));
  display:inline-flex;align-items:center;justify-content:center;
  color:#fff;box-shadow:0 4px 14px rgba(229,160,13,.3);flex-shrink:0;
}
.logo-mark svg{width:17px;height:17px}
.brand-title{font-weight:800;font-size:15px;letter-spacing:-.2px;color:#fff}
.header-meta{display:flex;align-items:center;gap:6px;min-width:0;overflow:hidden}
.header-right{display:flex;align-items:center;gap:6px;flex-shrink:0}

.badge{
  font-size:11px;font-weight:600;
  padding:4px 10px;border-radius:99px;
  background:rgba(255,255,255,.05);
  border:1px solid var(--border);
  color:var(--text-dim);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  display:inline-flex;align-items:center;gap:5px;
  max-width:190px;
}
.badge.mode-act{background:rgba(88,101,242,.14);border-color:rgba(88,101,242,.35);color:#c7ceff}
.badge.sync-ok{background:rgba(35,165,90,.15);border-color:rgba(35,165,90,.38);color:#7ee8a9}
.badge.rpc-btn{
  background:rgba(88,101,242,.18);
  border-color:rgba(88,101,242,.42);
  color:#e0e4ff;cursor:pointer;
  transition:all .15s ease;max-width:none;
}
.badge.rpc-btn:hover{background:rgba(88,101,242,.3);border-color:var(--accent-hi);transform:translateY(-1px)}
.badge.rpc-btn.sync-ok{background:rgba(35,165,90,.18);border-color:rgba(35,165,90,.45);color:#86efac}

/* Main Workspace */
main{
  position:relative;z-index:2;
  display:grid;
  grid-template-columns:300px 1fr;
  gap:14px;padding:14px;
  flex:1;min-height:0;overflow:hidden;
}
.panel{
  background:var(--surface);
  backdrop-filter:blur(28px);-webkit-backdrop-filter:blur(28px);
  border:1px solid var(--border);
  border-radius:var(--radius-lg);
  padding:16px;
  display:flex;flex-direction:column;gap:14px;
  min-height:0;overflow:hidden;
  box-shadow:0 16px 40px rgba(0,0,0,.45);
}

/* Player Panel (Left Dock on Desktop, Mini-Player + Full Sheet on Mobile) */
#player-panel{justify-content:space-between;position:relative}
.player-sheet-bar{
  display:none;
  align-items:center;justify-content:space-between;
  padding-bottom:6px;border-bottom:1px solid var(--border);
  flex-shrink:0;
}
.sheet-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--text-dim)}

.now-row{display:flex;flex-direction:column;align-items:center;text-align:center;gap:14px;min-width:0}
.art-wrap{
  width:184px;height:184px;flex-shrink:0;
  background:linear-gradient(145deg,#141722,#222738);
  border:1px solid var(--border-hi);
  border-radius:18px;overflow:hidden;
  display:flex;align-items:center;justify-content:center;
  font-size:48px;color:rgba(255,255,255,.22);
  box-shadow:0 16px 36px rgba(0,0,0,.55);
  position:relative;
}
.art-wrap svg{width:54px;height:54px;opacity:.45}
.art-wrap img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;z-index:2}
.eq-overlay{
  position:absolute;bottom:8px;right:8px;z-index:3;
  background:rgba(7,8,13,.82);backdrop-filter:blur(8px);
  border:1px solid var(--border-hi);border-radius:7px;
  padding:4px 6px;display:none;align-items:flex-end;gap:2.5px;height:20px;
}
.eq-overlay.playing{display:inline-flex}
.eq-bar{width:3px;background:var(--gold);border-radius:2px;animation:eq .75s ease-in-out infinite alternate}
.eq-bar:nth-child(2){animation-delay:.2s;background:var(--accent-hi)}
.eq-bar:nth-child(3){animation-delay:.4s}
@keyframes eq{0%{height:3px}100%{height:12px}}

.now-meta{width:100%;min-width:0;display:flex;flex-direction:column;gap:3px}
.now-title{font-size:16px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#fff;letter-spacing:-.2px}
.now-sub{font-size:12px;color:var(--text-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#now-artist{color:var(--gold-hi);font-weight:600;font-size:13px}

/* Progress / Seek */
.progress-box{display:flex;flex-direction:column;gap:7px;flex-shrink:0}
.bar{
  width:100%;height:6px;
  background:rgba(255,255,255,.1);
  border-radius:99px;cursor:pointer;position:relative;
  transition:height .15s ease,background .15s ease;
}
.bar:hover{height:8px;background:rgba(255,255,255,.15)}
.bar-fill{
  height:100%;
  background:linear-gradient(90deg,var(--accent),var(--gold));
  width:0%;border-radius:99px;position:relative;
  transition:width .2s linear;
}
.bar-fill::after{
  content:"";position:absolute;right:-6px;top:50%;transform:translateY(-50%);
  width:12px;height:12px;border-radius:50%;background:#fff;
  box-shadow:0 2px 8px rgba(0,0,0,.6);opacity:0;transition:opacity .15s;
}
.bar:hover .bar-fill::after{opacity:1}
.times{display:flex;justify-content:space-between;font-size:11px;color:var(--text-dim);font-variant-numeric:tabular-nums;font-weight:600}

/* Buttons & Transport Controls */
button{
  background:var(--surface-2);color:var(--text);
  border:1px solid var(--border);border-radius:10px;
  padding:8px 12px;font-size:12px;font-weight:600;font-family:inherit;
  cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:6px;
  transition:all .15s ease;white-space:nowrap;
}
button:hover{background:var(--surface-3);border-color:var(--border-hi);transform:translateY(-1px)}
button:active{transform:scale(.96)}
button.primary{
  background:linear-gradient(135deg,var(--accent),var(--accent-hi));
  border-color:rgba(255,255,255,.16);color:#fff;
  box-shadow:0 4px 14px rgba(88,101,242,.32);
}
button.primary:hover{filter:brightness(1.08)}
button.ok{
  background:linear-gradient(135deg,var(--ok),#2bc46c);
  border-color:rgba(255,255,255,.16);color:#fff;
  box-shadow:0 4px 12px rgba(35,165,90,.28);
}
button.danger{
  background:rgba(229,72,77,.15);
  border-color:rgba(229,72,77,.35);color:#ff8b8e;
}
button.danger:hover{background:var(--danger);color:#fff;border-color:var(--danger)}
button.icon-btn{width:38px;height:38px;padding:0;border-radius:50%}

.controls{display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;flex-shrink:0}
#btn-play{
  height:44px;padding:0 18px;border-radius:99px;
  font-size:13px;font-weight:700;
  box-shadow:0 6px 20px rgba(88,101,242,.42);
}
#btn-expand-player{display:none}

/* Volume */
.vol-row{
  display:flex;align-items:center;gap:8px;
  font-size:11px;color:var(--text-dim);flex-shrink:0;
  background:rgba(0,0,0,.22);padding:8px 10px;
  border-radius:12px;border:1px solid var(--border);
}
.vol-row input[type=range]{
  flex:1;min-width:60px;accent-color:var(--gold);
  cursor:pointer;height:5px;
}
.vol-btn{width:28px;height:28px;padding:0;border-radius:8px;font-size:11px}
#vol-val{min-width:36px;text-align:right;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums}
.listeners-pill{
  font-size:11px;color:#86efac;
  background:rgba(35,165,90,.12);border:1px solid rgba(35,165,90,.3);
  padding:6px 10px;border-radius:10px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  text-align:center;font-weight:600;
}

/* Navigation Tabs (Segmented Bar on Desktop, Bottom Bar on Mobile) */
#main-panel{padding:14px 16px;gap:12px}
.tabs{
  display:flex;gap:5px;
  background:rgba(8,10,15,.6);
  padding:5px;border-radius:13px;
  border:1px solid var(--border);
  flex-shrink:0;overflow-x:auto;
}
.tab{
  flex:1;background:transparent;border-color:transparent;
  color:var(--text-dim);padding:8px 12px;border-radius:9px;
  font-size:12px;font-weight:600;gap:6px;
}
.tab:hover{background:rgba(255,255,255,.04);color:var(--text);transform:none}
.tab.active{
  background:linear-gradient(135deg,var(--accent),var(--accent-hi));
  color:#fff;box-shadow:0 3px 12px rgba(88,101,242,.34);
}
.tab-count{
  background:rgba(255,255,255,.16);color:#fff;
  padding:1px 6px;border-radius:99px;font-size:10.5px;font-weight:700;
  font-variant-numeric:tabular-nums;
}

/* Inputs & Search Bar */
.search-bar{display:flex;gap:8px;flex-wrap:wrap;flex-shrink:0}
.search-input-wrap{position:relative;flex:1;min-width:160px;display:flex;align-items:center}
.search-input-wrap svg{position:absolute;left:12px;color:var(--text-dim);pointer-events:none}
.search-input-wrap input[type=search]{padding-left:36px;width:100%}
input[type=search],input[type=text],input[type=password],input[type=number],select{
  background:rgba(10,12,18,.75);color:var(--text);
  border:1px solid var(--border);border-radius:11px;
  padding:9px 12px;font-size:12.5px;font-family:inherit;
  outline:none;min-width:0;
  transition:border-color .15s,box-shadow .15s,background .15s;
}
input[type=search]:focus,input[type=text]:focus,input[type=password]:focus,input[type=number]:focus,select:focus{
  border-color:var(--accent);
  background:rgba(14,17,26,.92);
  box-shadow:0 0 0 3px rgba(88,101,242,.2);
}

/* Track & Playlist List Items */
.list{
  flex:1;overflow-y:auto;overflow-x:hidden;
  display:flex;flex-direction:column;gap:6px;
  padding-right:2px;min-height:0;
}
.item{
  display:flex;align-items:center;justify-content:space-between;
  gap:12px;padding:8px 10px;
  background:rgba(24,27,38,.52);
  border:1px solid rgba(255,255,255,.05);
  border-radius:12px;flex-shrink:0;
  transition:background .15s ease,border-color .15s ease,transform .15s ease;
}
.item:hover{
  background:rgba(36,40,56,.78);
  border-color:var(--border-hi);
}
.item-thumb{
  width:46px;height:46px;min-width:46px;min-height:46px;
  border-radius:10px;
  background:linear-gradient(145deg,#151822,#232838);
  border:1px solid var(--border-hi);
  flex-shrink:0;overflow:hidden;
  display:flex;align-items:center;justify-content:center;
  font-size:18px;color:var(--text-dim);position:relative;
  box-shadow:0 4px 10px rgba(0,0,0,.35);
}
.item-thumb svg{width:20px;height:20px;opacity:.45;position:relative;z-index:1}
.item-thumb span{position:relative;z-index:1;line-height:1;pointer-events:none;user-select:none}
.item-thumb img{
  position:absolute;inset:0;width:100%;height:100%;
  object-fit:cover;display:block;z-index:2;
}

.item-info{min-width:0;flex:1;display:flex;flex-direction:column;gap:2px}
.item-title{font-size:13px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#fff}
.item-artist{font-size:11.5px;font-weight:600;color:var(--gold-hi);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.item-meta{font-size:11px;color:var(--text-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:6px;margin-top:1px}
.pill-dur{
  background:rgba(255,255,255,.07);
  padding:1px 6px;border-radius:5px;
  font-variant-numeric:tabular-nums;color:#d6dae3;font-weight:600;font-size:10.5px;
}
.item-actions{display:flex;align-items:center;gap:6px;flex-shrink:0}
.item-actions button{padding:7px 11px;font-size:11.5px;border-radius:9px}

.empty-state{
  margin:auto;padding:28px 18px;text-align:center;
  display:flex;flex-direction:column;align-items:center;gap:8px;
  color:var(--text-dim);max-width:360px;
}
.empty-icon{
  width:46px;height:46px;border-radius:14px;
  background:rgba(255,255,255,.04);border:1px solid var(--border);
  display:flex;align-items:center;justify-content:center;
  color:var(--gold);margin-bottom:2px;
}
.empty-icon svg{width:22px;height:22px}
.empty-title{font-size:13.5px;font-weight:700;color:var(--text)}
.empty-sub{font-size:12px;line-height:1.45;color:var(--text-dim)}

/* Settings & Account Cards */
.cfg-grid{flex:1;display:flex;flex-direction:column;gap:10px;overflow-y:auto;padding-right:2px;min-height:0}
.cfg-box{
  background:rgba(22,25,36,.62);
  border:1px solid var(--border);
  border-radius:14px;padding:14px;
  display:flex;flex-direction:column;gap:10px;flex-shrink:0;
}
.cfg-title{
  font-size:13px;font-weight:700;
  display:flex;align-items:center;justify-content:space-between;
  gap:8px;flex-wrap:wrap;color:#fff;
}
.cfg-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.cfg-row label{font-size:11.5px;color:var(--text-dim);min-width:130px;font-weight:600}
.cfg-row input,.cfg-row select{flex:1;min-width:120px}
.pin-card{
  display:none;flex-direction:column;gap:10px;margin-top:4px;padding:14px;
  background:rgba(9,11,16,.92);border:1px solid rgba(229,160,13,.55);
  border-radius:12px;text-align:center;box-shadow:0 10px 28px rgba(0,0,0,.5);
}
.pin-code{
  font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
  font-size:28px;font-weight:900;letter-spacing:8px;color:var(--gold-hi);
  background:var(--surface-2);border:1px dashed rgba(229,160,13,.55);
  padding:8px 18px;border-radius:10px;display:inline-block;margin:2px auto;
  user-select:all;cursor:pointer;
}
.lib-item{
  display:flex;align-items:center;justify-content:space-between;
  padding:8px 11px;background:rgba(12,14,20,.65);
  border:1px solid var(--border);border-radius:10px;
  font-size:12px;gap:8px;
}

.toast{
  position:fixed;bottom:calc(18px + var(--safe-bottom));right:18px;
  background:rgba(18,20,28,.96);backdrop-filter:blur(16px);
  border:1px solid var(--border-hi);border-left:4px solid var(--gold);
  padding:10px 15px;border-radius:11px;font-size:12px;font-weight:600;
  display:none;z-index:100;box-shadow:0 10px 30px rgba(0,0,0,.65);
  max-width:calc(100vw - 36px);
}

::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.14);border-radius:99px}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,.26)}

/* ==========================================================================
   INTERFACCIA MOBILE & COMPACT SPLIT-VIEW (Smartphone, Tablet, Chat Vocale)
   ========================================================================== */
@media (max-width: 820px), (max-height: 540px) {
  header{padding:calc(8px + var(--safe-top)) 12px 8px}
  #sdk-status,#mode-badge{display:none}
  .badge{max-width:140px;font-size:10.5px;padding:3px 8px}

  main{
    display:flex;
    flex-direction:column;
    padding:0;gap:0;
  }

  /* Il pannello principale occupa tutto lo spazio centrale sopra il mini-player */
  #main-panel{
    order:1;
    flex:1;
    border-radius:0;
    border:none;
    background:transparent;
    backdrop-filter:none;
    box-shadow:none;
    padding:10px 12px 6px;
    gap:10px;
  }

  /* Barra di navigazione inferiore nativa su Mobile */
  .tabs{
    position:fixed;
    left:0;right:0;bottom:0;
    z-index:35;
    border-radius:0;
    border:none;
    border-top:1px solid var(--border);
    background:rgba(10,12,18,.94);
    backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);
    padding:6px 8px calc(6px + var(--safe-bottom));
    gap:2px;
    justify-content:space-around;
  }
  .tab{
    flex-direction:column;
    padding:6px 4px;
    font-size:10px;
    gap:3px;
    border-radius:10px;
  }
  .tab svg{width:18px;height:18px}
  .tab.active{
    background:rgba(88,101,242,.2);
    color:#fff;
    box-shadow:none;
  }

  /* Mini-Player flottante sopra la barra di navigazione inferiore */
  body:not(.player-expanded) #player-panel{
    order:2;
    flex-shrink:0;
    margin:0 8px calc(58px + var(--safe-bottom));
    padding:8px 10px;
    border-radius:14px;
    background:rgba(20,23,34,.94);
    border:1px solid var(--border-hi);
    box-shadow:0 8px 26px rgba(0,0,0,.6);
    flex-direction:row;
    align-items:center;
    gap:10px;
  }
  body:not(.player-expanded) .now-row{
    flex-direction:row;
    text-align:left;
    gap:10px;
    flex:1;
    min-width:0;
    cursor:pointer;
  }
  body:not(.player-expanded) .art-wrap{
    width:44px;height:44px;
    border-radius:10px;
    box-shadow:0 3px 10px rgba(0,0,0,.4);
  }
  body:not(.player-expanded) .art-wrap svg{width:22px;height:22px}
  body:not(.player-expanded) .eq-overlay{display:none !important}
  body:not(.player-expanded) .now-title{font-size:13px}
  body:not(.player-expanded) #now-artist{font-size:11.5px}
  body:not(.player-expanded) #now-album{display:none}
  body:not(.player-expanded) .progress-box{
    position:absolute;
    left:10px;right:10px;top:0;
    padding:0;gap:0;
    pointer-events:none;
  }
  body:not(.player-expanded) .bar{height:2.5px;background:rgba(255,255,255,.08)}
  body:not(.player-expanded) .bar-fill::after,
  body:not(.player-expanded) .times,
  body:not(.player-expanded) .vol-row,
  body:not(.player-expanded) .listeners-pill,
  body:not(.player-expanded) .ctrl-extra{
    display:none !important;
  }
  body:not(.player-expanded) .controls{
    gap:5px;flex-wrap:nowrap;
  }
  body:not(.player-expanded) #btn-play{
    width:36px;height:36px;padding:0;border-radius:50%;
  }
  body:not(.player-expanded) #btn-play .btn-play-lbl{display:none}
  body:not(.player-expanded) #btn-skip{width:34px;height:34px}
  body:not(.player-expanded) #btn-expand-player{
    display:inline-flex;width:34px;height:34px;padding:0;border-radius:50%;
  }

  /* Full-Screen Player Sheet quando espanso su Mobile */
  body.player-expanded #player-panel{
    position:fixed;
    inset:0;
    z-index:45;
    border-radius:0;
    border:none;
    background:rgba(9,11,17,.97);
    backdrop-filter:blur(32px);-webkit-backdrop-filter:blur(32px);
    padding:calc(14px + var(--safe-top)) 20px calc(22px + var(--safe-bottom));
    justify-content:space-evenly;
  }
  body.player-expanded .player-sheet-bar{display:flex}
  body.player-expanded .art-wrap{
    width:min(62vw,230px);
    height:min(62vw,230px);
    border-radius:20px;
  }

  /* Ottimizzazione pulsanti lista brani su schermi stretti */
  .item{padding:7px 9px;gap:9px}
  .item-actions button{padding:6px 9px;font-size:11px}
  .cfg-row label{min-width:100%;margin-bottom:-2px}
  .toast{bottom:calc(124px + var(--safe-bottom));right:12px;left:12px;text-align:center}
}

@media (max-width: 440px) {
  .item-actions .lbl-hide-xs{display:none}
  .search-bar select{flex:1}
}
</style>
</head>
<body>
<div id="ambient-bg"></div>
<div id="ambient-grad"></div>

<header>
  <div class="brand">
    <span class="logo-mark">
      <svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg>
    </span>
    <span class="brand-title">Plexcord</span>
    <div class="header-meta">
      <span class="badge" id="srv">Connessione...</span>
      <span class="badge mode-act" id="mode-badge">Activity</span>
    </div>
  </div>
  <div class="header-right">
    <button type="button" class="badge rpc-btn" id="btn-header-rpc" title="Mostra il brano in ascolto sul tuo profilo personale Discord (RPC)">🟣 Attiva RPC</button>
    <span class="badge sync-ok" id="sync-badge" style="display:none">🎧 Sync Plex</span>
    <span class="badge" id="sdk-status">Web / Activity</span>
  </div>
</header>

<main>
  <section class="panel" id="player-panel">
    <div class="player-sheet-bar">
      <button type="button" class="icon-btn" id="btn-collapse-player" title="Riduci player">
        <svg viewBox="0 0 24 24"><path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41Z"/></svg>
      </button>
      <span class="sheet-title">In Riproduzione</span>
      <span style="width:38px"></span>
    </div>

    <div class="now-row" id="now-row-tap">
      <div class="art-wrap" id="art">
        <span id="art-icon">
          <svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg>
        </span>
        <div class="eq-overlay" id="eq-overlay"><div class="eq-bar"></div><div class="eq-bar"></div><div class="eq-bar"></div></div>
      </div>
      <div class="now-meta">
        <div class="now-title" id="now-title">Nessun brano in riproduzione</div>
        <div class="now-sub" id="now-artist">Cerca un brano per iniziare</div>
        <div class="now-sub" id="now-album"></div>
      </div>
    </div>

    <div class="progress-box">
      <div class="bar" id="seek-bar" title="Clicca per saltare a questo punto"><div class="bar-fill" id="bar-fill"></div></div>
      <div class="times"><span id="t-cur">0:00</span><span id="t-dur">0:00</span></div>
    </div>

    <div class="controls">
      <button type="button" class="icon-btn ctrl-extra" id="btn-restart" title="Ricomincia brano">
        <svg viewBox="0 0 24 24"><path d="M6 6h2v12H6zm3.5 6 8.5 6V6z"/></svg>
      </button>
      <button type="button" class="primary" id="btn-play" title="Play / Pausa">
        <svg viewBox="0 0 24 24" id="ico-play"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
        <span class="btn-play-lbl" id="lbl-play">Pausa</span>
      </button>
      <button type="button" class="icon-btn" id="btn-skip" title="Salta brano">
        <svg viewBox="0 0 24 24"><path d="m6 18 8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
      </button>
      <button type="button" class="icon-btn ctrl-extra" id="btn-shuffle" title="Mescola coda">
        <svg viewBox="0 0 24 24"><path d="M10.59 9.17 5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z"/></svg>
      </button>
      <button type="button" class="icon-btn danger ctrl-extra" id="btn-stop" title="Ferma e svuota coda">
        <svg viewBox="0 0 24 24"><path d="M6 6h12v12H6z"/></svg>
      </button>
      <button type="button" class="icon-btn ctrl-extra" id="btn-leave" title="Disconnetti dal canale vocale">
        <svg viewBox="0 0 24 24"><path d="M10.09 15.59 11.5 17l5-5-5-5-1.41 1.41L12.67 11H3v2h9.67l-2.58 2.59zM19 3H5a2 2 0 0 0-2 2v4h2V5h14v14H5v-4H3v4a2 2 0 0 0 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/></svg>
      </button>
      <button type="button" class="icon-btn" id="btn-expand-player" title="Espandi player">
        <svg viewBox="0 0 24 24"><path d="M7.41 15.41 12 10.83l4.59 4.58L18 14l-6-6-6 6 1.41 1.41Z"/></svg>
      </button>
    </div>

    <div class="vol-row">
      <button type="button" class="vol-btn" id="btn-voldown" title="Volume -10%">−</button>
      <svg viewBox="0 0 24 24" style="width:15px;height:15px;opacity:.7"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/></svg>
      <input type="range" id="vol" min="0" max="150" value="100">
      <button type="button" class="vol-btn" id="btn-volup" title="Volume +10%">+</button>
      <span id="vol-val">100%</span>
    </div>

    <div class="listeners-pill" id="listeners-pill" style="display:none"></div>
  </section>

  <section class="panel" id="main-panel">
    <nav class="tabs" id="main-tabs">
      <button type="button" class="tab active" id="tab-s">
        <svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
        <span>Cerca</span>
      </button>
      <button type="button" class="tab" id="tab-p">
        <svg viewBox="0 0 24 24"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg>
        <span>Playlist</span>
      </button>
      <button type="button" class="tab" id="tab-q">
        <svg viewBox="0 0 24 24"><path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-1 9h-4v4h-2v-4H9V9h4V5h2v4h4v2z"/></svg>
        <span>Coda <span class="tab-count" id="q-count">0</span></span>
      </button>
      <button type="button" class="tab" id="tab-u">
        <svg viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
        <span>Account</span>
      </button>
      <button type="button" class="tab" id="tab-c">
        <svg viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.48.48 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 0 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1 1 12 8.4a3.6 3.6 0 0 1 0 7.2z"/></svg>
        <span>Config</span>
      </button>
    </nav>

    <div id="view-s" style="display:flex;flex-direction:column;gap:10px;flex:1;min-height:0">
      <div class="search-bar">
        <div class="search-input-wrap">
          <svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
          <input type="search" id="q-in" placeholder="Cerca brano, artista o album su Plex...">
        </div>
        <select id="lib-sel"><option value="">Tutte le librerie</option></select>
        <button type="button" class="primary" id="btn-search">Cerca</button>
      </div>
      <div id="s-list" class="list">
        <div class="empty-state">
          <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg></div>
          <div class="empty-title">Esplora la tua libreria Plex</div>
          <div class="empty-sub">Digita il titolo di una canzone o il nome di un artista per cercare con anteprima copertina.</div>
        </div>
      </div>
    </div>

    <div id="view-p" style="display:none;flex-direction:column;gap:10px;flex:1;min-height:0">
      <div class="search-bar" id="pl-header-bar">
        <select id="pl-user-sel" style="flex:1"><option value="">Seleziona account Plex collegato...</option></select>
        <button type="button" class="primary" id="btn-pl-refresh">Aggiorna</button>
      </div>
      <div class="search-bar" id="pl-detail-bar" style="display:none;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:8px;min-width:0">
          <button type="button" id="btn-pl-back">← Indietro</button>
          <span class="item-title" id="pl-detail-title" style="font-size:13.5px">Playlist</span>
        </div>
        <div style="display:flex;gap:6px;flex-shrink:0">
          <button type="button" class="ok" id="btn-pl-play-all">▶ Ora</button>
          <button type="button" id="btn-pl-shuffle-all">🔀 Shuffle</button>
          <button type="button" class="primary" id="btn-pl-queue-all">+ Coda</button>
        </div>
      </div>
      <div id="p-list" class="list">
        <div class="empty-state">
          <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg></div>
          <div class="empty-title">Le tue Playlist Plex</div>
          <div class="empty-sub">Collega il tuo account Plex nella scheda <b>Account</b> per sfogliare e riprodurre le tue playlist personali.</div>
        </div>
      </div>
    </div>

    <div id="view-q" class="list" style="display:none"></div>

    <div id="view-u" class="cfg-grid" style="display:none">
      <div class="cfg-box">
        <div class="cfg-title">
          <span>🟣 Discord Rich Presence (Stato Profilo)</span>
          <span class="badge" id="rpc-status-badge">Non autorizzato</span>
        </div>
        <div class="now-sub" style="white-space:normal;line-height:1.5">
          Mostra il brano, l'artista e il timer direttamente sul tuo profilo personale Discord. L'autorizzazione viene salvata automaticamente sul server.
          <span id="secret-hint"><br>1. Nel <b>Discord Developer Portal → OAuth2</b> copia il <b>Client Secret</b>, incollalo qui sotto e aggiungi un Redirect URL (es. <code>https://127.0.0.1</code>).</span>
        </div>
        <div class="cfg-row" id="secret-row">
          <label>Discord Client Secret</label>
          <input type="password" id="cfg-discord-secret" placeholder="Incolla Client Secret da OAuth2...">
          <button type="button" id="btn-save-secret">Salva Secret</button>
        </div>
        <div class="cfg-row">
          <button type="button" class="primary" id="btn-auth-rpc">🟣 Attiva / Autorizza Discord RPC</button>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title">
          <span>🎧 Account Personale Plex (Playlist & Scrobbling)</span>
        </div>
        <div class="now-sub" style="white-space:normal;line-height:1.5">
          Collega il tuo account Plex per accedere alle tue <b>Playlist personali</b> e sincronizzare lo stato di ascolto sulla <b>Dashboard di Plex</b>.
        </div>
        <div class="cfg-row">
          <label>Il tuo utente Discord</label>
          <select id="user-sel"><option value="">Seleziona il tuo utente nel canale vocale...</option></select>
        </div>
        <div class="cfg-row">
          <button type="button" class="primary" id="btn-user-pin">🔑 Collega con PIN a 4 Cifre</button>
          <button type="button" class="danger" id="btn-user-unlink">Scollega Account</button>
        </div>
        <div class="pin-card" id="user-pin-box">
          <div style="font-size:12px">Vai su <b>https://plex.tv/link</b> e inserisci questo codice a 4 caratteri:</div>
          <div class="pin-code" id="user-pin-code" title="Clicca per copiare">----</div>
          <div class="cfg-row" style="justify-content:center">
            <button type="button" class="primary" id="btn-user-open-link">Apri plex.tv/link</button>
            <button type="button" id="btn-user-copy">Copia Codice</button>
            <button type="button" class="ok" id="btn-user-check">Ho inserito il PIN</button>
          </div>
          <div class="now-sub">⏳ Verifica automatica ogni 3 secondi...</div>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title"><span>👥 Ascoltatori nel Canale Vocale</span></div>
        <div id="voice-users-list" style="display:flex;flex-direction:column;gap:6px">
          <div class="now-sub">Nessun utente rilevato nel canale vocale.</div>
        </div>
      </div>
    </div>

    <div id="view-c" class="cfg-grid" style="display:none">
      <div class="cfg-box">
        <div class="cfg-title">
          <span>🎛️ Modalità Operativa Bot</span>
          <span class="badge" id="cfg-mode-label">Comandi</span>
        </div>
        <div class="cfg-row">
          <button type="button" class="primary" id="btn-mode-activity">🎛️ Modalità Activity</button>
          <button type="button" id="btn-mode-commands">💬 Modalità Comandi Slash</button>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title">
          <span>🔑 Server Plex del Bot (Admin)</span>
          <span class="badge" id="cfg-plex-status">Verifica...</span>
        </div>
        <div class="cfg-row">
          <button type="button" class="primary" id="btn-plex-login">🔑 Collega Server con PIN</button>
          <button type="button" class="danger" id="btn-plex-logout">Scollega Server</button>
        </div>
        <div class="pin-card" id="plex-pin-box">
          <div style="font-size:12px">Apri <b>https://plex.tv/link</b> e inserisci il codice PIN a 4 caratteri:</div>
          <div class="pin-code" id="plex-pin-code" title="Clicca per copiare">----</div>
          <div class="cfg-row" style="justify-content:center">
            <button type="button" class="primary" id="btn-plex-open-link">Apri plex.tv/link</button>
            <button type="button" id="btn-plex-copy">Copia Codice</button>
            <button type="button" class="ok" id="btn-plex-complete">Ho inserito il PIN</button>
          </div>
          <div class="now-sub">⏳ Verifica automatica ogni 3 secondi...</div>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title">
          <span>🖥️ Scelta Server & Indirizzo</span>
          <button type="button" id="btn-load-servers" style="padding:5px 10px;font-size:11px">Carica Server</button>
        </div>
        <div class="cfg-row">
          <label>Indirizzo manuale</label>
          <input type="text" id="cfg-addr" placeholder="Automatico (es. http://192.168.1.20:32400)">
          <button type="button" id="btn-save-addr">Salva URL</button>
        </div>
        <div class="cfg-row">
          <label>Server Plex</label>
          <select id="cfg-server-sel"><option value="">Clicca 'Carica Server'...</option></select>
          <button type="button" class="primary" id="btn-select-server">Connetti</button>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title">
          <span>📚 Librerie Musicali</span>
          <button type="button" id="btn-libs-all" style="padding:5px 10px;font-size:11px">Abilita Tutte</button>
        </div>
        <div id="cfg-libs-list" style="display:flex;flex-direction:column;gap:5px">
          <div class="now-sub">Nessuna libreria caricata.</div>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title"><span>🔊 Audio & Limiti</span></div>
        <div class="cfg-row">
          <label>Volume predefinito (0–150%)</label>
          <input type="number" id="cfg-vol" min="0" max="150" value="100">
        </div>
        <div class="cfg-row">
          <label>Bitrate Opus (kbps)</label>
          <input type="number" id="cfg-bit" min="32" max="320" value="128">
        </div>
        <div class="cfg-row">
          <label>Timeout inattività (s)</label>
          <input type="number" id="cfg-idle" min="15" max="1800" value="120">
        </div>
        <div class="cfg-row">
          <label>Max brani in coda</label>
          <input type="number" id="cfg-maxq" min="1" max="500" value="100">
        </div>
        <div class="cfg-row">
          <button type="button" class="ok" id="btn-save-settings">Salva Impostazioni</button>
        </div>
      </div>
    </div>
  </section>
</main>
<div class="toast" id="toast"></div>
<script>
const params = new URLSearchParams(location.search);
let guildId = params.get("guild_id") || "";
let channelId = params.get("channel_id") || "";
const token = params.get("token") || "";
const frameId = params.get("frame_id") || "";
const clientId = "__CLIENT_ID__" || params.get("client_id") || "";
let sdkReady = false;
let rpcAuthed = false;
let authInFlight = false;
let stateLoaded = false;
let discordUser = null;
const pendingRpc = new Map();

function getSavedRpcToken() {
  try { return localStorage.getItem("plexcord_discord_token") || ""; } catch { return ""; }
}
function setSavedRpcToken(tok) {
  try {
    if (tok) localStorage.setItem("plexcord_discord_token", tok);
    else localStorage.removeItem("plexcord_discord_token");
  } catch {}
}

function rpcCall(cmd, args = {}) {
  if (!frameId || window.parent === window) return Promise.reject(new Error("Non in Discord Activity"));
  const nonce = Math.random().toString(36).slice(2) + Date.now().toString(36);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pendingRpc.delete(nonce);
      reject(new Error("Timeout RPC " + cmd));
    }, 30000);
    pendingRpc.set(nonce, {resolve, reject, timer});
    window.parent.postMessage([1, {cmd, args, nonce}], "*");
  });
}

function openExternalUrl(url) {
  if (!frameId || window.parent === window) {
    window.open(url, "_blank", "noopener");
    return;
  }
  rpcCall("OPEN_EXTERNAL_LINK", {url}).catch(() => window.open(url, "_blank", "noopener"));
}

async function copyText(text) {
  const clean = (text || "").trim();
  if (!clean || clean === "----") return false;
  let ok = false;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(clean);
      ok = true;
    }
  } catch {}
  if (!ok) {
    const ta = document.createElement("textarea");
    ta.value = clean;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, clean.length);
    try { ok = document.execCommand("copy"); } catch {}
    document.body.removeChild(ta);
  }
  return ok;
}

function setRpcAuthUI(user) {
  rpcAuthed = true;
  discordUser = user;
  const name = (user && (user.global_name || user.username)) || "Attivo";
  const hdrBtn = document.getElementById("btn-header-rpc");
  hdrBtn.textContent = "🟣 RPC: " + name;
  hdrBtn.classList.add("sync-ok");
  const badge = document.getElementById("rpc-status-badge");
  badge.textContent = "✅ Attivo (" + name + ")";
  badge.classList.add("sync-ok");
  if (user && user.id) {
    const uSel = document.getElementById("user-sel");
    if ([...uSel.options].some(o => o.value === String(user.id))) {
      uSel.value = String(user.id);
    }
  }
  lastPresenceKey = "";
  lastPresenceSentAt = 0;
  updateDiscordActivityPresence(true);
}

async function tryAuthenticateToken(tok) {
  if (!tok) return false;
  try {
    const auth = await rpcCall("AUTHENTICATE", {access_token: tok});
    setSavedRpcToken(tok);
    setRpcAuthUI(auth && auth.user);
    return true;
  } catch {
    setSavedRpcToken("");
    return false;
  }
}

async function authorizeDiscordRpc(interactive = false) {
  if (!sdkReady || !clientId) {
    if (interactive) msg("⚠️ Apri l'Activity direttamente dentro il canale vocale di Discord per usare l'RPC.");
    return;
  }
  if (rpcAuthed) {
    lastPresenceKey = "";
    lastPresenceSentAt = 0;
    updateDiscordActivityPresence(true);
    if (interactive) msg("🟣 Discord RPC attivo! Stato aggiornato sul tuo profilo.");
    return;
  }
  if (authInFlight) return;
  authInFlight = true;
  try {
    // 1. Prova prima il token salvato in localStorage (senza mostrare alcun popup AUTHORIZE)
    const localTok = getSavedRpcToken();
    if (localTok && await tryAuthenticateToken(localTok)) {
      if (interactive) msg("🟣 Discord RPC già attivo!");
      return;
    }

    // 2. Prova a ripristinare (o rinnovare tramite refresh_token) il token salvato sul server SQLite
    try {
      const rSaved = await fetch(apiPath("api/discord_token"), {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({action: "restore", client_id: clientId})
      });
      if (rSaved.ok) {
        const savedData = await rSaved.json();
        if (savedData.access_token && await tryAuthenticateToken(savedData.access_token)) {
          if (interactive) msg("🟣 Discord RPC già attivo!");
          return;
        }
        // Se il token salvato è stato revocato/scaduto su Discord, forza il refresh col refresh_token
        const rRef = await fetch(apiPath("api/discord_token"), {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({action: "restore", refresh: true, client_id: clientId})
        });
        if (rRef.ok) {
          const refData = await rRef.json();
          if (refData.access_token && await tryAuthenticateToken(refData.access_token)) {
            if (interactive) msg("🟣 Discord RPC già attivo!");
            return;
          }
        }
      }
    } catch {}

    // IMPORTANTE: non chiamare MAI rpcCall("AUTHORIZE") in automatico all'avvio!
    // Mostra il popup di autorizzazione SOLO quando l'utente clicca esplicitamente il pulsante.
    if (!interactive) return;

    if (!state.has_discord_secret) {
      showTab("u");
      msg("⚠️ Inserisci prima il Discord Client Secret nella scheda '🎧 RPC & Account'.");
      document.getElementById("cfg-discord-secret").focus();
      return;
    }

    const authRes = await rpcCall("AUTHORIZE", {
      client_id: clientId,
      response_type: "code",
      state: "",
      prompt: "none",
      scope: ["identify", "rpc.activities.write"]
    });
    if (!authRes || !authRes.code) throw new Error("Codice OAuth2 non ricevuto");
    const r = await fetch(apiPath("api/discord_token"), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action: "exchange", code: authRes.code, client_id: clientId})
    });
    const tokData = await r.json();
    if (!r.ok || !tokData.access_token) {
      throw new Error(tokData.error || "Scambio token Discord fallito");
    }
    if (!await tryAuthenticateToken(tokData.access_token)) {
      throw new Error("Autenticazione RPC con Discord non riuscita");
    }
    msg("🟣 Discord RPC attivato! Il brano ora appare sul tuo profilo Discord.");
  } catch (err) {
    if (interactive) msg("⚠️ " + (err.message || "Autorizzazione Discord RPC non riuscita."));
  } finally {
    authInFlight = false;
  }
}

function initDiscordSdk() {
  if (!frameId || window.parent === window) return;
  document.getElementById("sdk-status").textContent = "Discord Activity";
  window.addEventListener("message", (ev) => {
    const d = ev.data;
    if (!Array.isArray(d) || d[0] !== 1 || !d[1]) return;
    const p = d[1];
    if (p.nonce && pendingRpc.has(p.nonce)) {
      const entry = pendingRpc.get(p.nonce);
      pendingRpc.delete(p.nonce);
      clearTimeout(entry.timer);
      if (p.evt === "ERROR") {
        entry.reject(new Error((p.data && p.data.message) || "Errore RPC"));
      } else {
        entry.resolve(p.data);
      }
      return;
    }
    if (p.cmd === "DISPATCH" && p.evt === "READY") {
      sdkReady = true;
      document.getElementById("sdk-status").textContent = "Discord Activity Attiva";
      setTimeout(() => authorizeDiscordRpc(false), 300);
    }
  });
  window.parent.postMessage([0, {
    v: 1,
    encoding: "json",
    client_id: clientId,
    frame_id: frameId,
    sdk_version: "1.9.0"
  }], "*");
}
initDiscordSdk();

function padRpcStr(s, fallback) {
  let clean = String(s || fallback || "Plexcord").trim();
  if (clean.length < 2) clean = (clean + " · Plex").slice(0, 128);
  return clean.slice(0, 128);
}

let lastPresenceKey = "";
let lastPresenceTrackId = "";
let lastPresencePaused = false;
let lastPresenceStartSec = 0;
let lastPresenceSentAt = 0;
let presenceTimer = null;

function updateDiscordActivityPresence(force = false) {
  if (!sdkReady || !rpcAuthed || !stateLoaded) return;
  const cur = state.current;
  const nowMs = Date.now();
  const nowSec = Math.floor(nowMs / 1000);

  if (!cur) {
    if (lastPresenceKey === "idle" && !force) return;
    lastPresenceKey = "idle";
    lastPresenceTrackId = "";
    const idleAct = {
      type: 2,
      details: padRpcStr("In attesa di un brano", "Plexcord"),
      state: padRpcStr("Plexcord · " + (state.server_name || "Plex"), "Plex")
    };
    rpcCall("SET_ACTIVITY", {activity: idleAct}).catch(() => {
      rpcCall("SET_ACTIVITY", {activity: {...idleAct, type: 0}}).catch(() => {});
    });
    return;
  }

  const durSec = Math.floor((cur.duration || 0) / 1000);
  const elSec = Math.max(0, Math.min(durSec || (state.elapsed || 0), state.elapsed || 0));
  const computedStartSec = nowSec - elSec;
  const trackChanged = cur.id !== lastPresenceTrackId;
  const pauseChanged = Boolean(state.paused) !== lastPresencePaused;
  const seeked = !state.paused && Math.abs(computedStartSec - lastPresenceStartSec) >= 6;

  if (!force && !trackChanged && !pauseChanged && !seeked) return;

  // Rispetta il rate-limit RPC di Discord evitando invii ravvicinati
  const elapsedSinceLast = nowMs - lastPresenceSentAt;
  if (!force && !trackChanged && elapsedSinceLast < 4000) {
    clearTimeout(presenceTimer);
    presenceTimer = setTimeout(() => updateDiscordActivityPresence(true), 4000 - elapsedSinceLast);
    return;
  }

  lastPresenceKey = `${cur.id}:${state.paused}`;
  lastPresenceTrackId = cur.id;
  lastPresencePaused = Boolean(state.paused);
  lastPresenceStartSec = computedStartSec;
  lastPresenceSentAt = nowMs;

  const detailsStr = padRpcStr((state.paused ? "⏸️ " : "🎵 ") + cur.title, "Brano su Plex");
  const stateStr = padRpcStr("di " + cur.artist + (cur.album ? " · " + cur.album : ""), "Artista");
  const actObj = {
    type: 2,
    details: detailsStr,
    state: stateStr
  };
  if (!state.paused && durSec > 0) {
    const startMs = nowMs - (elSec * 1000);
    const endMs = startMs + Math.max(1000, durSec * 1000);
    actObj.timestamps = {
      start: startMs,
      end: endMs
    };
  }
  rpcCall("SET_ACTIVITY", {activity: actObj}).catch(() => {
    rpcCall("SET_ACTIVITY", {activity: {...actObj, type: 0}}).catch(() => {});
  });
}

function fmt(sec) {
  sec = Math.max(0, Math.floor(sec || 0));
  const m = Math.floor(sec / 60), s = sec % 60;
  return m + ":" + (s < 10 ? "0" : "") + s;
}
function esc(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}
function msg(text) {
  const el = document.getElementById("toast");
  el.textContent = text;
  el.style.display = "block";
  clearTimeout(window._t);
  window._t = setTimeout(() => el.style.display = "none", 3000);
}
function apiPath(path) {
  const base = location.pathname.endsWith("/") ? location.pathname : location.pathname + "/";
  return base + path + "?" + new URLSearchParams({guild_id: guildId, channel_id: channelId, token}).toString();
}
function artUrlFor(trackId) {
  return apiPath("api/art/" + encodeURIComponent(guildId || "0") + "/" + encodeURIComponent(trackId));
}

const artOkCache = new Set();
let thumbQueue = [];
let activeThumbLoads = 0;

function mountThumbImage(box, url) {
  const img = new Image();
  img.alt = "";
  img.src = url;
  box.innerHTML = "";
  box.appendChild(img);
}

function pumpThumbQueue() {
  while (activeThumbLoads < 6 && thumbQueue.length > 0) {
    const box = thumbQueue.shift();
    if (!box || !box.isConnected) continue;
    const url = box.getAttribute("data-art");
    if (!url) continue;
    box.removeAttribute("data-art");
    if (artOkCache.has(url)) {
      mountThumbImage(box, url);
      continue;
    }
    activeThumbLoads++;
    const img = new Image();
    img.alt = "";
    img.onload = () => {
      activeThumbLoads--;
      artOkCache.add(url);
      if (box.isConnected) {
        box.innerHTML = "";
        box.appendChild(img);
      }
      pumpThumbQueue();
    };
    img.onerror = () => {
      activeThumbLoads--;
      pumpThumbQueue();
    };
    img.src = url;
  }
}

function hydrateThumbs(root) {
  if (!root) return;
  root.querySelectorAll(".item-thumb[data-art]").forEach(box => {
    const url = box.getAttribute("data-art");
    if (!url) return;
    if (artOkCache.has(url)) {
      box.removeAttribute("data-art");
      mountThumbImage(box, url);
    } else {
      thumbQueue.push(box);
    }
  });
  pumpThumbQueue();
}

function isMobileView() {
  return window.matchMedia("(max-width: 820px), (max-height: 540px)").matches;
}

function showTab(t) {
  document.body.classList.remove("player-expanded");
  ["s", "p", "q", "u", "c"].forEach(k => {
    document.getElementById("tab-" + k).classList.toggle("active", k === t);
    document.getElementById("view-" + k).style.display = k === t ? "flex" : "none";
  });
  if (t === "s" && !isMobileView()) document.getElementById("q-in").focus();
  if (t === "p") loadPlaylists();
}
document.getElementById("tab-s").addEventListener("click", () => showTab("s"));
document.getElementById("tab-p").addEventListener("click", () => showTab("p"));
document.getElementById("tab-q").addEventListener("click", () => showTab("q"));
document.getElementById("tab-u").addEventListener("click", () => showTab("u"));
document.getElementById("tab-c").addEventListener("click", () => showTab("c"));
document.getElementById("btn-header-rpc").addEventListener("click", () => authorizeDiscordRpc(true));
document.getElementById("btn-auth-rpc").addEventListener("click", () => authorizeDiscordRpc(true));

document.getElementById("btn-expand-player").addEventListener("click", () => {
  document.body.classList.add("player-expanded");
});
document.getElementById("btn-collapse-player").addEventListener("click", () => {
  document.body.classList.remove("player-expanded");
});
document.getElementById("now-row-tap").addEventListener("click", () => {
  if (isMobileView() && !document.body.classList.contains("player-expanded")) {
    document.body.classList.add("player-expanded");
  }
});

let state = {current: null, elapsed: 0, paused: false, queue: [], libraries: [], all_libraries: [], voice_users: [], has_discord_secret: false, has_discord_token: false};
let lastArtId = "";
let lastQueueKey = null;
let lastLibsKey = null;
let lastAllLibsKey = null;
let lastVoiceUsersKey = null;
let volDragging = false;
let searchResults = [];
let userPlaylists = [];
let playlistTracks = [];
let activePlaylist = null;

function updateProgressUI() {
  const cur = state.current;
  if (!cur) {
    document.getElementById("t-cur").textContent = "0:00";
    document.getElementById("t-dur").textContent = "0:00";
    document.getElementById("bar-fill").style.width = "0%";
    return;
  }
  const dur = Math.floor((cur.duration || 0) / 1000);
  const el = Math.min(dur || state.elapsed, state.elapsed || 0);
  document.getElementById("t-cur").textContent = fmt(el);
  document.getElementById("t-dur").textContent = fmt(dur);
  document.getElementById("bar-fill").style.width = (dur > 0 ? Math.min(100, (el / dur) * 100) : 0) + "%";
}

function render(st) {
  state = st;
  stateLoaded = true;
  if (st.guild_id) guildId = String(st.guild_id);
  if (st.channel_id) channelId = String(st.channel_id);
  document.getElementById("srv").textContent = st.server_name || "Plex non configurato";
  const isAct = st.mode === "activity";
  document.getElementById("mode-badge").textContent = isAct ? "🎛️ Activity" : "💬 Comandi";
  document.getElementById("cfg-mode-label").textContent = isAct ? "Activity" : "Comandi Slash";
  document.getElementById("cfg-plex-status").textContent = st.has_token ? (st.server_name ? "✅ " + st.server_name : "⚠️ Scegli server") : "❌ Non collegato";

  if (st.has_discord_secret) {
    document.getElementById("cfg-discord-secret").placeholder = "✅ Client Secret configurato (incolla per sostituire)";
  }

  const linkedListeners = (st.voice_users || []).filter(u => u.plex_username);
  const syncBadge = document.getElementById("sync-badge");
  const pill = document.getElementById("listeners-pill");
  if (linkedListeners.length) {
    syncBadge.style.display = "inline-flex";
    syncBadge.textContent = "🎧 Sync Plex (" + linkedListeners.length + ")";
    pill.style.display = "block";
    pill.textContent = "🎧 Su Plex: " + linkedListeners.map(u => u.plex_username).join(", ");
  } else {
    syncBadge.style.display = "none";
    pill.style.display = "none";
  }

  if (!volDragging && document.activeElement !== document.getElementById("vol")) {
    const v = st.volume ?? 100;
    document.getElementById("vol").value = v;
    document.getElementById("vol-val").textContent = v + "%";
  }
  if (document.activeElement !== document.getElementById("cfg-vol") && st.volume !== undefined) {
    document.getElementById("cfg-vol").value = st.volume;
    document.getElementById("cfg-bit").value = st.bitrate ?? 128;
    document.getElementById("cfg-idle").value = st.idle_seconds ?? 120;
    document.getElementById("cfg-maxq").value = st.max_queue ?? 100;
  }
  if (document.activeElement !== document.getElementById("cfg-addr") && st.address_override !== undefined) {
    document.getElementById("cfg-addr").value = st.address_override || "";
  }

  const cur = st.current;
  const eqEl = document.getElementById("eq-overlay");
  const icoPlay = document.getElementById("ico-play");
  const lblPlay = document.getElementById("lbl-play");
  if (st.paused) {
    if (icoPlay) icoPlay.innerHTML = '<path d="M8 5v14l11-7z"/>';
    if (lblPlay) lblPlay.textContent = "Riprendi";
  } else {
    if (icoPlay) icoPlay.innerHTML = '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>';
    if (lblPlay) lblPlay.textContent = "Pausa";
  }
  if (cur) {
    eqEl.classList.toggle("playing", !st.paused);
    document.getElementById("now-title").textContent = cur.title;
    document.getElementById("now-artist").textContent = cur.artist;
    document.getElementById("now-album").textContent = (cur.album ? cur.album + " · " : "") + cur.library;
    updateProgressUI();
    updateDiscordActivityPresence();
    if (lastArtId !== cur.id) {
      lastArtId = cur.id;
      const artUrl = artUrlFor(cur.id);
      const img = new Image();
      img.onload = () => {
        const w = document.getElementById("art");
        const oldImg = w.querySelector("img");
        if (oldImg) oldImg.remove();
        document.getElementById("art-icon").style.display = "none";
        w.insertBefore(img, eqEl);
        const bg = document.getElementById("ambient-bg");
        bg.style.backgroundImage = `url("${artUrl}")`;
        bg.style.opacity = "1";
      };
      img.onerror = () => {
        const w = document.getElementById("art");
        const oldImg = w.querySelector("img");
        if (oldImg) oldImg.remove();
        document.getElementById("art-icon").style.display = "block";
        document.getElementById("ambient-bg").style.opacity = "0";
      };
      img.src = artUrl;
    }
  } else {
    lastArtId = "";
    eqEl.classList.remove("playing");
    const w = document.getElementById("art");
    const oldImg = w.querySelector("img");
    if (oldImg) oldImg.remove();
    document.getElementById("art-icon").style.display = "block";
    document.getElementById("ambient-bg").style.opacity = "0";
    document.getElementById("now-title").textContent = "Nessun brano in riproduzione";
    document.getElementById("now-artist").textContent = "Cerca un brano per iniziare";
    document.getElementById("now-album").textContent = "";
    updateProgressUI();
    updateDiscordActivityPresence();
  }

  const q = st.queue || [];
  document.getElementById("q-count").textContent = q.length;
  const qKey = guildId + ":" + JSON.stringify(q);
  if (qKey !== lastQueueKey) {
    lastQueueKey = qKey;
    const qEl = document.getElementById("view-q");
    qEl.innerHTML = q.length ? q.map((t, i) => `
      <div class="item">
        <div class="item-thumb" data-art="${esc(artUrlFor(t.id))}">
          <svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg>
        </div>
        <div class="item-info">
          <div class="item-title">${i + 1}. ${esc(t.title)}</div>
          <div class="item-artist">${esc(t.artist)}</div>
          <div class="item-meta">
            <span class="pill-dur">${fmt((t.duration || 0) / 1000)}</span>
            <span>${esc(t.album || t.library)}</span>
          </div>
        </div>
        <div class="item-actions">
          <button type="button" class="ok" data-qact="play_now" data-idx="${i}" title="Riproduci subito">▶ <span class="lbl-hide-xs">Ora</span></button>
          <button type="button" data-qact="top" data-idx="${i}" title="Sposta in cima">↑</button>
          <button type="button" class="danger" data-qact="remove" data-idx="${i}" title="Rimuovi">✕</button>
        </div>
      </div>`).join("") : `
      <div class="empty-state">
        <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg></div>
        <div class="empty-title">La coda è vuota</div>
        <div class="empty-sub">Usa la scheda <b>Cerca</b> o <b>Playlist</b> per aggiungere i tuoi brani preferiti!</div>
      </div>`;
    hydrateThumbs(qEl);
  }

  const vuKey = JSON.stringify(st.voice_users || []);
  if (vuKey !== lastVoiceUsersKey) {
    lastVoiceUsersKey = vuKey;
    const vUsers = st.voice_users || [];
    const uSel = document.getElementById("user-sel");
    const prevU = (discordUser && String(discordUser.id)) || uSel.value;
    uSel.innerHTML = "";
    vUsers.forEach(u => {
      const o = document.createElement("option");
      o.value = u.id;
      o.textContent = u.name + (u.plex_username ? " (Plex: " + u.plex_username + ")" : "");
      uSel.appendChild(o);
    });
    if (prevU && vUsers.some(u => u.id === prevU)) uSel.value = prevU;

    const plSel = document.getElementById("pl-user-sel");
    const prevPlU = (discordUser && String(discordUser.id)) || plSel.value;
    plSel.innerHTML = "";
    const linkedUsers = vUsers.filter(u => u.plex_username);
    if (linkedUsers.length) {
      linkedUsers.forEach(u => {
        const o = document.createElement("option");
        o.value = u.id;
        o.textContent = "🎧 " + u.plex_username + " (" + u.name + ")";
        plSel.appendChild(o);
      });
      if (prevPlU && linkedUsers.some(u => u.id === prevPlU)) plSel.value = prevPlU;
    } else {
      const o = document.createElement("option");
      o.value = "";
      o.textContent = "Nessun account Plex collegato nel canale";
      plSel.appendChild(o);
    }

    const vuList = document.getElementById("voice-users-list");
    vuList.innerHTML = vUsers.length ? vUsers.map(u => `
      <div class="lib-item">
        <span>👤 <b>${esc(u.name)}</b></span>
        <span class="badge ${u.plex_username ? 'sync-ok' : ''}">
          ${u.plex_username ? '✅ Plex: ' + esc(u.plex_username) : 'Non collegato'}
        </span>
      </div>`).join("") : '<div class="now-sub">Entra nel canale vocale per collegare il tuo account.</div>';
  }

  const libsKey = JSON.stringify(st.libraries || []);
  if (libsKey !== lastLibsKey) {
    lastLibsKey = libsKey;
    const sel = document.getElementById("lib-sel");
    const curVal = sel.value;
    sel.innerHTML = '<option value="">Tutte le librerie</option>';
    (st.libraries || []).forEach(l => {
      const o = document.createElement("option");
      o.value = l.id;
      o.textContent = l.title;
      sel.appendChild(o);
    });
    sel.value = curVal;
  }

  const allLibsKey = JSON.stringify(st.all_libraries || []);
  if (allLibsKey !== lastAllLibsKey) {
    lastAllLibsKey = allLibsKey;
    const box = document.getElementById("cfg-libs-list");
    const allLibs = st.all_libraries || [];
    box.innerHTML = allLibs.length ? allLibs.map(l => `
      <div class="lib-item">
        <span><b>${esc(l.title)}</b> (ID: ${esc(l.id)})</span>
        <button type="button" class="${l.enabled ? 'ok' : ''}" data-libid="${esc(l.id)}" data-enabled="${l.enabled ? '0' : '1'}">
          ${l.enabled ? '✅ Abilitata' : '❌ Disabilitata'}
        </button>
      </div>`).join("") : '<div class="now-sub">Collega un server Plex per vedere le librerie musicali.</div>';
  }
}

async function act(action, extra = {}, silent = false) {
  try {
    const r = await fetch(apiPath("api/control"), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action, ...extra})
    });
    const data = await r.json();
    if (!r.ok) { if (!silent) msg("⚠️ " + (data.error || "Errore")); return null; }
    if (data.message && !silent) msg(data.message);
    if (data.state) render(data.state);
    return data;
  } catch {
    if (!silent) msg("⚠️ Connessione al bot non riuscita.");
    return null;
  }
}

async function cfgAct(action, extra = {}, silent = false) {
  try {
    const r = await fetch(apiPath("api/config"), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action, ...extra})
    });
    const data = await r.json();
    if (!r.ok) { if (!silent) msg("⚠️ " + (data.error || "Errore")); return null; }
    if (data.message && !silent) msg(data.message);
    if (data.state) render(data.state);
    return data;
  } catch {
    if (!silent) msg("⚠️ Errore di connessione al bot.");
    return null;
  }
}

// Controlli principali del player
document.getElementById("btn-restart").addEventListener("click", () => act("seek", {seconds: 0}));
document.getElementById("btn-play").addEventListener("click", () => act("toggle"));
document.getElementById("btn-skip").addEventListener("click", () => act("skip"));
document.getElementById("btn-shuffle").addEventListener("click", () => act("shuffle"));
document.getElementById("btn-stop").addEventListener("click", () => act("stop"));
document.getElementById("btn-leave").addEventListener("click", () => act("leave"));

document.getElementById("seek-bar").addEventListener("click", (e) => {
  if (!state.current || !state.current.duration) return;
  const rect = e.currentTarget.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  const seconds = Math.floor(ratio * (state.current.duration / 1000));
  act("seek", {seconds});
});

// Controlli Volume in tempo reale (senza interrompere la riproduzione)
const volEl = document.getElementById("vol");
let volLiveTimer = null;
volEl.addEventListener("pointerdown", () => { volDragging = true; });
volEl.addEventListener("input", () => {
  document.getElementById("vol-val").textContent = volEl.value + "%";
  if (!volLiveTimer) {
    volLiveTimer = setTimeout(() => {
      volLiveTimer = null;
      act("volume", {volume: Number(volEl.value)}, true);
    }, 100);
  }
});
volEl.addEventListener("change", () => {
  volDragging = false;
  clearTimeout(volLiveTimer);
  volLiveTimer = null;
  act("volume", {volume: Number(volEl.value)});
});
document.getElementById("btn-voldown").addEventListener("click", () => {
  const v = Math.max(0, Number(volEl.value) - 10);
  volEl.value = v;
  document.getElementById("vol-val").textContent = v + "%";
  act("volume", {volume: v});
});
document.getElementById("btn-volup").addEventListener("click", () => {
  const v = Math.min(150, Number(volEl.value) + 10);
  volEl.value = v;
  document.getElementById("vol-val").textContent = v + "%";
  act("volume", {volume: v});
});

// Event delegation per la Coda
document.getElementById("view-q").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-qact]");
  if (!btn) return;
  const idx = Number(btn.dataset.idx);
  const qact = btn.dataset.qact;
  if (qact === "play_now") act("promote", {index: idx, play_now: true});
  else if (qact === "top") act("promote", {index: idx, play_now: false});
  else if (qact === "remove") act("remove", {index: idx});
});

// Gestione Playlist Personali Plex
function currentPlUserId() {
  const selVal = document.getElementById("pl-user-sel").value;
  if (selVal) return selVal;
  if (discordUser && discordUser.id) return String(discordUser.id);
  const linked = (state.voice_users || []).find(u => u.plex_username);
  return linked ? linked.id : "";
}

function renderPlaylistList() {
  activePlaylist = null;
  document.getElementById("pl-header-bar").style.display = "flex";
  document.getElementById("pl-detail-bar").style.display = "none";
  const list = document.getElementById("p-list");
  if (!userPlaylists.length) {
    list.innerHTML = '<div class="empty-state"><div class="empty-title">Nessuna playlist trovata</div><div class="empty-sub">Non ci sono playlist audio sul tuo account Plex.</div></div>';
    return;
  }
  list.innerHTML = userPlaylists.map((p, i) => `
    <div class="item">
      <div class="item-thumb" data-art="${esc(artUrlFor('pl_' + p.id))}">
        <svg viewBox="0 0 24 24"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg>
      </div>
      <div class="item-info" style="cursor:pointer" data-pact="open" data-idx="${i}">
        <div class="item-title">${esc(p.title)}</div>
        <div class="item-artist">${p.track_count} brani</div>
        <div class="item-meta">
          <span class="pill-dur">${fmt((p.duration || 0) / 1000)}</span>
          <span>Tocca per aprire</span>
        </div>
      </div>
      <div class="item-actions">
        <button type="button" class="ok" data-pact="play" data-idx="${i}" title="Riproduci subito la playlist">▶ <span class="lbl-hide-xs">Ora</span></button>
        <button type="button" data-pact="shuffle" data-idx="${i}" title="Riproduci playlist mescolata">🔀</button>
        <button type="button" class="primary" data-pact="queue" data-idx="${i}" title="Aggiungi playlist in coda">+ <span class="lbl-hide-xs">Coda</span></button>
        <button type="button" data-pact="open" data-idx="${i}" title="Apri e vedi i brani">📂</button>
      </div>
    </div>`).join("");
  hydrateThumbs(list);
}

async function loadPlaylists() {
  const uid = currentPlUserId();
  const list = document.getElementById("p-list");
  activePlaylist = null;
  document.getElementById("pl-header-bar").style.display = "flex";
  document.getElementById("pl-detail-bar").style.display = "none";
  if (!uid) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg></div>
        <div class="empty-title">Collega il tuo Account Plex</div>
        <div class="empty-sub">Accedi con il codice PIN a 4 cifre nella scheda <b>Account</b> per sfogliare e riprodurre le tue playlist personali.</div>
        <button type="button" class="primary" id="btn-go-link-plex" style="margin-top:6px">🔑 Collega Account Plex</button>
      </div>`;
    const goBtn = document.getElementById("btn-go-link-plex");
    if (goBtn) goBtn.addEventListener("click", () => showTab("u"));
    return;
  }
  list.innerHTML = '<div class="empty-state"><div class="empty-sub">⏳ Caricamento delle tue playlist Plex...</div></div>';
  try {
    const u = new URLSearchParams({guild_id: guildId, channel_id: channelId, token, discord_id: uid});
    const base = location.pathname.endsWith("/") ? location.pathname : location.pathname + "/";
    const r = await fetch(base + "api/playlists?" + u.toString());
    const data = await r.json();
    if (!r.ok) {
      list.innerHTML = `<div class="empty-state"><div class="empty-sub">⚠️ ${esc(data.error || "Errore caricamento playlist")}</div></div>`;
      return;
    }
    if (!data.linked) {
      list.innerHTML = `
        <div class="empty-state">
          <div class="empty-title">Account Plex non ancora collegato</div>
          <div class="empty-sub">${esc(data.error || "Collega il tuo account Plex nella scheda 'Account'.")}</div>
          <button type="button" class="primary" id="btn-go-link-plex2" style="margin-top:6px">🔑 Collega Account Plex</button>
        </div>`;
      const goBtn = document.getElementById("btn-go-link-plex2");
      if (goBtn) goBtn.addEventListener("click", () => showTab("u"));
      return;
    }
    userPlaylists = data.playlists || [];
    renderPlaylistList();
  } catch {
    list.innerHTML = '<div class="empty-state"><div class="empty-sub">⚠️ Errore di rete durante il caricamento delle playlist.</div></div>';
  }
}

async function openPlaylist(pl) {
  if (!pl) return;
  activePlaylist = pl;
  document.getElementById("pl-header-bar").style.display = "none";
  document.getElementById("pl-detail-bar").style.display = "flex";
  document.getElementById("pl-detail-title").textContent = pl.title + " (" + pl.track_count + ")";
  const list = document.getElementById("p-list");
  list.innerHTML = '<div class="empty-state"><div class="empty-sub">⏳ Caricamento brani della playlist...</div></div>';
  try {
    const uid = currentPlUserId();
    const u = new URLSearchParams({guild_id: guildId, channel_id: channelId, token, playlist_id: pl.id, discord_id: uid});
    const base = location.pathname.endsWith("/") ? location.pathname : location.pathname + "/";
    const r = await fetch(base + "api/playlist_tracks?" + u.toString());
    const data = await r.json();
    if (!r.ok) {
      list.innerHTML = `<div class="empty-state"><div class="empty-sub">⚠️ ${esc(data.error || "Errore")}</div></div>`;
      return;
    }
    playlistTracks = data.tracks || [];
    list.innerHTML = playlistTracks.length ? playlistTracks.map((t, i) => `
      <div class="item">
        <div class="item-thumb" data-art="${esc(artUrlFor(t.id))}">
          <svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg>
        </div>
        <div class="item-info">
          <div class="item-title">${i + 1}. ${esc(t.title)}</div>
          <div class="item-artist">${esc(t.artist)}</div>
          <div class="item-meta">
            <span class="pill-dur">${fmt((t.duration || 0) / 1000)}</span>
            <span>${esc(t.album || t.library)}</span>
          </div>
        </div>
        <div class="item-actions">
          <button type="button" class="ok" data-ptact="now" data-idx="${i}" title="Riproduci subito">▶ <span class="lbl-hide-xs">Ora</span></button>
          <button type="button" class="primary" data-ptact="queue" data-idx="${i}" title="Aggiungi alla coda">+ <span class="lbl-hide-xs">Coda</span></button>
        </div>
      </div>`).join("") : '<div class="empty-state"><div class="empty-sub">Questa playlist è vuota.</div></div>';
    hydrateThumbs(list);
  } catch {
    list.innerHTML = '<div class="empty-state"><div class="empty-sub">⚠️ Errore di rete.</div></div>';
  }
}

document.getElementById("pl-user-sel").addEventListener("change", loadPlaylists);
document.getElementById("btn-pl-refresh").addEventListener("click", loadPlaylists);
document.getElementById("btn-pl-back").addEventListener("click", renderPlaylistList);
document.getElementById("btn-pl-play-all").addEventListener("click", () => {
  if (activePlaylist) act("play_playlist", {playlist_id: activePlaylist.id, discord_id: currentPlUserId(), play_now: true, shuffle: false});
});
document.getElementById("btn-pl-shuffle-all").addEventListener("click", () => {
  if (activePlaylist) act("play_playlist", {playlist_id: activePlaylist.id, discord_id: currentPlUserId(), play_now: true, shuffle: true});
});
document.getElementById("btn-pl-queue-all").addEventListener("click", () => {
  if (activePlaylist) act("play_playlist", {playlist_id: activePlaylist.id, discord_id: currentPlUserId(), play_now: false, shuffle: false});
});

document.getElementById("p-list").addEventListener("click", (e) => {
  const pEl = e.target.closest("[data-pact]");
  if (pEl) {
    const pl = userPlaylists[Number(pEl.dataset.idx)];
    if (!pl) return;
    const pact = pEl.dataset.pact;
    const uid = currentPlUserId();
    if (pact === "open") openPlaylist(pl);
    else if (pact === "play") act("play_playlist", {playlist_id: pl.id, discord_id: uid, play_now: true, shuffle: false});
    else if (pact === "shuffle") act("play_playlist", {playlist_id: pl.id, discord_id: uid, play_now: true, shuffle: true});
    else if (pact === "queue") act("play_playlist", {playlist_id: pl.id, discord_id: uid, play_now: false, shuffle: false});
    return;
  }
  const tBtn = e.target.closest("button[data-ptact]");
  if (tBtn) {
    const track = playlistTracks[Number(tBtn.dataset.idx)];
    if (!track) return;
    act("play", {track, play_now: tBtn.dataset.ptact === "now"});
  }
});

// Ricerca brani con copertina
let searchTimer = null;
document.getElementById("q-in").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(doSearch, 300);
});
document.getElementById("q-in").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { clearTimeout(searchTimer); doSearch(); }
});
document.getElementById("lib-sel").addEventListener("change", doSearch);
document.getElementById("btn-search").addEventListener("click", doSearch);

async function doSearch() {
  const q = document.getElementById("q-in").value.trim();
  const lib = document.getElementById("lib-sel").value;
  const list = document.getElementById("s-list");
  if (!q) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg></div>
        <div class="empty-title">Esplora la tua libreria Plex</div>
        <div class="empty-sub">Digita il titolo di una canzone o il nome di un artista per cercare con anteprima copertina.</div>
      </div>`;
    return;
  }
  list.innerHTML = '<div class="empty-state"><div class="empty-sub">⏳ Ricerca in corso su Plex...</div></div>';
  try {
    const u = new URLSearchParams({guild_id: guildId, channel_id: channelId, token, query: q, library: lib});
    const base = location.pathname.endsWith("/") ? location.pathname : location.pathname + "/";
    const r = await fetch(base + "api/search?" + u.toString());
    const data = await r.json();
    if (!r.ok) {
      list.innerHTML = `<div class="empty-state"><div class="empty-sub">⚠️ ${esc(data.error)}</div></div>`;
      return;
    }
    searchResults = data.tracks || [];
    list.innerHTML = searchResults.length ? searchResults.map((t, i) => `
      <div class="item">
        <div class="item-thumb" data-art="${esc(artUrlFor(t.id))}">
          <svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg>
        </div>
        <div class="item-info">
          <div class="item-title">${esc(t.title)}</div>
          <div class="item-artist">${esc(t.artist)}</div>
          <div class="item-meta">
            <span class="pill-dur">${fmt((t.duration || 0) / 1000)}</span>
            <span>${esc(t.album ? t.album + ' · ' + t.library : t.library)}</span>
          </div>
        </div>
        <div class="item-actions">
          <button type="button" class="ok" data-sact="now" data-idx="${i}" title="Riproduci subito">▶ <span class="lbl-hide-xs">Ora</span></button>
          <button type="button" class="primary" data-sact="queue" data-idx="${i}" title="Aggiungi alla coda">+ <span class="lbl-hide-xs">Coda</span></button>
        </div>
      </div>`).join("") : '<div class="empty-state"><div class="empty-title">Nessun risultato</div><div class="empty-sub">Nessun brano trovato per questa ricerca.</div></div>';
    hydrateThumbs(list);
  } catch {
    list.innerHTML = '<div class="empty-state"><div class="empty-sub">⚠️ Errore di rete durante la ricerca.</div></div>';
  }
}

document.getElementById("s-list").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-sact]");
  if (!btn) return;
  const track = searchResults[Number(btn.dataset.idx)];
  if (!track) return;
  const playNow = btn.dataset.sact === "now";
  act("play", {track, play_now: playNow});
});

// Salvataggio Discord Client Secret per RPC
document.getElementById("btn-save-secret").addEventListener("click", async () => {
  const sec = document.getElementById("cfg-discord-secret").value.trim();
  if (!sec) { msg("⚠️ Incolla il Client Secret di Discord."); return; }
  const d = await cfgAct("save_discord_secret", {client_secret: sec});
  if (d) {
    document.getElementById("cfg-discord-secret").value = "";
    authorizeDiscordRpc(true);
  }
});

// Collegamento Account Personale Plex <-> Discord (PIN 4 cifre + auto-polling)
let userPinPoll = null;
document.getElementById("btn-user-pin").addEventListener("click", async () => {
  const uid = document.getElementById("user-sel").value;
  if (!uid) { msg("⚠️ Entra nel canale vocale e seleziona il tuo utente Discord."); return; }
  const d = await cfgAct("user_pin", {discord_id: uid});
  if (d && d.code) {
    document.getElementById("user-pin-code").textContent = d.code;
    document.getElementById("user-pin-box").style.display = "flex";
    clearInterval(userPinPoll);
    userPinPoll = setInterval(async () => {
      const chk = await cfgAct("user_check_pin", {discord_id: uid}, true);
      if (chk && chk.ok) {
        clearInterval(userPinPoll);
        document.getElementById("user-pin-box").style.display = "none";
        msg(chk.message || "✅ Account Plex collegato!");
      }
    }, 3000);
  }
});
document.getElementById("btn-user-open-link").addEventListener("click", () => openExternalUrl("https://plex.tv/link"));
async function copyUserPin() {
  const c = document.getElementById("user-pin-code").textContent.trim();
  const ok = await copyText(c);
  msg(ok ? "📋 Codice " + c + " copiato negli appunti!" : "📋 Codice PIN: " + c);
}
document.getElementById("btn-user-copy").addEventListener("click", copyUserPin);
document.getElementById("user-pin-code").addEventListener("click", copyUserPin);
document.getElementById("btn-user-check").addEventListener("click", async () => {
  const uid = document.getElementById("user-sel").value;
  const chk = await cfgAct("user_check_pin", {discord_id: uid});
  if (chk && chk.ok) {
    clearInterval(userPinPoll);
    document.getElementById("user-pin-box").style.display = "none";
  }
});
document.getElementById("btn-user-unlink").addEventListener("click", () => {
  const uid = document.getElementById("user-sel").value;
  if (!uid) return;
  clearInterval(userPinPoll);
  document.getElementById("user-pin-box").style.display = "none";
  cfgAct("user_unlink", {discord_id: uid});
});

// Eventi scheda Configurazione Server (PIN 4 cifre + auto-polling)
let srvPinPoll = null;
document.getElementById("btn-mode-activity").addEventListener("click", () => cfgAct("set_mode", {mode: "activity"}));
document.getElementById("btn-mode-commands").addEventListener("click", () => cfgAct("set_mode", {mode: "commands"}));

document.getElementById("btn-plex-login").addEventListener("click", async () => {
  const d = await cfgAct("plex_pin");
  if (d && d.code) {
    document.getElementById("plex-pin-code").textContent = d.code;
    document.getElementById("plex-pin-box").style.display = "flex";
    clearInterval(srvPinPoll);
    srvPinPoll = setInterval(async () => {
      const chk = await cfgAct("plex_check_pin", {}, true);
      if (chk && chk.ok) {
        clearInterval(srvPinPoll);
        document.getElementById("plex-pin-box").style.display = "none";
        msg(chk.message || "✅ Login Plex completato!");
        loadPlexServers();
      }
    }, 3000);
  }
});
document.getElementById("btn-plex-open-link").addEventListener("click", () => openExternalUrl("https://plex.tv/link"));
async function copySrvPin() {
  const c = document.getElementById("plex-pin-code").textContent.trim();
  const ok = await copyText(c);
  msg(ok ? "📋 Codice " + c + " copiato negli appunti!" : "📋 Codice PIN: " + c);
}
document.getElementById("btn-plex-copy").addEventListener("click", copySrvPin);
document.getElementById("plex-pin-code").addEventListener("click", copySrvPin);
document.getElementById("btn-plex-complete").addEventListener("click", async () => {
  const d = await cfgAct("plex_check_pin");
  if (d && d.ok) {
    clearInterval(srvPinPoll);
    document.getElementById("plex-pin-box").style.display = "none";
    loadPlexServers();
  }
});
document.getElementById("btn-plex-logout").addEventListener("click", () => {
  clearInterval(srvPinPoll);
  document.getElementById("plex-pin-box").style.display = "none";
  cfgAct("plex_logout");
});

async function loadPlexServers() {
  const d = await cfgAct("plex_servers");
  if (!d || !d.servers) return;
  const sel = document.getElementById("cfg-server-sel");
  sel.innerHTML = "";
  d.servers.forEach(s => {
    const o = document.createElement("option");
    o.value = s.id;
    o.textContent = s.name + " (" + s.id.slice(0, 8) + ")";
    if (s.selected) o.selected = true;
    sel.appendChild(o);
  });
}
document.getElementById("btn-load-servers").addEventListener("click", loadPlexServers);
document.getElementById("btn-save-addr").addEventListener("click", () => {
  cfgAct("plex_address", {url: document.getElementById("cfg-addr").value.trim()});
});
document.getElementById("btn-select-server").addEventListener("click", () => {
  const id = document.getElementById("cfg-server-sel").value;
  if (!id) { msg("⚠️ Carica e seleziona prima un server Plex."); return; }
  cfgAct("plex_server", {server_id: id});
});
document.getElementById("btn-libs-all").addEventListener("click", () => cfgAct("plex_all_libraries"));
document.getElementById("cfg-libs-list").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-libid]");
  if (!btn) return;
  cfgAct("plex_library", {library_id: btn.dataset.libid, enabled: btn.dataset.enabled === "1"});
});
document.getElementById("btn-save-settings").addEventListener("click", () => {
  cfgAct("save_settings", {
    volume: Number(document.getElementById("cfg-vol").value),
    bitrate: Number(document.getElementById("cfg-bit").value),
    idle_seconds: Number(document.getElementById("cfg-idle").value),
    max_queue: Number(document.getElementById("cfg-maxq").value)
  });
});

function connectWs() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(proto + "//" + location.host + apiPath("api/ws"));
  ws.onmessage = (ev) => {
    try { render(JSON.parse(ev.data)); } catch {}
  };
  ws.onclose = () => setTimeout(connectWs, 2500);
}
fetch(apiPath("api/state")).then(r => r.json()).then(d => { if (!d.error) render(d); }).catch(() => {});
connectWs();
setInterval(() => {
  if (state.current && !state.paused) {
    state.elapsed = (state.elapsed || 0) + 1;
    updateProgressUI();
  }
}, 1000);
</script>
</body>
</html>
"""


class ActivityServer:
    """Server HTTP/WebSocket ultraleggero per Discord Embedded App SDK / Web Player."""

    def __init__(self, bot, host: str = "0.0.0.0", port: int = 8080):
        self.bot = bot
        self.host = host
        self.port = port
        self.secret = bot.store.client_id.encode()
        self.runner: web.AppRunner | None = None
        self.art_cache: dict[tuple[int, str], tuple[bytes, str]] = {}
        self.lib_cache: dict[int, tuple[int, list]] = {}
        self.user_name_cache: dict[int, str] = {}
        self.pending_pins: dict[int, int] = {}
        self.pending_user_pins: dict[int, tuple[int, str]] = {}

    def _discord_secret(self) -> str:
        env_sec = os.environ.get("DISCORD_CLIENT_SECRET", "").strip()
        if env_sec:
            return env_sec
        if hasattr(self.bot.store, "get_meta"):
            return self.bot.store.get_meta("discord_client_secret", "")
        return ""

    def sign(self, guild_id: int, channel_id: int) -> str:
        exp = int(time.time()) + 86400
        payload = f"{guild_id}:{channel_id}:{exp}"
        sig = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()[:32]
        return f"{payload}:{sig}"

    def _channel_has_humans(self, vc) -> bool:
        bot_id = getattr(getattr(self.bot, "user", None), "id", None)
        voice_states = getattr(vc, "voice_states", None)
        if isinstance(voice_states, dict) and any(uid != bot_id for uid in voice_states):
            return True
        members = getattr(vc, "members", None)
        if members and any(not getattr(m, "bot", False) for m in members):
            return True
        return False

    async def _voice_users(self, guild, channel) -> list[dict]:
        if not channel:
            return []
        bot_id = getattr(getattr(self.bot, "user", None), "id", None)
        user_map: dict[int, str] = {}
        for m in getattr(channel, "members", []) or []:
            if not getattr(m, "bot", False):
                name = getattr(m, "display_name", None) or getattr(m, "name", f"Utente {m.id}")
                user_map[m.id] = name
                self.user_name_cache[m.id] = name
        vs = getattr(channel, "voice_states", None)
        if isinstance(vs, dict):
            for uid in vs:
                if uid == bot_id or uid in user_map:
                    continue
                if uid in self.user_name_cache:
                    user_map[uid] = self.user_name_cache[uid]
                    continue
                member = guild.get_member(uid) if hasattr(guild, "get_member") else None
                if not member and hasattr(guild, "fetch_member"):
                    with contextlib.suppress(Exception):
                        member = await guild.fetch_member(uid)
                if member and getattr(member, "bot", False):
                    continue
                name = getattr(member, "display_name", None) or getattr(member, "name", f"Utente {uid}")
                self.user_name_cache[uid] = name
                user_map[uid] = name
        links = {
            u.discord_id: u
            for u in (self.bot.store.list_users(list(user_map.keys())) if hasattr(self.bot.store, "list_users") else [])
        }
        return [
            {
                "id": str(uid),
                "name": name,
                "plex_username": links[uid].plex_username if uid in links else "",
            }
            for uid, name in user_map.items()
        ]

    def resolve_context(self, request: web.Request, *, require_active: bool = False):
        token = request.query.get("token", "")
        guild_id = 0
        channel_id = 0
        if token:
            parts = token.split(":")
            if len(parts) != 4 or not parts[0].isdigit() or not parts[1].isdigit() or not parts[2].isdigit():
                raise PlexError("Token di sessione non valido. Usa /activity su Discord.")
            payload = ":".join(parts[:3])
            expected = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()[:32]
            if not hmac.compare_digest(parts[3], expected) or int(parts[2]) < int(time.time()):
                raise PlexError("Sessione scaduta o non valida. Usa /activity su Discord.")
            guild_id, channel_id = int(parts[0]), int(parts[1])
        else:
            raw_guild = request.query.get("guild_id", "")
            if not raw_guild or raw_guild == "0":
                raw_guild = request.match_info.get("guild_id", "")
            raw_channel = request.query.get("channel_id", "")
            if raw_guild.isdigit():
                guild_id = int(raw_guild)
            if raw_channel.isdigit():
                channel_id = int(raw_channel)
            if not guild_id:
                for g in self.bot.guilds:
                    if getattr(g, "voice_client", None):
                        guild_id = g.id
                        break
                if not guild_id:
                    for g in self.bot.guilds:
                        if any(self._channel_has_humans(vc) for vc in getattr(g, "voice_channels", [])):
                            guild_id = g.id
                            break
                if not guild_id and self.bot.guilds:
                    guild_id = self.bot.guilds[0].id
        guild = self.bot.get_guild(guild_id) if guild_id else None
        if not guild:
            raise PlexError("Apri l'Activity da un canale vocale del server Discord o usa /activity.")
        voice = getattr(guild, "voice_client", None)
        channel = guild.get_channel(channel_id) if channel_id and hasattr(guild, "get_channel") else None
        if voice and getattr(voice, "channel", None):
            channel = voice.channel
        if not channel:
            for vc in getattr(guild, "voice_channels", []):
                if self._channel_has_humans(vc):
                    channel = vc
                    break
        if require_active and not channel:
            raise PlexError("Entra in un canale vocale su Discord per riprodurre la musica.")
        if require_active and not voice and channel:
            has_voice_tracking = hasattr(channel, "voice_states") or hasattr(channel, "members")
            if has_voice_tracking and not self._channel_has_humans(channel):
                raise PlexError("Deve esserci almeno un utente nel canale vocale per controllare la musica.")
        return guild, channel

    async def _get_libraries(self, guild_id: int, settings):
        if not settings.server_url or not settings.server_token:
            return []
        cached = self.lib_cache.get(guild_id)
        if cached and cached[0] == settings.revision:
            return cached[1]
        with contextlib.suppress(Exception):
            libs = await self.bot.plex.libraries(settings)
            self.lib_cache[guild_id] = (settings.revision, libs)
            return libs
        return []

    def _saved_discord_oauth(self) -> dict:
        if not hasattr(self.bot.store, "get_meta"):
            return {}
        raw = self.bot.store.get_meta("discord_oauth_json", "")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_discord_oauth(self, payload: dict):
        if not hasattr(self.bot.store, "set_meta"):
            return
        access_token = str(payload.get("access_token") or "").strip()
        if not access_token:
            return
        prev = self._saved_discord_oauth()
        refresh_token = str(payload.get("refresh_token") or prev.get("refresh_token") or "").strip()
        expires_in = int(payload.get("expires_in") or 604800)
        saved = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": int(time.time()) + max(60, expires_in - 120),
        }
        self.bot.store.set_meta("discord_oauth_json", json.dumps(saved))

    async def build_state(self, guild, channel=None):
        settings = self.bot.store.get(guild.id)
        player = self.bot.players.get(guild.id)
        all_libs = await self._get_libraries(guild.id, settings)
        enabled_libs = [
            {"id": lib.id, "title": lib.title}
            for lib in all_libs
            if settings.libraries is None or lib.id in settings.libraries
        ]
        all_libs_info = [
            {
                "id": lib.id,
                "title": lib.title,
                "enabled": settings.libraries is None or lib.id in settings.libraries,
            }
            for lib in all_libs
        ]
        oauth = self._saved_discord_oauth()
        return {
            "guild_id": str(guild.id),
            "channel_id": str(channel.id) if channel else "",
            "server_name": settings.server_name or "",
            "has_token": bool(settings.token),
            "has_discord_secret": bool(self._discord_secret()),
            "has_discord_token": bool(oauth.get("access_token")),
            "address_override": settings.address_override,
            "mode": settings.mode,
            "volume": settings.volume,
            "bitrate": settings.bitrate,
            "idle_seconds": settings.idle_seconds,
            "max_queue": settings.max_queue,
            "paused": bool(player and player.paused_at),
            "elapsed": player.elapsed if player else 0,
            "current": asdict(player.current) if player and player.current else None,
            "queue": [asdict(t) for t in player.queue] if player else [],
            "libraries": enabled_libs,
            "all_libraries": all_libs_info,
            "voice_users": await self._voice_users(guild, channel),
        }

    async def index(self, request: web.Request):
        bot_uid = getattr(getattr(self.bot, "user", None), "id", "")
        client_id = str(self.bot.application_id or os.environ.get("DISCORD_CLIENT_ID", "") or bot_uid or "")
        html = ACTIVITY_HTML.replace("__CLIENT_ID__", client_id)
        return web.Response(text=html, content_type="text/html")

    async def discord_token_handler(self, request: web.Request):
        try:
            data = await request.json()
            action = str(data.get("action") or "exchange").strip()
            code = str(data.get("code") or "").strip()
            bot_uid = getattr(getattr(self.bot, "user", None), "id", "")
            client_id = str(
                self.bot.application_id
                or os.environ.get("DISCORD_CLIENT_ID", "")
                or data.get("client_id")
                or bot_uid
                or ""
            ).strip()
            client_secret = self._discord_secret()
            session = getattr(self.bot, "http_session", None)

            if action == "restore":
                oauth = self._saved_discord_oauth()
                force_refresh = bool(data.get("refresh"))
                now = int(time.time())
                if oauth.get("access_token") and not force_refresh and int(oauth.get("expires_at") or 0) > now:
                    return web.json_response({"access_token": oauth["access_token"]})
                refresh_tok = str(oauth.get("refresh_token") or "").strip()
                if refresh_tok and client_id and client_secret and session:
                    async with session.post(
                        "https://discord.com/api/v10/oauth2/token",
                        data={
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_tok,
                        },
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    ) as resp:
                        payload = await resp.json()
                        if resp.status < 300 and "access_token" in payload:
                            self._save_discord_oauth(payload)
                            return web.json_response({"access_token": payload["access_token"]})
                return web.json_response({"access_token": ""})

            if not code or not client_id or not client_secret:
                raise PlexError("Configura prima il Discord Client Secret nella scheda '🎧 RPC & Account'.")
            if not session:
                raise PlexError("Sessione HTTP non pronta.")
            async with session.post(
                "https://discord.com/api/v10/oauth2/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                payload = await resp.json()
                if resp.status >= 300 or "access_token" not in payload:
                    err_detail = str(payload.get("error_description") or payload.get("error") or "").strip()
                    suffix = f" ({err_detail[:120]})" if err_detail else ""
                    raise PlexError(
                        f"Autorizzazione OAuth2 Discord fallita{suffix}. Verifica Client Secret e Redirect URL su Discord Developer Portal."
                    )
                self._save_discord_oauth(payload)
                return web.json_response({"access_token": payload["access_token"]})
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)
        except Exception:
            return web.json_response({"error": "Errore durante lo scambio del token Discord."}, status=400)

    async def state_handler(self, request: web.Request):
        try:
            guild, channel = self.resolve_context(request)
            return web.json_response(await self.build_state(guild, channel))
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)

    def _resolve_user_link(self, guild, channel, raw_uid: str = ""):
        if not hasattr(self.bot.store, "get_user"):
            return None
        uid_str = str(raw_uid or "").strip()
        if uid_str.isdigit():
            link = self.bot.store.get_user(int(uid_str))
            if link and link.plex_token:
                return link
        if channel and hasattr(self.bot.store, "list_users"):
            ids = set()
            vs = getattr(channel, "voice_states", None)
            if isinstance(vs, dict):
                ids.update(vs.keys())
            for m in getattr(channel, "members", []) or []:
                if not getattr(m, "bot", False):
                    ids.add(m.id)
            links = self.bot.store.list_users(list(ids))
            if links:
                return links[0]
        return None

    async def playlists_handler(self, request: web.Request):
        try:
            guild, channel = self.resolve_context(request)
            raw_uid = request.query.get("discord_id", "").strip()
            link = self._resolve_user_link(guild, channel, raw_uid)
            if not link:
                return web.json_response({
                    "linked": False,
                    "playlists": [],
                    "error": "Collega prima il tuo account Plex nella scheda '🎧 RPC & Account' per vedere le tue playlist personali.",
                })
            settings = self.bot.store.get(guild.id)
            playlists = await self.bot.plex.playlists(settings, user_token=link.plex_token)
            return web.json_response({
                "linked": True,
                "plex_username": link.plex_username,
                "discord_id": str(link.discord_id),
                "playlists": [asdict(p) for p in playlists],
            })
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)
        except Exception:
            return web.json_response({"error": "Impossibile caricare le playlist da Plex."}, status=400)

    async def playlist_tracks_handler(self, request: web.Request):
        try:
            guild, channel = self.resolve_context(request)
            playlist_id = request.query.get("playlist_id", "").strip()
            raw_uid = request.query.get("discord_id", "").strip()
            link = self._resolve_user_link(guild, channel, raw_uid)
            if not link:
                raise PlexError("Collega prima il tuo account Plex per accedere alle tue playlist.")
            settings = self.bot.store.get(guild.id)
            tracks = await self.bot.plex.playlist_tracks(settings, playlist_id, user_token=link.plex_token)
            return web.json_response({"tracks": [asdict(t) for t in tracks]})
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)
        except Exception:
            return web.json_response({"error": "Impossibile caricare i brani della playlist."}, status=400)

    async def search_handler(self, request: web.Request):
        try:
            guild, _ = self.resolve_context(request)
            query = request.query.get("query", "").strip()
            library = request.query.get("library", "").strip() or None
            if not query or len(query) > 200:
                raise PlexError("Inserisci un titolo o autore da 1 a 200 caratteri.")
            settings = self.bot.store.get(guild.id)
            tracks = await self.bot.plex.search(settings, query, library)
            return web.json_response({"tracks": [asdict(t) for t in tracks[:50]]})
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)

    async def control_handler(self, request: web.Request):
        try:
            data = await request.json()
            action = data.get("action", "")
            guild, channel = self.resolve_context(request, require_active=(action != "volume"))
            message = ""
            async with self.bot.config_lock(guild.id):
                player = self.bot.player(guild)
                voice = guild.voice_client
                if action == "play":
                    raw = data.get("track") or {}
                    track_id = str(raw.get("id", ""))
                    if not track_id.isdigit():
                        raise PlexError("Brano non valido.")
                    play_now = bool(data.get("play_now"))
                    track = Track(
                        track_id,
                        str(raw.get("title") or "Senza titolo")[:200],
                        str(raw.get("artist") or "Artista sconosciuto")[:200],
                        str(raw.get("album") or "")[:200],
                        str(raw.get("library") or "Musica")[:100],
                        int(raw.get("duration") or 0),
                    )
                    await player.add(channel, track, player.text_channel, play_now=play_now)
                    message = f"{'▶️ In riproduzione' if play_now else '➕ Aggiunto in coda'}: {track.label}"
                elif action == "play_playlist":
                    playlist_id = str(data.get("playlist_id") or "").strip()
                    raw_uid = str(data.get("discord_id") or "").strip()
                    play_now = bool(data.get("play_now"))
                    shuffle = bool(data.get("shuffle"))
                    link = self._resolve_user_link(guild, channel, raw_uid)
                    if not link:
                        raise PlexError("Collega prima il tuo account Plex per riprodurre le tue playlist.")
                    settings = self.bot.store.get(guild.id)
                    tracks = await self.bot.plex.playlist_tracks(settings, playlist_id, user_token=link.plex_token)
                    added = await player.add_many(
                        channel, tracks, player.text_channel,
                        play_now=play_now, shuffle_tracks=shuffle,
                    )
                    mode_lbl = "🔀 In riproduzione (shuffle)" if (play_now and shuffle) else ("▶️ In riproduzione" if play_now else "➕ Aggiunti in coda")
                    message = f"{mode_lbl}: {added} brani dalla playlist!"
                elif action == "volume":
                    vol = max(0, min(150, int(data.get("volume", 100))))
                    settings = self.bot.store.get(guild.id)
                    settings.volume = vol
                    self.bot.store.save(guild.id, settings)
                    player.set_volume(vol)
                    message = f"🔊 Volume impostato al {vol}%."
                else:
                    if not voice:
                        raise PlexError("Il bot non è connesso a un canale vocale.")
                    if action == "toggle":
                        if voice.is_paused():
                            player.resume()
                            message = "▶️ Riproduzione ripresa."
                        else:
                            player.pause()
                            message = "⏸️ In pausa."
                    elif action == "skip":
                        player.skip()
                        message = "⏭️ Brano saltato."
                    elif action == "seek":
                        player.seek(int(data.get("seconds", 0)))
                        message = "⏩ Posizione aggiornata."
                    elif action == "shuffle":
                        player.shuffle()
                        message = "🔀 Coda mescolata."
                    elif action == "remove":
                        removed = player.remove(int(data.get("index", -1)))
                        message = f"Rimosso: {removed.label}"
                    elif action == "promote":
                        play_now = bool(data.get("play_now"))
                        promoted = player.promote(int(data.get("index", -1)), play_now=play_now)
                        message = f"{'▶️ In riproduzione' if play_now else '⬆️ Spostato in cima'}: {promoted.label}"
                    elif action == "stop":
                        player.stop()
                        message = "⏹️ Riproduzione fermata e coda svuotata."
                    elif action == "leave":
                        await player.close()
                        message = "👋 Disconnesso dal canale vocale."
                    else:
                        raise PlexError("Azione non supportata.")
            return web.json_response({"message": message, "state": await self.build_state(guild, channel)})
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)
        except Exception:
            return web.json_response({"error": "Richiesta non valida."}, status=400)

    async def config_handler(self, request: web.Request):
        try:
            guild, channel = self.resolve_context(request, require_active=False)
            data = await request.json()
            action = data.get("action", "")
            message = ""
            extra = {}
            async with self.bot.config_lock(guild.id):
                settings = self.bot.store.get(guild.id)
                if action == "set_mode":
                    mode = str(data.get("mode", "commands"))
                    if mode not in ("commands", "activity"):
                        raise PlexError("Modalità non valida.")
                    settings.mode = mode
                    self.bot.store.save(guild.id, settings)
                    message = f"Modalità impostata su: {'🎛️ Activity' if mode == 'activity' else '💬 Comandi Slash'}."
                elif action == "save_discord_secret":
                    sec = str(data.get("client_secret") or "").strip()
                    if not sec:
                        raise PlexError("Inserisci un Client Secret valido.")
                    if hasattr(self.bot.store, "set_meta"):
                        self.bot.store.set_meta("discord_client_secret", sec)
                    message = "💾 Discord Client Secret salvato! Ora puoi autorizzare l'RPC."
                elif action == "plex_pin":
                    pin_id, code, auth_url, expiry = await self.bot.plex.pin_code()
                    self.pending_pins[guild.id] = pin_id
                    extra["code"] = code
                    extra["auth_url"] = auth_url
                    extra["expiry"] = expiry
                    message = f"Inserisci il codice {code} su plex.tv/link"
                elif action == "plex_check_pin":
                    pin = self.pending_pins.get(guild.id)
                    if not pin:
                        raise PlexError("Avvia prima 'Collega con PIN a 4 Cifre'.")
                    token = await self.bot.plex.check_pin(pin)
                    if not token:
                        raise PlexError("Codice PIN non ancora autorizzato su plex.tv/link.")
                    await self.bot.disconnect(guild.id)
                    settings.token = token
                    settings.server_token = settings.server_id = settings.server_name = settings.server_url = ""
                    settings.libraries = None
                    self.bot.store.save(guild.id, settings)
                    self.pending_pins.pop(guild.id, None)
                    extra["ok"] = True
                    message = "✅ Login Plex completato! Ora carica e scegli il tuo server Plex."
                elif action == "user_pin":
                    raw_uid = str(data.get("discord_id", "")).strip()
                    if not raw_uid.isdigit():
                        raise PlexError("Seleziona prima il tuo utente Discord.")
                    uid = int(raw_uid)
                    cid = f"{self.bot.store.client_id}-u{uid}"
                    pin_id, code, auth_url, expiry = await self.bot.plex.pin_code(client_id=cid)
                    self.pending_user_pins[uid] = (pin_id, cid)
                    extra["code"] = code
                    extra["auth_url"] = auth_url
                    extra["expiry"] = expiry
                    message = f"Inserisci il codice {code} su plex.tv/link"
                elif action == "user_check_pin":
                    raw_uid = str(data.get("discord_id", "")).strip()
                    if not raw_uid.isdigit():
                        raise PlexError("Seleziona prima il tuo utente Discord.")
                    uid = int(raw_uid)
                    pending = self.pending_user_pins.get(uid)
                    if not pending:
                        raise PlexError("Genera prima il codice PIN a 4 cifre.")
                    pin_id, cid = pending
                    user_token = await self.bot.plex.check_pin(pin_id, client_id=cid)
                    if not user_token:
                        raise PlexError("Codice PIN non ancora autorizzato su plex.tv/link.")
                    plex_user = await self.bot.plex.user_info(user_token)
                    d_name = self.user_name_cache.get(uid, f"Utente {uid}")
                    self.bot.store.save_user(UserLink(discord_id=uid, plex_token=user_token, plex_username=plex_user, discord_name=d_name))
                    self.pending_user_pins.pop(uid, None)
                    extra["ok"] = True
                    player = self.bot.players.get(guild.id)
                    if player and player.current:
                        asyncio.create_task(player.sync_timeline("paused" if player.paused_at else "playing", player.current))
                    message = f"🎧 Account Plex '{plex_user}' collegato a {d_name}!"
                elif action == "user_unlink":
                    raw_uid = str(data.get("discord_id", "")).strip()
                    if not raw_uid.isdigit():
                        raise PlexError("Utente non valido.")
                    uid = int(raw_uid)
                    self.bot.store.delete_user(uid)
                    self.pending_user_pins.pop(uid, None)
                    message = "🗑️ Account Plex scollegato dal profilo Discord."
                elif action == "plex_logout":
                    await self.bot.disconnect(guild.id)
                    settings.token = settings.server_token = settings.server_id = settings.server_name = settings.server_url = ""
                    settings.address_override = ""
                    settings.libraries = None
                    self.bot.store.save(guild.id, settings)
                    self.lib_cache.pop(guild.id, None)
                    message = "🚪 Credenziali del server Plex rimosse."
                elif action == "plex_servers":
                    if not settings.token:
                        raise PlexError("Collega prima l'account Plex.")
                    resources = await self.bot.plex.resources(settings.token)
                    extra["servers"] = [
                        {
                            "id": r["clientIdentifier"],
                            "name": r["name"],
                            "selected": r["clientIdentifier"] == settings.server_id,
                        }
                        for r in resources
                    ]
                    message = f"Trovati {len(extra['servers'])} server Plex."
                elif action == "plex_address":
                    url = str(data.get("url") or "").strip()
                    if url:
                        url = valid_url(url)
                        if settings.server_id and settings.token:
                            resources = await self.bot.plex.resources(settings.token)
                            resource = next((r for r in resources if r["clientIdentifier"] == settings.server_id), None)
                            if not resource:
                                raise PlexError("Server selezionato non trovato.")
                            await self.bot.plex.connect(resource, url)
                            settings.server_url = url
                    await self.bot.disconnect(guild.id)
                    settings.address_override = url
                    self.bot.store.save(guild.id, settings)
                    self.lib_cache.pop(guild.id, None)
                    message = f"Indirizzo manuale: {url}" if url else "Indirizzo manuale rimosso (rilevamento automatico)."
                elif action == "plex_server":
                    server_id = str(data.get("server_id") or "").strip()
                    if not settings.token:
                        raise PlexError("Collega prima l'account Plex.")
                    resources = await self.bot.plex.resources(settings.token)
                    resource = next((r for r in resources if r["clientIdentifier"] == server_id), None)
                    if not resource:
                        raise PlexError("Server Plex non trovato.")
                    url, srv_token = await self.bot.plex.connect(resource, settings.address_override)
                    await self.bot.disconnect(guild.id)
                    settings.server_id, settings.server_name = server_id, resource["name"]
                    settings.server_url, settings.server_token = url, srv_token
                    settings.libraries = None
                    self.bot.store.save(guild.id, settings)
                    self.lib_cache.pop(guild.id, None)
                    message = f"✅ Connesso al server Plex: {settings.server_name}"
                elif action == "plex_all_libraries":
                    await self.bot.disconnect(guild.id)
                    settings.libraries = None
                    self.bot.store.save(guild.id, settings)
                    self.lib_cache.pop(guild.id, None)
                    message = "✅ Tutte le librerie musicali sono abilitate."
                elif action == "plex_library":
                    lib_id = str(data.get("library_id") or "").strip()
                    enabled = bool(data.get("enabled"))
                    libs = await self.bot.plex.libraries(settings)
                    known = {lib.id for lib in libs}
                    if lib_id not in known:
                        raise PlexError("Libreria musicale non trovata.")
                    await self.bot.disconnect(guild.id)
                    active = set(known if settings.libraries is None else settings.libraries) & known
                    if enabled:
                        active.add(lib_id)
                    else:
                        active.discard(lib_id)
                    settings.libraries = sorted(active)
                    self.bot.store.save(guild.id, settings)
                    self.lib_cache.pop(guild.id, None)
                    message = f"Libreria {lib_id}: {'abilitata' if enabled else 'disabilitata'}."
                elif action == "save_settings":
                    settings.volume = max(0, min(150, int(data.get("volume", settings.volume))))
                    settings.bitrate = max(32, min(320, int(data.get("bitrate", settings.bitrate))))
                    settings.idle_seconds = max(15, min(1800, int(data.get("idle_seconds", settings.idle_seconds))))
                    settings.max_queue = max(1, min(500, int(data.get("max_queue", settings.max_queue))))
                    self.bot.store.save(guild.id, settings)
                    player = self.bot.players.get(guild.id)
                    if player:
                        player.set_volume(settings.volume)
                    message = "💾 Impostazioni salvate."
                else:
                    raise PlexError("Azione di configurazione non supportata.")
            return web.json_response({"message": message, "state": await self.build_state(guild, channel), **extra})
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)
        except Exception:
            return web.json_response({"error": "Richiesta di configurazione non valida."}, status=400)

    async def art_handler(self, request: web.Request):
        try:
            guild, _ = self.resolve_context(request)
            track_id = request.match_info.get("track_id", "")
            is_playlist = track_id.startswith("pl_") and track_id[3:].isdigit()
            if not track_id.isdigit() and not is_playlist:
                return web.Response(status=404)
            key = (guild.id, track_id)
            if key not in self.art_cache:
                settings = self.bot.store.get(guild.id)
                art = await self.bot.plex.artwork(settings, track_id)
                if not art:
                    return web.Response(status=404)
                self.art_cache[key] = art
                if len(self.art_cache) > 120:
                    self.art_cache.pop(next(iter(self.art_cache)))
            body, content_type = self.art_cache[key]
            return web.Response(body=body, content_type=content_type, headers={"Cache-Control": "private, max-age=3600"})
        except Exception:
            return web.Response(status=404)

    async def ws_handler(self, request: web.Request):
        ws = web.WebSocketResponse(heartbeat=25)
        await ws.prepare(request)
        try:
            while not ws.closed:
                with contextlib.suppress(PlexError):
                    guild, channel = self.resolve_context(request)
                    state = await self.build_state(guild, channel)
                    await ws.send_str(json.dumps(state))
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
                    if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                        break
                except TimeoutError:
                    pass
        except Exception:
            pass
        finally:
            with contextlib.suppress(Exception):
                await ws.close()
        return ws

    def create_app(self) -> web.Application:
        app = web.Application(client_max_size=65536)
        app.router.add_get("/", self.index)
        app.router.add_get("/api/state", self.state_handler)
        app.router.add_get("/api/search", self.search_handler)
        app.router.add_get("/api/playlists", self.playlists_handler)
        app.router.add_get("/api/playlist_tracks", self.playlist_tracks_handler)
        app.router.add_post("/api/control", self.control_handler)
        app.router.add_post("/api/config", self.config_handler)
        app.router.add_post("/api/discord_token", self.discord_token_handler)
        app.router.add_get("/api/art/{guild_id}/{track_id}", self.art_handler)
        app.router.add_get("/api/ws", self.ws_handler)
        return app

    async def start(self):
        if self.port <= 0:
            return
        app = self.create_app()
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()

    async def close(self):
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
